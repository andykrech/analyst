"""API сущностей: список по теме и запуск извлечения."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.integrations.llm import LLMService, get_llm_service
from app.integrations.prompts import PromptService, get_prompt_service
from app.modules.auth.router import get_current_user
from app.modules.entity.model import Entity, EntityAlias
from app.modules.entity.schemas import EntityAliasOut, EntityListOut, EntityOut
from app.modules.entity.service import EntitiesExtractionService
from app.modules.theme.service import get_theme_with_queries
from app.modules.user.model import User

router = APIRouter(prefix="/api/v1", tags=["entities"])

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


def _entity_to_out(entity: Entity, aliases: list[EntityAlias]) -> EntityOut:
    """Собрать EntityOut из строки Entity и списка алиасов."""
    alias_outs = [
        EntityAliasOut(
            alias_value=a.alias_value,
            kind=a.kind,
            source=a.source,
            lang=a.lang,
            confidence=a.confidence,
        )
        for a in aliases
    ]
    return EntityOut(
        id=str(entity.id),
        theme_id=str(entity.theme_id),
        entity_type=entity.entity_type,
        canonical_name=entity.canonical_name,
        normalized_name=entity.normalized_name,
        mention_count=entity.mention_count or 0,
        first_seen_at=entity.first_seen_at,
        last_seen_at=entity.last_seen_at,
        importance=entity.importance,
        confidence=entity.confidence,
        status=entity.status,
        is_user_pinned=entity.is_user_pinned,
        aliases=alias_outs,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


@router.get(
    "/themes/{theme_id}/entities",
    response_model=EntityListOut,
)
async def list_theme_entities(
    theme_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EntityListOut:
    """Список сущностей по теме (активные, не удалённые)."""
    try:
        tid = uuid.UUID(theme_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат theme_id (ожидается UUID)",
        )

    await _ensure_theme_access(db, theme_id=tid, user_id=current_user.id)

    stmt = (
        select(Entity)
        .where(Entity.theme_id == tid)
        .where(Entity.deleted_at.is_(None))
        .where(Entity.status == "active")
        .order_by(Entity.importance.desc().nulls_last(), Entity.mention_count.desc())
    )
    result = await db.execute(stmt)
    entities = list(result.scalars().all())
    if not entities:
        return EntityListOut(items=[], total=0)

    entity_ids = [e.id for e in entities]
    alias_stmt = select(EntityAlias).where(EntityAlias.entity_id.in_(entity_ids))
    alias_result = await db.execute(alias_stmt)
    aliases = list(alias_result.scalars().all())
    aliases_by_entity: dict[uuid.UUID, list[EntityAlias]] = {}
    for a in aliases:
        aliases_by_entity.setdefault(a.entity_id, []).append(a)

    items = [
        _entity_to_out(e, aliases_by_entity.get(e.id, []))
        for e in entities
    ]
    return EntityListOut(items=items, total=len(items))


@router.post(
    "/themes/{theme_id}/entities/extract",
    response_model=EntityListOut,
)
async def extract_theme_entities(
    theme_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service),
    prompt_service: PromptService = Depends(get_prompt_service),
) -> EntityListOut:
    """Запустить извлечение сущностей из квантов по теме и вернуть обновлённый список сущностей."""
    try:
        tid = uuid.UUID(theme_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат theme_id (ожидается UUID)",
        )

    await _ensure_theme_access(db, theme_id=tid, user_id=current_user.id)

    service = EntitiesExtractionService(
        llm_service=llm_service,
        prompt_service=prompt_service,
    )
    batches_done = 0
    while batches_done < MAX_EXTRACT_BATCHES:
        n = await service.process_next_batch(db, theme_id=tid)
        if n == 0:
            break
        batches_done += 1

    # Вернуть актуальный список сущностей (тот же контракт, что и GET)
    stmt = (
        select(Entity)
        .where(Entity.theme_id == tid)
        .where(Entity.deleted_at.is_(None))
        .where(Entity.status == "active")
        .order_by(Entity.importance.desc().nulls_last(), Entity.mention_count.desc())
    )
    result = await db.execute(stmt)
    entities = list(result.scalars().all())
    if not entities:
        return EntityListOut(items=[], total=0)

    entity_ids = [e.id for e in entities]
    alias_stmt = select(EntityAlias).where(EntityAlias.entity_id.in_(entity_ids))
    alias_result = await db.execute(alias_stmt)
    aliases = list(alias_result.scalars().all())
    aliases_by_entity: dict[uuid.UUID, list[EntityAlias]] = {}
    for a in aliases:
        aliases_by_entity.setdefault(a.entity_id, []).append(a)

    items = [
        _entity_to_out(e, aliases_by_entity.get(e.id, []))
        for e in entities
    ]
    return EntityListOut(items=items, total=len(items))
