"""Add event_roles, event_plots, event_attribute_defs, event_participants, event_attributes (ШАГ 2+)

Revision ID: o9p0q1r2s3t4
Revises: n8o9p0q1r2s3
Create Date: 2026-03-06

ШАГ 2+: таблицы для ролей, сюжетов, определений атрибутов, участников событий и значений атрибутов.
Добавление FK events.plot_id -> event_plots.id.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "o9p0q1r2s3t4"
down_revision: Union[str, Sequence[str], None] = "n8o9p0q1r2s3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) event_roles
    op.create_table(
        "event_roles",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор роли.",
        ),
        sa.Column(
            "code",
            sa.Text(),
            nullable=False,
            comment="Машинный код роли: actor/target/cause/effect/instrument/location/etc.",
        ),
        sa.Column(
            "title",
            sa.Text(),
            nullable=False,
            comment="Отображаемое имя роли.",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Пояснение, как использовать роль.",
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
            comment="Дата/время последнего изменения.",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_event_roles_code"),
        comment="Словарь ролей участников событий (actor, target, cause, effect и т.д.)",
    )

    # 2) event_plots
    op.create_table(
        "event_plots",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор сюжета.",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=False,
            comment="Тема, к которой относится сюжет.",
        ),
        sa.Column(
            "code",
            sa.Text(),
            nullable=False,
            comment="Код сюжета уникален в рамках темы.",
        ),
        sa.Column(
            "title",
            sa.Text(),
            nullable=False,
            comment="Название сюжета.",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Описание сюжета.",
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'draft'"),
            comment="Статус сюжета: draft / approved / archived.",
        ),
        sa.Column(
            "required_roles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Список обязательных ролей (по role.code), например ['actor','target'].",
        ),
        sa.Column(
            "optional_roles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Список опциональных ролей.",
        ),
        sa.Column(
            "required_attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Список обязательных атрибутов (по attribute_def.code).",
        ),
        sa.Column(
            "allowed_attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Список разрешённых атрибутов.",
        ),
        sa.Column(
            "aliases",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Синонимы/варианты названия сюжета.",
        ),
        sa.Column(
            "created_by_user_id",
            sa.UUID(),
            nullable=True,
            comment="Пользователь, создавший сюжет.",
        ),
        sa.Column(
            "approved_by_user_id",
            sa.UUID(),
            nullable=True,
            comment="Пользователь, одобривший сюжет.",
        ),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Дата/время одобрения.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время создания.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время последнего изменения.",
        ),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("theme_id", "code", name="uq_event_plots_theme_id_code"),
        comment="Сюжеты событий в рамках темы (theme-scoped)",
    )
    op.create_index("idx_event_plots_theme_status", "event_plots", ["theme_id", "status", "code"], unique=False)
    op.create_index(
        "idx_event_plots_theme_updated",
        "event_plots",
        ["theme_id", "updated_at"],
        unique=False,
        postgresql_ops={"updated_at": "DESC"},
    )
    op.execute(
        "CREATE INDEX gin_event_plots_required_roles ON event_plots USING gin (required_roles);"
    )
    op.execute(
        "CREATE INDEX gin_event_plots_allowed_attributes ON event_plots USING gin (allowed_attributes);"
    )

    # 3) event_attribute_defs
    op.create_table(
        "event_attribute_defs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор определения атрибута.",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=False,
            comment="Тема, к которой относится определение.",
        ),
        sa.Column(
            "code",
            sa.Text(),
            nullable=False,
            comment="Канонический ключ атрибута: price/currency/stake_percent/value_before/etc.",
        ),
        sa.Column(
            "title",
            sa.Text(),
            nullable=False,
            comment="Отображаемое название атрибута.",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Пояснение к атрибуту.",
        ),
        sa.Column(
            "value_type",
            sa.Text(),
            nullable=False,
            comment="Тип значения: number/text/bool/date/json.",
        ),
        sa.Column(
            "unit_kind",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'none'"),
            comment="Единица измерения: none/currency/percent/time/length/mass/temperature/etc.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время создания.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время последнего изменения.",
        ),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("theme_id", "code", name="uq_event_attribute_defs_theme_id_code"),
        comment="Словарь характеристик событий в рамках темы",
    )
    op.create_index("idx_event_attr_defs_theme", "event_attribute_defs", ["theme_id", "code"], unique=False)

    # 4) FK на events.plot_id -> event_plots.id
    op.create_foreign_key(
        "fk_events_plot_id_event_plots",
        "events",
        "event_plots",
        ["plot_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 5) event_participants
    op.create_table(
        "event_participants",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор записи участника.",
        ),
        sa.Column(
            "event_id",
            sa.UUID(),
            nullable=False,
            comment="Событие.",
        ),
        sa.Column(
            "entity_id",
            sa.UUID(),
            nullable=True,
            comment="Ссылка на сущность.",
        ),
        sa.Column(
            "role_id",
            sa.UUID(),
            nullable=False,
            comment="Роль участника.",
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=True,
            comment="Уверенность извлечения связи участника с ролью (0..1).",
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время добавления участника.",
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["role_id"], ["event_roles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id",
            "role_id",
            "entity_id",
            name="uq_event_participants_event_role_entity",
        ),
        comment="Участники события (связь событие–сущность–роль); не дублировать одну сущность в одной роли в рамках события.",
    )
    op.create_index("idx_event_participants_event", "event_participants", ["event_id"], unique=False)
    op.create_index("idx_event_participants_entity_id", "event_participants", ["entity_id"], unique=False)
    op.create_index("idx_event_participants_role", "event_participants", ["role_id"], unique=False)
    op.create_index(
        "idx_event_participants_entity_role",
        "event_participants",
        ["entity_id", "role_id"],
        unique=False,
    )
    op.create_index(
        "idx_event_participants_event_role",
        "event_participants",
        ["event_id", "role_id"],
        unique=False,
    )

    # 6) event_attributes
    op.create_table(
        "event_attributes",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор записи атрибута.",
        ),
        sa.Column(
            "event_id",
            sa.UUID(),
            nullable=False,
            comment="Событие.",
        ),
        sa.Column(
            "attribute_def_id",
            sa.UUID(),
            nullable=False,
            comment="Определение атрибута.",
        ),
        sa.Column(
            "value_num",
            sa.Numeric(20, 6),
            nullable=True,
            comment="Числовое значение.",
        ),
        sa.Column(
            "value_text",
            sa.Text(),
            nullable=True,
            comment="Текстовое значение.",
        ),
        sa.Column(
            "value_bool",
            sa.Boolean(),
            nullable=True,
            comment="Булево значение.",
        ),
        sa.Column(
            "value_ts",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Значение даты/времени.",
        ),
        sa.Column(
            "value_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Произвольное JSON-значение.",
        ),
        sa.Column(
            "unit",
            sa.Text(),
            nullable=True,
            comment="Единица измерения (если применимо).",
        ),
        sa.Column(
            "currency",
            sa.Text(),
            nullable=True,
            comment="Валюта (если применимо).",
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=True,
            comment="Уверенность извлечения значения (0..1).",
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время добавления.",
        ),
        sa.CheckConstraint(
            """NOT (
                value_num IS NULL AND value_text IS NULL AND value_bool IS NULL
                AND value_ts IS NULL AND (value_json IS NULL OR value_json = '{}'::jsonb)
            )""",
            name="ck_event_attributes_at_least_one_value",
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attribute_def_id"], ["event_attribute_defs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "attribute_def_id", name="uq_event_attributes_event_def"),
        comment="Значения характеристик события; хотя бы одно value_* или непустой value_json.",
    )
    op.create_index("idx_event_attributes_event", "event_attributes", ["event_id"], unique=False)
    op.create_index("idx_event_attributes_def", "event_attributes", ["attribute_def_id"], unique=False)
    op.create_index(
        "idx_event_attributes_def_num",
        "event_attributes",
        ["attribute_def_id", "value_num"],
        unique=False,
    )
    op.create_index(
        "idx_event_attributes_def_ts",
        "event_attributes",
        ["attribute_def_id", "value_ts"],
        unique=False,
    )
    op.execute(
        "CREATE INDEX gin_event_attributes_value_json ON event_attributes USING gin (value_json);"
    )


def downgrade() -> None:
    op.drop_index("gin_event_attributes_value_json", table_name="event_attributes")
    op.drop_index("idx_event_attributes_def_ts", table_name="event_attributes")
    op.drop_index("idx_event_attributes_def_num", table_name="event_attributes")
    op.drop_index("idx_event_attributes_def", table_name="event_attributes")
    op.drop_index("idx_event_attributes_event", table_name="event_attributes")
    op.drop_table("event_attributes")

    op.drop_index("idx_event_participants_event_role", table_name="event_participants")
    op.drop_index("idx_event_participants_entity_role", table_name="event_participants")
    op.drop_index("idx_event_participants_role", table_name="event_participants")
    op.drop_index("idx_event_participants_entity_id", table_name="event_participants")
    op.drop_index("idx_event_participants_event", table_name="event_participants")
    op.drop_table("event_participants")

    op.drop_constraint("fk_events_plot_id_event_plots", "events", type_="foreignkey")

    op.drop_index("idx_event_attr_defs_theme", table_name="event_attribute_defs")
    op.drop_table("event_attribute_defs")

    op.drop_index("gin_event_plots_allowed_attributes", table_name="event_plots")
    op.drop_index("gin_event_plots_required_roles", table_name="event_plots")
    op.drop_index("idx_event_plots_theme_updated", table_name="event_plots")
    op.drop_index("idx_event_plots_theme_status", table_name="event_plots")
    op.drop_table("event_plots")

    op.drop_table("event_roles")
