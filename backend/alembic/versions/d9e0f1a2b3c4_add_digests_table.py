"""Add digests table

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-01-30

Периодические дайджесты по теме с поддержкой compaction/retention.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "digests",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор дайджеста.",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор темы, к которой относится дайджест.",
        ),
        sa.Column(
            "run_id",
            sa.UUID(),
            nullable=True,
            comment="Идентификатор запуска (search_runs), в рамках которого был создан/пересобран дайджест.",
        ),
        sa.Column(
            "digest_type",
            sa.Text(),
            nullable=False,
            server_default="period",
            comment="Тип дайджеста: monthly / weekly / daily / period / other (строкой, без enum).",
        ),
        sa.Column(
            "period_start",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Начало периода, который покрывает дайджест.",
        ),
        sa.Column(
            "period_end",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Конец периода, который покрывает дайджест.",
        ),
        sa.Column(
            "period_label",
            sa.Text(),
            nullable=True,
            comment="Человекочитаемая метка периода для UI (например '2025-01' для месяца).",
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="queued",
            comment="Статус генерации: queued / running / done / failed.",
        ),
        sa.Column(
            "queued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Когда дайджест был поставлен в очередь на генерацию.",
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Когда дайджест был успешно сгенерирован (status=done).",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="Краткое сообщение об ошибке генерации (status=failed).",
        ),
        sa.Column(
            "error_details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Структурированные детали ошибки/контекста генерации.",
        ),
        sa.Column(
            "content_md",
            sa.Text(),
            nullable=True,
            comment="Полный текст дайджеста в Markdown (может быть очищен при compaction).",
        ),
        sa.Column(
            "bullets",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Ключевые пункты дайджеста (список строк/объектов), может быть оставлен даже при compaction.",
        ),
        sa.Column(
            "highlights",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Выделенные важные моменты/инсайты (структурировано), может быть очищено при compaction.",
        ),
        sa.Column(
            "entities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Сущности, извлечённые из дайджеста (канонические имена/алиасы/веса).",
        ),
        sa.Column(
            "events",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="События, извлечённые из дайджеста (структурированные факты, участники, время, источники).",
        ),
        sa.Column(
            "subtopics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Подтемы, обнаруженные в рамках периода.",
        ),
        sa.Column(
            "signals",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Сигналы (слабые признаки изменений) в периоде.",
        ),
        sa.Column(
            "trends",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Тренды, наблюдаемые в периоде (локальные/срез периода).",
        ),
        sa.Column(
            "drivers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Внешние драйверы, замеченные в периоде.",
        ),
        sa.Column(
            "scenarios",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Сценарии/гипотезы, сформулированные на основе периода (обычно кратко).",
        ),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Метрики периода (attention index, novelty, частоты сущностей и др.).",
        ),
        sa.Column(
            "storage_tier",
            sa.Text(),
            nullable=False,
            server_default="hot",
            comment="Слой хранения: hot / warm / cold. Hot = полный контент, Warm = укороченный/сжатый, Cold = только минимальные поля.",
        ),
        sa.Column(
            "is_compacted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Признак, что дайджест был уплотнён (тяжёлые поля очищены/сжаты).",
        ),
        sa.Column(
            "compacted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Когда выполнена компактация (retention).",
        ),
        sa.Column(
            "content_deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Когда был очищен полный текст content_md (если удалён).",
        ),
        sa.Column(
            "compact_summary_md",
            sa.Text(),
            nullable=True,
            comment="Архивная краткая версия дайджеста (Markdown), сохраняется после компактации.",
        ),
        sa.Column(
            "compact_bullets",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Архивные ключевые пункты (коротко) для warm/cold.",
        ),
        sa.Column(
            "compact_meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Метаданные компактации (что очищено, какие правила применены, размеры до/после).",
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Когда пользователь открыл/прочитал дайджест (для подсветки непрочитанного).",
        ),
        sa.Column(
            "pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Закреплён ли дайджест пользователем (исключение из агрессивной компактации).",
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="Заметки пользователя по дайджесту (на будущее).",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Версия дайджеста для данного периода (1 — первая генерация, 2+ — пересборки).",
        ),
        sa.Column(
            "previous_digest_id",
            sa.UUID(),
            nullable=True,
            comment="Ссылка на предыдущую версию дайджеста (если пересобран).",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время создания записи дайджеста.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время последнего изменения записи дайджеста.",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Мягкое удаление дайджеста (soft delete).",
        ),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["search_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="Периодические дайджесты по теме с поддержкой compaction/retention",
    )

    op.create_index(
        op.f("ix_digests_theme_id"),
        "digests",
        ["theme_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_digests_run_id"),
        "digests",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_digests_period_start"),
        "digests",
        ["period_start"],
        unique=False,
    )
    op.create_index(
        op.f("ix_digests_period_end"),
        "digests",
        ["period_end"],
        unique=False,
    )
    op.create_index(
        op.f("ix_digests_previous_digest_id"),
        "digests",
        ["previous_digest_id"],
        unique=False,
    )
    op.create_index(
        "ix_digests_theme_id_period_start",
        "digests",
        ["theme_id", "period_start"],
        unique=False,
        postgresql_ops={"period_start": "DESC"},
    )
    op.create_index(
        "ix_digests_theme_id_period_end",
        "digests",
        ["theme_id", "period_end"],
        unique=False,
        postgresql_ops={"period_end": "DESC"},
    )
    op.create_index(
        "ix_digests_theme_id_status_queued_at",
        "digests",
        ["theme_id", "status", "queued_at"],
        unique=False,
        postgresql_ops={"queued_at": "DESC"},
    )
    op.create_index(
        "ix_digests_theme_id_storage_tier_period_start",
        "digests",
        ["theme_id", "storage_tier", "period_start"],
        unique=False,
        postgresql_ops={"period_start": "DESC"},
    )
    op.create_index(
        "uq_digests_theme_type_period",
        "digests",
        ["theme_id", "digest_type", "period_start", "period_end"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND previous_digest_id IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_digests_theme_type_period",
        table_name="digests",
    )
    op.drop_index(
        "ix_digests_theme_id_storage_tier_period_start",
        table_name="digests",
    )
    op.drop_index(
        "ix_digests_theme_id_status_queued_at",
        table_name="digests",
    )
    op.drop_index(
        "ix_digests_theme_id_period_end",
        table_name="digests",
    )
    op.drop_index(
        "ix_digests_theme_id_period_start",
        table_name="digests",
    )
    op.drop_index(op.f("ix_digests_previous_digest_id"), table_name="digests")
    op.drop_index(op.f("ix_digests_period_end"), table_name="digests")
    op.drop_index(op.f("ix_digests_period_start"), table_name="digests")
    op.drop_index(op.f("ix_digests_run_id"), table_name="digests")
    op.drop_index(op.f("ix_digests_theme_id"), table_name="digests")
    op.drop_table("digests")
