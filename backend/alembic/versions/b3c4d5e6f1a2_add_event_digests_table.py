"""Add event_digests table

Revision ID: b3c4d5e6f1a2
Revises: a2b3c4d5e6f1
Create Date: 2026-01-30

В каких дайджестах фигурировало событие (и в каком качестве).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b3c4d5e6f1a2"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_digests",
        sa.Column(
            "event_id",
            sa.UUID(),
            nullable=False,
            comment="Ссылка на событие.",
        ),
        sa.Column(
            "digest_id",
            sa.UUID(),
            nullable=False,
            comment="Ссылка на дайджест.",
        ),
        sa.Column(
            "role",
            sa.Text(),
            nullable=False,
            server_default="mentioned",
            comment="Роль события в дайджесте: mentioned / key / highlight / other.",
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Когда событие было связано с дайджестом.",
        ),
        sa.Column(
            "rank",
            sa.Integer(),
            nullable=True,
            comment="Порядок/ранг события внутри дайджеста (если нужно).",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["digest_id"],
            ["digests.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", "digest_id"),
        comment="В каких дайджестах фигурировало событие (и в каком качестве)",
    )

    op.create_index(
        op.f("ix_event_digests_digest_id"),
        "event_digests",
        ["digest_id"],
        unique=False,
    )
    op.create_index(
        "ix_event_digests_digest_id_role",
        "event_digests",
        ["digest_id", "role"],
        unique=False,
    )
    op.create_index(
        "ix_event_digests_digest_id_rank",
        "event_digests",
        ["digest_id", "rank"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_event_digests_digest_id_rank",
        table_name="event_digests",
    )
    op.drop_index(
        "ix_event_digests_digest_id_role",
        table_name="event_digests",
    )
    op.drop_index(op.f("ix_event_digests_digest_id"), table_name="event_digests")
    op.drop_table("event_digests")
