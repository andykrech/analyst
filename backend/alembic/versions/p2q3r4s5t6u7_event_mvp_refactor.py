"""Event MVP refactor: simplify event architecture

Revision ID: p2q3r4s5t6u7
Revises: o9p0q1r2s3t4
Create Date: 2026-03-06

Удаление старой тяжёлой архитектуры событий и создание облегчённой
MVP-модели: event_plots, event_roles, events, event_participants.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p2q3r4s5t6u7"
down_revision: Union[str, Sequence[str], None] = "p0q1r2s3t4u5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Удаляем все существующие таблицы старой event-архитектуры (если остались)
    # Порядок: сначала зависимые, затем родительские.
    op.execute("DROP TABLE IF EXISTS event_attributes CASCADE")
    op.execute("DROP TABLE IF EXISTS event_participants CASCADE")
    op.execute("DROP TABLE IF EXISTS event_attribute_defs CASCADE")
    op.execute("DROP TABLE IF EXISTS event_plots CASCADE")
    op.execute("DROP TABLE IF EXISTS event_roles CASCADE")
    op.execute("DROP TABLE IF EXISTS events CASCADE")

    # 2) Лёгкий глобальный справочник сюжетов событий: event_plots
    op.create_table(
        "event_plots",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор сюжета события.",
        ),
        sa.Column(
            "code",
            sa.Text(),
            nullable=False,
            comment="Уникальный код сюжета (например action/change/relation/statement).",
        ),
        sa.Column(
            "name",
            sa.Text(),
            nullable=False,
            comment="Краткое отображаемое имя сюжета.",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Описание сюжета и его типичного использования.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время создания записи сюжета.",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_event_plots_code"),
        comment="Глобальный справочник сюжетов событий (action/change/relation/statement и др.).",
    )
    op.create_index("idx_event_plots_code", "event_plots", ["code"], unique=False)

    # 3) Лёгкий глобальный справочник ролей участников событий: event_roles
    op.create_table(
        "event_roles",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор роли участника события.",
        ),
        sa.Column(
            "code",
            sa.Text(),
            nullable=False,
            comment="Уникальный код роли (например actor/target/source/subject/object/etc.).",
        ),
        sa.Column(
            "name",
            sa.Text(),
            nullable=False,
            comment="Краткое отображаемое имя роли.",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Описание роли и примеры её использования.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время создания записи роли.",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_event_roles_code"),
        comment="Глобальный справочник ролей участников событий.",
    )
    op.create_index("idx_event_roles_code", "event_roles", ["code"], unique=False)

    # 4) Минимальная таблица событий: events
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
            comment="Тема (themes.id), в контексте которой зафиксировано событие.",
        ),
        sa.Column(
            "run_id",
            sa.UUID(),
            nullable=True,
            comment="Идентификатор запуска пайплайна, в рамках которого извлечено событие.",
        ),
        sa.Column(
            "plot_id",
            sa.UUID(),
            nullable=False,
            comment="Сюжет события (event_plots.id), к которому отнесён данный event mention.",
        ),
        sa.Column(
            "predicate_text",
            sa.Text(),
            nullable=False,
            comment="Исходный текст предиката события (как он встретился в тексте/кванте).",
        ),
        sa.Column(
            "predicate_normalized",
            sa.Text(),
            nullable=False,
            comment="Нормализованная форма предиката (для агрегации/аналитики).",
        ),
        sa.Column(
            "predicate_class",
            sa.Text(),
            nullable=True,
            comment="Опциональный класс/тип предиката (например action/change/relation/statement).",
        ),
        sa.Column(
            "display_text",
            sa.Text(),
            nullable=False,
            comment="Человекочитаемое описание события для UI.",
        ),
        sa.Column(
            "event_time",
            sa.Text(),
            nullable=True,
            comment="Текстовое представление времени события (дата/период/словесное описание).",
        ),
        sa.Column(
            "attributes_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment=(
                "Массив атрибутов события в виде JSON. Каждый элемент: "
                '{"attribute_for": "subject|object|predicate|event", '
                '"attribute_text": "…", "attribute_normalized": "…" | null}.'
            ),
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=True,
            comment="Уверенность извлечения события (0..1).",
        ),
        sa.Column(
            "extraction_version",
            sa.Text(),
            nullable=True,
            comment="Версия промпта/правил, по которым извлечено событие.",
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
            comment="Дата/время последнего обновления записи события.",
        ),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plot_id"], ["event_plots.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        comment=(
            "Event mention, извлечённый из одного кванта: "
            "привязан к теме и сюжету, с нормализованным предикатом и атрибутами."
        ),
    )
    op.create_index("idx_events_theme_id", "events", ["theme_id"], unique=False)
    op.create_index("idx_events_plot_id", "events", ["plot_id"], unique=False)
    op.create_index(
        "idx_events_predicate_normalized",
        "events",
        ["predicate_normalized"],
        unique=False,
    )

    # 5) Таблица участников событий: event_participants
    op.create_table(
        "event_participants",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор участника события.",
        ),
        sa.Column(
            "event_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор события (events.id), к которому относится участник.",
        ),
        sa.Column(
            "role_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор роли участника (event_roles.id).",
        ),
        sa.Column(
            "entity_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор сущности (entities.id), являющейся участником события.",
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=True,
            comment="Уверенность в корректности связи event–entity–role (0..1).",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время создания записи участника события.",
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["event_roles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id",
            "role_id",
            "entity_id",
            name="uq_event_participants_event_role_entity",
        ),
        comment=(
            "Участники событий: связь событие–сущность–роль с возможностью фильтрации "
            "по событию, роли и сущности."
        ),
    )
    op.create_index(
        "idx_event_participants_event_id",
        "event_participants",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        "idx_event_participants_role_id",
        "event_participants",
        ["role_id"],
        unique=False,
    )
    op.create_index(
        "idx_event_participants_entity_id",
        "event_participants",
        ["entity_id"],
        unique=False,
    )


def downgrade() -> None:
    # Упрощённый откат: просто удаляем новые таблицы.
    # Старую сложную архитектуру событий не восстанавливаем.
    op.drop_index(
        "idx_event_participants_entity_id",
        table_name="event_participants",
    )
    op.drop_index("idx_event_participants_role_id", table_name="event_participants")
    op.drop_index("idx_event_participants_event_id", table_name="event_participants")
    op.drop_table("event_participants")

    op.drop_index("idx_events_predicate_normalized", table_name="events")
    op.drop_index("idx_events_plot_id", table_name="events")
    op.drop_index("idx_events_theme_id", table_name="events")
    op.drop_table("events")

    op.drop_index("idx_event_roles_code", table_name="event_roles")
    op.drop_table("event_roles")

    op.drop_index("idx_event_plots_code", table_name="event_plots")
    op.drop_table("event_plots")

