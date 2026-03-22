"""Export all quanta with attached entities (tech, person, phenomenon) to a text file.

Output file: backend/docs/quanta_entities.txt
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.modules.entity.model import Cluster
from app.modules.quanta.models import Quantum
from app.modules.relation.model import Relation, RelationClaim


PHENOMENON_PROPERTY_TYPE = "phenomenon_modifier_condition"


async def _gather_data(session: AsyncSession) -> List[Tuple[Quantum, Dict[str, Any]]]:
    """Load all quanta and their related entities grouped by type."""
    quanta = (
        await session.execute(
            select(Quantum).order_by(Quantum.theme_id, Quantum.created_at)
        )
    ).scalars().all()
    if not quanta:
        return []

    quantum_ids = [q.id for q in quanta]

    # Load all cluster–quantum relations with clusters in one go:
    # - technologies & phenomena: relation_type='mentions'
    # - persons: relation_type='author'
    rel_rows = (
        await session.execute(
            select(Relation, Cluster)
            .join(Cluster, Cluster.id == Relation.subject_id)
            .where(
                Relation.object_type == "quantum",
                Relation.object_id.in_(quantum_ids),
                Relation.subject_type == "cluster",
                Relation.relation_type.in_(["mentions", "author"]),
                Relation.deleted_at.is_(None),
                Relation.status == "active",
            )
        )
    ).all()

    # Map relations by id and by quantum
    relations_by_id: Dict[Any, Relation] = {}
    quantum_entities: Dict[Any, Dict[str, List[Tuple[Cluster, Any]]]] = {}
    for rel, cluster in rel_rows:
        # tech & phenomenon: mentions; person: author
        if cluster.type == "tech" and rel.relation_type == "mentions":
            type_bucket = "tech"
        elif cluster.type == "phenomenon" and rel.relation_type == "mentions":
            type_bucket = "phenomenon"
        elif cluster.type == "person" and rel.relation_type == "author":
            type_bucket = "person"
        else:
            continue
        relations_by_id[rel.id] = rel
        qid = rel.object_id
        bucket = quantum_entities.setdefault(qid, {})
        lst = bucket.setdefault(type_bucket, [])
        lst.append((cluster, rel.id))

    # Load all claims for these relations (for phenomena)
    if relations_by_id:
        rel_ids = list(relations_by_id.keys())
        claim_rows = (
            await session.execute(
                select(RelationClaim)
                .where(
                    RelationClaim.relation_id.in_(rel_ids),
                    RelationClaim.property_type == PHENOMENON_PROPERTY_TYPE,
                )
            )
        ).scalars().all()
    else:
        claim_rows = []

    claims_by_relation: Dict[Any, List[Tuple[str, str]]] = {}
    for c in claim_rows:
        props = c.properties_json or {}
        mod = str(props.get("modifier") or "").strip()
        cond = str(props.get("condition_text") or "").strip()
        claims_by_relation.setdefault(c.relation_id, []).append((mod, cond))

    result: List[Tuple[Quantum, Dict[str, Any]]] = []
    for q in quanta:
        per_type = quantum_entities.get(q.id, {})
        result.append(
            (
                q,
                {
                    "tech": per_type.get("tech", []),
                    "person": per_type.get("person", []),
                    "phenomenon": per_type.get("phenomenon", []),
                    "claims_by_relation": claims_by_relation,
                },
            )
        )

    return result


def _format_quantum_block(q: Quantum, data: Dict[str, Any]) -> str:
    """Format one quantum and its entities into a text block."""
    lines: List[str] = []
    title = (q.title or "").strip()
    summary = (q.summary_text or "").strip()

    lines.append("===")
    lines.append(f"Наименование кванта: {title}")
    lines.append("summary_text:")
    lines.append(summary)
    lines.append("")

    tech_items: List[Tuple[Cluster, Any]] = data.get("tech", []) or []
    person_items: List[Tuple[Cluster, Any]] = data.get("person", []) or []
    phen_items: List[Tuple[Cluster, Any]] = data.get("phenomenon", []) or []
    claims_by_relation: Dict[Any, List[Tuple[str, str]]] = data.get(
        "claims_by_relation", {}
    ) or {}

    lines.append("Технологии:")
    if not tech_items:
        lines.append("  (нет)")
    else:
        for cluster, _rel_id in tech_items:
            lines.append(
                f'  normalized_text="{cluster.normalized_text}", '
                f'display_text="{cluster.display_text}"'
            )

    lines.append("")
    lines.append("Персоны:")
    if not person_items:
        lines.append("  (нет)")
    else:
        for cluster, _rel_id in person_items:
            lines.append(
                f'  normalized_text="{cluster.normalized_text}", '
                f'display_text="{cluster.display_text}"'
            )

    lines.append("")
    lines.append("Явления:")
    if not phen_items:
        lines.append("  (нет)")
    else:
        for cluster, rel_id in phen_items:
            claims = claims_by_relation.get(rel_id) or [("", "")]
            for mod, cond in claims:
                lines.append(f'  normalized_text="{cluster.normalized_text}"')
                lines.append(f'  display_text="{cluster.display_text}"')
                lines.append(f"  модификатор: {mod}")
                lines.append(f"  условие: {cond}")
                lines.append("")

    return "\n".join(lines).rstrip() + "\n"


async def main() -> None:
    docs_dir = Path(__file__).resolve().parents[2] / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    out_path = docs_dir / "quanta_entities.txt"

    async with AsyncSessionLocal() as session:
        data = await _gather_data(session)

    blocks: List[str] = []
    for q, info in data:
        blocks.append(_format_quantum_block(q, info))

    out_text = "\n".join(blocks) if blocks else "Нет квантов в базе.\n"
    out_path.write_text(out_text, encoding="utf-8")

    print(f"Exported {len(data)} quanta to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())

