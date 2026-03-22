"""API сущностей (кластеров): список по теме и запуск извлечения."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.integrations.llm import LLMService, get_llm_service
from app.integrations.prompts import PromptService, get_prompt_service
from app.modules.auth.router import get_current_user
from app.modules.entity.extractors.atoms_clusters_extractor import AtomsClustersExtractor
from app.modules.entity.model import Cluster
from app.modules.entity.schemas import EntityListOut, EntityOut
from app.modules.theme.service import get_theme_with_queries
from app.modules.user.model import User

router = APIRouter(prefix="/api/v1", tags=["entities"])
logger = logging.getLogger(__name__)


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


def _cluster_to_entity_out(cluster: Cluster) -> EntityOut:
    """Собрать EntityOut из кластера (совместимость API)."""
    return EntityOut(
        id=str(cluster.id),
        theme_id=str(cluster.theme_id),
        entity_type=cluster.type,
        canonical_name=cluster.display_text,
        normalized_name=cluster.normalized_text,
        mention_count=cluster.global_df,
        importance=cluster.global_score if cluster.global_score else None,
        global_df=cluster.global_df,
        global_score=cluster.global_score,
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
    """Список сущностей (кластеров) по теме."""
    try:
        tid = uuid.UUID(theme_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат theme_id (ожидается UUID)",
        )

    await _ensure_theme_access(db, theme_id=tid, user_id=current_user.id)

    stmt = (
        select(Cluster)
        .where(Cluster.theme_id == tid)
        .order_by(Cluster.global_score.desc().nulls_last(), Cluster.global_df.desc())
    )
    result = await db.execute(stmt)
    clusters = list(result.scalars().all())
    items = [_cluster_to_entity_out(c) for c in clusters]
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
    stop_after_first_prompt: bool = Query(
        False,
        description="Для отладки: только первый промпт к ИИ, ответ в лог, в БД не писать.",
    ),
) -> EntityListOut:
    """
    Запустить извлечение сущностей (v2: атомы/кластеры/аббревиатуры) из квантов по теме.
    Обрабатывается один квант с entity_extraction_version = null; подробный вывод — в logs/events_llm_debug.log.
    При stop_after_first_prompt=true — только один запрос к ИИ, ответ в лог, квант не помечается обработанным.
    """
    try:
        tid = uuid.UUID(theme_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат theme_id (ожидается UUID)",
        )

    await _ensure_theme_access(db, theme_id=tid, user_id=current_user.id)

    logger.info(
        "entities/extract: starting AtomsClustersExtractor (1 quantum, debug_log=True, stop_after_first_prompt=%s) theme_id=%s",
        stop_after_first_prompt,
        tid,
    )
    extractor = AtomsClustersExtractor(llm_service=llm_service, prompt_service=prompt_service)
    n = await extractor.process_next_batch(
        db,
        theme_id=tid,
        batch_size=1,
        debug_log=True,
        stop_after_first_prompt=stop_after_first_prompt,
    )
    logger.info("entities/extract: processed %s quantum(s)", n)

    stmt = (
        select(Cluster)
        .where(Cluster.theme_id == tid)
        .order_by(Cluster.global_score.desc().nulls_last(), Cluster.global_df.desc())
    )
    result = await db.execute(stmt)
    clusters = list(result.scalars().all())
    items = [_cluster_to_entity_out(c) for c in clusters]
    return EntityListOut(items=items, total=len(items))
