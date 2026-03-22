"""API ландшафта темы."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.integrations.llm import LLMService, get_llm_service
from app.integrations.prompts import PromptService, get_prompt_service
from app.modules.auth.router import get_current_user
from app.modules.landscape.builder import LandscapeBuilder
from app.modules.landscape.exceptions import LandscapePromptTooLargeError
from app.modules.landscape.model import Landscape
from app.modules.landscape.schemas import LandscapeOut
from app.modules.theme.service import get_theme_with_queries
from app.modules.user.model import User

router = APIRouter(prefix="/api/v1", tags=["landscapes"])


async def _ensure_theme_access(
    db: AsyncSession,
    *,
    theme_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    theme, _ = await get_theme_with_queries(db, theme_id, user_id)
    if not theme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тема не найдена или недоступна",
        )


@router.get(
    "/themes/{theme_id}/landscape",
    response_model=LandscapeOut,
)
async def get_latest_landscape(
    theme_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LandscapeOut:
    """Последняя сохранённая версия ландшафта темы."""
    try:
        tid = uuid.UUID(theme_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат theme_id (ожидается UUID)",
        )
    await _ensure_theme_access(db, theme_id=tid, user_id=current_user.id)

    stmt = (
        select(Landscape)
        .where(Landscape.theme_id == tid)
        .order_by(Landscape.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ландшафт для этой темы ещё не строился",
        )
    return LandscapeOut(
        id=row.id,
        theme_id=row.theme_id,
        text=row.text,
        created_at=row.created_at,
    )


@router.post(
    "/themes/{theme_id}/landscape/build",
    response_model=LandscapeOut,
)
async def build_landscape(
    theme_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service),
    prompt_service: PromptService = Depends(get_prompt_service),
    settings: Settings = Depends(get_settings),
) -> LandscapeOut:
    """Построить новую версию ландшафта (LLM) и сохранить в историю."""
    try:
        tid = uuid.UUID(theme_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат theme_id (ожидается UUID)",
        )
    await _ensure_theme_access(db, theme_id=tid, user_id=current_user.id)

    builder = LandscapeBuilder(
        llm_service=llm_service,
        prompt_service=prompt_service,
        settings=settings,
    )
    try:
        row = await builder.build(db, theme_id=tid, user_id=current_user.id)
    except LandscapePromptTooLargeError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"{e} (символов в промпте: {e.char_count}, лимит: {e.limit})"
            ),
        )
    except ValueError as e:
        code = str(e)
        if code == "theme_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Тема не найдена или недоступна",
            )
        if code == "empty_llm_response":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Пустой ответ модели",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка построения ландшафта",
        )

    return LandscapeOut(
        id=row.id,
        theme_id=row.theme_id,
        text=row.text,
        created_at=row.created_at,
    )
