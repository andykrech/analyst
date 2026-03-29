"""Сервис извлечения сущностей из квантов и апсерта сущностей/связей."""

from __future__ import annotations

import asyncio
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
from app.modules.entity.extractors.phenomenon_extractor import (
    PhenomenonEntitiesExtractor,
    PhenomenonExtractorResult,
)
from app.modules.entity.extractors.tech_extractor import (
    TechEntitiesExtractor,
    TechEntityCandidate,
)
from app.modules.entity.model import Cluster
from app.modules.quanta.models import Quantum
from app.modules.relation.model import Relation, RelationClaim
from app.modules.theme.model import Theme


logger = logging.getLogger(__name__)

PROMPT_NAME_ENTITY_NAME_TRANSLATE = "entity.entities_name_translate.v1"
RELATION_CLAIM_PROPERTY_PHENOMENON = "phenomenon_modifier_condition"


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


def _normalize_name_for_key(s: str) -> str:
    """Lowercase и схлопнуть пробелы для normalized_name."""
    if not s or not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.strip()).lower()


def _capitalize_first(s: str) -> str:
    """Первая буква заглавная, остальное без изменений (для персон и т.п.)."""
    if not s:
        return s
    if len(s) == 1:
        return s.upper()
    return s[0].upper() + s[1:]


def _capitalize_first_letter_only(s: str) -> str:
    """Только первая буква заглавная, остальные строчные (для явлений)."""
    s = (s or "").strip()
    if not s:
        return ""
    if len(s) == 1:
        return s.upper()
    return s[0].upper() + s[1:].lower()


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


@dataclass
class _PhenomenonOccurrence:
    quantum_id: Any
    modifier: str
    condition_text: str


