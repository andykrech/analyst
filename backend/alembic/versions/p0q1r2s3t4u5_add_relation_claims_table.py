"""Add relation_claims table.

Revision ID: p0q1r2s3t4u5
Revises: o9p0q1r2s3t4
Create Date: 2026-03-03

Таблица утверждений о свойствах связи (модификатор явления, условия и т.п.).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p0q1r2s3t4u5"
down_revision: Union[str, Sequence[str], None] = "o9p0q1r2s3t4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "relation_claims",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор утверждения.",
        ),
        sa.Column(
            "relation_id",
            sa.UUID(),
            nullable=False,
            comment="Связь, к которой относится утверждение (например entity–quantum, type=mentions).",
        ),
        sa.Column(
            "property_type",
            sa.Text(),
            nullable=False,
            comment="Тип свойства (напр. phenomenon_modifier_condition) — для фильтрации и интерпретации properties_json.",
        ),
        sa.Column(
            "properties_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Структурированные данные свойства (напр. modifier, condition_text для явлений).",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время создания записи утверждения.",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["relation_id"],
            ["relations.id"],
            ondelete="CASCADE",
        ),
        comment="Утверждения о свойствах связи (модификатор явления, условия и т.п.)",
    )
    op.create_index(
        "ix_relation_claims_relation_id",
        "relation_claims",
        ["relation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_relation_claims_relation_id", table_name="relation_claims")
    op.drop_table("relation_claims")
