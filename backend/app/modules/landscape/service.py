"""Загрузка событий темы в структуру для промпта ландшафта."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.entity.model import Cluster
from app.modules.event.model import Event, EventParticipant, EventPlot, EventRole


def _entity_label(cluster: Cluster) -> str:
    dt = (cluster.display_text or "").strip()
    nt = (cluster.normalized_text or "").strip()
    return dt or nt


def _attributes_for_prompt(ev: Event, clusters_by_id: dict[uuid.UUID, Cluster]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    raw = ev.attributes_json
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        attribute_for = str(item.get("attribute_for") or "").strip()
        attribute_text = str(item.get("attribute_text") or "").strip()
        if not attribute_for or not attribute_text:
            continue
        attr_norm = item.get("attribute_normalized")
        attr_norm_str = (str(attr_norm).strip() if attr_norm is not None else None) or None
        entity_text: str | None = None
        ent_id_val = item.get("entity_id")
        if ent_id_val is not None:
            try:
                eid = uuid.UUID(str(ent_id_val))
            except ValueError:
                eid = None
            if eid is not None:
                c = clusters_by_id.get(eid)
                if c is not None:
                    entity_text = _entity_label(c) or None
        out.append(
            {
                "attribute_for": attribute_for,
                "attribute_text": attribute_text,
                "attribute_normalized": attr_norm_str,
                "entity_text": entity_text,
            }
        )
    return out


async def load_events_json_payload(
    db: AsyncSession,
    *,
    theme_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """
    События темы в виде списка словарей для сериализации в JSON (промпт).

    Участники — только текстовые строки; предикат — все доступные формы;
    атрибуты — текстовые поля; отдельно display_text.
    """
    stmt_ev = (
        select(Event, EventPlot)
        .outerjoin(EventPlot, EventPlot.id == Event.plot_id)
        .where(Event.theme_id == theme_id)
        .order_by(Event.created_at.asc())
    )
    result_ev = await db.execute(stmt_ev)
    rows: list[tuple[Event, EventPlot | None]] = list(result_ev.all())
    if not rows:
        return []

    event_ids = [ev.id for ev, _ in rows]

    stmt_parts = (
        select(EventParticipant, EventRole, Cluster)
        .join(EventRole, EventRole.id == EventParticipant.role_id)
        .join(Cluster, Cluster.id == EventParticipant.entity_id)
        .where(EventParticipant.event_id.in_(event_ids))
    )
    result_parts = await db.execute(stmt_parts)
    participants_lines: dict[uuid.UUID, list[str]] = defaultdict(list)
    for part, role, cluster in result_parts.all():
        role_label = (role.name or role.code or "").strip()
        ent = _entity_label(cluster)
        if role_label and ent:
            participants_lines[part.event_id].append(f"{role_label}: {ent}")
        elif ent:
            participants_lines[part.event_id].append(ent)
        elif role_label:
            participants_lines[part.event_id].append(role_label)

    all_attr_entity_ids: set[uuid.UUID] = set()
    for ev, _plot in rows:
        raw = ev.attributes_json
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, dict):
                continue
            ent_id_val = item.get("entity_id")
            if ent_id_val is None:
                continue
            try:
                all_attr_entity_ids.add(uuid.UUID(str(ent_id_val)))
            except ValueError:
                pass

    clusters_by_id: dict[uuid.UUID, Cluster] = {}
    if all_attr_entity_ids:
        stmt_cl = select(Cluster).where(Cluster.id.in_(list(all_attr_entity_ids)))
        result_cl = await db.execute(stmt_cl)
        for c in result_cl.scalars().all():
            clusters_by_id[c.id] = c

    payload: list[dict[str, Any]] = []
    for ev, _plot in rows:
        payload.append(
            {
                "display_text": ev.display_text,
                "predicate": {
                    "text": ev.predicate_text,
                    "normalized": ev.predicate_normalized,
                    "class": ev.predicate_class,
                },
                "participants": participants_lines.get(ev.id, []),
                "attributes": _attributes_for_prompt(ev, clusters_by_id),
            }
        )
    return payload
