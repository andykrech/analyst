"""
Извлечение сущностей типа person из квантов publication (авторы).
Только для квантов из OpenAlex; структура attrs.publication.contributors.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from sqlalchemy import select, text as sql_text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.entity.model import Entity, EntityAlias
from app.modules.quanta.models import Quantum
from app.modules.relation.model import Relation


logger = logging.getLogger(__name__)

# Источник и тип кванта
SOURCE_OPENALEX = "openalex"
ENTITY_KIND_PUBLICATION = "publication"
RELATION_TYPE_AUTHOR = "author"

# Путь в attrs кванта
ATTRS_PUBLICATION_KEY = "publication"
ATTRS_CONTRIBUTORS_KEY = "contributors"

# Префиксы для алиасов (идемпотентный поиск по ORCID / OpenAlex id)
ALIAS_PREFIX_ORCID = "orcid:"
ALIAS_PREFIX_OPENALEX = "openalex:"


def _normalize_display_name(s: str | None) -> str:
    """Нормализованное имя для дедупа: lowercase, схлопнуть пробелы."""
    if not s or not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.strip()).lower()


def _canonical_person_name(normalized_name: str) -> str:
    """Каноническое имя: каждое слово с большой буквы (имя и фамилия). Идентификаторы (orcid:/openalex:) — без изменений."""
    if not normalized_name:
        return ""
    n = normalized_name.strip()
    if n.startswith(ALIAS_PREFIX_ORCID) or n.startswith(ALIAS_PREFIX_OPENALEX):
        return n
    return " ".join(w.capitalize() for w in n.split())


@dataclass
class PersonAuthorCandidate:
    """Один автор из одного кванта (сырой кандидат)."""

    theme_id: Any
    quantum_id: Any
    date_at: Any
    normalized_name: str
    canonical_name: str
    display_name: str
    orcid: str | None
    openalex_id: str | None


@dataclass
class PersonGroup:
    """Свёрнутая группа авторов (один person entity)."""

    theme_id: Any
    normalized_name: str
    canonical_name: str
    orcid: str | None
    openalex_id: str | None
    alias_values: set[str] = field(default_factory=set)
    quantum_ids: set[Any] = field(default_factory=set)
    min_date_at: Any = None
    max_date_at: Any = None


def _is_publication_from_openalex(q: Quantum) -> bool:
    if getattr(q, "entity_kind", None) is None:
        return False
    kind = q.entity_kind.value if hasattr(q.entity_kind, "value") else str(q.entity_kind)
    if kind != ENTITY_KIND_PUBLICATION:
        return False
    return (getattr(q, "source_system", None) or "").strip().lower() == SOURCE_OPENALEX


def _get_contributors(attrs: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not attrs or not isinstance(attrs, dict):
        return []
    pub = attrs.get(ATTRS_PUBLICATION_KEY)
    if not pub or not isinstance(pub, dict):
        return []
    contrib = pub.get(ATTRS_CONTRIBUTORS_KEY)
    if not isinstance(contrib, list):
        return []
    return contrib


def collect_candidates(quanta: Iterable[Quantum]) -> list[PersonAuthorCandidate]:
    """
    Собрать кандидатов person из квантов publication (OpenAlex).
    Автор без ORCID, OpenAlex id и display_name не включается.
    """
    out: list[PersonAuthorCandidate] = []
    for q in quanta:
        if not _is_publication_from_openalex(q):
            continue
        attrs = getattr(q, "attrs", None) or {}
        for item in _get_contributors(attrs):
            if not isinstance(item, dict):
                continue
            author = item.get("author")
            if not author or not isinstance(author, dict):
                continue
            display_name = (author.get("display_name") or "").strip()
            orcid_raw = author.get("orcid")
            orcid = (orcid_raw.strip() if isinstance(orcid_raw, str) and orcid_raw else None) or None
            oa_id_raw = author.get("id")
            openalex_id = (
                str(oa_id_raw).strip() if oa_id_raw is not None and str(oa_id_raw).strip() else None
            )
            if not orcid and not openalex_id and not display_name:
                continue
            normalized_name = _normalize_display_name(display_name) if display_name else ""
            if not normalized_name and not orcid and not openalex_id:
                continue
            if not normalized_name:
                normalized_name = (
                    ALIAS_PREFIX_ORCID + orcid
                    if orcid
                    else (ALIAS_PREFIX_OPENALEX + openalex_id) if openalex_id else ""
                )
            canonical_name = _canonical_person_name(normalized_name)
            date_at = getattr(q, "date_at", None) or getattr(q, "retrieved_at", None)
            out.append(
                PersonAuthorCandidate(
                    theme_id=q.theme_id,
                    quantum_id=q.id,
                    date_at=date_at,
                    normalized_name=normalized_name,
                    canonical_name=canonical_name,
                    display_name=display_name or normalized_name,
                    orcid=orcid,
                    openalex_id=openalex_id,
                )
            )
    return out


def _merge_into_groups(candidates: list[PersonAuthorCandidate]) -> list[PersonGroup]:
    """
    Свернуть кандидатов в группы по ORCID / OpenAlex id / normalized_name.
    Два кандидата — один человек, если совпадает хотя бы один из трёх.
    """
    # Граф связности: индекс кандидата -> множество индексов того же человека
    n = len(candidates)
    parent: list[int] = list(range(n))

    def find(i: int) -> int:
        if parent[i] != i:
            parent[i] = find(parent[i])
        return parent[i]

    def union(i: int, j: int) -> None:
        pi, pj = find(i), find(j)
        if pi != pj:
            parent[pi] = pj

    for i in range(n):
        for j in range(i + 1, n):
            a, b = candidates[i], candidates[j]
            if a.theme_id != b.theme_id:
                continue
            same = False
            if a.orcid and b.orcid and a.orcid == b.orcid:
                same = True
            if not same and a.openalex_id and b.openalex_id and a.openalex_id == b.openalex_id:
                same = True
            if not same and a.normalized_name and b.normalized_name and a.normalized_name == b.normalized_name:
                same = True
            if same:
                union(i, j)

    # Собрать группы по корню
    from collections import defaultdict
    by_root: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        by_root[find(i)].append(i)

    groups: list[PersonGroup] = []
    for indices in by_root.values():
        first = candidates[indices[0]]
        alias_values: set[str] = set()
        quantum_ids: set[Any] = set()
        min_date = first.date_at
        max_date = first.date_at
        normalized_name = first.normalized_name
        canonical_name = first.canonical_name
        orcid = first.orcid
        openalex_id = first.openalex_id
        for idx in indices:
            c = candidates[idx]
            quantum_ids.add(c.quantum_id)
            if c.display_name:
                alias_values.add(c.display_name.strip())
            if c.orcid:
                alias_values.add(ALIAS_PREFIX_ORCID + c.orcid)
            if c.openalex_id:
                alias_values.add(ALIAS_PREFIX_OPENALEX + c.openalex_id)
            if c.date_at is not None:
                if min_date is None or c.date_at < min_date:
                    min_date = c.date_at
                if max_date is None or c.date_at > max_date:
                    max_date = c.date_at
        groups.append(
            PersonGroup(
                theme_id=first.theme_id,
                normalized_name=normalized_name,
                canonical_name=canonical_name,
                orcid=orcid,
                openalex_id=openalex_id,
                alias_values=alias_values,
                quantum_ids=quantum_ids,
                min_date_at=min_date,
                max_date_at=max_date,
            )
        )
    return groups


def collapse_candidates(candidates: list[PersonAuthorCandidate]) -> list[PersonGroup]:
    """Публичная обёртка над _merge_into_groups."""
    return _merge_into_groups(candidates)


async def apply_person_results(
    session: AsyncSession,
    groups: list[PersonGroup],
) -> None:
    """
    Найти или создать Entity (person), обновить mention_count/dates,
    добавить алиасы (orcid, openalex id, display_name), создать связи author.
    Уникальность: сначала по ORCID, затем по OpenAlex id, затем по normalized_name.
    """
    if not groups:
        return
    theme_ids = {g.theme_id for g in groups}
    orcid_aliases = {ALIAS_PREFIX_ORCID + g.orcid for g in groups if g.orcid}
    openalex_aliases = {ALIAS_PREFIX_OPENALEX + g.openalex_id for g in groups if g.openalex_id}
    normalized_names = {g.normalized_name for g in groups}

    # Загрузить существующие person по теме и (alias in orcid|openalex или normalized_name)
    stmt = (
        select(Entity)
        .where(Entity.theme_id.in_(list(theme_ids)))
        .where(Entity.entity_type == "person")
        .where(Entity.deleted_at.is_(None))
    )
    # Подгрузить алиасы для этих сущностей
    result = await session.execute(stmt)
    entities: list[Entity] = list(result.scalars().all())
    aliases_by_entity: dict[Any, list[EntityAlias]] = {}
    if entities:
        entity_ids = [e.id for e in entities]
        alias_stmt = select(EntityAlias).where(EntityAlias.entity_id.in_(entity_ids))
        alias_res = await session.execute(alias_stmt)
        for al in alias_res.scalars().all():
            aliases_by_entity.setdefault(al.entity_id, []).append(al)

    # Построить маппинг: (theme_id, orcid) -> entity, (theme_id, openalex_id) -> entity, (theme_id, normalized_name) -> entity
    by_orcid: dict[tuple[Any, str], Entity] = {}
    by_openalex: dict[tuple[Any, str], Entity] = {}
    by_normalized: dict[tuple[Any, str], Entity] = {}
    for ent in entities:
        key_theme = ent.theme_id
        by_normalized[(key_theme, (ent.normalized_name or "").strip().lower())] = ent
        for al in aliases_by_entity.get(ent.id, []):
            v = (al.alias_value or "").strip()
            if v.startswith(ALIAS_PREFIX_ORCID):
                by_orcid[(key_theme, v)] = ent
            if v.startswith(ALIAS_PREFIX_OPENALEX):
                by_openalex[(key_theme, v)] = ent

    entities_by_key: dict[tuple[Any, str], Entity] = {}
    alias_rows: list[dict[str, Any]] = []
    relation_rows: list[dict[str, Any]] = []

    for g in groups:
        ent = None
        lookup_key: tuple[Any, str] | None = None
        if g.orcid:
            ent = by_orcid.get((g.theme_id, ALIAS_PREFIX_ORCID + g.orcid))
            if ent:
                lookup_key = (g.theme_id, f"orcid:{g.orcid}")
        if ent is None and g.openalex_id:
            ent = by_openalex.get((g.theme_id, ALIAS_PREFIX_OPENALEX + g.openalex_id))
            if ent:
                lookup_key = (g.theme_id, f"openalex:{g.openalex_id}")
        if ent is None:
            norm_lower = (g.normalized_name or "").strip().lower()
            ent = by_normalized.get((g.theme_id, norm_lower))
            if ent:
                lookup_key = (g.theme_id, g.normalized_name)

        if ent is not None:
            ent.mention_count = (ent.mention_count or 0) + len(g.quantum_ids)
            if g.min_date_at is not None:
                if ent.first_seen_at is None or g.min_date_at < ent.first_seen_at:
                    ent.first_seen_at = g.min_date_at
            if g.max_date_at is not None:
                if ent.last_seen_at is None or g.max_date_at > ent.last_seen_at:
                    ent.last_seen_at = g.max_date_at
            if lookup_key:
                entities_by_key[lookup_key] = ent
            # Добавить недостающие алиасы (orcid, openalex, новый display_name если normalized_name другой)
            existing_alias_values = {a.alias_value.strip().lower() for a in aliases_by_entity.get(ent.id, [])}
            for v in g.alias_values:
                if not v or v.strip().lower() in existing_alias_values:
                    continue
                alias_rows.append(
                    {
                        "theme_id": g.theme_id,
                        "entity_id": ent.id,
                        "entity_type": "person",
                        "alias_value": v.strip(),
                        "lang": None,
                        "kind": "surface",
                        "confidence": None,
                        "source": "ai",
                    }
                )
                existing_alias_values.add(v.strip().lower())
        else:
            new_ent = Entity(
                theme_id=g.theme_id,
                run_id=None,
                entity_type="person",
                canonical_name=g.canonical_name,
                normalized_name=g.normalized_name,
                mention_count=len(g.quantum_ids),
                first_seen_at=g.min_date_at,
                last_seen_at=g.max_date_at,
                is_name_translated=False,
            )
            session.add(new_ent)
            await session.flush()
            entities_by_key[(g.theme_id, g.normalized_name)] = new_ent
            by_normalized[(g.theme_id, (g.normalized_name or "").strip().lower())] = new_ent
            for v in g.alias_values:
                if v and v.strip():
                    alias_rows.append(
                        {
                            "theme_id": g.theme_id,
                            "entity_id": new_ent.id,
                            "entity_type": "person",
                            "alias_value": v.strip(),
                            "lang": None,
                            "kind": "surface",
                            "confidence": None,
                            "source": "ai",
                        }
                    )
            ent = new_ent

        for qid in g.quantum_ids:
            relation_rows.append(
                {
                    "theme_id": g.theme_id,
                    "subject_type": "entity",
                    "subject_id": ent.id,
                    "object_type": "quantum",
                    "object_id": qid,
                    "relation_type": RELATION_TYPE_AUTHOR,
                    "direction": "forward",
                    "status": "active",
                    "is_user_created": False,
                }
            )

    await session.flush()

    if alias_rows:
        stmt_alias = (
            insert(EntityAlias)
            .values(alias_rows)
            .on_conflict_do_nothing(
                index_elements=[EntityAlias.entity_id, EntityAlias.alias_value]
            )
        )
        await session.execute(stmt_alias)
    if relation_rows:
        stmt_rel = (
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
                index_where=sql_text("deleted_at IS NULL AND status = 'active'"),
            )
        )
        await session.execute(stmt_rel)
