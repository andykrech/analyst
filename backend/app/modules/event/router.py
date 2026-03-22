"""API событий: запуск извлечения событий из квантов (MVP)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.integrations.llm import LLMService, get_llm_service
from app.integrations.prompts import PromptService, get_prompt_service
from app.modules.auth.router import get_current_user
from app.modules.entity.model import Cluster
from app.modules.event.model import Event, EventParticipant, EventPlot, EventRole
from app.modules.event.schemas import (
    EventDetailOut,
    EventExtractResponse,
    EventOut,
    EventAttributeOut,
    EventParticipantOut,
)
from app.modules.event.service import EventExtractionService
from app.modules.theme.service import get_theme_with_queries
from app.modules.user.model import User


router = APIRouter(prefix="/api/v1", tags=["events"])

MAX_EXTRACT_BATCHES = 50


async def _ensure_theme_access(
    db: AsyncSession,
    *,
    theme_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Проверяет, что тема существует и принадлежит пользователю."""
    theme, _ = await get_theme_with_queries(db, theme_id, user_id)
    if not theme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тема не найдена или недоступна",
        )


@router.post(
    "/themes/{theme_id}/events/extract",
    response_model=EventExtractResponse,
)
async def extract_theme_events(
    theme_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service),
    prompt_service: PromptService = Depends(get_prompt_service),
) -> EventExtractResponse:
    """Запустить извлечение событий из квантов по теме."""
    try:
        tid = uuid.UUID(theme_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат theme_id (ожидается UUID)",
        )

    await _ensure_theme_access(db, theme_id=tid, user_id=current_user.id)

    service = EventExtractionService(
        llm_service=llm_service,
        prompt_service=prompt_service,
    )

    batches_done = 0
    processed_quanta = 0
    created_events = 0
    while batches_done < MAX_EXTRACT_BATCHES:
        n_quanta, n_events = await service.process_next_batch(db, theme_id=tid)
        if n_quanta == 0:
            break
        processed_quanta += n_quanta
        created_events += n_events
        batches_done += 1

    return EventExtractResponse(processed_quanta=processed_quanta, created_events=created_events)


@router.get(
    "/themes/{theme_id}/events",
    response_model=list[EventOut],
)
async def list_theme_events(
    theme_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EventOut]:
    """Список событий по теме (для вкладки «События»)."""
    try:
        tid = uuid.UUID(theme_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат theme_id (ожидается UUID)",
        )

    await _ensure_theme_access(db, theme_id=tid, user_id=current_user.id)

    stmt = (
        select(Event, EventPlot)
        .outerjoin(EventPlot, EventPlot.id == Event.plot_id)
        .where(Event.theme_id == tid)
        .order_by(Event.created_at.desc())
    )
    result = await db.execute(stmt)
    rows: list[tuple[Event, EventPlot | None]] = list(result.all())

    out: list[EventOut] = []
    for ev, plot in rows:
        out.append(
            EventOut(
                id=ev.id,
                theme_id=ev.theme_id,
                plot_code=(plot.code if plot is not None else None),
                plot_name=(plot.name if plot is not None else None),
                predicate_text=ev.predicate_text,
                predicate_normalized=ev.predicate_normalized,
                predicate_class=ev.predicate_class,
                display_text=ev.display_text,
                event_time=ev.event_time,
                created_at=ev.created_at,
                updated_at=ev.updated_at,
            )
        )
    return out


@router.get(
    "/events/{event_id}",
    response_model=EventDetailOut,
)
async def get_event_detail(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventDetailOut:
    """Детали события: участники, атрибуты, предикаты."""
    try:
        eid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат event_id (ожидается UUID)",
        )

    # Загрузить событие и убедиться, что тема доступна пользователю
    stmt_event = select(Event, EventPlot).outerjoin(EventPlot, EventPlot.id == Event.plot_id).where(Event.id == eid)
    result_event = await db.execute(stmt_event)
    row = result_event.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Событие не найдено")

    ev, plot = row
    await _ensure_theme_access(db, theme_id=ev.theme_id, user_id=current_user.id)

    # Участники: EventParticipant + EventRole + Cluster
    stmt_parts = (
        select(EventParticipant, EventRole, Cluster)
        .join(EventRole, EventRole.id == EventParticipant.role_id)
        .join(Cluster, Cluster.id == EventParticipant.entity_id)
        .where(EventParticipant.event_id == ev.id)
    )
    result_parts = await db.execute(stmt_parts)
    part_rows: list[tuple[EventParticipant, EventRole, Cluster]] = list(result_parts.all())

    participants: list[EventParticipantOut] = []
    for part, role, cluster in part_rows:
        participants.append(
            EventParticipantOut(
                role_code=role.code,
                role_name=role.name,
                entity_id=cluster.id,
                entity_normalized_name=cluster.normalized_text,
                entity_canonical_name=cluster.display_text,
            )
        )

    # Атрибуты: разбираем attributes_json + загружаем кластеры для entity_id
    raw_attrs: list[dict[str, Any]] = []
    if isinstance(ev.attributes_json, list):
        for item in ev.attributes_json:
            if isinstance(item, dict):
                raw_attrs.append(item)

    entity_ids_from_attrs = {
        uuid.UUID(str(a.get("entity_id")))
        for a in raw_attrs
        if a.get("entity_id") is not None
    }
    clusters_by_id: dict[uuid.UUID, Cluster] = {}
    if entity_ids_from_attrs:
        stmt_attr_ents = select(Cluster).where(Cluster.id.in_(list(entity_ids_from_attrs)))
        result_attr_ents = await db.execute(stmt_attr_ents)
        for c in result_attr_ents.scalars().all():
            clusters_by_id[c.id] = c

    attributes: list[EventAttributeOut] = []
    for a in raw_attrs:
        attribute_for = str(a.get("attribute_for") or "").strip()
        attribute_text = str(a.get("attribute_text") or "").strip()
        if not attribute_for or not attribute_text:
            continue
        attr_norm = a.get("attribute_normalized")
        attr_norm_str = (str(attr_norm).strip() if attr_norm is not None else None) or None

        ent_id_val = a.get("entity_id")
        ent_uuid: uuid.UUID | None = None
        ent_norm_name: str | None = None
        if ent_id_val is not None:
            try:
                ent_uuid = uuid.UUID(str(ent_id_val))
            except ValueError:
                ent_uuid = None
            if ent_uuid is not None:
                cluster_obj = clusters_by_id.get(ent_uuid)
                if cluster_obj is not None:
                    ent_norm_name = cluster_obj.normalized_text

        attributes.append(
            EventAttributeOut(
                attribute_for=attribute_for,
                entity_id=ent_uuid,
                entity_normalized_name=ent_norm_name,
                attribute_text=attribute_text,
                attribute_normalized=attr_norm_str,
            )
        )

    event_out = EventOut(
        id=ev.id,
        theme_id=ev.theme_id,
        plot_code=(plot.code if plot is not None else None),
        plot_name=(plot.name if plot is not None else None),
        predicate_text=ev.predicate_text,
        predicate_normalized=ev.predicate_normalized,
        predicate_class=ev.predicate_class,
        display_text=ev.display_text,
        event_time=ev.event_time,
        created_at=ev.created_at,
        updated_at=ev.updated_at,
    )

    return EventDetailOut(event=event_out, participants=participants, attributes=attributes)

