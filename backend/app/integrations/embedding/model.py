"""
SQLAlchemy-модель для таблицы embeddings (векторы релевантности, поиска, кластеризации).
"""

import uuid
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# ENUM-типы (уже созданы миграцией, create_type=False)
_embedding_object_type_enum = ENUM(
    "theme",
    "quantum",
    "entity",
    "event",
    "digest",
    "overview",
    name="embedding_object_type",
    create_type=False,
)
_embedding_kind_enum = ENUM(
    "relevance",
    "search",
    "clustering",
    name="embedding_kind",
    create_type=False,
)


class Embedding(Base):
    """
    Запись эмбеддинга: вектор для объекта (тема, квант, сущность и т.д.)
    с типом (relevance/search/clustering) и хешем текста для актуальности.
    """

    __tablename__ = "embeddings"
    __table_args__ = (
        {"comment": "Векторные эмбеддинги объектов для семантического поиска и кластеризации"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор записи embedding",
    )
    theme_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Идентификатор темы; обязателен для theme-scoped объектов",
    )
    object_type: Mapped[str] = mapped_column(
        _embedding_object_type_enum,
        nullable=False,
        comment="Тип объекта, к которому относится embedding",
    )
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Идентификатор объекта внутри своей таблицы",
    )
    embedding_kind: Mapped[str] = mapped_column(
        _embedding_kind_enum,
        nullable=False,
        comment="Тип семантического представления (relevance, search, clustering)",
    )
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Название модели embedding",
    )
    dims: Mapped[int] = mapped_column(
        nullable=False,
        comment="Размерность вектора",
    )
    embedding: Mapped[list[float]] = mapped_column(
        Vector(1536),
        nullable=False,
        comment="Вектор эмбеддинга (pgvector)",
    )
    text_hash: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="Хеш текста, на основе которого построен embedding",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата создания embedding",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Дата последнего обновления embedding",
    )
