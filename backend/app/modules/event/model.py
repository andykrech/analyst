"""SQLAlchemy-модели событий (MVP, Event = hyperedge).

Упрощённая архитектура:
- глобальные справочники сюжетов (`event_plots`) и ролей (`event_roles`);
- минимальная таблица событий (`events`) с текстовым представлением предиката
  и произвольными атрибутами в `attributes_json`;
- таблица участников (`event_participants`) для связи событие–сущность–роль.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.entity.model import Cluster


class EventPlot(Base):
    """Лёгкий глобальный справочник сюжетов событий."""

    __tablename__ = "event_plots"
    __table_args__ = (
        UniqueConstraint("code", name="uq_event_plots_code"),
        Index("idx_event_plots_code", "code"),
        {"comment": "Глобальный справочник сюжетов событий (action/change/relation/statement и др.)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор сюжета события.",
    )
    code: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Уникальный код сюжета (например action/change/relation/statement).",
    )
    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Краткое отображаемое имя сюжета.",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Описание сюжета и его типичного использования.",
    )
    schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment=(
            "Схема сюжета с определением возможных ролей, обязательных ролей, "
            "ролей, для которых возможны атрибуты."
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата/время создания записи сюжета.",
    )

    events: Mapped[list["Event"]] = relationship(
        "Event",
        back_populates="plot",
    )


class EventRole(Base):
    """Лёгкий глобальный справочник ролей участников событий."""

    __tablename__ = "event_roles"
    __table_args__ = (
        UniqueConstraint("code", name="uq_event_roles_code"),
        Index("idx_event_roles_code", "code"),
        {"comment": "Глобальный справочник ролей участников событий."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор роли участника события.",
    )
    code: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Уникальный код роли (например actor/target/source/subject/object/etc.).",
    )
    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Краткое отображаемое имя роли.",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Описание роли и примеры её использования.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата/время создания записи роли.",
    )

    participants: Mapped[list["EventParticipant"]] = relationship(
        "EventParticipant",
        back_populates="role",
    )


class Event(Base):
    """Event mention, извлечённый из одного кванта, в контексте темы."""

    __tablename__ = "events"
    __table_args__ = (
        Index("idx_events_theme_id", "theme_id"),
        Index("idx_events_plot_id", "plot_id"),
        Index("idx_events_predicate_normalized", "predicate_normalized"),
        {
            "comment": (
                "Event mention, извлечённый из одного кванта: "
                "привязан к теме и сюжету, с нормализованным предикатом и атрибутами."
            )
        },
    )

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
        comment="Тема (themes.id), в контексте которой зафиксировано событие.",
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Идентификатор запуска пайплайна, в рамках которого извлечено событие.",
    )
    plot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("event_plots.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Сюжет события (event_plots.id), к которому отнесён данный event mention.",
    )

    predicate_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Исходный текст предиката события (как он встретился в тексте/кванте).",
    )
    predicate_normalized: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Нормализованная форма предиката (для агрегации/аналитики).",
    )
    predicate_class: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Опциональный класс/тип предиката (например action/change/relation/statement).",
    )
    display_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Человекочитаемое описание события для UI.",
    )
    event_time: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Текстовое представление времени события (дата/период/словесное описание).",
    )

    attributes_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment=(
            "Массив атрибутов события в виде JSON. Каждый элемент: "
            '{"attribute_for": "subject|object|predicate|event", '
            '"attribute_text": "…", "attribute_normalized": "…" | null}.'
        ),
    )

    confidence: Mapped[Decimal | None] = mapped_column(
        Float,
        nullable=True,
        comment="Уверенность извлечения события (0..1).",
    )
    extraction_version: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Версия промпта/правил, по которым извлечено событие.",
    )

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
        comment="Дата/время последнего обновления записи события.",
    )

    plot: Mapped["EventPlot"] = relationship(
        "EventPlot",
        back_populates="events",
    )
    participants: Mapped[list["EventParticipant"]] = relationship(
        "EventParticipant",
        back_populates="event",
        cascade="all, delete-orphan",
    )


class EventParticipant(Base):
    """Участник события в нормализованной роли."""

    __tablename__ = "event_participants"
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "role_id",
            "entity_id",
            name="uq_event_participants_event_role_entity",
        ),
        Index("idx_event_participants_event_id", "event_id"),
        Index("idx_event_participants_role_id", "role_id"),
        Index("idx_event_participants_entity_id", "entity_id"),
        {
            "comment": (
                "Участники событий: связь событие–сущность–роль с возможностью фильтрации "
                "по событию, роли и сущности."
            )
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор участника события.",
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        comment="Идентификатор события (events.id), к которому относится участник.",
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("event_roles.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Идентификатор роли участника (event_roles.id).",
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clusters.id", ondelete="CASCADE"),
        nullable=False,
        comment="Идентификатор кластера сущности (clusters.id), являющейся участником события.",
    )
    confidence: Mapped[Decimal | None] = mapped_column(
        Float,
        nullable=True,
        comment="Уверенность в корректности связи event–entity–role (0..1).",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата/время создания записи участника события.",
    )

    event: Mapped["Event"] = relationship(
        "Event",
        back_populates="participants",
    )
    role: Mapped["EventRole"] = relationship(
        "EventRole",
        back_populates="participants",
    )
    cluster: Mapped["Cluster"] = relationship(
        "Cluster",
        foreign_keys=[entity_id],
    )
