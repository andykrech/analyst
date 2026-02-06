"""SQLAlchemy-модели для событий и связей с источниками, дайджестами и сущностями."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.modules.digest.model import Digest
    from app.modules.source_link.model import SourceLink


class Event(Base):
    """
    Структурированные события по теме: что произошло, с временной привязкой,
    типом, формулировкой, уверенностью и ссылками на доказательства.
    """

    __tablename__ = "events"
    __table_args__ = (
        Index(
            "ix_events_theme_id_active",
            "theme_id",
            "created_at",
            postgresql_where=text("deleted_at IS NULL AND status = 'active'"),
            postgresql_ops={"created_at": "DESC"},
        ),
        Index(
            "uq_events_theme_id_fingerprint",
            "theme_id",
            "fingerprint",
            unique=True,
            postgresql_where=text(
                "fingerprint IS NOT NULL AND deleted_at IS NULL"
            ),
        ),
        {"comment": "Структурированные события по теме с привязкой к источникам и дайджестам"},
    )

    # --- Идентификация и связи ---
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор события.",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Тема, к которой относится событие.",
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Запуск обработки, в рамках которого событие было извлечено/обновлено.",
    )

    # --- Суть события ---
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Короткая формулировка события (1 строка).",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Расширенное описание события (как ИИ интерпретировал факт).",
    )
    event_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="other",
        comment="Тип события: regulatory / market / technology / finance / incident / litigation / product / other.",
    )

    # --- Временная привязка ---
    occurred_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Момент события (если известен точно).",
    )
    occurred_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Начало интервала события (если известно как период).",
    )
    occurred_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Конец интервала события (если известно как период).",
    )
    timezone_hint: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Подсказка по часовому поясу источника/события (если актуально).",
    )

    # --- Качество и управляемость ---
    importance: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 3),
        nullable=True,
        comment="Важность события (0..1 или иной масштаб), если используется.",
    )
    confidence: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 3),
        nullable=True,
        comment="Уверенность извлечения/интерпретации события (0..1), если используется.",
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="active",
        comment="Статус события: active / superseded / retracted / duplicate.",
    )
    is_user_pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Закреплено пользователем как важное событие (исключение из авто-очистки/пересборки).",
    )

    # --- Нормализация/дедупликация и происхождение ---
    fingerprint: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        index=True,
        comment="Отпечаток события для дедупликации (хэш от нормализованного title+time+key entities).",
    )
    extracted_from: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="ai",
        comment="Источник формирования: ai / user / imported (на будущее).",
    )
    provider_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Сырые данные извлечения (подсказки модели, промпт-мета, intermediate), для трассировки.",
    )

    # --- Структура участников ---
    participants: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Участники события в структурированном виде (имя/тип/роль/ссылки на канонические сущности когда появятся).",
    )

    # --- Кэш связей (источник истины — связующие таблицы) ---
    source_link_ids: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Кэш списка связанных source_link_id (ускорение), первично хранится в event_source_links.",
    )
    digest_ids: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Кэш списка связанных digest_id (ускорение), первично хранится в event_digests.",
    )

    # --- UI/прочитанность ---
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда пользователь просмотрел событие (для подсветки непрочитанного).",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Заметки пользователя по событию.",
    )

    # --- Технические поля ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата/время создания записи события.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Дата/время последнего изменения события.",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Мягкое удаление (soft delete).",
    )

    # --- Связи ---
    event_source_links: Mapped[list["EventSourceLink"]] = relationship(
        "EventSourceLink",
        back_populates="event",
        cascade="all, delete-orphan",
    )
    event_digest_links: Mapped[list["EventDigestLink"]] = relationship(
        "EventDigestLink",
        back_populates="event",
        cascade="all, delete-orphan",
    )
    event_entity_links: Mapped[list["EventEntityLink"]] = relationship(
        "EventEntityLink",
        back_populates="event",
        cascade="all, delete-orphan",
    )


class EventSourceLink(Base):
    """
    Связь события с источниками: какими источниками подтверждается событие + роль.
    """

    __tablename__ = "event_source_links"
    __table_args__ = (
        Index("ix_event_source_links_event_id_role", "event_id", "role"),
        {"comment": "Какими источниками подтверждается событие + роль источника"},
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Ссылка на событие.",
    )
    source_link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_links.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Ссылка на источник (документ/URL).",
    )
    role: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="evidence",
        comment="Роль источника: evidence / mention / background / counterpoint / other.",
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Когда источник был привязан к событию.",
    )
    quote: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Короткая цитата/фрагмент из источника, подтверждающий событие.",
    )
    score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 3),
        nullable=True,
        comment="Сила доказательства/релевантность источника этому событию.",
    )

    event: Mapped["Event"] = relationship("Event", back_populates="event_source_links")
    source_link: Mapped["SourceLink"] = relationship(
        "SourceLink",
        back_populates="event_source_links",
    )


class EventDigestLink(Base):
    """
    Связь события с дайджестами: в каких дайджестах фигурировало событие и в каком качестве.
    """

    __tablename__ = "event_digests"
    __table_args__ = (
        Index("ix_event_digests_digest_id_role", "digest_id", "role"),
        Index("ix_event_digests_digest_id_rank", "digest_id", "rank"),
        {"comment": "В каких дайджестах фигурировало событие (и в каком качестве)"},
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Ссылка на событие.",
    )
    digest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("digests.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Ссылка на дайджест.",
    )
    role: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="mentioned",
        comment="Роль события в дайджесте: mentioned / key / highlight / other.",
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Когда событие было связано с дайджестом.",
    )
    rank: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Порядок/ранг события внутри дайджеста (если нужно).",
    )

    event: Mapped["Event"] = relationship("Event", back_populates="event_digest_links")
    digest: Mapped["Digest"] = relationship(
        "Digest",
        back_populates="event_digest_links",
    )


class EventEntityLink(Base):
    """
    Связь события с сущностями по каноническому имени (entity_id — на будущее).
    """

    __tablename__ = "event_entities"
    __table_args__ = (
        Index("ix_event_entities_entity_name", "entity_name"),
        Index("ix_event_entities_event_id_role", "event_id", "role"),
        {"comment": "Связь событий с сущностями (по имени; entity_id — для будущей нормализации)"},
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Ссылка на событие.",
    )
    entity_name: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        comment="Каноническое имя сущности (используется сейчас для связи без таблицы entities).",
    )
    role: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        server_default="participant",
        comment="Роль сущности в событии: initiator / target / regulator / affected / partner / other.",
    )
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Ссылка на сущность (будущая нормализация), пока может быть NULL.",
    )
    entity_type: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Тип сущности: person / org / product / tech / country / doc / other.",
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Когда сущность была связана с событием.",
    )
    confidence: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 3),
        nullable=True,
        comment="Уверенность извлечения связи (0..1), если используется.",
    )

    event: Mapped["Event"] = relationship("Event", back_populates="event_entity_links")
