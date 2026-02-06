"""Add entities table

Revision ID: d5e6f1a2b3c4
Revises: c4d5e6f1a2b3
Create Date: 2026-01-30

Сущности по теме (канонические имена, алиасы, типы) с поддержкой compaction.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d5e6f1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
            comment="Запуск (search_runs), в рамках которого сущность была впервые обнаружена или обновлена.",
        ),
        sa.Column(
            "canonical_name",
            sa.Text(),
            nullable=False,
            comment="Каноническое (основное) имя сущности.",
        ),
        sa.Column(
            "normalized_name",
            sa.Text(),
            nullable=False,
            comment="Нормализованная форма canonical_name (lowercase, без лишних символов) для дедупликации.",
        ),
        sa.Column(
            "fingerprint",
            sa.Text(),
            nullable=True,
            comment="Отпечаток сущности для дедупликации (например хэш от normalized_name + entity_type).",
        ),
        sa.Column(
            "entity_type",
            sa.Text(),
            nullable=False,
            server_default="other",
            comment="Тип сущности: person / org / product / tech / country / document / regulation / other.",
        ),
        sa.Column(
            "aliases",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Алиасы/варианты имен (список строк или объектов с полями value/source/confidence).",
        ),
        sa.Column(
            "external_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Внешние идентификаторы (wikidata, isin, inn, ticker, doi и т.д.), если извлекли.",
        ),
        sa.Column(
            "homepage_url",
            sa.Text(),
            nullable=True,
            comment="Официальный сайт/домашняя страница (если применимо).",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Краткое описание сущности.",
        ),
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Произвольные атрибуты (отрасль, роль, технологии, география и т.п.).",
        ),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Теги/категории (для UI и фильтров).",
        ),
        sa.Column(
            "importance",
            sa.Numeric(6, 3),
            nullable=True,
            comment="Важность сущности для темы (например 0..1).",
        ),
        sa.Column(
            "confidence",
            sa.Numeric(6, 3),
            nullable=True,
            comment="Уверенность канонизации/извлечения (например 0..1).",
        ),
        sa.Column(
            "relevance_score",
            sa.Numeric(6, 3),
            nullable=True,
            comment="Релевантность сущности теме (если используется).",
        ),
        sa.Column(
            "extracted_from",
            sa.Text(),
            nullable=False,
            server_default="ai",
            comment="Происхождение сущности: ai / user / imported.",
        ),
        sa.Column(
            "provider",
            sa.Text(),
            nullable=True,
            comment="Провайдер/пайплайн извлечения (название модели/шагов), если нужно.",
        ),
        sa.Column(
            "provider_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Сырые данные извлечения/трассировки (промпт-мета, промежуточные результаты и т.п.).",
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="active",
            comment="Статус сущности: active / merged / deprecated / duplicate.",
        ),
        sa.Column(
            "merged_into_entity_id",
            sa.UUID(),
            nullable=True,
            comment="Если сущность слита (merged), ссылка на сущность-приёмник.",
        ),
        sa.Column(
            "is_user_pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Закреплено пользователем как ключевая сущность.",
        ),
        sa.Column(
            "mention_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Сколько раз сущность упоминалась (агрегат, обновляется пайплайном).",
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Когда сущность впервые появилась в источниках/событиях.",
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Когда сущность последний раз встречалась (для определения актуальности).",
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Когда пользователь просмотрел сущность (для подсветки непрочитанного).",
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="Заметки пользователя по сущности.",
        ),
        sa.Column(
            "storage_tier",
            sa.Text(),
            nullable=False,
            server_default="hot",
            comment="Слой хранения: hot / warm / cold.",
        ),
        sa.Column(
            "is_compacted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Признак, что сущность была уплотнена.",
        ),
        sa.Column(
            "compacted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Когда выполнена компактация.",
        ),
        sa.Column(
            "description_deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Когда очищено поле description (если удалено).",
        ),
        sa.Column(
            "compact_summary",
            sa.Text(),
            nullable=True,
            comment="Архивная краткая версия описания сущности.",
        ),
        sa.Column(
            "compact_meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Метаданные компактации (что очищено, правила, размеры).",
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
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["search_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="Сущности по теме (канонические имена, алиасы, типы) с поддержкой compaction",
    )

    op.create_index(
        op.f("ix_entities_theme_id"),
        "entities",
        ["theme_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_entities_run_id"),
        "entities",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_entities_fingerprint"),
        "entities",
        ["fingerprint"],
        unique=False,
    )
    op.create_index(
        op.f("ix_entities_last_seen_at"),
        "entities",
        ["last_seen_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_entities_merged_into_entity_id"),
        "entities",
        ["merged_into_entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_entities_theme_id_canonical_name",
        "entities",
        ["theme_id", "canonical_name"],
        unique=False,
    )
    op.create_index(
        "ix_entities_theme_id_entity_type",
        "entities",
        ["theme_id", "entity_type"],
        unique=False,
    )
    op.create_index(
        "ix_entities_theme_id_last_seen_at",
        "entities",
        ["theme_id", "last_seen_at"],
        unique=False,
        postgresql_ops={"last_seen_at": "DESC"},
    )
    op.create_index(
        "ix_entities_theme_id_status_created_at",
        "entities",
        ["theme_id", "status", "created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
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
        "uq_entities_theme_type_normalized",
        "entities",
        ["theme_id", "entity_type", "normalized_name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_entities_theme_type_normalized",
        table_name="entities",
    )
    op.drop_index(
        "ix_entities_theme_id_active",
        table_name="entities",
    )
    op.drop_index(
        "ix_entities_theme_id_status_created_at",
        table_name="entities",
    )
    op.drop_index(
        "ix_entities_theme_id_last_seen_at",
        table_name="entities",
    )
    op.drop_index(
        "ix_entities_theme_id_entity_type",
        table_name="entities",
    )
    op.drop_index(
        "ix_entities_theme_id_canonical_name",
        table_name="entities",
    )
    op.drop_index(op.f("ix_entities_merged_into_entity_id"), table_name="entities")
    op.drop_index(op.f("ix_entities_last_seen_at"), table_name="entities")
    op.drop_index(op.f("ix_entities_fingerprint"), table_name="entities")
    op.drop_index(op.f("ix_entities_run_id"), table_name="entities")
    op.drop_index(op.f("ix_entities_theme_id"), table_name="entities")
    op.drop_table("entities")
