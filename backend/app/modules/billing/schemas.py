"""Схемы API для биллинга (детальные события)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


class BillingUsageEventOut(BaseModel):
    id: str
    theme_id: str
    occurred_at: datetime

    service_type: str
    task_type: str
    service_impl: Optional[str] = None

    quantity: Decimal
    quantity_unit_code: str
    extra: Any | None = None

    cost_tariff_currency: Decimal
    tariff_currency_code: str
    cost_display_currency: Decimal
    display_currency_code: str

    deleted: bool


class BillingUsageEventsListOut(BaseModel):
    items: list[BillingUsageEventOut] = Field(default_factory=list)
    total: int = Field(..., ge=0)

