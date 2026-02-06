"""SQLAlchemy-модель для связей между объектами внутри темы (полиморфные subject/object)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Relation(Base):
    """
    Связи между объектами внутри одной темы: event<->entity, event<->event,
    entity<->entity, event<->trend и т.д. Полиморфные ссылки через (type, id).
    """

    __tablename__ = "relations"
    __table_args__ = (
        Index(
            "ix_relations_theme_id_active",
            "theme_id",
            "created_at",
            postgresql_where=text("deleted_at IS NULL AND status = 'active'"),
            postgresql_ops={"created_at": "DESC"},
        ),
        Index(
            "uq_relations_theme_subject_relation_object",
            "theme_id",
            "subject_type",
            "subject_id",
            "relation_type",
            "object_type",
            "object_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND status = 'active'"),
        ),
        {"comment": "Связи между объектами внутри темы (subject -> object, полиморфные ссылки)"},
    )

    # --- Идентификация ---
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор связи.",
    )

    # --- Принадлежность ---
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Тема, внутри которой существует связь.",
    )

    # --- Субъект и объект (полиморфные ссылки, без FK) ---
    subject_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Тип субъекта связи: entity / event / digest / source_link / overview / trend / signal / scenario / subtopic / other.",
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Идентификатор субъекта (UUID соответствующей таблицы).",
    )
    object_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Тип объекта связи (те же значения, что и subject_type).",
    )
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Идентификатор объекта (UUID соответствующей таблицы).",
    )

    # --- Тип связи и свойства ---
    relation_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Тип связи: mentions / supports / similar / causes / part_of / contradicts / related / other.",
    )
    direction: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="forward",
        comment="Направление интерпретации: forward (subject->object) / bidirectional.",
    )
    weight: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 3),
        nullable=True,
        comment="Вес/сила связи (например 0..1).",
    )
    confidence: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 3),
        nullable=True,
        comment="Уверенность связи (например 0..1).",
    )

    # --- Объяснимость/доказательства ---
    explanation: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Короткое объяснение, почему связь существует.",
    )
    evidence: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Доказательства связи (например список source_link_id/event_id + фрагменты).",
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Запуск (search_runs), в рамках которого связь была создана/обновлена.",
    )

    # --- Статус ---
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="active",
        comment="Статус связи: active / deprecated / removed.",
    )
    is_user_created: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Связь создана пользователем вручную (не удалять автоматически).",
    )

    # --- Технические поля ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата/время создания связи.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Дата/время последнего изменения связи.",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Мягкое удаление связи.",
    )
