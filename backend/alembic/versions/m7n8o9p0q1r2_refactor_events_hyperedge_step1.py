"""Refactor events: Event = hyperedge (ШАГ 1)

Revision ID: m7n8o9p0q1r2
Revises: k6l7m8n9o0p1
Create Date: 2026-03-06

ШАГ 1: удаление старых таблиц events, event_source_links, event_digests, event_entities;
добавление enum event_plot в embedding_object_type; создание новой таблицы events
(привязка к теме и кванту, поля сюжета, без участников/ролей — те в шаге 2+).
Данных в БД нет, только DROP и CREATE.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "m7n8o9p0q1r2"
down_revision: Union[str, Sequence[str], None] = "k6l7m8n9o0p1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # a) Удаление старых таблиц (порядок важен из-за FK: сначала связующие, потом events)
    op.execute("DROP TABLE IF EXISTS event_source_links CASCADE")
    op.execute("DROP TABLE IF EXISTS event_digests CASCADE")
    op.execute("DROP TABLE IF EXISTS event_entities CASCADE")
    op.execute("DROP TABLE IF EXISTS events CASCADE")

    # e) Добавить значение 'event_plot' в enum embedding_object_type (Postgres: ADD VALUE в отдельной транзакции)
    op.execute("ALTER TYPE embedding_object_type ADD VALUE IF NOT EXISTS 'event_plot'")

    # f) Создать новую таблицу events со всеми колонками и комментариями
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
            "quantum_id",
            sa.UUID(),
            nullable=False,
            comment="Квант (theme_quanta.id) — доказательство в тексте; FK будет добавлен позже.",
        ),
        sa.Column(
            "run_id",
            sa.UUID(),
            nullable=True,
            comment="Запуск пайплайна, в рамках которого событие извлечено; FK опционально позже.",
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Точное или примерное время события (одна точка).",
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
            "time_precision",
            sa.Text(),
            nullable=True,
            comment="Точность времени: exact / day / month / year / unknown.",
        ),
        sa.Column(
            "title",
            sa.Text(),
            nullable=False,
            comment="Короткое название события.",
        ),
        sa.Column(
            "summary",
            sa.Text(),
            nullable=True,
            comment="Расширенное описание события.",
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=True,
            comment="Уверенность извлечения/интерпретации (0..1).",
        ),
        sa.Column(
            "importance",
            sa.Float(),
            nullable=True,
            comment="Важность для пользователя (0..1).",
        ),
        sa.Column(
            "plot_id",
            sa.UUID(),
            nullable=True,
            comment="Ссылка на theme_event_plots (появится позже); FK не добавляем сейчас.",
        ),
        sa.Column(
            "plot_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'unassigned'"),
            comment="Статус классификации сюжета: unassigned / assigned / needs_review / proposed.",
        ),
        sa.Column(
            "plot_confidence",
            sa.Float(),
            nullable=True,
            comment="Уверенность отнесения к сюжету (0..1).",
        ),
        sa.Column(
            "plot_proposed_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Если LLM предложил новый сюжет — данные предложения (для ревью).",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время создания записи.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время последнего изменения (обновляется приложением).",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Мягкое удаление (soft delete) на будущее.",
        ),
        sa.Column(
            "extraction_version",
            sa.Text(),
            nullable=True,
            comment="Версия логики/промпта извлечения событий.",
        ),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="События по теме с привязкой к кванту (доказательство); участники/роли/сюжеты — в следующих шагах",
    )

    # Индексы
    op.create_index(op.f("ix_events_theme_id"), "events", ["theme_id"], unique=False)
    op.create_index(op.f("ix_events_quantum_id"), "events", ["quantum_id"], unique=False)
    op.create_index(op.f("idx_events_run_id"), "events", ["run_id"], unique=False)
    op.create_index(
        "idx_events_theme_created_at",
        "events",
        ["theme_id", "created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "idx_events_theme_occurred_at",
        "events",
        ["theme_id", "occurred_at"],
        unique=False,
        postgresql_ops={"occurred_at": "DESC"},
    )
    op.create_index(
        "idx_events_theme_quantum",
        "events",
        ["theme_id", "quantum_id"],
        unique=False,
    )
    op.create_index(
        "idx_events_plot_status",
        "events",
        ["theme_id", "plot_status", "created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )
    op.execute(
        """
        CREATE INDEX idx_events_plot_proposed_payload_gin
        ON events USING gin (plot_proposed_payload);
        """
    )


def downgrade() -> None:
    op.drop_index("idx_events_plot_proposed_payload_gin", table_name="events")
    op.drop_index("idx_events_plot_status", table_name="events")
    op.drop_index("idx_events_theme_quantum", table_name="events")
    op.drop_index("idx_events_theme_occurred_at", table_name="events")
    op.drop_index("idx_events_theme_created_at", table_name="events")
    op.drop_index(op.f("idx_events_run_id"), table_name="events")
    op.drop_index(op.f("ix_events_quantum_id"), table_name="events")
    op.drop_index(op.f("ix_events_theme_id"), table_name="events")
    op.drop_table("events")
    # Значение 'event_plot' из enum embedding_object_type не удаляем:
    # в Postgres удаление значений из ENUM не поддерживается без пересоздания типа.
    # Старые таблицы (event_source_links, event_digests, event_entities, events)
    # не восстанавливаем — данные по ТЗ отсутствовали.