"""Add landscapes table (versioned snapshots per theme).

Revision ID: w8x9y0z1a2b3
Revises: u7v9w0x1y2z3
Create Date: 2026-03-21

История версий текстового ландшафта темы (без уникальности по theme_id).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "w8x9y0z1a2b3"
down_revision: Union[str, Sequence[str], None] = "u7v9w0x1y2z3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "landscapes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Идентификатор версии ландшафта.",
        ),
        sa.Column(
            "theme_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Тема, к которой относится эта версия ландшафта.",
        ),
        sa.Column(
            "text",
            sa.Text(),
            nullable=False,
            comment="Сгенерированный текст ландшафта темы.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Время создания версии.",
        ),
        sa.ForeignKeyConstraint(
            ["theme_id"],
            ["themes.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Версии текстового ландшафта темы.",
    )
    op.create_index(
        "idx_landscapes_theme_id_created_at",
        "landscapes",
        ["theme_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("idx_landscapes_theme_id_created_at", table_name="landscapes")
    op.drop_table("landscapes")
