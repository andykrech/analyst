"""Add source_links table

Revision ID: a6b7c8d9e0f1
Revises: f5a2b3c4d5e6
Create Date: 2026-01-30

Таблица найденных по теме ссылок/документов и метаданных поиска/парсинга.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a6b7c8d9e0f1"
down_revision: Union[str, Sequence[str], None] = "f5a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_links",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор источника (ссылки/документа) в рамках БД.",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор темы (themes.id), к которой относится источник.",
        ),
        sa.Column(
            "run_id",
            sa.UUID(),
            nullable=True,
            comment="Идентификатор запуска (SearchRun), в рамках которого источник был найден/обработан. В MVP может быть NULL.",
        ),
        sa.Column(
            "period_start",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Начало периода, за который выполнялся поиск (например, первый день месяца при backfill).",
        ),
        sa.Column(
            "period_end",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Конец периода, за который выполнялся поиск (например, последний день месяца при backfill).",
        ),
        sa.Column(
            "url",
            sa.Text(),
            nullable=False,
            comment="Исходный URL источника.",
        ),
        sa.Column(
            "url_normalized",
            sa.Text(),
            nullable=False,
            comment="Нормализованный URL для дедупликации (без UTM/якорей, с приведением схемы/хоста и т.п.).",
        ),
        sa.Column(
            "url_hash",
            sa.Text(),
            nullable=False,
            comment="Хэш нормализованного URL (для быстрого поиска и уникальности).",
        ),
        sa.Column(
            "canonical_url",
            sa.Text(),
            nullable=True,
            comment="Канонический URL страницы (если удалось определить при парсинге/загрузке). Может отличаться от исходного.",
        ),
        sa.Column(
            "domain",
            sa.Text(),
            nullable=False,
            comment="Домен источника (например, 'example.com') для фильтров и статистики.",
        ),
        sa.Column(
            "title",
            sa.Text(),
            nullable=True,
            comment="Заголовок материала (из поиска или со страницы).",
        ),
        sa.Column(
            "snippet",
            sa.Text(),
            nullable=True,
            comment="Сниппет/краткое описание из поисковой выдачи.",
        ),
        sa.Column(
            "author",
            sa.Text(),
            nullable=True,
            comment="Автор материала, если удалось определить.",
        ),
        sa.Column(
            "source_name",
            sa.Text(),
            nullable=True,
            comment="Название источника/издания (если известно), например 'Reuters'.",
        ),
        sa.Column(
            "language",
            sa.Text(),
            nullable=True,
            comment="Язык источника (ISO 639-1, например 'ru', 'en'), если определён.",
        ),
        sa.Column(
            "country",
            sa.Text(),
            nullable=True,
            comment="Страна/регион источника, если определены (например 'RU', 'US', 'EU').",
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Дата/время публикации материала, если удалось определить.",
        ),
        sa.Column(
            "found_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время, когда ссылка была найдена сервисом.",
        ),
        sa.Column(
            "source_type",
            sa.Text(),
            nullable=False,
            server_default="web",
            comment="Тип источника: web/pdf/video/social/news/other (пока строкой, без enum).",
        ),
        sa.Column(
            "mime_type",
            sa.Text(),
            nullable=True,
            comment="MIME-тип контента (например 'text/html', 'application/pdf'), если известен.",
        ),
        sa.Column(
            "paywalled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Признак, что контент за paywall/ограничением доступа (если определено).",
        ),
        sa.Column(
            "relevance_score",
            sa.Numeric(6, 3),
            nullable=True,
            comment="Оценка релевантности источника теме (поисковая/ИИ-оценка), если используется.",
        ),
        sa.Column(
            "rank_in_results",
            sa.Integer(),
            nullable=True,
            comment="Позиция в поисковой выдаче (если известна).",
        ),
        sa.Column(
            "content_status",
            sa.Text(),
            nullable=False,
            server_default="not_fetched",
            comment="Статус извлечения контента: not_fetched / fetched / failed / skipped.",
        ),
        sa.Column(
            "content_fetched_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Когда контент в последний раз извлекался.",
        ),
        sa.Column(
            "content_text",
            sa.Text(),
            nullable=True,
            comment="Извлечённый полный текст материала (если извлекали).",
        ),
        sa.Column(
            "content_excerpt",
            sa.Text(),
            nullable=True,
            comment="Короткий фрагмент/выжимка текста (опционально), удобный для быстрого анализа.",
        ),
        sa.Column(
            "content_checksum",
            sa.Text(),
            nullable=True,
            comment="Хэш/контрольная сумма извлечённого контента (для определения изменений при повторной загрузке).",
        ),
        sa.Column(
            "provider",
            sa.Text(),
            nullable=True,
            comment="Идентификатор провайдера поиска (например 'yandex', 'google', 'custom').",
        ),
        sa.Column(
            "provider_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Сырые данные/поля от провайдера поиска (для трассировки и улучшения качества).",
        ),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Дополнительные метаданные источника (картинка, теги, категории, любые расширения).",
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Когда пользователь открыл/просмотрел источник (для подсветки непрочитанного).",
        ),
        sa.Column(
            "pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Закреплён пользователем (важный источник) — для будущих UX-функций.",
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="Заметки пользователя по источнику (на будущее).",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время создания записи источника.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата/время последнего изменения записи источника.",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Дата/время мягкого удаления (soft delete).",
        ),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Найденные по теме ссылки/документы и метаданные поиска/парсинга",
    )

    op.create_index(
        op.f("ix_source_links_theme_id"),
        "source_links",
        ["theme_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_links_run_id"),
        "source_links",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_links_domain"),
        "source_links",
        ["domain"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_links_published_at"),
        "source_links",
        ["published_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_links_found_at"),
        "source_links",
        ["found_at"],
        unique=False,
    )
    op.create_index(
        "ix_source_links_theme_id_found_at",
        "source_links",
        ["theme_id", "found_at"],
        unique=False,
        postgresql_ops={"found_at": "DESC"},
    )
    op.create_index(
        "ix_source_links_theme_id_published_at",
        "source_links",
        ["theme_id", "published_at"],
        unique=False,
        postgresql_ops={"published_at": "DESC"},
    )
    op.create_index(
        "ix_source_links_theme_id_not_deleted",
        "source_links",
        ["theme_id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_source_links_theme_id_read_at",
        "source_links",
        ["theme_id", "read_at"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_source_links_theme_id_url_hash",
        "source_links",
        ["theme_id", "url_hash"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_source_links_theme_id_url_hash",
        "source_links",
        type_="unique",
    )
    op.drop_index("ix_source_links_theme_id_read_at", table_name="source_links")
    op.drop_index(
        "ix_source_links_theme_id_not_deleted",
        table_name="source_links",
    )
    op.drop_index(
        "ix_source_links_theme_id_published_at",
        table_name="source_links",
    )
    op.drop_index(
        "ix_source_links_theme_id_found_at",
        table_name="source_links",
    )
    op.drop_index(op.f("ix_source_links_found_at"), table_name="source_links")
    op.drop_index(op.f("ix_source_links_published_at"), table_name="source_links")
    op.drop_index(op.f("ix_source_links_domain"), table_name="source_links")
    op.drop_index(op.f("ix_source_links_run_id"), table_name="source_links")
    op.drop_index(op.f("ix_source_links_theme_id"), table_name="source_links")
    op.drop_table("source_links")
