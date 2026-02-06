"""SQLAlchemy-модель для сущностей по теме (организации, персоны, технологии и т.п.)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Entity(Base):
    """
    Сущности по теме (кто/что): организации, персоны, технологии, продукты,
    страны, документы. Канонизация: одна сущность = множество алиасов.
    Поддержка retention/compaction (hot/warm/cold).
    """

    __tablename__ = "entities"
    __table_args__ = (
        Index(
            "ix_entities_theme_id_active",
            "theme_id",
            "created_at",
            postgresql_where=text("deleted_at IS NULL AND status = 'active'"),
            postgresql_ops={"created_at": "DESC"},
        ),
        Index(
            "uq_entities_theme_type_normalized",
            "theme_id",
            "entity_type",
            "normalized_name",
            unique=True,
            postgresql_where=text(
                "deleted_at IS NULL AND status = 'active'"
            ),
        ),
        {"comment": "Сущности по теме (канонические имена, алиасы, типы) с поддержкой compaction"},
    )

    # --- Идентификация и связи ---
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
        comment="Запуск (search_runs), в рамках которого сущность была впервые обнаружена или обновлена.",
    )

    # --- Канонизация ---
    canonical_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Каноническое (основное) имя сущности.",
    )
    normalized_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Нормализованная форма canonical_name (lowercase, без лишних символов) для дедупликации.",
    )
    fingerprint: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        index=True,
        comment="Отпечаток сущности для дедупликации (например хэш от normalized_name + entity_type).",
    )
    entity_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="other",
        comment="Тип сущности: person / org / product / tech / country / document / regulation / other.",
    )

    # --- Алиасы и идентификаторы ---
    aliases: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Алиасы/варианты имен (список строк или объектов с полями value/source/confidence).",
    )
    external_ids: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Внешние идентификаторы (wikidata, isin, inn, ticker, doi и т.д.), если извлекли.",
    )
    homepage_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Официальный сайт/домашняя страница (если применимо).",
    )

    # --- Описание и свойства ---
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Краткое описание сущности.",
    )
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Произвольные атрибуты (отрасль, роль, технологии, география и т.п.).",
    )
    tags: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Теги/категории (для UI и фильтров).",
    )

    # --- Качество/важность ---
    importance: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 3),
        nullable=True,
        comment="Важность сущности для темы (например 0..1).",
    )
    confidence: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 3),
        nullable=True,
        comment="Уверенность канонизации/извлечения (например 0..1).",
    )
    relevance_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 3),
        nullable=True,
        comment="Релевантность сущности теме (если используется).",
    )

    # --- Происхождение и трассировка ---
    extracted_from: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="ai",
        comment="Происхождение сущности: ai / user / imported.",
    )
    provider: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Провайдер/пайплайн извлечения (название модели/шагов), если нужно.",
    )
    provider_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Сырые данные извлечения/трассировки (промпт-мета, промежуточные результаты и т.п.).",
    )

    # --- Статус и управление ---
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="active",
        comment="Статус сущности: active / merged / deprecated / duplicate.",
    )
    merged_into_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Если сущность слита (merged), ссылка на сущность-приёмник.",
    )
    is_user_pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Закреплено пользователем как ключевая сущность.",
    )

    # --- Частотность/агрегации ---
    mention_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Сколько раз сущность упоминалась (агрегат, обновляется пайплайном).",
    )
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда сущность впервые появилась в источниках/событиях.",
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Когда сущность последний раз встречалась (для определения актуальности).",
    )

    # --- UI/прочитанность/заметки ---
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда пользователь просмотрел сущность (для подсветки непрочитанного).",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Заметки пользователя по сущности.",
    )

    # --- Compaction/Retention ---
    storage_tier: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="hot",
        comment="Слой хранения: hot / warm / cold.",
    )
    is_compacted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Признак, что сущность была уплотнена.",
    )
    compacted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда выполнена компактация.",
    )
    description_deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда очищено поле description (если удалено).",
    )
    compact_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Архивная краткая версия описания сущности.",
    )
    compact_meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Метаданные компактации (что очищено, правила, размеры).",
    )

    # --- Технические поля ---
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
