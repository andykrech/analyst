"""billing_usage_events.service_impl; daily summary key + COALESCE(service_impl); billing_daily_services_tasks.

Revision ID: p3q4r5s6t7u8
Revises: n6m5l4k3j2h1
Create Date: 2026-03-29

- Детальные события: service_impl (nullable) для свёртки.
- Сводка: service_impl (nullable); уникальный индекс с COALESCE(service_impl, '') (PostgreSQL 10+).
- Агрегат по service_type + task_type в валюте отображения.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "p3q4r5s6t7u8"
down_revision: Union[str, Sequence[str], None] = "n6m5l4k3j2h1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "billing_usage_events",
        sa.Column("service_impl", sa.Text(), nullable=True, comment="Реализация тарифа (совпадает с billing_tariffs.service_impl)."),
    )

    op.drop_constraint(
        "uq_billing_daily_summaries_slice",
        "billing_daily_summaries",
        type_="unique",
    )
    op.add_column(
        "billing_daily_summaries",
        sa.Column("service_impl", sa.Text(), nullable=True, comment="Реализация; NULL и '' объединяются в уникальном ключе через COALESCE."),
    )

    op.execute(
        """
        CREATE UNIQUE INDEX uq_billing_daily_summaries_slice
        ON billing_daily_summaries (
            theme_id,
            summary_local_date,
            service_type,
            task_type,
            quantity_unit_code,
            tariff_currency_code,
            (COALESCE(service_impl, ''))
        )
        """
    )

    op.create_table(
        "billing_daily_services_tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("theme_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "summary_local_date",
            sa.Date(),
            nullable=False,
            comment="Календарная дата в timezone темы (как в billing_daily_summaries).",
        ),
        sa.Column("service_type", sa.Text(), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("sum_cost_display_currency", sa.Numeric(20, 8), nullable=False),
        sa.Column("display_currency_code", sa.String(length=3), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "theme_id",
            "summary_local_date",
            "service_type",
            "task_type",
            "display_currency_code",
            name="uq_billing_daily_services_tasks_slice",
        ),
        comment="Сводка по типу сервиса и задаче за локальный день темы; только суммы в валюте отображения.",
    )
    op.create_index(
        "ix_billing_daily_services_tasks_theme_date",
        "billing_daily_services_tasks",
        ["theme_id", "summary_local_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_billing_daily_services_tasks_theme_date", table_name="billing_daily_services_tasks")
    op.drop_table("billing_daily_services_tasks")

    op.execute("DROP INDEX IF EXISTS uq_billing_daily_summaries_slice")
    op.drop_column("billing_daily_summaries", "service_impl")
    op.create_unique_constraint(
        "uq_billing_daily_summaries_slice",
        "billing_daily_summaries",
        [
            "theme_id",
            "summary_local_date",
            "service_type",
            "task_type",
            "quantity_unit_code",
            "tariff_currency_code",
        ],
    )

    op.drop_column("billing_usage_events", "service_impl")
