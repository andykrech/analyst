"""Theme: language -> languages (JSONB NOT NULL)

Revision ID: f5a2b3c4d5e6
Revises: e4f8a1b2c3d4
Create Date: 2026-01-30

Переименование и смена типа: language (TEXT NULL) -> languages (JSONB NOT NULL, default []).
Существующие значения переносятся в массив из одного элемента.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f5a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e4f8a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "themes",
        sa.Column(
            "languages",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Список языков источников и поиска (например, [\"ru\", \"en\"])",
        ),
    )
    # Переносим старые значения: одно значение language -> массив [language]
    op.execute(
        sa.text(
            "UPDATE themes SET languages = jsonb_build_array(language) "
            "WHERE language IS NOT NULL AND language != ''"
        )
    )
    op.drop_column("themes", "language")


def downgrade() -> None:
    op.add_column(
        "themes",
        sa.Column(
            "language",
            sa.Text(),
            nullable=True,
            comment="Язык источников и поиска (например, ru, en)",
        ),
    )
    # Обратный перенос: берём первый элемент массива
    op.execute(
        sa.text(
            "UPDATE themes SET language = languages->>0 "
            "WHERE jsonb_array_length(languages) > 0"
        )
    )
    op.drop_column("themes", "languages")
