"""
Извлечение сущностей типа person из квантов publication (авторы).
Только для квантов из OpenAlex; структура attrs.publication.contributors.
В новой архитектуре создаются кластеры (Cluster), алиасы не используются.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from sqlalchemy import select, text as sql_text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.entity.model import Cluster
from app.modules.quanta.models import Quantum
from app.modules.relation.model import Relation


logger = logging.getLogger(__name__)

SOURCE_OPENALEX = "openalex"
ENTITY_KIND_PUBLICATION = "publication"
RELATION_TYPE_AUTHOR = "author"

ATTRS_PUBLICATION_KEY = "publication"
ATTRS_CONTRIBUTORS_KEY = "contributors"


def _normalize_display_name(s: str | None) -> str:
    if not s or not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.strip()).lower()


def _canonical_person_name(normalized_name: str) -> str:
    if not normalized_name:
        return ""
    n = normalized_name.strip()
    return " ".join(w.capitalize() for w in n.split())


@dataclass
class PersonAuthorCandidate:
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
            orcid = (author.get("orcid") or "").strip() or None
            openalex_id = (author.get("openalex_id") or "").strip() or None
            if not display_name and not orcid and not openalex_id:
                continue
            normalized_name = _normalize_display_name(display_name or author.get("raw_affiliation_string"))
            if not normalized_name and not orcid and not openalex_id:
                continue
            if not normalized_name:
                normalized_name = orcid or openalex_id or ""
            canonical_name = _canonical_person_name(normalized_name)
            date_at = getattr(q, "date_at", None) or getattr(q, "retrieved_at", None)
            out.append(
                PersonAuthorCandidate(
                    theme_id=q.theme_id,
                    quantum_id=q.id,
                    date_at=date_at,
                    normalized_name=normalized_name,
                    canonical_name=canonical_name,
                    display_name=display_name,
                    orcid=orcid,
                    openalex_id=openalex_id,
                )
            )
    return out


def collapse_candidates(candidates: list[PersonAuthorCandidate]) -> list[PersonGroup]:
    by_key: dict[tuple[Any, str], PersonGroup] = {}
    for c in candidates:
        key = (c.theme_id, (c.normalized_name or "").strip().lower())
        if key not in by_key:
            by_key[key] = PersonGroup(
                theme_id=c.theme_id,
                normalized_name=c.normalized_name,
                canonical_name=c.canonical_name,
                orcid=c.orcid,
                openalex_id=c.openalex_id,
                alias_values=set(),
                quantum_ids=set(),
                min_date_at=c.date_at,
                max_date_at=c.date_at,
            )
        g = by_key[key]
        g.quantum_ids.add(c.quantum_id)
        if c.display_name and c.display_name.strip():
            g.alias_values.add(c.display_name.strip())
        if c.orcid:
            g.alias_values.add(f"orcid:{c.orcid}")
        if c.openalex_id:
            g.alias_values.add(f"openalex:{c.openalex_id}")
        if c.date_at is not None:
            if g.min_date_at is None or c.date_at < g.min_date_at:
                g.min_date_at = c.date_at
            if g.max_date_at is None or c.date_at > g.max_date_at:
                g.max_date_at = c.date_at
    return list(by_key.values())


async def apply_person_results(
    session: AsyncSession,
    groups: list[PersonGroup],
) -> None:
    """
    Найти или создать Cluster (person), обновить global_df,
    создать связи author. Уникальность по (theme_id, normalized_text).
    """
    if not groups:
        return
    theme_ids = {g.theme_id for g in groups}
    normalized_names = {g.normalized_name for g in groups}

    stmt = (
        select(Cluster)
        .where(Cluster.theme_id.in_(list(theme_ids)))
        .where(Cluster.type == "person")
    )
    result = await session.execute(stmt)
    clusters: list[Cluster] = list(result.scalars().all())
    by_normalized: dict[tuple[Any, str], Cluster] = {}
    for c in clusters:
        key = (c.theme_id, (c.normalized_text or "").strip().lower())
        by_normalized[key] = c

    clusters_by_key: dict[tuple[Any, str], Cluster] = {}
    relation_rows: list[dict[str, Any]] = []

    for g in groups:
        norm_lower = (g.normalized_name or "").strip().lower()
        cluster = by_normalized.get((g.theme_id, norm_lower))

        if cluster is not None:
            cluster.global_df = (cluster.global_df or 0) + len(g.quantum_ids)
            clusters_by_key[(g.theme_id, g.normalized_name)] = cluster
        else:
            new_cluster = Cluster(
                theme_id=g.theme_id,
                normalized_text=g.normalized_name,
                display_text=g.canonical_name,
                type="person",
                global_df=len(g.quantum_ids),
                global_score=0.0,
            )
            session.add(new_cluster)
            await session.flush()
            by_normalized[(g.theme_id, norm_lower)] = new_cluster
            clusters_by_key[(g.theme_id, g.normalized_name)] = new_cluster
            cluster = new_cluster

        for qid in g.quantum_ids:
            relation_rows.append(
                {
                    "theme_id": g.theme_id,
                    "subject_type": "cluster",
                    "subject_id": cluster.id,
                    "object_type": "quantum",
                    "object_id": qid,
                    "relation_type": RELATION_TYPE_AUTHOR,
                    "direction": "forward",
                    "status": "active",
                    "is_user_created": False,
                }
            )

    await session.flush()

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
