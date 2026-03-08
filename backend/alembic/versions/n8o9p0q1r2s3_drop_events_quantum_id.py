"""Drop quantum_id from events

Revision ID: n8o9p0q1r2s3
Revises: m7n8o9p0q1r2
Create Date: 2026-03-06

Удаление поля quantum_id и связанных индексов из таблицы events.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "n8o9p0q1r2s3"
down_revision: Union[str, Sequence[str], None] = "m7n8o9p0q1r2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Сначала удаляем индексы, в которых участвует quantum_id
    op.drop_index("idx_events_theme_quantum", table_name="events")
    op.drop_index(op.f("ix_events_quantum_id"), table_name="events")
    op.drop_column("events", "quantum_id")


def downgrade() -> None:
    op.add_column(
        "events",
        sa.Column(
            "quantum_id",
            sa.UUID(),
            nullable=True,
            comment="Квант (theme_quanta.id) — доказательство в тексте; FK будет добавлен позже.",
        ),
    )
    op.create_index(op.f("ix_events_quantum_id"), "events", ["quantum_id"], unique=False)
    op.create_index(
        "idx_events_theme_quantum",
        "events",
        ["theme_id", "quantum_id"],
        unique=False,
    )
