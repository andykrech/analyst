"""SQLAlchemy-модели для горячих сущностей и их алиасов по теме."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Entity(Base):
    """Горячие сущности по теме (минимальные поля для дедупа, списков и агрегаций)."""

    __tablename__ = "entities"
    __table_args__ = (
        Index(
            "uq_entities_theme_type_normalized_active",
            "theme_id",
            "entity_type",
            "normalized_name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND status = 'active'"),
            info={
                "comment": (
                    "Уникальность сущностей внутри темы по типу и нормализованному имени "
                    "(только active и не удалённые)."
                )
            },
        ),
        Index(
            "ix_entities_theme_id_active",
            "theme_id",
            "created_at",
            postgresql_where=text("deleted_at IS NULL AND status = 'active'"),
            postgresql_ops={"created_at": "DESC"},
            info={
                "comment": (
                    "Быстрый выбор активных сущностей по теме (для списков/UI)."
                )
            },
        ),
        {
            "comment": (
                "Горячие сущности по теме (минимальные поля для дедупа, списков и агрегаций)."
            ),
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор сущности.",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Идентификатор темы, к которой относится сущность.",
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment=(
            "Идентификатор запуска (search_runs), в рамках которого сущность впервые "
            "обнаружена или обновлена."
        ),
    )
    entity_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="other",
        comment=(
            "Тип сущности: person/org/tech/product/country/document/regulation/other."
        ),
    )
    canonical_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment=(
            "Каноническое имя (display name) — то, что показываем пользователю "
            "(может быть на языке темы)."
        ),
    )
    normalized_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment=(
            "Нормализованное имя для дедупликации (ключ уникальности; например англ. "
            "pivot normalized)."
        ),
    )
    fingerprint: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        index=True,
        comment=(
            "Отпечаток для дедупликации (например хэш от normalized_name + entity_type)."
        ),
    )
    mention_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment=(
            "Сколько раз сущность упоминалась (агрегат, обновляется пайплайном)."
        ),
    )
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда сущность впервые появилась в источниках/квантах.",
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment=(
            "Когда сущность последний раз встречалась (для определения актуальности)."
        ),
    )
    importance: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Важность сущности для темы (например 0..1).",
    )
    confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment=(
            "Уверенность извлечения/канонизации сущности (например 0..1)."
        ),
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="active",
        comment="Статус сущности: active/merged/deprecated/duplicate.",
    )
    is_user_pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Закреплено пользователем как ключевая сущность.",
    )
    is_name_translated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Флаг, было ли переведено наименование сущности.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата/время создания записи сущности.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Дата/время последнего изменения записи сущности.",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Мягкое удаление сущности (soft delete).",
    )


class EntityAlias(Base):
    """Алиасы сущностей по теме (для резолва кандидатов и поиска)."""

    __tablename__ = "entity_aliases"
    __table_args__ = (
        Index(
            "ix_entity_aliases_lookup",
            "theme_id",
            "entity_type",
            "alias_value",
            info={
                "comment": (
                    "Быстрый поиск сущности по алиасу в рамках темы и типа."
                )
            },
        ),
        UniqueConstraint(
            "entity_id",
            "alias_value",
            name="uq_entity_aliases_entity_alias",
            info={
                "comment": (
                    "Запрет дублей: один и тот же алиас не должен повторяться у одной сущности."
                )
            },
        ),
        {
            "comment": (
                "Алиасы сущностей по теме (для резолва кандидатов и поиска)."
            ),
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор алиаса.",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=(
            "Идентификатор темы (денормализация для быстрого поиска алиасов без join)."
        ),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Идентификатор сущности, которой принадлежит алиас.",
    )
    entity_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
        comment=(
            "Тип сущности (денормализация для ускорения резолва по алиасу)."
        ),
    )
    alias_value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment=(
            "Значение алиаса (считается уже нормализованным; используется для поиска кандидатов)."
        ),
    )
    lang: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Язык алиаса (например en/ru/ja/und).",
    )
    kind: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="surface",
        comment=(
            "Вид алиаса: surface/acronym/pivot/translation/spelling/user."
        ),
    )
    confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Уверенность в корректности алиаса (например 0..1).",
    )
    source: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="ai",
        comment="Источник алиаса: ai/user/import/pattern.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата/время добавления алиаса.",
    )