@dataclass
class _PhenomenonGroup:
    theme_id: Any
    normalized_name: str
    quantum_ids: set[Any]
    occurrences: list[_PhenomenonOccurrence]
    surface_forms: set[str]
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
        self._phenomenon_extractor = PhenomenonEntitiesExtractor(llm_service, prompt_service)
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
                result = await self._extractor.extract_for_text(
                    source_text,
                    billing_session=session,
                    billing_theme_id=q.theme_id,
                )
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

        per_quantum_phenomena = await self._extract_phenomena_for_quanta(session, quanta)
        logger.info(
            "entities_extraction: phenomenon extraction done, quanta_with_phenomena=%s",
            len(per_quantum_phenomena),
        )
        if per_quantum_phenomena:
            logger.info("entities_extraction: applying phenomenon results...")
            await self._apply_phenomenon_results(session, quanta, per_quantum_phenomena)
            logger.info("entities_extraction: phenomenon results applied")

        successful_quantum_ids = {q.id for q in quanta}
        if successful_quantum_ids:
            logger.info(
                "entities_extraction: updating entity_extraction_version for quanta=%s",
                len(successful_quantum_ids),
            )
            await session.execute(
                update(Quantum)
                .where(Quantum.id.in_(list(successful_quantum_ids)))
                .values(
                    entity_extraction_version=self._version,
                    updated_at=func.now(),
                )
            )
            await session.flush()
            logger.info("entities_extraction: entity_extraction_version updated in DB")
        processed_quanta = len(successful_quantum_ids)
        logger.info("entities_extraction: processed quanta count=%s, returning", processed_quanta)
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

        existing_clusters = await self._load_existing_clusters(session, groups.keys(), cluster_type="tech")
        primary_languages = await self._load_primary_languages_for_themes(
            session, {k.theme_id for k in groups.keys()}
        )
        clusters_by_key: dict[_EntityGroupKey, Cluster] = {}

        for key, group in groups.items():
            existing = existing_clusters.get(key)
            if existing is None:
                primary_lang = primary_languages.get(group.theme_id, "en")
                src_lang = _normalize_lang_code(group.language)
                tgt_lang = _normalize_lang_code(primary_lang) or "en"
                display_text = None
                if src_lang and tgt_lang and src_lang.lower() != tgt_lang.lower():
                    translated = await self._translate_entity_name(
                        term=group.normalized_name,
                        source_language=src_lang,
                        target_language=tgt_lang,
                    )
                    if translated:
                        display_text = _capitalize_first(translated)
                if not display_text:
                    display_text = _capitalize_first(group.normalized_name)

                cluster = Cluster(
                    theme_id=group.theme_id,
                    normalized_text=group.normalized_name,
                    display_text=display_text,
                    type="tech",
                    global_df=len(group.quantum_ids),
                    global_score=0.0,
                )
                session.add(cluster)
                clusters_by_key[key] = cluster
            else:
                existing.global_df = (existing.global_df or 0) + len(group.quantum_ids)
                clusters_by_key[key] = existing

        await session.flush()

        await self._upsert_relations(session, clusters_by_key, entity_to_quanta)

    async def _load_existing_clusters(
        self,
        session: AsyncSession,
        keys: Iterable[_EntityGroupKey],
        *,
        cluster_type: str = "tech",
    ) -> dict[_EntityGroupKey, Cluster]:
        theme_ids = {k.theme_id for k in keys}
        normalized_names = {k.normalized_name for k in keys}
        if not theme_ids or not normalized_names:
            return {}
        stmt = select(Cluster).where(
            Cluster.theme_id.in_(list(theme_ids)),
            Cluster.type == cluster_type,
            Cluster.normalized_text.in_(list(normalized_names)),
        )
        result = await session.execute(stmt)
        rows: list[Cluster] = list(result.scalars().all())
        by_key: dict[_EntityGroupKey, Cluster] = {}
        for c in rows:
            key = _EntityGroupKey(theme_id=c.theme_id, normalized_name=c.normalized_text)
            by_key[key] = c
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
        clusters_by_key: dict[_EntityGroupKey, Cluster],
        entity_to_quanta: dict[_EntityGroupKey, set[Any]],
    ) -> None:
        rows: list[dict[str, Any]] = []
        for key, cluster in clusters_by_key.items():
            quantum_ids = entity_to_quanta.get(key) or set()
            for qid in quantum_ids:
                rows.append(
                    {
                        "theme_id": cluster.theme_id,
                        "subject_type": "cluster",
                        "subject_id": cluster.id,
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

    async def _extract_phenomena_for_quanta(
        self,
        session: AsyncSession,
        quanta: list[Quantum],
    ) -> dict[Any, list[Any]]:
        """Извлечь явления из каждого кванта через LLM. Возвращает quantum_id -> list[PhenomenonCandidate]."""
        quanta_by_id = {q.id: q for q in quanta}
        per_quantum: dict[Any, list[Any]] = {}
        for q in quanta:
            text = self._build_text_for_quantum(q)
            if not text.strip():
                continue
            try:
                result = await self._phenomenon_extractor.extract_for_text(
                    text,
                    billing_session=session,
                    billing_theme_id=q.theme_id,
                )
            except Exception as e:
                logger.warning(
                    "entities_extraction: phenomenon extraction failed for quantum_id=%s: %s",
                    q.id,
                    e,
                )
                continue
            if result.phenomena:
                per_quantum[q.id] = list(result.phenomena)
        return per_quantum

    async def _apply_phenomenon_results(
        self,
        session: AsyncSession,
        quanta: Iterable[Quantum],
        per_quantum_phenomena: dict[Any, list[Any]],
    ) -> None:
        from app.modules.entity.extractors.phenomenon_extractor import PhenomenonCandidate

        logger.info(
            "entities_extraction: _apply_phenomenon_results start, groups to build from %s quanta",
            len(per_quantum_phenomena),
        )
        quanta_by_id = {q.id: q for q in quanta}
        primary_languages = await self._load_primary_languages_for_themes(
            session, {q.theme_id for q in quanta}
        )

        groups: dict[_EntityGroupKey, _PhenomenonGroup] = {}
        for quantum_id, candidates in per_quantum_phenomena.items():
            q = quanta_by_id.get(quantum_id)
            if q is None:
                continue
            theme_id = q.theme_id
            event_date = q.date_at or q.retrieved_at
            q_lang = _normalize_lang_code(q.language)

            for cand in candidates:
                if not isinstance(cand, PhenomenonCandidate):
                    continue
                phenomenon_text = (cand.phenomenon or "").strip()
                if not phenomenon_text:
                    continue
                if q_lang and q_lang.lower() != "en":
                    translated = await self._translate_entity_name(
                        term=phenomenon_text,
                        source_language=q_lang,
                        target_language="en",
                    )
                    normalized_name = _normalize_name_for_key(translated or phenomenon_text)
                else:
                    normalized_name = _normalize_name_for_key(phenomenon_text)
                if not normalized_name:
                    continue

                key = _EntityGroupKey(theme_id=theme_id, normalized_name=normalized_name)
                if key not in groups:
                    groups[key] = _PhenomenonGroup(
                        theme_id=theme_id,
                        normalized_name=normalized_name,
                        quantum_ids=set(),
                        occurrences=[],
                        surface_forms=set(),
                        min_date_at=event_date,
                        max_date_at=event_date,
                    )
                g = groups[key]
                g.quantum_ids.add(quantum_id)
                g.occurrences.append(
                    _PhenomenonOccurrence(
                        quantum_id=quantum_id,
                        modifier=(cand.modifier or "none").strip().lower(),
                        condition_text=(cand.condition_text or "").strip(),
                    )
                )
                g.surface_forms.add(phenomenon_text)
                if event_date is not None:
                    if g.min_date_at is None or event_date < g.min_date_at:
                        g.min_date_at = event_date
                    if g.max_date_at is None or event_date > g.max_date_at:
                        g.max_date_at = event_date

        if not groups:
            logger.info("entities_extraction: _apply_phenomenon_results: no groups, exit")
            return

        logger.info("entities_extraction: _apply_phenomenon_results: groups=%s, loading existing clusters", len(groups))
        existing = await self._load_existing_clusters(
            session, groups.keys(), cluster_type="phenomenon"
        )
        primary_languages_grp = await self._load_primary_languages_for_themes(
            session, {k.theme_id for k in groups.keys()}
        )

        to_translate: list[tuple[_EntityGroupKey, _PhenomenonGroup, str]] = []
        for key, group in groups.items():
            ent = existing.get(key)
            primary_lang = primary_languages_grp.get(key.theme_id, "en")
            tgt_lang = _normalize_lang_code(primary_lang) or "en"
            need_canonical = ent is None or not (ent.display_text or "").strip()
            if need_canonical and tgt_lang.lower() != "en":
                to_translate.append((key, group, tgt_lang))

        translated_by_key: dict[_EntityGroupKey, str] = {}
        if to_translate:
            coros = [
                self._translate_entity_name(
                    term=group.normalized_name,
                    source_language="en",
                    target_language=tgt_lang,
                )
                for _key, group, tgt_lang in to_translate
            ]
            results = await asyncio.gather(*coros, return_exceptions=True)
            for (key, _group, _tgt_lang), raw in zip(to_translate, results, strict=True):
                if isinstance(raw, BaseException):
                    logger.warning(
                        "entities_extraction: translation failed for key=%s: %s",
                        key,
                        raw,
                    )
                    continue
                if raw:
                    canonical_name = _capitalize_first_letter_only(raw)
                    translated_by_key[key] = canonical_name

        clusters_by_key: dict[_EntityGroupKey, Cluster] = {}
        for key, group in groups.items():
            ent = existing.get(key)
            primary_lang = primary_languages_grp.get(key.theme_id, "en")
            tgt_lang = _normalize_lang_code(primary_lang) or "en"
            need_canonical = ent is None or not (ent.display_text or "").strip()
            canonical_name = translated_by_key.get(key) if need_canonical else None
            if need_canonical and not canonical_name:
                canonical_name = _capitalize_first_letter_only(group.normalized_name or "")

            if ent is None:
                ent = Cluster(
                    theme_id=group.theme_id,
                    normalized_text=group.normalized_name,
                    display_text=canonical_name or group.normalized_name,
                    type="phenomenon",
                    global_df=len(group.quantum_ids),
                    global_score=0.0,
                )
                session.add(ent)
                clusters_by_key[key] = ent
            else:
                ent.global_df = (ent.global_df or 0) + len(group.quantum_ids)
                if need_canonical and canonical_name:
                    ent.display_text = canonical_name
                clusters_by_key[key] = ent

        logger.info("entities_extraction: _apply_phenomenon_results: clusters created/updated, flush")
        await session.flush()

        relation_rows = []
        for key, group in groups.items():
            ent = clusters_by_key.get(key)
            if ent is None:
                continue
            for qid in group.quantum_ids:
                relation_rows.append(
                    {
                        "theme_id": ent.theme_id,
                        "subject_type": "cluster",
                        "subject_id": ent.id,
                        "object_type": "quantum",
                        "object_id": qid,
                        "relation_type": "mentions",
                        "direction": "forward",
                        "status": "active",
                        "is_user_created": False,
                    }
                )
        if relation_rows:
            await session.execute(
                insert(Relation)
                .values(relation_rows)
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
            await session.flush()
        logger.info("entities_extraction: _apply_phenomenon_results: relation_rows inserted=%s", len(relation_rows))

        relation_id_by_entity_quantum: dict[tuple[Any, Any], Any] = {}
        if clusters_by_key and relation_rows:
            cluster_ids = {c.id for c in clusters_by_key.values()}
            quantum_ids = {r["object_id"] for r in relation_rows}
            theme_ids_rel = {r["theme_id"] for r in relation_rows}
            stmt_rel = select(Relation).where(
                Relation.theme_id.in_(list(theme_ids_rel)),
                Relation.subject_type == "cluster",
                Relation.subject_id.in_(list(cluster_ids)),
                Relation.relation_type == "mentions",
                Relation.object_type == "quantum",
                Relation.object_id.in_(list(quantum_ids)),
                Relation.deleted_at.is_(None),
                Relation.status == "active",
            )
            res_rel = await session.execute(stmt_rel)
            for r in res_rel.scalars().all():
                relation_id_by_entity_quantum[(r.subject_id, r.object_id)] = r.id
        logger.info(
            "entities_extraction: _apply_phenomenon_results: relation_id_by_entity_quantum loaded, count=%s",
            len(relation_id_by_entity_quantum),
        )

        claim_rows = []
        seen_per_relation: dict[Any, set[tuple[str, str]]] = {}
        for key, group in groups.items():
            ent = clusters_by_key.get(key)
            if ent is None:
                continue
            by_q: dict[Any, list[tuple[str, str]]] = {}
            for occ in group.occurrences:
                by_q.setdefault(occ.quantum_id, []).append(
                    (occ.modifier, occ.condition_text)
                )
            for qid, mod_cond_list in by_q.items():
                rel_id = relation_id_by_entity_quantum.get((ent.id, qid))
                if rel_id is None:
                    continue
                seen = seen_per_relation.setdefault(rel_id, set())
                for mod, ctext in mod_cond_list:
                    if (mod, ctext) in seen:
                        continue
                    seen.add((mod, ctext))
                    claim_rows.append(
                        {
                            "relation_id": rel_id,
                            "property_type": RELATION_CLAIM_PROPERTY_PHENOMENON,
                            "properties_json": {"modifier": mod, "condition_text": ctext},
                        }
                    )
        logger.info("entities_extraction: _apply_phenomenon_results: claim_rows=%s, inserting", len(claim_rows))
        if claim_rows:
            await session.execute(insert(RelationClaim).values(claim_rows))
        logger.info("entities_extraction: _apply_phenomenon_results: claim_rows inserted")

        logger.info(
            "entities_extraction: phenomenon groups=%s, claims=%s",
            len(groups),
            len(claim_rows),
        )

    @staticmethod
    def _build_text_for_quantum(q: Quantum) -> str:
        title = (q.title or "").strip()
        summary = (q.summary_text or "").strip()
        if title and summary:
            return f"{title}\n\n{summary}"
        if title:
            return title
        return summary

