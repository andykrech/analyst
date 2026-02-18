"""Роутер пользователя: ui_state (состояние UI)."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.router import get_current_user
from app.modules.user.model import User, UiState
from app.modules.user.schemas import UiStateGetResponse, UiStatePutRequest

router = APIRouter(prefix="/api/v1/ui-state", tags=["ui-state"])


@router.get("", response_model=UiStateGetResponse)
async def get_ui_state(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UiStateGetResponse:
    """
    Получить состояние UI текущего пользователя.
    Если записи нет — вернуть пустой state.
    """
    result = await db.execute(
        select(UiState).where(UiState.user_id == current_user.id)
    )
    row = result.scalar_one_or_none()
    if not row or not row.state_json:
        return UiStateGetResponse(state={})
    return UiStateGetResponse(state=dict(row.state_json))


@router.put("", response_model=UiStateGetResponse)
async def put_ui_state(
    body: UiStatePutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UiStateGetResponse:
    """
    Обновить состояние UI (upsert по user_id).
    Переданные поля (active_theme_id, url) мержатся в существующий state_json.
    """
    result = await db.execute(
        select(UiState).where(UiState.user_id == current_user.id)
    )
    row = result.scalar_one_or_none()

    state = dict(row.state_json) if row and row.state_json else {}
    if body.active_theme_id is not None:
        state["active_theme_id"] = body.active_theme_id
    if body.url is not None:
        state["url"] = body.url

    if row:
        row.state_json = state
        await db.flush()
        await db.refresh(row)
    else:
        new_row = UiState(
            user_id=current_user.id,
            state_json=state,
        )
        db.add(new_row)
        await db.flush()
        await db.refresh(new_row)
        row = new_row

    return UiStateGetResponse(state=dict(row.state_json))
