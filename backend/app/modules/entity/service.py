"""Сервис извлечения сущностей из квантов и апсерта сущностей/связей."""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import Select, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.integrations.llm import LLMService
from app.integrations.prompts import PromptService
from app.modules.entity.extractors.person_publication_authors_extractor import (
    apply_person_results,
    collapse_candidates,
    collect_candidates,
)
from app.modules.entity.extractors.tech_extractor import (
    TechEntitiesExtractor,
    TechEntityCandidate,
)
from app.modules.entity.model import Entity, EntityAlias
from app.modules.quanta.models import Quantum
from app.modules.relation.model import Relation
from app.modules.theme.model import Theme


logger = logging.getLogger(__name__)

PROMPT_NAME_ENTITY_NAME_TRANSLATE = "entity.entities_name_translate.v1"


def _expand_canonical_aliases(canonical: str) -> list[str]:
    """
    Если canonical_name имеет вид «term (ABBR)», возвращает [term, ABBR] (без полной строки).
    Иначе — [canonical]. Все значения strip(), пустые не возвращаются.
    """
    s = (canonical or "").strip()
    if not s:
        return []
    m = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", s)
    if not m:
        return [s]
    term, abbr = m.group(1).strip(), m.group(2).strip()
    result: list[str] = []
    if term:
        result.append(term)
    if abbr and abbr not in result:
        result.append(abbr)
    return result


def _capitalize_first(s: str) -> str:
    """Первая буква заглавная, остальное без изменений."""
    if not s:
        return s
    if len(s) == 1:
        return s.upper()
    return s[0].upper() + s[1:]


def _normalize_lang_code(lang: str | None) -> str | None:
    if not lang:
        return None
    s = str(lang).strip()
    return s or None


