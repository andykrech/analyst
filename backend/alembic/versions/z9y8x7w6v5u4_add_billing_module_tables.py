"""Биллинг: тарифы, курсы, детальные события, дневные сводки; поля темы в theme_stats.

Revision ID: z9y8x7w6v5u4
Revises: w8x9y0z1a2b3
Create Date: 2026-03-22

Инфраструктура модуля billing + billing_timezone и billing_display_currency в theme_stats.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "z9y8x7w6v5u4"
down_revision: Union[str, Sequence[str], None] = "w8x9y0z1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "billing_tariffs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Идентификатор тарифа.",
        ),
        sa.Column(
            "service_type",
            sa.Text(),
            nullable=False,
            comment="Тип сервиса (например llm, embedding, translator).",
        ),
        sa.Column(
            "service_impl",
            sa.Text(),
            nullable=False,
            comment="Реализация: модель ИИ, имя переводчика, провайдер и т.п.",
        ),
        sa.Column(
            "unit_code",
            sa.Text(),
            nullable=False,
            comment="Код единицы объёма (например input_tokens, chars, requests).",
        ),
        sa.Column(
            "units_per_price",
            sa.Numeric(30, 6),
            nullable=False,
            comment="Сколько единиц объёма покрывает поле price (например 1_000_000 токенов).",
        ),
        sa.Column(
            "price",
            sa.Numeric(20, 8),
            nullable=False,
            comment="Стоимость пакета units_per_price единиц в валюте currency_code.",
        ),
        sa.Column(
            "currency_code",
            sa.String(length=3),
            nullable=False,
            comment="Код валюты цены (ISO 4217).",
        ),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Момент начала действия тарифа.",
        ),
        sa.Column(
            "valid_until",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Момент окончания (NULL — тариф текущий).",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Время создания записи.",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Тарифы на внешние сервисы с интервалом действия (valid_until NULL = текущий).",
    )
    op.create_index(
        "ix_billing_tariffs_service_impl_unit_valid",
        "billing_tariffs",
        ["service_type", "service_impl", "unit_code", "valid_from"],
        unique=False,
    )

    op.create_table(
        "billing_exchange_rates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Идентификатор курса.",
        ),
        sa.Column(
            "rate_date",
            sa.Date(),
            nullable=False,
            comment="Дата котировки (календарный день).",
        ),
        sa.Column(
            "from_currency",
            sa.String(length=3),
            nullable=False,
            comment="Исходная валюта (ISO 4217).",
        ),
        sa.Column(
            "to_currency",
            sa.String(length=3),
            nullable=False,
            comment="Целевая валюта (ISO 4217).",
        ),
        sa.Column(
            "rate",
            sa.Numeric(24, 12),
            nullable=False,
            comment="Сколько единиц to_currency за 1 from_currency.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Время занесения курса.",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "rate_date",
            "from_currency",
            "to_currency",
            name="uq_billing_exchange_rates_date_pair",
        ),
        comment="Курсы валют для пересчёта стоимости в валюту отображения темы.",
    )
    op.create_index(
        "ix_billing_exchange_rates_date",
        "billing_exchange_rates",
        ["rate_date"],
        unique=False,
    )

    op.create_table(
        "billing_usage_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Идентификатор события.",
        ),
        sa.Column(
            "theme_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Тема, к которой относится расход.",
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Момент события (UTC).",
        ),
        sa.Column(
            "service_type",
            sa.Text(),
            nullable=False,
            comment="Тип сервиса.",
        ),
        sa.Column(
            "task_type",
            sa.Text(),
            nullable=False,
            comment="Тип задачи продукта.",
        ),
        sa.Column(
            "quantity",
            sa.Numeric(24, 6),
            nullable=False,
            comment="Объём расхода в единицах quantity_unit_code.",
        ),
        sa.Column(
            "quantity_unit_code",
            sa.Text(),
            nullable=False,
            comment="Код основного параметра объёма (согласован с тарифами).",
        ),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Дополнительные параметры (модель, trace_id и т.д.).",
        ),
        sa.Column(
            "cost_tariff_currency",
            sa.Numeric(20, 8),
            nullable=False,
            comment="Стоимость в валюте тарифа на момент записи.",
        ),
        sa.Column(
            "tariff_currency_code",
            sa.String(length=3),
            nullable=False,
            comment="Валюта тарифа (ISO 4217).",
        ),
        sa.Column(
            "cost_display_currency",
            sa.Numeric(20, 8),
            nullable=False,
            comment="Стоимость в валюте отображения темы на момент записи.",
        ),
        sa.Column(
            "display_currency_code",
            sa.String(length=3),
            nullable=False,
            comment="Валюта отображения темы (ISO 4217).",
        ),
        sa.Column(
            "tariff_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Применённый тариф (для аудита).",
        ),
        sa.Column(
            "exchange_rate_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Применённый курс (для аудита).",
        ),
        sa.Column(
            "deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment=(
                "True — строка учтена в дневной сводке и исключена из активного детального отчёта."
            ),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Время вставки записи.",
        ),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tariff_id"], ["billing_tariffs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["exchange_rate_id"],
            ["billing_exchange_rates.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Детальный журнал биллинга по темам; deleted — свёрнуто в дневную сводку.",
    )
    op.create_index(
        op.f("ix_billing_usage_events_theme_id"),
        "billing_usage_events",
        ["theme_id"],
        unique=False,
    )
    op.create_index(
        "ix_billing_usage_theme_occurred",
        "billing_usage_events",
        ["theme_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_billing_usage_theme_deleted_occurred",
        "billing_usage_events",
        ["theme_id", "deleted", "occurred_at"],
        unique=False,
    )

    op.create_table(
        "billing_daily_summaries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Идентификатор строки сводки.",
        ),
        sa.Column(
            "theme_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Тема.",
        ),
        sa.Column(
            "summary_local_date",
            sa.Date(),
            nullable=False,
            comment="Календарная дата в timezone темы.",
        ),
        sa.Column(
            "service_type",
            sa.Text(),
            nullable=False,
            comment="Тип сервиса.",
        ),
        sa.Column(
            "task_type",
            sa.Text(),
            nullable=False,
            comment="Тип задачи.",
        ),
        sa.Column(
            "quantity_unit_code",
            sa.Text(),
            nullable=False,
            comment="Код единицы объёма для суммы quantity.",
        ),
        sa.Column(
            "tariff_currency_code",
            sa.String(length=3),
            nullable=False,
            comment="Валюта тарифа для суммы cost_tariff_currency.",
        ),
        sa.Column(
            "sum_quantity",
            sa.Numeric(24, 6),
            nullable=False,
            comment="Сумма объёмов за день.",
        ),
        sa.Column(
            "sum_cost_tariff_currency",
            sa.Numeric(20, 8),
            nullable=False,
            comment="Сумма стоимостей в валюте тарифа.",
        ),
        sa.Column(
            "sum_cost_display_currency",
            sa.Numeric(20, 8),
            nullable=False,
            comment="Сумма стоимостей в валюте отображения темы.",
        ),
        sa.Column(
            "display_currency_code",
            sa.String(length=3),
            nullable=False,
            comment="Валюта отображения (для sum_cost_display_currency).",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Время последнего обновления агрегата.",
        ),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "theme_id",
            "summary_local_date",
            "service_type",
            "task_type",
            "quantity_unit_code",
            "tariff_currency_code",
            name="uq_billing_daily_summaries_slice",
        ),
        comment=(
            "Агрегаты по теме за локальный день; ключ включает валюту тарифа и код единицы объёма."
        ),
    )
    op.create_index(
        "ix_billing_daily_theme_date",
        "billing_daily_summaries",
        ["theme_id", "summary_local_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_daily_summaries_theme_id"),
        "billing_daily_summaries",
        ["theme_id"],
        unique=False,
    )

    op.add_column(
        "theme_stats",
        sa.Column(
            "billing_timezone",
            sa.Text(),
            server_default=sa.text("'Asia/Krasnoyarsk'"),
            nullable=False,
            comment=(
                "IANA timezone для границы календарного дня биллинга "
                "(по умолчанию UTC+7, на 4 ч вперёд от Москвы)."
            ),
        ),
    )
    op.add_column(
        "theme_stats",
        sa.Column(
            "billing_display_currency",
            sa.String(length=3),
            server_default=sa.text("'RUB'"),
            nullable=False,
            comment="Валюта отображения расходов по теме (ISO 4217).",
        ),
    )


def downgrade() -> None:
    op.drop_column("theme_stats", "billing_display_currency")
    op.drop_column("theme_stats", "billing_timezone")

    op.drop_index(op.f("ix_billing_daily_summaries_theme_id"), table_name="billing_daily_summaries")
    op.drop_index("ix_billing_daily_theme_date", table_name="billing_daily_summaries")
    op.drop_table("billing_daily_summaries")

    op.drop_index("ix_billing_usage_theme_deleted_occurred", table_name="billing_usage_events")
    op.drop_index("ix_billing_usage_theme_occurred", table_name="billing_usage_events")
    op.drop_index(op.f("ix_billing_usage_events_theme_id"), table_name="billing_usage_events")
    op.drop_table("billing_usage_events")

    op.drop_index("ix_billing_exchange_rates_date", table_name="billing_exchange_rates")
    op.drop_table("billing_exchange_rates")

    op.drop_index("ix_billing_tariffs_service_impl_unit_valid", table_name="billing_tariffs")
    op.drop_table("billing_tariffs")
