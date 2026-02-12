"""Add query_model to theme_search_queries and drop legacy columns.

Revision ID: fa1b2c3d4e5
Revises: a1b2c3d4e5f6
Create Date: 2026-02-10

Переход на структурную модель запроса (query_model) без query_text/must_have/exclude.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "fa1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Добавляем новый обязательный столбец query_model (данных нет, можно NOT NULL).
    op.add_column(
        "theme_search_queries",
        sa.Column(
            "query_model",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Структурная модель поискового запроса",
        ),
    )

    # Удаляем legacy-поля, которые больше не используются.
    op.drop_column("theme_search_queries", "query_text")
    op.drop_column("theme_search_queries", "must_have")
    op.drop_column("theme_search_queries", "exclude")


def downgrade() -> None:
    """Downgrade schema."""
    # Возвращаем legacy-поля в исходном виде.
    op.add_column(
        "theme_search_queries",
        sa.Column(
            "exclude",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Список слов/фраз-исключений (опционально)",
        ),
    )
    op.add_column(
        "theme_search_queries",
        sa.Column(
            "must_have",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Список обязательных слов/фраз (опционально)",
        ),
    )
    op.add_column(
        "theme_search_queries",
        sa.Column(
            "query_text",
            sa.Text(),
            nullable=False,
            comment="Явный текст поискового запроса, задаваемый пользователем",
        ),
    )

    # Удаляем query_model.
    op.drop_column("theme_search_queries", "query_model")

