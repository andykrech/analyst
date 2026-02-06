"""Add digest_source_links table

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-01-30

Связь дайджестов с источниками (какие источники вошли в дайджест).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e0f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "digest_source_links",
        sa.Column(
            "digest_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор дайджеста.",
        ),
        sa.Column(
            "source_link_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор источника, использованного в дайджесте.",
        ),
        sa.Column(
            "role",
            sa.Text(),
            nullable=False,
            server_default="input",
            comment="Роль источника: input / evidence / excluded / other.",
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Когда источник был добавлен в состав дайджеста.",
        ),
        sa.Column(
            "rank",
            sa.Integer(),
            nullable=True,
            comment="Позиция/ранг источника в отборе для дайджеста (если используется).",
        ),
        sa.ForeignKeyConstraint(
            ["digest_id"],
            ["digests.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_link_id"],
            ["source_links.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("digest_id", "source_link_id"),
        comment="Связь дайджестов с источниками (какие источники вошли в дайджест)",
    )

    op.create_index(
        op.f("ix_digest_source_links_source_link_id"),
        "digest_source_links",
        ["source_link_id"],
        unique=False,
    )
    op.create_index(
        "ix_digest_source_links_digest_id_rank",
        "digest_source_links",
        ["digest_id", "rank"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_digest_source_links_digest_id_rank",
        table_name="digest_source_links",
    )
    op.drop_index(
        op.f("ix_digest_source_links_source_link_id"),
        table_name="digest_source_links",
    )
    op.drop_table("digest_source_links")
