"""Add rejected_quanta_candidates table

Revision ID: r8s9t0u1v2w3
Revises: p3q4r5s6t7u8
Create Date: 2026-03-29

Отклонённые кандидаты в кванты (эмбеддинг / ИИ), чтобы не обрабатывать повторно.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "r8s9t0u1v2w3"
down_revision: Union[str, Sequence[str], None] = "p3q4r5s6t7u8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    entity_kind_type = postgresql.ENUM(
        "publication",
        "patent",
        "webpage",
        name="quantum_entity_kind",
        create_type=False,
    )

    op.create_table(
        "rejected_quanta_candidates",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Идентификатор записи",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=False,
            comment="Тема, в контексте которой квант отклонён",
        ),
        sa.Column(
            "entity_kind",
            entity_kind_type,
            nullable=False,
            comment="Класс кванта (тот же enum, что у theme_quanta.entity_kind)",
        ),
        sa.Column(
            "key",
            sa.Text(),
            nullable=False,
            comment="Ключ дедупликации кванта (как dedup_key в theme_quanta)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Когда кандидат занесён в список отклонённых",
        ),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "theme_id",
            "entity_kind",
            "key",
            name="uq_rejected_quanta_candidates_theme_id_entity_kind_key",
        ),
    )
    op.create_index(
        "ix_rejected_quanta_candidates_theme_id",
        "rejected_quanta_candidates",
        ["theme_id"],
        unique=False,
    )
    op.create_index(
        "idx_rejected_quanta_candidates_theme_kind_key",
        "rejected_quanta_candidates",
        ["theme_id", "entity_kind", "key"],
        unique=False,
    )
    op.execute(
        "COMMENT ON TABLE rejected_quanta_candidates IS "
        "'Отклонённые кандидаты в кванты (не пересматривать при повторном поиске)'"
    )


def downgrade() -> None:
    op.drop_index(
        "idx_rejected_quanta_candidates_theme_kind_key",
        table_name="rejected_quanta_candidates",
    )
    op.drop_index("ix_rejected_quanta_candidates_theme_id", table_name="rejected_quanta_candidates")
    op.drop_table("rejected_quanta_candidates")
