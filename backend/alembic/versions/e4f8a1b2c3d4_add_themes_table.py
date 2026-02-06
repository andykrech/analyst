"""Add themes table

Revision ID: e4f8a1b2c3d4
Revises: b78f77c3c96f
Create Date: 2026-01-30

Таблица пользовательских тем аналитического сервиса.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e4f8a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "b78f77c3c96f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "themes",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            comment="Уникальный идентификатор темы",
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            nullable=False,
            comment="Пользователь, которому принадлежит тема",
        ),
        sa.Column(
            "title",
            sa.Text(),
            nullable=False,
            comment="Краткое название темы, отображаемое в интерфейсе",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
            comment="Исходное текстовое описание темы, сформулированное пользователем",
        ),
        sa.Column(
            "keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Список ключевых слов и фраз для поиска информации по теме",
        ),
        sa.Column(
            "must_have",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Обязательные слова или сущности в найденных материалах",
        ),
        sa.Column(
            "exclude",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Минус-слова и фразы, исключаемые из поиска",
        ),
        sa.Column(
            "language",
            sa.Text(),
            nullable=True,
            comment="Язык источников и поиска (например, ru, en)",
        ),
        sa.Column(
            "region",
            sa.Text(),
            nullable=True,
            comment="Регион или географическая область интереса (например, RU, EU, US)",
        ),
        sa.Column(
            "update_interval",
            sa.Text(),
            nullable=False,
            server_default="weekly",
            comment="Периодичность обновления темы (daily / 3d / weekly)",
        ),
        sa.Column(
            "last_run_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Дата и время последнего запуска обновления темы",
        ),
        sa.Column(
            "next_run_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Дата и время следующего планируемого обновления темы",
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="draft",
            comment="Текущее состояние темы (draft / active / paused / archived)",
        ),
        sa.Column(
            "backfill_status",
            sa.Text(),
            nullable=False,
            server_default="not_started",
            comment="Статус первичного исторического сбора (not_started / running / done / failed)",
        ),
        sa.Column(
            "backfill_horizon_months",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("12"),
            comment="Глубина первичного анализа в месяцах (например, 3 / 6 / 12)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время создания темы",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время последнего изменения темы",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Дата и время мягкого удаления темы (soft delete)",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Пользовательские темы аналитического сервиса",
    )

    # Индекс для выборки тем пользователя
    op.create_index(
        op.f("ix_themes_user_id"),
        "themes",
        ["user_id"],
        unique=False,
    )
    # Индекс для планировщика обновлений (выбор тем по next_run_at)
    op.create_index(
        op.f("ix_themes_next_run_at"),
        "themes",
        ["next_run_at"],
        unique=False,
    )
    # Частичный индекс для soft-delete: активные темы пользователя (deleted_at IS NULL)
    op.create_index(
        "ix_themes_user_id_not_deleted",
        "themes",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # Частичный индекс для планировщика: следующие запуски только по неудалённым темам
    op.create_index(
        "ix_themes_next_run_at_not_deleted",
        "themes",
        ["next_run_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_themes_next_run_at_not_deleted", table_name="themes")
    op.drop_index("ix_themes_user_id_not_deleted", table_name="themes")
    op.drop_index(op.f("ix_themes_next_run_at"), table_name="themes")
    op.drop_index(op.f("ix_themes_user_id"), table_name="themes")
    op.drop_table("themes")
