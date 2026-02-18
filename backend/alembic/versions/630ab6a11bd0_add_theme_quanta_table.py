"""Add theme_quanta table

Revision ID: 630ab6a11bd0
Revises: e5f6a7b8c9d0
Create Date: 2026-02-17 18:16:32.556393

Таблица квантов информации по темам: атомарные проверяемые кликом единицы знания.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "630ab6a11bd0"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    enum_name = "quantum_entity_kind"
    # Создаём тип один раз (checkfirst — не падать, если уже есть после частичного прогона)
    postgresql.ENUM(
        "publication",
        "patent",
        "webpage",
        name=enum_name,
    ).create(op.get_bind(), checkfirst=True)

    # Для колонки используем ENUM с create_type=False, чтобы create_table не пытался создать тип повторно
    entity_kind_type = postgresql.ENUM(
        "publication",
        "patent",
        "webpage",
        name=enum_name,
        create_type=False,
    )

    # 2) Table
    op.create_table(
        "theme_quanta",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Primary key квантa",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=False,
            comment="Тема-владелец, изолированная зона знаний",
        ),
        sa.Column(
            "run_id",
            sa.UUID(),
            nullable=True,
            comment="Идентификатор прогона поиска (опционально)",
        ),
        sa.Column(
            "entity_kind",
            entity_kind_type,
            nullable=False,
            comment="Класс кванта (тип сущности)",
        ),
        sa.Column(
            "title",
            sa.Text(),
            nullable=False,
            comment="Заголовок/название объекта",
        ),
        sa.Column(
            "summary_text",
            sa.Text(),
            nullable=False,
            comment="Короткое текстовое описание (snippet/abstract/lead), используется для UX и AI анализа",
        ),
        sa.Column(
            "key_points",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Ключевые пункты (список строк), могут быть из источника или derived",
        ),
        sa.Column(
            "language",
            sa.Text(),
            nullable=True,
            comment="Язык контента (ru/en/...)",
        ),
        sa.Column(
            "date_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Дата публикации/выхода объекта",
        ),
        sa.Column(
            "verification_url",
            sa.Text(),
            nullable=False,
            comment="Кликабельная ссылка для проверки существования (повышает доверие)",
        ),
        sa.Column(
            "canonical_url",
            sa.Text(),
            nullable=True,
            comment="Канонический URL после нормализации (без utm и т.п.)",
        ),
        sa.Column(
            "dedup_key",
            sa.Text(),
            nullable=False,
            comment="Ключ дедупликации внутри темы: prefer strong id, иначе url, иначе fp, должен устанавливаться ретривером",
        ),
        sa.Column(
            "fingerprint",
            sa.Text(),
            nullable=False,
            comment="Fallback-хэш для дедупа и поиска кандидатов, считается внутри темы",
        ),
        sa.Column(
            "identifiers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Нормализованные идентификаторы (doi, patent_number, etc.) как массив объектов {scheme,value,is_primary}",
        ),
        sa.Column(
            "matched_terms",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Термы/слова, которые совпали при поиске и привели к попаданию кванта в выдачу (для фильтра на фронте)",
        ),
        sa.Column(
            "matched_term_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="ID термов темы (если в теме есть справочник термов); для точной фильтрации",
        ),
        sa.Column(
            "retriever_query",
            sa.Text(),
            nullable=True,
            comment="Реальная строка запроса, отправленная ретривером во внешний источник",
        ),
        sa.Column(
            "rank_score",
            sa.Float(precision=53),
            nullable=True,
            comment="Оценка релевантности/ранга из источника",
        ),
        sa.Column(
            "source_system",
            sa.Text(),
            nullable=False,
            comment="Система-источник (OpenAlex, Lens, Web, ...)",
        ),
        sa.Column(
            "site_id",
            sa.UUID(),
            nullable=True,
            comment="сайт, с которого эта ссылка (опционально)",
        ),
        sa.Column(
            "retriever_name",
            sa.Text(),
            nullable=False,
            comment="Имя ретривера/модуля, который сформировал квант",
        ),
        sa.Column(
            "retriever_version",
            sa.Text(),
            nullable=True,
            comment="Версия ретривера (опционально)",
        ),
        sa.Column(
            "retrieved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Когда квант был получен из источника",
        ),
        sa.Column(
            "attrs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Расширяемые поля (типоспецифичные данные) без миграций",
        ),
        sa.Column(
            "raw_payload_ref",
            sa.UUID(),
            nullable=True,
            comment="Ссылка на сырой payload (если вынесен в отдельную таблицу/хранилище)",
        ),
        sa.Column(
            "content_ref",
            sa.Text(),
            nullable=True,
            comment="Ссылка на извлеченный контент (MinIO key / internal path)",
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="active",
            comment="Служебный статус: active|duplicate|rejected|error",
        ),
        sa.Column(
            "duplicate_of_id",
            sa.UUID(),
            nullable=True,
            comment="Если квант признан дублем, ссылка на мастер-квант",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Создано в БД",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Обновлено в БД",
        ),
        sa.CheckConstraint(
            "status IN ('active','duplicate','rejected','error')",
            name="ck_theme_quanta_status",
        ),
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
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_of_id"],
            ["theme_quanta.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "theme_id",
            "dedup_key",
            name="uq_theme_quanta_theme_id_dedup_key",
        ),
        comment="Кванты информации внутри темы (атомарные, проверяемые кликом единицы знания)",
    )

    # 3) Indexes
    op.create_index(
        "idx_theme_quanta_theme_kind",
        "theme_quanta",
        ["theme_id", "entity_kind"],
        unique=False,
    )
    op.create_index(
        "idx_theme_quanta_theme_published",
        "theme_quanta",
        ["theme_id", "date_at"],
        unique=False,
        postgresql_ops={"date_at": "DESC"},
    )
    op.create_index(
        "idx_theme_quanta_theme_retrieved",
        "theme_quanta",
        ["theme_id", "retrieved_at"],
        unique=False,
        postgresql_ops={"retrieved_at": "DESC"},
    )
    op.create_index(
        "idx_theme_quanta_fingerprint",
        "theme_quanta",
        ["theme_id", "fingerprint"],
        unique=False,
    )
    op.create_index(
        "gin_theme_quanta_matched_term_ids",
        "theme_quanta",
        ["matched_term_ids"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "gin_theme_quanta_attrs",
        "theme_quanta",
        ["attrs"],
        unique=False,
        postgresql_using="gin",
    )

    # 4) Explicit comments (COMMENT ON COLUMN)
    # (Column comments via create_table are kept too; this makes it deterministic.)
    column_comments: dict[str, str] = {
        "id": "Primary key квантa",
        "theme_id": "Тема-владелец, изолированная зона знаний",
        "run_id": "Идентификатор прогона поиска (опционально)",
        "entity_kind": "Класс кванта (тип сущности)",
        "title": "Заголовок/название объекта",
        "summary_text": "Короткое текстовое описание (snippet/abstract/lead), используется для UX и AI анализа",
        "key_points": "Ключевые пункты (список строк), могут быть из источника или derived",
        "language": "Язык контента (ru/en/...)",
        "date_at": "Дата публикации/выхода объекта",
        "verification_url": "Кликабельная ссылка для проверки существования (повышает доверие)",
        "canonical_url": "Канонический URL после нормализации (без utm и т.п.)",
        "dedup_key": "Ключ дедупликации внутри темы: prefer strong id, иначе url, иначе fp, должен устанавливаться ретривером",
        "fingerprint": "Fallback-хэш для дедупа и поиска кандидатов, считается внутри темы",
        "identifiers": "Нормализованные идентификаторы (doi, patent_number, etc.) как массив объектов {scheme,value,is_primary}",
        "matched_terms": "Термы/слова, которые совпали при поиске и привели к попаданию кванта в выдачу (для фильтра на фронте)",
        "matched_term_ids": "ID термов темы (если в теме есть справочник термов); для точной фильтрации",
        "retriever_query": "Реальная строка запроса, отправленная ретривером во внешний источник",
        "rank_score": "Оценка релевантности/ранга из источника",
        "source_system": "Система-источник (OpenAlex, Lens, Web, ...)",
        "site_id": "сайт, с которого эта ссылка (опционально)",
        "retriever_name": "Имя ретривера/модуля, который сформировал квант",
        "retriever_version": "Версия ретривера (опционально)",
        "retrieved_at": "Когда квант был получен из источника",
        "attrs": "Расширяемые поля (типоспецифичные данные) без миграций",
        "raw_payload_ref": "Ссылка на сырой payload (если вынесен в отдельную таблицу/хранилище)",
        "content_ref": "Ссылка на извлеченный контент (MinIO key / internal path)",
        "status": "Служебный статус: active|duplicate|rejected|error",
        "duplicate_of_id": "Если квант признан дублем, ссылка на мастер-квант",
        "created_at": "Создано в БД",
        "updated_at": "Обновлено в БД",
    }

    for col, comment in column_comments.items():
        # COMMENT ON не везде дружит с bind-параметрами, поэтому экранируем вручную.
        escaped = comment.replace("'", "''")
        op.execute(f"COMMENT ON COLUMN theme_quanta.{col} IS '{escaped}'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("gin_theme_quanta_attrs", table_name="theme_quanta")
    op.drop_index(
        "gin_theme_quanta_matched_term_ids",
        table_name="theme_quanta",
    )
    op.drop_index("idx_theme_quanta_fingerprint", table_name="theme_quanta")
    op.drop_index(
        "idx_theme_quanta_theme_retrieved",
        table_name="theme_quanta",
    )
    op.drop_index(
        "idx_theme_quanta_theme_published",
        table_name="theme_quanta",
    )
    op.drop_index(
        "idx_theme_quanta_theme_kind",
        table_name="theme_quanta",
    )

    op.drop_table("theme_quanta")

    enum_name = "quantum_entity_kind"
    quantum_kind_enum = postgresql.ENUM(
        "publication",
        "patent",
        "webpage",
        name=enum_name,
    )
    quantum_kind_enum.drop(op.get_bind(), checkfirst=True)
