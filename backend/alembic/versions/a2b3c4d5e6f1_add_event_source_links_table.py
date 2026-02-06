"""Add event_source_links table

Revision ID: a2b3c4d5e6f1
Revises: f1a2b3c4d5e6
Create Date: 2026-01-30

Какими источниками подтверждается событие + роль источника.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a2b3c4d5e6f1"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_source_links",
        sa.Column(
            "event_id",
            sa.UUID(),
            nullable=False,
            comment="Ссылка на событие.",
        ),
        sa.Column(
            "source_link_id",
            sa.UUID(),
            nullable=False,
            comment="Ссылка на источник (документ/URL).",
        ),
        sa.Column(
            "role",
            sa.Text(),
            nullable=False,
            server_default="evidence",
            comment="Роль источника: evidence / mention / background / counterpoint / other.",
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Когда источник был привязан к событию.",
        ),
        sa.Column(
            "quote",
            sa.Text(),
            nullable=True,
            comment="Короткая цитата/фрагмент из источника, подтверждающий событие.",
        ),
        sa.Column(
            "score",
            sa.Numeric(6, 3),
            nullable=True,
            comment="Сила доказательства/релевантность источника этому событию.",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_link_id"],
            ["source_links.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", "source_link_id"),
        comment="Какими источниками подтверждается событие + роль источника",
    )

    op.create_index(
        op.f("ix_event_source_links_source_link_id"),
        "event_source_links",
        ["source_link_id"],
        unique=False,
    )
    op.create_index(
        "ix_event_source_links_event_id_role",
        "event_source_links",
        ["event_id", "role"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_event_source_links_event_id_role",
        table_name="event_source_links",
    )
    op.drop_index(
        op.f("ix_event_source_links_source_link_id"),
        table_name="event_source_links",
    )
    op.drop_table("event_source_links")
