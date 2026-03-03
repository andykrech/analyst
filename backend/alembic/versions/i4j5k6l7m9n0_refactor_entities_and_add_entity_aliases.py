"""Refactor entities table to a light schema and add entity_aliases table.

Revision ID: i4j5k6l7m9n0
Revises: h3i4j5k6l7m8
Create Date: 2026-03-03

Лёгкая (горячая) таблица сущностей по теме и отдельная таблица алиасов.
Данных в старой таблице entities нет, поэтому используем DROP/CREATE.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i4j5k6l7m9n0"
down_revision: Union[str, Sequence[str], None] = "h3i4j5k6l7m8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Дроп старой тяжёлой таблицы entities (данных нет)
    op.drop_table("entities")

    # 2) Новая лёгкая таблица entities
    op.create_table(
        "entities",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор сущности.",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор темы, к которой относится сущность.",
        ),
        sa.Column(
            "run_id",
            sa.UUID(),
            nullable=True,
            comment=(
                "Идентификатор запуска (search_runs), в рамках которого сущность впервые "
                "обнаружена или обновлена."
            ),
        ),
        sa.Column(
            "entity_type",
            sa.Text(),
            nullable=False,
            server_default="other",
            comment=(
                "Тип сущности: person/org/tech/product/country/document/regulation/other."
            ),
        ),
        sa.Column(
            "canonical_name",
            sa.Text(),
            nullable=False,
            comment=(
                "Каноническое имя (display name) — то, что показываем пользователю "
                "(может быть на языке темы)."
            ),
        ),
        sa.Column(
            "normalized_name",
            sa.Text(),
            nullable=False,
            comment=(
                "Нормализованное имя для дедупликации (ключ уникальности; например англ. "
                "pivot normalized)."
            ),
        ),
        sa.Column(
            "fingerprint",
            sa.Text(),
            nullable=True,
            comment=(
                "Отпечаток для дедупликации (например хэш от normalized_name + entity_type)."
            ),
        ),
        sa.Column(
            "mention_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment=(
                "Сколько раз сущность упоминалась (агрегат, обновляется пайплайном)."
            ),
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Когда сущность впервые появилась в источниках/квантах.",
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "Когда сущность последний раз встречалась (для определения актуальности)."
            ),
        ),
        sa.Column(
            "importance",
            sa.Float(),
            nullable=True,
            comment="Важность сущности для темы (например 0..1).",
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=True,
            comment=(
                "Уверенность извлечения/канонизации сущности (например 0..1)."
            ),
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="active",
            comment="Статус сущности: active/merged/deprecated/duplicate.",
        ),
        sa.Column(
            "is_user_pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Закреплено пользователем как ключевая сущность.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время создания записи сущности.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время последнего изменения записи сущности.",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Мягкое удаление сущности (soft delete).",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["theme_id"],
            ["themes.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["search_runs.id"],
            ondelete="SET NULL",
        ),
        comment=(
            "Горячие сущности по теме (минимальные поля для дедупа, списков и агрегаций)."
        ),
    )

    # Индексы для entities
    op.create_index(
        "uq_entities_theme_type_normalized_active",
        "entities",
        ["theme_id", "entity_type", "normalized_name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND status = 'active'"),
    )
    op.create_index(
        "ix_entities_theme_id_active",
        "entities",
        ["theme_id", "created_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL AND status = 'active'"),
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "ix_entities_theme_id",
        "entities",
        ["theme_id"],
        unique=False,
    )
    op.create_index(
        "ix_entities_run_id",
        "entities",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_entities_fingerprint",
        "entities",
        ["fingerprint"],
        unique=False,
    )
    op.create_index(
        "ix_entities_last_seen_at",
        "entities",
        ["last_seen_at"],
        unique=False,
    )

    # Комментарии к индексам entities
    op.execute(
        """
        COMMENT ON INDEX uq_entities_theme_type_normalized_active IS
        'Уникальность сущностей внутри темы по типу и нормализованному имени (только active и не удалённые).'
        """
    )
    op.execute(
        """
        COMMENT ON INDEX ix_entities_theme_id_active IS
        'Быстрый выбор активных сущностей по теме (для списков/UI).'
        """
    )
    op.execute(
        """
        COMMENT ON INDEX ix_entities_theme_id IS
        'Индекс по theme_id для фильтрации сущностей по теме.'
        """
    )
    op.execute(
        """
        COMMENT ON INDEX ix_entities_run_id IS
        'Индекс по run_id для выборки сущностей по запуску.'
        """
    )
    op.execute(
        """
        COMMENT ON INDEX ix_entities_fingerprint IS
        'Индекс по fingerprint для ускорения дедупликации.'
        """
    )
    op.execute(
        """
        COMMENT ON INDEX ix_entities_last_seen_at IS
        'Индекс по last_seen_at для сортировки и фильтра по свежести сущности.'
        """
    )

    # 3) Таблица entity_aliases
    op.create_table(
        "entity_aliases",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор алиаса.",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=False,
            comment=(
                "Идентификатор темы (денормализация для быстрого поиска алиасов без join)."
            ),
        ),
        sa.Column(
            "entity_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор сущности, которой принадлежит алиас.",
        ),
        sa.Column(
            "entity_type",
            sa.Text(),
            nullable=False,
            comment=(
                "Тип сущности (денормализация для ускорения резолва по алиасу)."
            ),
        ),
        sa.Column(
            "alias_value",
            sa.Text(),
            nullable=False,
            comment=(
                "Значение алиаса (считается уже нормализованным; используется для поиска кандидатов)."
            ),
        ),
        sa.Column(
            "lang",
            sa.Text(),
            nullable=True,
            comment="Язык алиаса (например en/ru/ja/und).",
        ),
        sa.Column(
            "kind",
            sa.Text(),
            nullable=False,
            server_default="surface",
            comment=(
                "Вид алиаса: surface/acronym/pivot/translation/spelling/user."
            ),
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=True,
            comment="Уверенность в корректности алиаса (например 0..1).",
        ),
        sa.Column(
            "source",
            sa.Text(),
            nullable=False,
            server_default="ai",
            comment="Источник алиаса: ai/user/import/pattern.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время добавления алиаса.",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["theme_id"],
            ["themes.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entities.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "entity_id",
            "alias_value",
            name="uq_entity_aliases_entity_alias",
        ),
        comment=(
            "Алиасы сущностей по теме (для резолва кандидатов и поиска)."
        ),
    )

    # Индексы для entity_aliases
    op.create_index(
        "ix_entity_aliases_lookup",
        "entity_aliases",
        ["theme_id", "entity_type", "alias_value"],
        unique=False,
    )
    op.create_index(
        "ix_entity_aliases_theme_id",
        "entity_aliases",
        ["theme_id"],
        unique=False,
    )
    op.create_index(
        "ix_entity_aliases_entity_id",
        "entity_aliases",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_entity_aliases_entity_type",
        "entity_aliases",
        ["entity_type"],
        unique=False,
    )

    # Комментарии к индексам и уникальным ограничениям entity_aliases
    op.execute(
        """
        COMMENT ON INDEX ix_entity_aliases_lookup IS
        'Быстрый поиск сущности по алиасу в рамках темы и типа.'
        """
    )
    op.execute(
        """
        COMMENT ON INDEX ix_entity_aliases_theme_id IS
        'Индекс по theme_id для быстрого фильтра алиасов по теме.'
        """
    )
    op.execute(
        """
        COMMENT ON INDEX ix_entity_aliases_entity_id IS
        'Индекс по entity_id для выборки алиасов конкретной сущности.'
        """
    )
    op.execute(
        """
        COMMENT ON INDEX ix_entity_aliases_entity_type IS
        'Индекс по entity_type для фильтрации алиасов по типу сущности.'
        """
    )
    op.execute(
        """
        COMMENT ON CONSTRAINT uq_entity_aliases_entity_alias ON entity_aliases IS
        'Запрет дублей: один и тот же алиас не должен повторяться у одной сущности.'
        """
    )


def downgrade() -> None:
    # В упрощённом downgrade мы не восстанавливаем старую тяжёлую схему entities,
    # так как таблица была пустой и данные не теряются.
    op.drop_table("entity_aliases")
    op.drop_table("entities")

