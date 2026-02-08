"""Add theme_search_queries table

Revision ID: a1b2c3d4e5f6
Revises: e6f1a2b3c4d5
Create Date: 2026-02-06

Явные поисковые запросы по теме — источник истины для планировщика поиска.
Ключевые слова (keywords), must_have, exclude из themes — лишь подсказки для пользователя,
планировщик использует только theme_search_queries.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "e6f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "theme_search_queries",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор поискового запроса",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=False,
            comment="Ссылка на тему, к которой относится запрос",
        ),
        sa.Column(
            "order_index",
            sa.Integer(),
            nullable=False,
            comment="Порядок выполнения запроса внутри темы",
        ),
        sa.Column(
            "title",
            sa.Text(),
            nullable=True,
            comment="Короткое название запроса для UI",
        ),
        sa.Column(
            "query_text",
            sa.Text(),
            nullable=False,
            comment="Явный текст поискового запроса, задаваемый пользователем",
        ),
        sa.Column(
            "must_have",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Список обязательных слов/фраз (опционально)",
        ),
        sa.Column(
            "exclude",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Список слов/фраз-исключений (опционально)",
        ),
        sa.Column(
            "time_window_days",
            sa.Integer(),
            nullable=True,
            comment="Ограничение по давности источников в днях, NULL = по умолчанию",
        ),
        sa.Column(
            "target_links",
            sa.Integer(),
            nullable=True,
            comment="Максимум ссылок с этого запроса, NULL = без ограничения",
        ),
        sa.Column(
            "enabled_retrievers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Ограничение retriever'ов для этого запроса (опционально)",
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Включён ли запрос в план поиска",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата создания",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата последнего изменения",
        ),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment=(
            "Явные поисковые запросы по теме — источник истины для планировщика поиска. "
            "Keywords, must_have, exclude из themes — лишь подсказки для пользователя."
        ),
    )

    op.create_index(
        "ix_theme_search_queries_theme_id_order_index",
        "theme_search_queries",
        ["theme_id", "order_index"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_theme_search_queries_theme_id_order_index",
        table_name="theme_search_queries",
    )
    op.drop_table("theme_search_queries")
