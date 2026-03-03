"""Add is_name_translated column to entities.

Revision ID: k6l7m8n9o0p1
Revises: j5k6l7m8n9o0
Create Date: 2026-03-03

Добавляет поле is_name_translated в таблицу entities.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k6l7m8n9o0p1"
down_revision: Union[str, Sequence[str], None] = "j5k6l7m8n9o0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "entities",
        sa.Column(
            "is_name_translated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="Флаг, было ли переведено наименование сущности.",
        ),
    )


def downgrade() -> None:
    op.drop_column("entities", "is_name_translated")
