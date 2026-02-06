"""Add event_entities table

Revision ID: c4d5e6f1a2b3
Revises: b3c4d5e6f1a2
Create Date: 2026-01-30

Связь событий с сущностями по каноническому имени (entity_id — для будущей нормализации).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4d5e6f1a2b3"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_entities",
        sa.Column(
            "event_id",
            sa.UUID(),
            nullable=False,
            comment="Ссылка на событие.",
        ),
        sa.Column(
            "entity_name",
            sa.Text(),
            nullable=False,
            comment="Каноническое имя сущности (используется сейчас для связи без таблицы entities).",
        ),
        sa.Column(
            "role",
            sa.Text(),
            nullable=False,
            server_default="participant",
            comment="Роль сущности в событии: initiator / target / regulator / affected / partner / other.",
        ),
        sa.Column(
            "entity_id",
            sa.UUID(),
            nullable=True,
            comment="Ссылка на сущность (будущая нормализация), пока может быть NULL.",
        ),
        sa.Column(
            "entity_type",
            sa.Text(),
            nullable=True,
            comment="Тип сущности: person / org / product / tech / country / doc / other.",
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Когда сущность была связана с событием.",
        ),
        sa.Column(
            "confidence",
            sa.Numeric(6, 3),
            nullable=True,
            comment="Уверенность извлечения связи (0..1), если используется.",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", "entity_name", "role"),
        comment="Связь событий с сущностями (по имени; entity_id — для будущей нормализации)",
    )

    op.create_index(
        op.f("ix_event_entities_entity_name"),
        "event_entities",
        ["entity_name"],
        unique=False,
    )
    op.create_index(
        "ix_event_entities_event_id_role",
        "event_entities",
        ["event_id", "role"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_event_entities_event_id_role",
        table_name="event_entities",
    )
    op.drop_index(
        op.f("ix_event_entities_entity_name"),
        table_name="event_entities",
    )
    op.drop_table("event_entities")