def _theme_primary_language(theme: Theme | None) -> str:
    """Первый язык темы или 'en' (локальная копия логики из search.service)."""
    if not theme:
        return "en"
    langs = theme.languages or []
    if isinstance(langs, list) and len(langs) > 0:
        first = langs[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    return "en"


@dataclass(frozen=True)
class _EntityGroupKey:
    theme_id: Any
    normalized_name: str


@dataclass
class _EntityGroup:
    theme_id: Any
    normalized_name: str
    language: str | None
    quantum_ids: set[Any]
    canonical_names: Counter[str]
    min_date_at: Any | None
    max_date_at: Any | None


class EntitiesExtractionService:
    """Сервис батчевого извлечения сущностей из квантов (MVP: только tech)."""

    def __init__(
        self,
        llm_service: LLMService,
        prompt_service: PromptService,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._batch_size = self._settings.BATCH_SIZE_FOR_ENTITIES_EXTRACTION
        self._version = self._settings.ENTITY_EXTRACTION_VERSION
        self._extractor = TechEntitiesExtractor(llm_service, prompt_service)
        self._llm_service = llm_service
        self._prompt_service = prompt_service

    async def _translate_entity_name(
        self,
        *,
        term: str,
        source_language: str,
        target_language: str,
    ) -> str | None:
        term_clean = (term or "").strip()
        if not term_clean:
            return None
        src = (source_language or "").strip()
        tgt = (target_language or "").strip()
        if not tgt:
            return None
        if src and src.lower() == tgt.lower():
            return _capitalize_first(term_clean)
        try:
            response = await self._llm_service.generate_from_prompt(
                PROMPT_NAME_ENTITY_NAME_TRANSLATE,
                {
                    "term": term_clean,
                    "source_language": src or "auto",
                    "target_language": tgt,
                },
                self._prompt_service,
            )
        except Exception as e:
            logger.warning(
                "entities_extraction: name translation LLM error (src=%s, tgt=%s): %s",
                src,
                tgt,
                e,
            )
            return None
        text_out = (getattr(response, "text", None) or "").strip()
        if not text_out:
            return None
        return text_out

    async def process_next_batch(
        self,
        session: AsyncSession,
        *,
        theme_id: Any | None = None,
    ) -> int:
        """
        Обработать один батч квантов с entity_extraction_version IS NULL.

        Возвращает количество квантов, для которых успешно выставлена версия.
        """
        quanta = await self._fetch_quanta_batch(session, theme_id=theme_id)
        if not quanta:
            return 0

        logger.info("entities_extraction: fetched quanta batch size=%s", len(quanta))

        per_quantum_entities: dict[Any, list[TechEntityCandidate]] = {}
        for q in quanta:
            source_text = self._build_text_for_quantum(q)
            logger.info(
                "++++++++++ entities_extraction: sending quantum_id=%s to LLM (len=%s)",
                getattr(q, "id", None),
                len(source_text),
            )
            try:
                result = await self._extractor.extract_for_text(source_text)
            except Exception as e:
                logger.warning(
                    "entities_extraction: LLM extraction failed for quantum_id=%s: %s",
                    getattr(q, "id", None),
                    e,
                )
                continue
            logger.info(
                "++++++++++ entities_extraction: LLM returned %s entities for quantum_id=%s",
                len(result.entities),
                getattr(q, "id", None),
            )
            if not result.entities:
                continue
            per_quantum_entities[q.id] = list(result.entities)

        if not per_quantum_entities:
            logger.info(
                "entities_extraction: no entities extracted for batch (quanta=%s)",
                len(quanta),
            )
            return 0

        await self._apply_extraction_results(session, quanta, per_quantum_entities)

        person_candidates = collect_candidates(quanta)
        if person_candidates:
            person_groups = collapse_candidates(person_candidates)
            if person_groups:
                await apply_person_results(session, person_groups)
                logger.info(
                    "entities_extraction: person (publication authors) groups=%s",
                    len(person_groups),
                )

        successful_quantum_ids = {q.id for q in quanta}
        if successful_quantum_ids:
            await session.execute(
                update(Quantum)
                .where(Quantum.id.in_(list(successful_quantum_ids)))
                .values(
                    entity_extraction_version=self._version,
                    updated_at=func.now(),
                )
            )
        processed_quanta = len(successful_quantum_ids)
        logger.info("entities_extraction: processed quanta count=%s", processed_quanta)
        return processed_quanta

    async def _fetch_quanta_batch(
        self,
        session: AsyncSession,
        *,
        theme_id: Any | None = None,
    ) -> list[Quantum]:
        stmt: Select[tuple[Quantum]] = select(Quantum).where(
            Quantum.entity_extraction_version.is_(None),
        )
        if theme_id is not None:
            stmt = stmt.where(Quantum.theme_id == theme_id)
        stmt = (
            stmt.order_by(Quantum.created_at)
            .limit(self._batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(stmt)
        quanta = list(result.scalars().all())
        return quanta

    async def _apply_extraction_results(
        self,
        session: AsyncSession,
        quanta: Iterable[Quantum],
        per_quantum_entities: dict[Any, list[TechEntityCandidate]],
    ) -> None:
        quanta_by_id = {q.id: q for q in quanta}

        groups: dict[_EntityGroupKey, _EntityGroup] = {}
        entity_to_quanta: dict[_EntityGroupKey, set[Any]] = defaultdict(set)

        for quantum_id, entities in per_quantum_entities.items():
            quantum = quanta_by_id.get(quantum_id)
            if quantum is None:
                continue
            theme_id = quantum.theme_id
            event_date = quantum.date_at or quantum.retrieved_at

            for cand in entities:
                normalized = cand.normalized_name.strip()
                canonical = cand.canonical_name.strip()
                if not normalized or not canonical:
                    continue
                key = _EntityGroupKey(theme_id=theme_id, normalized_name=normalized)
                if key not in groups:
                    groups[key] = _EntityGroup(
                        theme_id=theme_id,
                        normalized_name=normalized,
                        language=quantum.language,
                        quantum_ids=set(),
                        canonical_names=Counter(),
                        min_date_at=event_date,
                        max_date_at=event_date,
                    )
                group = groups[key]
                group.quantum_ids.add(quantum_id)
                for alias_candidate in _expand_canonical_aliases(canonical):
                    group.canonical_names[alias_candidate] += 1
                if event_date is not None:
                    if group.min_date_at is None or event_date < group.min_date_at:
                        group.min_date_at = event_date
                    if group.max_date_at is None or event_date > group.max_date_at:
                        group.max_date_at = event_date
                entity_to_quanta[key].add(quantum_id)

        if not groups:
            return

        existing_entities = await self._load_existing_entities(session, groups.keys())
        primary_languages = await self._load_primary_languages_for_themes(
            session, {k.theme_id for k in groups.keys()}
        )
        entities_by_key: dict[_EntityGroupKey, Entity] = {}

        for key, group in groups.items():
            existing = existing_entities.get(key)
            if existing is None:
                primary_lang = primary_languages.get(group.theme_id, "en")
                src_lang = _normalize_lang_code(group.language)
                tgt_lang = _normalize_lang_code(primary_lang) or "en"
                canonical_name = None
                is_name_translated = False
                if src_lang and tgt_lang and src_lang.lower() != tgt_lang.lower():
                    translated = await self._translate_entity_name(
                        term=group.normalized_name,
                        source_language=src_lang,
                        target_language=tgt_lang,
                    )
                    if translated:
                        canonical_name = _capitalize_first(translated)
                        is_name_translated = True
                if not canonical_name:
                    canonical_name = _capitalize_first(group.normalized_name)
                    is_name_translated = False

                ent = Entity(
                    theme_id=group.theme_id,
                    run_id=None,
                    entity_type="tech",
                    canonical_name=canonical_name,
                    normalized_name=group.normalized_name,
                    mention_count=len(group.quantum_ids),
                    first_seen_at=group.min_date_at,
                    last_seen_at=group.max_date_at,
                    is_name_translated=is_name_translated,
                )
                session.add(ent)
                entities_by_key[key] = ent
            else:
                existing.mention_count = (existing.mention_count or 0) + len(
                    group.quantum_ids
                )
                if group.min_date_at is not None:
                    if existing.first_seen_at is None or group.min_date_at < existing.first_seen_at:
                        existing.first_seen_at = group.min_date_at
                if group.max_date_at is not None:
                    if existing.last_seen_at is None or group.max_date_at > existing.last_seen_at:
                        existing.last_seen_at = group.max_date_at
                entities_by_key[key] = existing

        await session.flush()

        await self._upsert_relations(session, entities_by_key, entity_to_quanta)
        await self._upsert_aliases(session, entities_by_key, groups)

    async def _load_existing_entities(
        self,
        session: AsyncSession,
        keys: Iterable[_EntityGroupKey],
    ) -> dict[_EntityGroupKey, Entity]:
        theme_ids = {k.theme_id for k in keys}
        normalized_names = {k.normalized_name for k in keys}
        if not theme_ids or not normalized_names:
            return {}
        stmt = select(Entity).where(
            Entity.theme_id.in_(list(theme_ids)),
            Entity.entity_type == "tech",
            Entity.normalized_name.in_(list(normalized_names)),
            Entity.deleted_at.is_(None),
        )
        result = await session.execute(stmt)
        rows: list[Entity] = list(result.scalars().all())
        by_key: dict[_EntityGroupKey, Entity] = {}
        for ent in rows:
            key = _EntityGroupKey(theme_id=ent.theme_id, normalized_name=ent.normalized_name)
            by_key[key] = ent
        return by_key

    async def _load_primary_languages_for_themes(
        self,
        session: AsyncSession,
        theme_ids: Iterable[Any],
    ) -> dict[Any, str]:
        ids = {tid for tid in theme_ids if tid is not None}
        if not ids:
            return {}
        stmt = select(Theme).where(Theme.id.in_(list(ids)))
        result = await session.execute(stmt)
        rows: list[Theme] = list(result.scalars().all())
        return {t.id: _theme_primary_language(t) for t in rows}

    async def _upsert_relations(
        self,
        session: AsyncSession,
        entities_by_key: dict[_EntityGroupKey, Entity],
        entity_to_quanta: dict[_EntityGroupKey, set[Any]],
    ) -> None:
        rows: list[dict[str, Any]] = []
        for key, ent in entities_by_key.items():
            quantum_ids = entity_to_quanta.get(key) or set()
            for qid in quantum_ids:
                rows.append(
                    {
                        "theme_id": ent.theme_id,
                        "subject_type": "entity",
                        "subject_id": ent.id,
                        "object_type": "quantum",
                        "object_id": qid,
                        "relation_type": "mentions",
                        "direction": "forward",
                        "status": "active",
                        "is_user_created": False,
                    }
                )
        if not rows:
            return

        stmt = (
            insert(Relation)
            .values(rows)
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
        await session.execute(stmt)

    async def _upsert_aliases(
        self,
        session: AsyncSession,
        entities_by_key: dict[_EntityGroupKey, Entity],
        groups: dict[_EntityGroupKey, _EntityGroup],
    ) -> None:
        rows: list[dict[str, Any]] = []
        for key, group in groups.items():
            ent = entities_by_key.get(key)
            if ent is None:
                continue
            normalized_lower = (group.normalized_name or "").strip().lower()
            for canonical_name in group.canonical_names.keys():
                alias_value = canonical_name.strip()
                if not alias_value:
                    continue
                if alias_value.lower() == normalized_lower:
                    continue
                rows.append(
                    {
                        "theme_id": group.theme_id,
                        "entity_id": ent.id,
                        "entity_type": "tech",
                        "alias_value": alias_value,
                        "lang": None,
                        "kind": "surface",
                        "confidence": None,
                        "source": "ai",
                    }
                )
        if not rows:
            return

        stmt = (
            insert(EntityAlias)
            .values(rows)
            .on_conflict_do_nothing(
                index_elements=[
                    EntityAlias.entity_id,
                    EntityAlias.alias_value,
                ]
            )
        )
        await session.execute(stmt)

    @staticmethod
    def _build_text_for_quantum(q: Quantum) -> str:
        title = (q.title or "").strip()
        summary = (q.summary_text or "").strip()
        if title and summary:
            return f"{title}\n\n{summary}"
        if title:
            return title
        return summary

