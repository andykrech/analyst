"""Add search_runs table

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-01-30

Журнал запусков обработки темы (backfill, update, fetch_content и т.п.).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "a6b7c8d9e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "search_runs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор запуска обработки темы.",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор темы (themes.id), для которой выполняется запуск.",
        ),
        sa.Column(
            "run_type",
            sa.Text(),
            nullable=False,
            comment="Тип запуска: backfill / update / rebuild_overview / fetch_content / rerank_sources / other.",
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="queued",
            comment="Статус запуска: queued / running / done / failed / canceled.",
        ),
        sa.Column(
            "queued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Когда запуск был поставлен в очередь.",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Когда запуск фактически начался.",
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Когда запуск завершился (успех/ошибка/отмена).",
        ),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Параметры запуска (языки, период, лимиты, настройки провайдера поиска и т.п.).",
        ),
        sa.Column(
            "progress",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Текущий прогресс выполнения (done_periods/total_periods, этап пайплайна).",
        ),
        sa.Column(
            "stats",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Итоговая статистика запуска (ссылок найдено, дайджестов создано и т.п.).",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="Краткое сообщение об ошибке (если запуск завершился с failed).",
        ),
        sa.Column(
            "error_details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Структурированные детали ошибки (stack trace, коды провайдера, контекст шагов).",
        ),
        sa.Column(
            "logs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Опциональные структурированные логи по шагам (для отладки); в MVP может оставаться пустым.",
        ),
        sa.Column(
            "period_start",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Начало периода, который покрывает запуск (например месяц при backfill или интервал обновления).",
        ),
        sa.Column(
            "period_end",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Конец периода, который покрывает запуск.",
        ),
        sa.Column(
            "idempotency_key",
            sa.Text(),
            nullable=True,
            comment="Ключ идемпотентности для защиты от двойного запуска (например theme_id+run_type+period).",
        ),
        sa.Column(
            "triggered_by",
            sa.Text(),
            nullable=False,
            server_default="system",
            comment="Кем запущено: system / user / admin.",
        ),
        sa.Column(
            "trigger_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Контекст запуска (user_action, причина планировщика, параметры UI).",
        ),
        sa.Column(
            "attempt",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Номер попытки выполнения (1 — первый запуск, 2+ — ретраи).",
        ),
        sa.Column(
            "parent_run_id",
            sa.UUID(),
            nullable=True,
            comment="Ссылка на исходный запуск (если это повтор/ретрай).",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время создания записи запуска.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время последнего изменения записи запуска.",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Мягкое удаление записи запуска (обычно не нужно, но заложить).",
        ),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Журнал запусков обработки темы (backfill, update, fetch_content и т.п.)",
    )

    op.create_index(
        op.f("ix_search_runs_theme_id"),
        "search_runs",
        ["theme_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_runs_parent_run_id"),
        "search_runs",
        ["parent_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_runs_idempotency_key"),
        "search_runs",
        ["idempotency_key"],
        unique=False,
    )
    op.create_index(
        "ix_search_runs_theme_id_queued_at",
        "search_runs",
        ["theme_id", "queued_at"],
        unique=False,
        postgresql_ops={"queued_at": "DESC"},
    )
    op.create_index(
        "ix_search_runs_theme_id_status_queued_at",
        "search_runs",
        ["theme_id", "status", "queued_at"],
        unique=False,
        postgresql_ops={"queued_at": "DESC"},
    )
    op.create_index(
        "ix_search_runs_theme_id_run_type_queued_at",
        "search_runs",
        ["theme_id", "run_type", "queued_at"],
        unique=False,
        postgresql_ops={"queued_at": "DESC"},
    )
    op.create_index(
        "ix_search_runs_theme_id_active",
        "search_runs",
        ["theme_id", "status"],
        unique=False,
        postgresql_where=sa.text(
            "status IN ('queued', 'running') AND deleted_at IS NULL"
        ),
    )
    op.create_index(
        "uq_search_runs_idempotency_key",
        "search_runs",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_search_runs_idempotency_key",
        table_name="search_runs",
    )
    op.drop_index(
        "ix_search_runs_theme_id_active",
        table_name="search_runs",
    )
    op.drop_index(
        "ix_search_runs_theme_id_run_type_queued_at",
        table_name="search_runs",
    )
    op.drop_index(
        "ix_search_runs_theme_id_status_queued_at",
        table_name="search_runs",
    )
    op.drop_index(
        "ix_search_runs_theme_id_queued_at",
        table_name="search_runs",
    )
    op.drop_index(op.f("ix_search_runs_idempotency_key"), table_name="search_runs")
    op.drop_index(op.f("ix_search_runs_parent_run_id"), table_name="search_runs")
    op.drop_index(op.f("ix_search_runs_theme_id"), table_name="search_runs")
    op.drop_table("search_runs")
