"""Add schema JSONB column to event_plots

Revision ID: q3r4s5t6u8v9
Revises: p2q3r4s5t6u7
Create Date: 2026-03-06

Добавляет поле schema в таблицу event_plots для хранения схемы сюжета.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "q3r4s5t6u8v9"
down_revision: Union[str, Sequence[str], None] = "p2q3r4s5t6u7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "event_plots",
        sa.Column(
            "schema",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment=(
                "Схема сюжета с определением возможных ролей, обязательных ролей, "
                "ролей, для которых возможны атрибуты."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("event_plots", "schema")

