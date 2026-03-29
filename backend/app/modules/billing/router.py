"""Роутер биллинга: детальные события по теме."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.router import get_current_user
from app.modules.billing.model import BillingUsageEvent
from app.modules.billing.schemas import BillingUsageEventOut, BillingUsageEventsListOut
from app.modules.theme.service import get_theme_with_queries
from app.modules.user.model import User

router = APIRouter(prefix="/api/v1/themes", tags=["billing"])


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


def _row_to_out(row: BillingUsageEvent) -> BillingUsageEventOut:
    return BillingUsageEventOut(
        id=str(row.id),
        theme_id=str(row.theme_id),
        occurred_at=row.occurred_at,
        service_type=row.service_type,
        task_type=row.task_type,
        service_impl=row.service_impl,
        quantity=row.quantity,
        quantity_unit_code=row.quantity_unit_code,
        extra=row.extra,
        cost_tariff_currency=row.cost_tariff_currency,
        tariff_currency_code=row.tariff_currency_code,
        cost_display_currency=row.cost_display_currency,
        display_currency_code=row.display_currency_code,
        deleted=bool(row.deleted),
    )


@router.get(
    "/{theme_id}/billing/usage-events",
    response_model=BillingUsageEventsListOut,
)
async def list_billing_usage_events(
    theme_id: str,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BillingUsageEventsListOut:
    """
    Детальные события биллинга по теме (только несвёрнутые: deleted=false).
    """
    try:
        tid = uuid.UUID(theme_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат theme_id (ожидается UUID)",
        ) from None

    await _ensure_theme_access(db, theme_id=tid, user_id=current_user.id)

    q = (
        select(BillingUsageEvent)
        .where(BillingUsageEvent.theme_id == tid)
        .where(BillingUsageEvent.deleted.is_(False))
    )

    total_q = (
        select(func.count())
        .select_from(BillingUsageEvent)
        .where(BillingUsageEvent.theme_id == tid)
        .where(BillingUsageEvent.deleted.is_(False))
    )

    # Порядок: последние события сверху
    q = q.order_by(BillingUsageEvent.occurred_at.desc()).limit(limit).offset(offset)

    res = await db.execute(q)
    items = list(res.scalars().all())

    total_res = await db.execute(total_q)
    total = int(total_res.scalar_one() or 0)

    return BillingUsageEventsListOut(items=[_row_to_out(r) for r in items], total=total)

