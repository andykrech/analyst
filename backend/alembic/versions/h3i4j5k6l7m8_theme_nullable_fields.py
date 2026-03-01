"""Make theme keywords, must_have, exclude, languages nullable

Revision ID: h3i4j5k6l7m8
Revises: g2h3i4j5k6l7
Create Date: 2026-02-27

Все поля темы кроме title и description делаем nullable для поддержки
минимального создания темы (только название, описание, языки).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "h3i4j5k6l7m8"
down_revision: Union[str, Sequence[str], None] = "g2h3i4j5k6l7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # keywords, must_have, exclude, languages — nullable, без server_default
    op.alter_column(
        "themes",
        "keywords",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "themes",
        "must_have",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "themes",
        "exclude",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "themes",
        "languages",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    # Обратно: NOT NULL и server_default
    op.execute(
        sa.text(
            "UPDATE themes SET keywords = '[]'::jsonb WHERE keywords IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE themes SET must_have = '[]'::jsonb WHERE must_have IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE themes SET exclude = '[]'::jsonb WHERE exclude IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE themes SET languages = '[]'::jsonb WHERE languages IS NULL"
        )
    )
    op.alter_column(
        "themes",
        "keywords",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )
    op.alter_column(
        "themes",
        "must_have",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )
    op.alter_column(
        "themes",
        "exclude",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )
    op.alter_column(
        "themes",
        "languages",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )
