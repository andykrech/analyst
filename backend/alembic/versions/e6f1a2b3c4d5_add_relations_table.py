"""Add relations table

Revision ID: e6f1a2b3c4d5
Revises: d5e6f1a2b3c4
Create Date: 2026-01-30

Связи между объектами внутри темы (subject -> object, полиморфные ссылки).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e6f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "d5e6f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "relations",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор связи.",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=False,
            comment="Тема, внутри которой существует связь.",
        ),
        sa.Column(
            "subject_type",
            sa.Text(),
            nullable=False,
            comment="Тип субъекта связи: entity / event / digest / source_link / overview / trend / signal / scenario / subtopic / other.",
        ),
        sa.Column(
            "subject_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор субъекта (UUID соответствующей таблицы).",
        ),
        sa.Column(
            "object_type",
            sa.Text(),
            nullable=False,
            comment="Тип объекта связи (те же значения, что и subject_type).",
        ),
        sa.Column(
            "object_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор объекта (UUID соответствующей таблицы).",
        ),
        sa.Column(
            "relation_type",
            sa.Text(),
            nullable=False,
            comment="Тип связи: mentions / supports / similar / causes / part_of / contradicts / related / other.",
        ),
        sa.Column(
            "direction",
            sa.Text(),
            nullable=False,
            server_default="forward",
            comment="Направление интерпретации: forward (subject->object) / bidirectional.",
        ),
        sa.Column(
            "weight",
            sa.Numeric(6, 3),
            nullable=True,
            comment="Вес/сила связи (например 0..1).",
        ),
        sa.Column(
            "confidence",
            sa.Numeric(6, 3),
            nullable=True,
            comment="Уверенность связи (например 0..1).",
        ),
        sa.Column(
            "explanation",
            sa.Text(),
            nullable=True,
            comment="Короткое объяснение, почему связь существует.",
        ),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Доказательства связи (например список source_link_id/event_id + фрагменты).",
        ),
        sa.Column(
            "run_id",
            sa.UUID(),
            nullable=True,
            comment="Запуск (search_runs), в рамках которого связь была создана/обновлена.",
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="active",
            comment="Статус связи: active / deprecated / removed.",
        ),
        sa.Column(
            "is_user_created",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Связь создана пользователем вручную (не удалять автоматически).",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время создания связи.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время последнего изменения связи.",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Мягкое удаление связи.",
        ),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["search_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="Связи между объектами внутри темы (subject -> object, полиморфные ссылки)",
    )

    op.create_index(
        op.f("ix_relations_theme_id"),
        "relations",
        ["theme_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_relations_subject_id"),
        "relations",
        ["subject_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_relations_object_id"),
        "relations",
        ["object_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_relations_run_id"),
        "relations",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_relations_theme_id_relation_type",
        "relations",
        ["theme_id", "relation_type"],
        unique=False,
    )
    op.create_index(
        "ix_relations_theme_id_subject",
        "relations",
        ["theme_id", "subject_type", "subject_id"],
        unique=False,
    )
    op.create_index(
        "ix_relations_theme_id_object",
        "relations",
        ["theme_id", "object_type", "object_id"],
        unique=False,
    )
    op.create_index(
        "ix_relations_theme_id_active",
        "relations",
        ["theme_id", "created_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL AND status = 'active'"),
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "uq_relations_theme_subject_relation_object",
        "relations",
        [
            "theme_id",
            "subject_type",
            "subject_id",
            "relation_type",
            "object_type",
            "object_id",
        ],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_relations_theme_subject_relation_object",
        table_name="relations",
    )
    op.drop_index(
        "ix_relations_theme_id_active",
        table_name="relations",
    )
    op.drop_index(
        "ix_relations_theme_id_object",
        table_name="relations",
    )
    op.drop_index(
        "ix_relations_theme_id_subject",
        table_name="relations",
    )
    op.drop_index(
        "ix_relations_theme_id_relation_type",
        table_name="relations",
    )
    op.drop_index(op.f("ix_relations_run_id"), table_name="relations")
    op.drop_index(op.f("ix_relations_object_id"), table_name="relations")
    op.drop_index(op.f("ix_relations_subject_id"), table_name="relations")
    op.drop_index(op.f("ix_relations_theme_id"), table_name="relations")
    op.drop_table("relations")
