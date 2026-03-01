"""Add embeddings table with ENUMs and pgvector

Revision ID: g2h3i4j5k6l7
Revises: a8b9c0d1e2f3
Create Date: 2026-02-26

Таблица эмбеддингов: векторы для theme/quantum/entity/event/digest/overview
с типами relevance/search/clustering и HNSW-индексом для ANN-поиска.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "g2h3i4j5k6l7"
down_revision: Union[str, Sequence[str], None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) ENUM embedding_object_type (безопасное создание)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'embedding_object_type') THEN
                CREATE TYPE embedding_object_type AS ENUM (
                    'theme', 'quantum', 'entity', 'event', 'digest', 'overview'
                );
            END IF;
        END$$;
        """
    )

    # 2) ENUM embedding_kind (безопасное создание)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'embedding_kind') THEN
                CREATE TYPE embedding_kind AS ENUM (
                    'relevance', 'search', 'clustering'
                );
            END IF;
        END$$;
        """
    )

    # 3) Таблица embeddings (колонка vector — через raw SQL из-за pgvector)
    op.create_table(
        "embeddings",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор записи embedding",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=True,
            comment="Идентификатор темы; обязателен для theme-scoped объектов",
        ),
        sa.Column(
            "object_type",
            postgresql.ENUM(
                "theme",
                "quantum",
                "entity",
                "event",
                "digest",
                "overview",
                name="embedding_object_type",
                create_type=False,
            ),
            nullable=False,
            comment="Тип объекта, к которому относится embedding",
        ),
        sa.Column(
            "object_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор объекта внутри своей таблицы",
        ),
        sa.Column(
            "embedding_kind",
            postgresql.ENUM(
                "relevance",
                "search",
                "clustering",
                name="embedding_kind",
                create_type=False,
            ),
            nullable=False,
            comment="Тип семантического представления (relevance, search, clustering)",
        ),
        sa.Column(
            "model",
            sa.String(100),
            nullable=False,
            comment="Название модели embedding (например text-embedding-3-small или text-embedding-3-large)",
        ),
        sa.Column(
            "dims",
            sa.Integer(),
            nullable=False,
            comment="Размерность вектора (например 1536 или 3072)",
        ),
        sa.Column(
            "text_hash",
            sa.String(128),
            nullable=True,
            comment="Хеш текста, на основе которого был построен embedding (для контроля актуальности)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата создания embedding",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата последнего обновления embedding",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "theme_id",
            "object_type",
            "object_id",
            "embedding_kind",
            "model",
            name="uq_embeddings_theme_object_kind_model",
        ),
        comment="Векторные эмбеддинги объектов (темы, кванты, сущности, события и т.д.) для семантического поиска и кластеризации",
    )

    # Колонка embedding (pgvector) — не поддерживается стандартным SQLAlchemy, добавляем через SQL
    op.execute(
        """
        ALTER TABLE embeddings
        ADD COLUMN embedding vector(1536) NOT NULL;
        """
    )
    # Размещаем колонку между dims и text_hash для соответствия спецификации (в PG порядок задаётся при создании; после ADD колонка в конце — комментарий оставим)
    op.execute(
        "COMMENT ON COLUMN embeddings.embedding IS 'Вектор эмбеддинга (pgvector, размерность 1536 по умолчанию)';"
    )

    # 4) Индексы
    op.create_index(
        "ix_embeddings_object_type_object_id",
        "embeddings",
        ["object_type", "object_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_embeddings_theme_id"),
        "embeddings",
        ["theme_id"],
        unique=False,
    )
    # HNSW для ANN-поиска (cosine distance)
    op.execute(
        """
        CREATE INDEX ix_embeddings_embedding_hnsw
        ON embeddings
        USING hnsw (embedding vector_cosine_ops);
        """
    )

    # 5) Комментарии к колонкам (комментарий к таблице задан в create_table)
    op.execute("COMMENT ON COLUMN embeddings.id IS 'Уникальный идентификатор записи embedding';")
    op.execute("COMMENT ON COLUMN embeddings.theme_id IS 'Идентификатор темы; обязателен для theme-scoped объектов';")
    op.execute("COMMENT ON COLUMN embeddings.object_type IS 'Тип объекта, к которому относится embedding';")
    op.execute("COMMENT ON COLUMN embeddings.object_id IS 'Идентификатор объекта внутри своей таблицы';")
    op.execute("COMMENT ON COLUMN embeddings.embedding_kind IS 'Тип семантического представления (relevance, search, clustering)';")
    op.execute("COMMENT ON COLUMN embeddings.model IS 'Название модели embedding (например text-embedding-3-small или text-embedding-3-large)';")
    op.execute("COMMENT ON COLUMN embeddings.dims IS 'Размерность вектора (например 1536 или 3072)';")
    op.execute("COMMENT ON COLUMN embeddings.text_hash IS 'Хеш текста, на основе которого был построен embedding (для контроля актуальности)';")
    op.execute("COMMENT ON COLUMN embeddings.created_at IS 'Дата создания embedding';")
    op.execute("COMMENT ON COLUMN embeddings.updated_at IS 'Дата последнего обновления embedding';")


def downgrade() -> None:
    op.drop_index("ix_embeddings_embedding_hnsw", table_name="embeddings")
    op.drop_index(op.f("ix_embeddings_theme_id"), table_name="embeddings")
    op.drop_index("ix_embeddings_object_type_object_id", table_name="embeddings")
    op.drop_table("embeddings")
    op.execute("DROP TYPE IF EXISTS embedding_kind")
    op.execute("DROP TYPE IF EXISTS embedding_object_type")
