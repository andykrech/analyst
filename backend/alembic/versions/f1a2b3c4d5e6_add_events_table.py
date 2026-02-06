"""Add events table

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-01-30

Структурированные события по теме с привязкой к источникам и дайджестам.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e0f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор события.",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=False,
            comment="Тема, к которой относится событие.",
        ),
        sa.Column(
            "run_id",
            sa.UUID(),
            nullable=True,
            comment="Запуск обработки, в рамках которого событие было извлечено/обновлено.",
        ),
        sa.Column(
            "title",
            sa.Text(),
            nullable=False,
            comment="Короткая формулировка события (1 строка).",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Расширенное описание события (как ИИ интерпретировал факт).",
        ),
        sa.Column(
            "event_type",
            sa.Text(),
            nullable=False,
            server_default="other",
            comment="Тип события: regulatory / market / technology / finance / incident / litigation / product / other.",
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Момент события (если известен точно).",
        ),
        sa.Column(
            "occurred_start",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Начало интервала события (если известно как период).",
        ),
        sa.Column(
            "occurred_end",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Конец интервала события (если известно как период).",
        ),
        sa.Column(
            "timezone_hint",
            sa.Text(),
            nullable=True,
            comment="Подсказка по часовому поясу источника/события (если актуально).",
        ),
        sa.Column(
            "importance",
            sa.Numeric(6, 3),
            nullable=True,
            comment="Важность события (0..1 или иной масштаб), если используется.",
        ),
        sa.Column(
            "confidence",
            sa.Numeric(6, 3),
            nullable=True,
            comment="Уверенность извлечения/интерпретации события (0..1), если используется.",
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="active",
            comment="Статус события: active / superseded / retracted / duplicate.",
        ),
        sa.Column(
            "is_user_pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Закреплено пользователем как важное событие (исключение из авто-очистки/пересборки).",
        ),
        sa.Column(
            "fingerprint",
            sa.Text(),
            nullable=True,
            comment="Отпечаток события для дедупликации (хэш от нормализованного title+time+key entities).",
        ),
        sa.Column(
            "extracted_from",
            sa.Text(),
            nullable=False,
            server_default="ai",
            comment="Источник формирования: ai / user / imported (на будущее).",
        ),
        sa.Column(
            "provider_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Сырые данные извлечения (подсказки модели, промпт-мета, intermediate), для трассировки.",
        ),
        sa.Column(
            "participants",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Участники события в структурированном виде (имя/тип/роль/ссылки на канонические сущности когда появятся).",
        ),
        sa.Column(
            "source_link_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Кэш списка связанных source_link_id (ускорение), первично хранится в event_source_links.",
        ),
        sa.Column(
            "digest_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Кэш списка связанных digest_id (ускорение), первично хранится в event_digests.",
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Когда пользователь просмотрел событие (для подсветки непрочитанного).",
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="Заметки пользователя по событию.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время создания записи события.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время последнего изменения события.",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Мягкое удаление (soft delete).",
        ),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["search_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="Структурированные события по теме с привязкой к источникам и дайджестам",
    )

    op.create_index(op.f("ix_events_theme_id"), "events", ["theme_id"], unique=False)
    op.create_index(op.f("ix_events_run_id"), "events", ["run_id"], unique=False)
    op.create_index(op.f("ix_events_occurred_at"), "events", ["occurred_at"], unique=False)
    op.create_index(op.f("ix_events_occurred_start"), "events", ["occurred_start"], unique=False)
    op.create_index(op.f("ix_events_occurred_end"), "events", ["occurred_end"], unique=False)
    op.create_index(op.f("ix_events_fingerprint"), "events", ["fingerprint"], unique=False)
    op.create_index(
        "ix_events_theme_id_occurred_at",
        "events",
        ["theme_id", "occurred_at"],
        unique=False,
        postgresql_ops={"occurred_at": "DESC"},
    )
    op.create_index(
        "ix_events_theme_id_occurred_start",
        "events",
        ["theme_id", "occurred_start"],
        unique=False,
        postgresql_ops={"occurred_start": "DESC"},
    )
    op.create_index(
        "ix_events_theme_id_status_created_at",
        "events",
        ["theme_id", "status", "created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "ix_events_theme_id_active",
        "events",
        ["theme_id", "created_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL AND status = 'active'"),
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "uq_events_theme_id_fingerprint",
        "events",
        ["theme_id", "fingerprint"],
        unique=True,
        postgresql_where=sa.text("fingerprint IS NOT NULL AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_events_theme_id_fingerprint", table_name="events")
    op.drop_index("ix_events_theme_id_active", table_name="events")
    op.drop_index("ix_events_theme_id_status_created_at", table_name="events")
    op.drop_index("ix_events_theme_id_occurred_start", table_name="events")
    op.drop_index("ix_events_theme_id_occurred_at", table_name="events")
    op.drop_index(op.f("ix_events_fingerprint"), table_name="events")
    op.drop_index(op.f("ix_events_occurred_end"), table_name="events")
    op.drop_index(op.f("ix_events_occurred_start"), table_name="events")
    op.drop_index(op.f("ix_events_occurred_at"), table_name="events")
    op.drop_index(op.f("ix_events_run_id"), table_name="events")
    op.drop_index(op.f("ix_events_theme_id"), table_name="events")
    op.drop_table("events")
