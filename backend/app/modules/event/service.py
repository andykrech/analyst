"""Сервис извлечения событий из квантов (MVP, Event = hyperedge)."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Iterable
import os

from sqlalchemy import Select, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.integrations.llm import LLMService
from app.integrations.prompts import PromptService
from app.modules.entity.model import Cluster
from app.modules.event.model import Event, EventParticipant, EventPlot, EventRole
from app.modules.quanta.models import Quantum
from app.modules.relation.model import Relation


logger = logging.getLogger(__name__)

PROMPT_NAME_EXTRACT_EVENTS = "event.extract_events_from_quantum_mvp.v1"
_DEBUG_LOG_PATH = "logs/events_llm_debug.log"


def _get_debug_logger() -> logging.Logger:
    dbg = logging.getLogger("events_llm_debug")
    if not dbg.handlers:
        dbg.setLevel(logging.INFO)
        try:
            os.makedirs(os.path.dirname(_DEBUG_LOG_PATH) or ".", exist_ok=True)
            fh = logging.FileHandler(_DEBUG_LOG_PATH, encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
            dbg.addHandler(fh)
        except Exception as e:  # best-effort: не ломать основной поток
            logger.warning("events_extraction: failed to init debug logger: %s", e)
    return dbg


_debug_logger = _get_debug_logger()


@dataclass(frozen=True)
class _ExtractedParticipant:
    role: str
    entity_id: uuid.UUID


@dataclass(frozen=True)
class _ExtractedAttribute:
    attribute_for: str
    entity_id: uuid.UUID | None
    attribute_text: str
    attribute_normalized: str | None


@dataclass(frozen=True)
class _ExtractedEvent:
    plot_code: str
    predicate_text: str
    predicate_normalized: str
    predicate_class: str | None
    display_text: str
    event_time: str | None
    participants: tuple[_ExtractedParticipant, ...]
    attributes: tuple[_ExtractedAttribute, ...]


class EventExtractionService:
    """Сервис батчевого извлечения событий из квантов."""

    def __init__(
        self,
        llm_service: LLMService,
        prompt_service: PromptService,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._batch_size = self._settings.BATCH_SIZE_FOR_EVENTS_EXTRACTION
        self._version = self._settings.EVENT_EXTRACTION_VERSION
        self._llm_service = llm_service
        self._prompt_service = prompt_service

    async def process_next_batch(
        self,
        session: AsyncSession,
        *,
        theme_id: Any | None = None,
    ) -> tuple[int, int]:
        """
        Обработать один батч квантов с event_extraction_version IS NULL.

        Возвращает (processed_quanta, created_events).
        """
        quanta = await self._fetch_quanta_batch(session, theme_id=theme_id)
        if not quanta:
            return (0, 0)

        logger.info("events_extraction: fetched quanta batch size=%s", len(quanta))

        plots_by_code = await self._load_plots_by_code(session)
        roles_by_code = await self._load_roles_by_code(session)
        entities_by_quantum = await self._load_entities_for_quanta(session, quanta)

        processed_quantum_ids: set[Any] = set()
        created_events_total = 0

        for q in quanta:
            quantum_text = self._build_text_for_quantum(q)
            if not quantum_text.strip():
                processed_quantum_ids.add(q.id)
                continue

            ent_rows = entities_by_quantum.get(q.id, [])
            entities_json = [
                {
                    "entity_id": str(c.id),
                    "normalized_name": (c.normalized_text or "").strip(),
                    "entity_type": (c.type or "").strip(),
                }
                for c in ent_rows
                if getattr(c, "id", None) is not None and (c.normalized_text or "").strip()
            ]

            plots_json = [
                {
                    "code": code,
                    "name": (p.name or "").strip(),
                    "description": (p.description or "").strip() if p.description else None,
                    "schema": p.schema or {},
                }
                for code, p in plots_by_code.items()
            ]

            vars = {
                "quantum_text": quantum_text,
                "entities_json": json.dumps(entities_json, ensure_ascii=False),
                "plots_json": json.dumps(plots_json, ensure_ascii=False),
            }

            rendered = await self._prompt_service.render(PROMPT_NAME_EXTRACT_EVENTS, vars)
            prompt_text = rendered.text or ""
            logger.info(
                "++++++++++ events_extraction: sending quantum_id=%s to LLM (prompt_chars=%s)",
                q.id,
                len(prompt_text),
            )
            try:
                _debug_logger.info(
                    "quantum_id=%s theme_id=%s\nPROMPT (chars=%s):\n%s",
                    q.id,
                    q.theme_id,
                    len(prompt_text),
                    prompt_text,
                )
            except Exception:
                # не критично для основного потока
                pass

            try:
                response = await self._llm_service.generate_text(
                    messages=[{"role": "system", "content": prompt_text}],  # type: ignore[arg-type]
                    task=PROMPT_NAME_EXTRACT_EVENTS,
                    response_format=rendered.response_format,
                )
            except Exception as e:
                logger.warning(
                    "events_extraction: LLM extraction failed for quantum_id=%s: %s",
                    q.id,
                    e,
                )
                processed_quantum_ids.add(q.id)
                continue

            response_text = (getattr(response, "text", None) or "")
            try:
                _debug_logger.info(
                    "quantum_id=%s LLM RAW RESPONSE:\n%s",
                    q.id,
                    response_text,
                )
            except Exception:
                pass

            extracted = self._parse_llm_events(response_text=response_text)
            logger.info(
                "++++++++++ events_extraction: LLM returned %s events for quantum_id=%s",
                len(extracted),
                q.id,
            )

            candidates = self._validate_and_dedup(
                extracted,
                plots_by_code=plots_by_code,
                roles_by_code=roles_by_code,
                allowed_entity_ids={uuid.UUID(str(e["entity_id"])) for e in entities_json},
            )

            if candidates:
                created = await self._persist_events_for_quantum(
                    session,
                    quantum=q,
                    candidates=candidates,
                    plots_by_code=plots_by_code,
                    roles_by_code=roles_by_code,
                )
                created_events_total += created

            processed_quantum_ids.add(q.id)

        if processed_quantum_ids:
            await session.execute(
                update(Quantum)
                .where(Quantum.id.in_(list(processed_quantum_ids)))
                .values(
                    event_extraction_version=self._version,
                    updated_at=func.now(),
                )
            )
            await session.flush()

        return (len(processed_quantum_ids), created_events_total)

    async def _fetch_quanta_batch(
        self,
        session: AsyncSession,
        *,
        theme_id: Any | None = None,
    ) -> list[Quantum]:
        stmt: Select[tuple[Quantum]] = select(Quantum).where(
            Quantum.event_extraction_version.is_(None),
        )
        if theme_id is not None:
            stmt = stmt.where(Quantum.theme_id == theme_id)
        stmt = (
            stmt.order_by(Quantum.created_at)
            .limit(self._batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _build_text_for_quantum(q: Quantum) -> str:
        title = (q.title or "").strip()
        summary = (q.summary_text or "").strip()
        if title and summary:
            return f"{title}\n\n{summary}"
        if title:
            return title
        return summary

    async def _load_plots_by_code(self, session: AsyncSession) -> dict[str, EventPlot]:
        result = await session.execute(select(EventPlot))
        rows = list(result.scalars().all())
        by_code: dict[str, EventPlot] = {}
        for p in rows:
            code = (p.code or "").strip()
            if code:
                by_code[code] = p
        return by_code

    async def _load_roles_by_code(self, session: AsyncSession) -> dict[str, EventRole]:
        result = await session.execute(select(EventRole))
        rows = list(result.scalars().all())
        by_code: dict[str, EventRole] = {}
        for r in rows:
            code = (r.code or "").strip()
            if code:
                by_code[code] = r
        return by_code

    async def _load_entities_for_quanta(
        self,
        session: AsyncSession,
        quanta: Iterable[Quantum],
    ) -> dict[Any, list[Cluster]]:
        quantum_ids = [q.id for q in quanta if getattr(q, "id", None) is not None]
        if not quantum_ids:
            return {}

        stmt = (
            select(Relation.object_id, Cluster)
            .join(Cluster, Cluster.id == Relation.subject_id)
            .where(Relation.object_type == "quantum")
            .where(Relation.object_id.in_(quantum_ids))
            .where(Relation.subject_type == "cluster")
            .where(Relation.relation_type == "mentions")
            .where(Relation.deleted_at.is_(None))
            .where(Relation.status == "active")
        )
        result = await session.execute(stmt)
        rows = list(result.all())
        by_quantum: dict[Any, list[Cluster]] = {}
        for quantum_id, cluster in rows:
            by_quantum.setdefault(quantum_id, []).append(cluster)
        return by_quantum

    @staticmethod
    def _parse_llm_events(*, response_text: str) -> list[dict[str, Any]]:
        txt = (response_text or "").strip()
        if not txt:
            return []
        # Удаляем markdown-обёртку ```json ... ``` если модель её добавила
        if txt.startswith("```"):
            # обрезаем первый блок ```...``` до первой новой строки
            first_nl = txt.find("\n")
            if first_nl != -1:
                txt = txt[first_nl + 1 :]
            if txt.endswith("```"):
                txt = txt[: -3]
            txt = txt.strip()
        try:
            payload = json.loads(txt)
        except Exception:
            logger.warning("events_extraction: invalid JSON from LLM; preview=%r", txt[:500])
            return []
        if not isinstance(payload, dict):
            return []
        events_val = payload.get("events")
        if events_val is None:
            return []
        if not isinstance(events_val, list):
            return []
        return [e for e in events_val if isinstance(e, dict)]

    def _validate_and_dedup(
        self,
        raw_events: list[dict[str, Any]],
        *,
        plots_by_code: dict[str, EventPlot],
        roles_by_code: dict[str, EventRole],
        allowed_entity_ids: set[uuid.UUID],
    ) -> list[_ExtractedEvent]:
        result: list[_ExtractedEvent] = []
        seen: set[str] = set()

        for e in raw_events:
            plot_code = str(e.get("plot_code") or "").strip()
            if not plot_code or plot_code not in plots_by_code:
                continue

            predicate_text = str(e.get("predicate_text") or "").strip()
            predicate_normalized = str(e.get("predicate_normalized") or "").strip()
            predicate_class = (str(e.get("predicate_class")).strip() if e.get("predicate_class") is not None else None) or None
            display_text = str(e.get("display_text") or "").strip()
            event_time = (str(e.get("event_time")).strip() if e.get("event_time") is not None else None) or None

            if not predicate_text or not predicate_normalized or not display_text:
                continue

            participants_raw = e.get("participants") or []
            if not isinstance(participants_raw, list):
                participants_raw = []

            participants: list[_ExtractedParticipant] = []
            for p in participants_raw:
                if not isinstance(p, dict):
                    continue
                role = str(p.get("role") or "").strip()
                ent_id_raw = str(p.get("entity_id") or "").strip()
                if not role or not ent_id_raw:
                    continue
                if role not in roles_by_code:
                    continue
                try:
                    ent_id = uuid.UUID(ent_id_raw)
                except ValueError:
                    continue
                if ent_id not in allowed_entity_ids:
                    continue
                participants.append(_ExtractedParticipant(role=role, entity_id=ent_id))

            # Валидация required_roles по schema
            schema = plots_by_code[plot_code].schema or {}
            required_roles = schema.get("required_roles") if isinstance(schema, dict) else None
            if required_roles is None:
                required_roles = []
            if not isinstance(required_roles, list):
                required_roles = []

            required_set = {str(x).strip() for x in required_roles if str(x).strip()}
            if "predicate" in required_set:
                # predicate уже валидирован (непустые predicate_text/predicate_normalized)
                required_set.discard("predicate")
            participant_roles_present = {p.role for p in participants}
            if not required_set.issubset(participant_roles_present):
                continue

            attributes_raw = e.get("attributes") or []
            if not isinstance(attributes_raw, list):
                attributes_raw = []

            attributes: list[_ExtractedAttribute] = []
            for a in attributes_raw:
                if not isinstance(a, dict):
                    continue
                attribute_for = str(a.get("attribute_for") or "").strip()
                attribute_text = str(a.get("attribute_text") or "").strip()
                attribute_normalized = (str(a.get("attribute_normalized")).strip() if a.get("attribute_normalized") is not None else None) or None
                entity_id_raw = (str(a.get("entity_id")).strip() if a.get("entity_id") is not None else None) or None
                if not attribute_for or not attribute_text:
                    continue
                # entity_id обязателен, если attribute_for относится к сущности
                if attribute_for in {"subject", "object", "instrument", "reason", "speaker"}:
                    if not entity_id_raw:
                        continue
                    try:
                        entity_id = uuid.UUID(entity_id_raw)
                    except ValueError:
                        continue
                    if entity_id not in allowed_entity_ids:
                        continue
                else:
                    entity_id = None
                attributes.append(
                    _ExtractedAttribute(
                        attribute_for=attribute_for,
                        entity_id=entity_id,
                        attribute_text=attribute_text,
                        attribute_normalized=attribute_normalized,
                    )
                )

            # Дедуп внутри кванта
            part_key = sorted((p.role, str(p.entity_id)) for p in participants)
            attr_key = sorted(
                (
                    a.attribute_for,
                    str(a.entity_id) if a.entity_id else "",
                    a.attribute_normalized or "",
                    a.attribute_text,
                )
                for a in attributes
            )
            key = json.dumps(
                {
                    "plot": plot_code,
                    "pred": predicate_normalized,
                    "participants": part_key,
                    "attributes": attr_key,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            if key in seen:
                continue
            seen.add(key)

            result.append(
                _ExtractedEvent(
                    plot_code=plot_code,
                    predicate_text=predicate_text,
                    predicate_normalized=predicate_normalized,
                    predicate_class=predicate_class,
                    display_text=display_text,
                    event_time=event_time,
                    participants=tuple(participants),
                    attributes=tuple(attributes),
                )
            )

        return result

    async def _persist_events_for_quantum(
        self,
        session: AsyncSession,
        *,
        quantum: Quantum,
        candidates: list[_ExtractedEvent],
        plots_by_code: dict[str, EventPlot],
        roles_by_code: dict[str, EventRole],
    ) -> int:
        created = 0
        for e in candidates:
            plot = plots_by_code.get(e.plot_code)
            if plot is None:
                continue

            ev = Event(
                theme_id=quantum.theme_id,
                run_id=quantum.run_id,
                plot_id=plot.id,
                predicate_text=e.predicate_text,
                predicate_normalized=e.predicate_normalized,
                predicate_class=e.predicate_class,
                display_text=e.display_text,
                event_time=e.event_time,
                attributes_json=[
                    {
                        "attribute_for": a.attribute_for,
                        # entity_id храним как строку UUID или null,
                        # чтобы JSONB-сериализация не падала на объекте UUID
                        "entity_id": str(a.entity_id) if a.entity_id is not None else None,
                        "attribute_text": a.attribute_text,
                        "attribute_normalized": a.attribute_normalized,
                    }
                    for a in e.attributes
                ],
                confidence=None,
                extraction_version=self._version,
            )
            session.add(ev)
            await session.flush()  # нужен ev.id

            part_rows: list[dict[str, Any]] = []
            for p in e.participants:
                role = roles_by_code.get(p.role)
                if role is None:
                    continue
                part_rows.append(
                    {
                        "event_id": ev.id,
                        "role_id": role.id,
                        "entity_id": p.entity_id,
                        "confidence": None,
                    }
                )

            if part_rows:
                await session.execute(insert(EventParticipant).values(part_rows).on_conflict_do_nothing(
                    index_elements=["event_id", "role_id", "entity_id"],
                ))

            # Связь event -> quantum через relations (mentions)
            await session.execute(
                insert(Relation)
                .values(
                    [
                        {
                            "theme_id": quantum.theme_id,
                            "subject_type": "event",
                            "subject_id": ev.id,
                            "object_type": "quantum",
                            "object_id": quantum.id,
                            "relation_type": "mentions",
                            "direction": "forward",
                            "status": "active",
                            "is_user_created": False,
                            "run_id": quantum.run_id,
                        }
                    ]
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        "theme_id",
                        "subject_type",
                        "subject_id",
                        "relation_type",
                        "object_type",
                        "object_id",
                    ],
                    index_where=text("deleted_at IS NULL AND status = 'active'"),
                )
            )

            created += 1

        await session.flush()
        return created

