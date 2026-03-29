"""SQLAlchemy-модели биллинга."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Денежные суммы и курсы: запас по точности для промежуточных расчётов
_NUMERIC_MONEY = Numeric(20, 8)
_NUMERIC_QUANTITY = Numeric(24, 6)
_NUMERIC_UNITS_PER_PRICE = Numeric(30, 6)
_NUMERIC_EXCHANGE_RATE = Numeric(24, 12)


class BillingTariff(Base):
    """Тариф: цена за пакет единиц для связки тип сервиса + реализация + код единицы."""

    __tablename__ = "billing_tariffs"
    __table_args__ = (
        Index(
            "ix_billing_tariffs_service_impl_unit_valid",
            "service_type",
            "service_impl",
            "unit_code",
            "valid_from",
        ),
        {"comment": "Тарифы на внешние сервисы с интервалом действия (valid_until NULL = текущий)."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Идентификатор тарифа.",
    )
    service_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Тип сервиса (например llm, embedding, translator).",
    )
    service_impl: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Реализация: модель ИИ, имя переводчика, провайдер и т.п.",
    )
    unit_code: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Код единицы объёма (например input_tokens, chars, requests).",
    )
    units_per_price: Mapped[Decimal] = mapped_column(
        _NUMERIC_UNITS_PER_PRICE,
        nullable=False,
        comment="Сколько единиц объёма покрывает поле price (например 1_000_000 токенов).",
    )
    price: Mapped[Decimal] = mapped_column(
        _NUMERIC_MONEY,
        nullable=False,
        comment="Стоимость пакета units_per_price единиц в валюте currency_code.",
    )
    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        comment="Код валюты цены (ISO 4217).",
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Момент начала действия тарифа.",
    )
    valid_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Момент окончания (NULL — тариф текущий).",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Время создания записи.",
    )


class BillingExchangeRate(Base):
    """Курс валюты на дату: сколько единиц to_currency за одну from_currency."""

    __tablename__ = "billing_exchange_rates"
    __table_args__ = (
        UniqueConstraint(
            "rate_date",
            "from_currency",
            "to_currency",
            name="uq_billing_exchange_rates_date_pair",
        ),
        Index("ix_billing_exchange_rates_date", "rate_date"),
        {"comment": "Курсы валют для пересчёта стоимости в валюту отображения темы."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Идентификатор курса.",
    )
    rate_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Дата котировки (календарный день).",
    )
    from_currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        comment="Исходная валюта (ISO 4217).",
    )
    to_currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        comment="Целевая валюта (ISO 4217).",
    )
    rate: Mapped[Decimal] = mapped_column(
        _NUMERIC_EXCHANGE_RATE,
        nullable=False,
        comment="Сколько единиц to_currency за 1 from_currency.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Время занесения курса.",
    )


class BillingUsageEvent(Base):
    """Одно событие расхода ресурсов с рассчитанными суммами на момент записи."""

    __tablename__ = "billing_usage_events"
    __table_args__ = (
        Index("ix_billing_usage_theme_occurred", "theme_id", "occurred_at"),
        Index(
            "ix_billing_usage_theme_deleted_occurred",
            "theme_id",
            "deleted",
            "occurred_at",
        ),
        {"comment": "Детальный журнал биллинга по темам; deleted — свёрнуто в дневную сводку."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Идентификатор события.",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Тема, к которой относится расход.",
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Момент события (UTC).",
    )
    service_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Тип сервиса.",
    )
    task_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Тип задачи продукта.",
    )
    service_impl: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Реализация тарифа (совпадает с billing_tariffs.service_impl).",
    )
    quantity: Mapped[Decimal] = mapped_column(
        _NUMERIC_QUANTITY,
        nullable=False,
        comment="Объём расхода в единицах quantity_unit_code.",
    )
    quantity_unit_code: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Код основного параметра объёма (согласован с тарифами).",
    )
    extra: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Дополнительные параметры (модель, trace_id и т.д.).",
    )
    cost_tariff_currency: Mapped[Decimal] = mapped_column(
        _NUMERIC_MONEY,
        nullable=False,
        comment="Стоимость в валюте тарифа на момент записи.",
    )
    tariff_currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        comment="Валюта тарифа (ISO 4217).",
    )
    cost_display_currency: Mapped[Decimal] = mapped_column(
        _NUMERIC_MONEY,
        nullable=False,
        comment="Стоимость в валюте отображения темы на момент записи.",
    )
    display_currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        comment="Валюта отображения темы (ISO 4217).",
    )
    tariff_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("billing_tariffs.id", ondelete="SET NULL"),
        nullable=True,
        comment="Применённый тариф (для аудита).",
    )
    exchange_rate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("billing_exchange_rates.id", ondelete="SET NULL"),
        nullable=True,
        comment="Применённый курс (для аудита).",
    )
    deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="True — строка учтена в дневной сводке и исключена из активного детального отчёта.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Время вставки записи.",
    )


class BillingDailySummary(Base):
    """Сводка расходов за календарный день темы (в её timezone)."""

    __tablename__ = "billing_daily_summaries"
    __table_args__ = (
        Index(
            "uq_billing_daily_summaries_slice",
            "theme_id",
            "summary_local_date",
            "service_type",
            "task_type",
            "quantity_unit_code",
            "tariff_currency_code",
            text("(COALESCE(service_impl, ''))"),
            unique=True,
        ),
        Index("ix_billing_daily_theme_date", "theme_id", "summary_local_date"),
        {
            "comment": (
                "Агрегаты по теме за локальный день; ключ включает валюту тарифа, код единицы и service_impl "
                "(NULL и пустая строка объединяются в уникальном индексе через COALESCE)."
            ),
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Идентификатор строки сводки.",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Тема.",
    )
    summary_local_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Календарная дата в timezone темы.",
    )
    service_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Тип сервиса.",
    )
    task_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Тип задачи.",
    )
    service_impl: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Реализация; NULL и '' попадают в одну корзину уникальности (см. индекс).",
    )
    quantity_unit_code: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Код единицы объёма для суммы quantity.",
    )
    tariff_currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        comment="Валюта тарифа для суммы cost_tariff_currency.",
    )
    sum_quantity: Mapped[Decimal] = mapped_column(
        _NUMERIC_QUANTITY,
        nullable=False,
        comment="Сумма объёмов за день.",
    )
    sum_cost_tariff_currency: Mapped[Decimal] = mapped_column(
        _NUMERIC_MONEY,
        nullable=False,
        comment="Сумма стоимостей в валюте тарифа.",
    )
    sum_cost_display_currency: Mapped[Decimal] = mapped_column(
        _NUMERIC_MONEY,
        nullable=False,
        comment="Сумма стоимостей в валюте отображения темы.",
    )
    display_currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        comment="Валюта отображения (для sum_cost_display_currency).",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Время последнего обновления агрегата.",
    )


class BillingDailyServicesTasks(Base):
    """Агрегат за день по паре service_type + task_type только в валюте отображения."""

    __tablename__ = "billing_daily_services_tasks"
    __table_args__ = (
        UniqueConstraint(
            "theme_id",
            "summary_local_date",
            "service_type",
            "task_type",
            "display_currency_code",
            name="uq_billing_daily_services_tasks_slice",
        ),
        Index(
            "ix_billing_daily_services_tasks_theme_date",
            "theme_id",
            "summary_local_date",
        ),
        {
            "comment": (
                "Краткая сводка по типу сервиса и задаче за локальный день темы; суммы только в display_currency."
            ),
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Тема.",
    )
    summary_local_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Календарная дата в timezone темы (как в billing_daily_summaries).",
    )
    service_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Тип сервиса.",
    )
    task_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Тип задачи.",
    )
    sum_cost_display_currency: Mapped[Decimal] = mapped_column(
        _NUMERIC_MONEY,
        nullable=False,
        comment="Сумма стоимостей в валюте отображения.",
    )
    display_currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        comment="Валюта отображения.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Время последнего обновления.",
    )
