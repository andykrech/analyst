"""SQLAlchemy-модель квантов информации (theme_quanta)."""

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Enum as SAEnum

from app.db.base import Base


class QuantumEntityKind(str, enum.Enum):
    """Тип сущности кванта (строго фиксированный enum в Postgres)."""

    publication = "publication"
    patent = "patent"
    webpage = "webpage"


class Quantum(Base):
    """
    Квант информации — атомарная, проверяемая кликом единица знания внутри темы.
    Кванты не переиспользуются между темами.
    """

    __tablename__ = "theme_quanta"
    __table_args__ = (
        UniqueConstraint(
            "theme_id",
            "dedup_key",
            name="uq_theme_quanta_theme_id_dedup_key",
        ),
        CheckConstraint(
            "status IN ('active','duplicate','rejected','error')",
            name="ck_theme_quanta_status",
        ),
        Index("idx_theme_quanta_theme_kind", "theme_id", "entity_kind"),
        Index(
            "idx_theme_quanta_theme_published",
            "theme_id",
            "date_at",
            postgresql_ops={"date_at": "DESC"},
        ),
        Index(
            "idx_theme_quanta_theme_retrieved",
            "theme_id",
            "retrieved_at",
            postgresql_ops={"retrieved_at": "DESC"},
        ),
        Index("idx_theme_quanta_fingerprint", "theme_id", "fingerprint"),
        Index(
            "gin_theme_quanta_matched_term_ids",
            "matched_term_ids",
            postgresql_using="gin",
        ),
        Index(
            "gin_theme_quanta_attrs",
            "attrs",
            postgresql_using="gin",
        ),
        {"comment": "Кванты информации внутри темы (атомарные, проверяемые кликом единицы знания)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Primary key квантa",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Тема-владелец, изолированная зона знаний",
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Идентификатор прогона поиска (опционально)",
    )

    entity_kind: Mapped[QuantumEntityKind] = mapped_column(
        SAEnum(QuantumEntityKind, name="quantum_entity_kind"),
        nullable=False,
        comment="Класс кванта (тип сущности)",
    )

    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Заголовок/название объекта",
    )
    summary_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Короткое текстовое описание (snippet/abstract/lead), используется для UX и AI анализа",
    )
    key_points: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Ключевые пункты (список строк), могут быть из источника или derived",
    )
    language: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Язык контента (ru/en/...)",
    )
    date_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата публикации/выхода объекта",
    )

    verification_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Кликабельная ссылка для проверки существования (повышает доверие)",
    )
    canonical_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Канонический URL после нормализации (без utm и т.п.)",
    )

    dedup_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Ключ дедупликации внутри темы: prefer strong id, иначе url, иначе fp, должен устанавливаться ретривером",
    )
    fingerprint: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Fallback-хэш для дедупа и поиска кандидатов, считается внутри темы",
    )

    identifiers: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Нормализованные идентификаторы (doi, patent_number, etc.) как массив объектов {scheme,value,is_primary}",
    )
    matched_terms: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Термы/слова, которые совпали при поиске и привели к попаданию кванта в выдачу (для фильтра на фронте)",
    )
    matched_term_ids: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="ID термов темы (если в теме есть справочник термов); для точной фильтрации",
    )

    retriever_query: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Реальная строка запроса, отправленная ретривером во внешний источник",
    )
    rank_score: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="Оценка релевантности/ранга из источника",
    )

    source_system: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Система-источник (OpenAlex, Lens, Web, ...)",
    )
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="сайт, с которого эта ссылка (опционально)",
    )

    retriever_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Имя ретривера/модуля, который сформировал квант",
    )
    retriever_version: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Версия ретривера (опционально)",
    )
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Когда квант был получен из источника",
    )

    attrs: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Расширяемые поля (типоспецифичные данные) без миграций",
    )
    raw_payload_ref: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Ссылка на сырой payload (если вынесен в отдельную таблицу/хранилище)",
    )
    content_ref: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Ссылка на извлеченный контент (MinIO key / internal path)",
    )

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="active",
        comment="Служебный статус: active|duplicate|rejected|error",
    )
    duplicate_of_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("theme_quanta.id", ondelete="SET NULL"),
        nullable=True,
        comment="Если квант признан дублем, ссылка на мастер-квант",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Создано в БД",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Обновлено в БД",
    )

