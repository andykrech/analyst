"""SQLAlchemy-модели для событий (Event = hyperedge): events, роли, участники, сюжеты, атрибуты."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.modules.theme.model import Theme
    from app.modules.user.model import User


class Event(Base):
    """
    Событие (hyperedge) — контейнер, привязанный к теме.
    Участники, роли, сюжеты и атрибуты будут в отдельных таблицах на следующих шагах.
    """

    __tablename__ = "events"
    __table_args__ = (
        # idx_events_theme_created_at: список событий по теме по дате создания (новые сверху)
        Index(
            "idx_events_theme_created_at",
            "theme_id",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        # idx_events_theme_occurred_at: события по теме по времени наступления (хронология)
        Index(
            "idx_events_theme_occurred_at",
            "theme_id",
            "occurred_at",
            postgresql_ops={"occurred_at": "DESC"},
        ),
        # idx_events_plot_status: фильтрация по статусу классификации сюжета
        Index(
            "idx_events_plot_status",
            "theme_id",
            "plot_status",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        # idx_events_run_id: события, извлечённые в рамках конкретного запуска пайплайна
        Index("idx_events_run_id", "run_id"),
        # idx_events_plot_proposed_payload_gin: поиск/фильтрация по jsonb предложенного сюжета
        Index(
            "idx_events_plot_proposed_payload_gin",
            "plot_proposed_payload",
            postgresql_using="gin",
        ),
        {"comment": "События по теме; участники/роли/сюжеты — в следующих шагах"},
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
        nullable=True,
        comment="Запуск пайплайна, в рамках которого событие извлечено; FK опционально позже.",
    )

    # --- Время события ---
    occurred_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Точное или примерное время события (одна точка).",
    )
    occurred_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Начало интервала события (если известно как период).",
    )
    occurred_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Конец интервала события (если известно как период).",
    )
    time_precision: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Точность времени: exact / day / month / year / unknown.",
    )

    # --- Описание ---
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Короткое название события.",
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Расширенное описание события.",
    )

    # --- Качество ---
    confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Уверенность извлечения/интерпретации (0..1).",
    )
    importance: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Важность для пользователя (0..1).",
    )

    # --- Сюжет события (event_plot) ---
    plot_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("event_plots.id", ondelete="SET NULL"),
        nullable=True,
        comment="Ссылка на сюжет (event_plots.id).",
    )
    plot_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'unassigned'"),
        comment="Статус классификации сюжета: unassigned / assigned / needs_review / proposed.",
    )
    plot_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Уверенность отнесения к сюжету (0..1).",
    )
    plot_proposed_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Если LLM предложил новый сюжет — данные предложения (для ревью).",
    )

    # --- Жизненный цикл ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата/время создания записи.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Дата/время последнего изменения (обновляется приложением).",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Мягкое удаление (soft delete) на будущее.",
    )

    # --- Служебное ---
    extraction_version: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Версия логики/промпта извлечения событий.",
    )

    # --- Связи ---
    plot: Mapped[Optional["EventPlot"]] = relationship(
        "EventPlot",
        back_populates="events",
        foreign_keys=[plot_id],
    )
    participants: Mapped[list["EventParticipant"]] = relationship(
        "EventParticipant",
        back_populates="event",
        cascade="all, delete-orphan",
    )
    attributes: Mapped[list["EventAttribute"]] = relationship(
        "EventAttribute",
        back_populates="event",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# Словарь ролей участников (глобальный)
# ---------------------------------------------------------------------------


class EventRole(Base):
    """
    Фиксированный словарь ролей участников событий (универсальная «грамматика»).
    """

    __tablename__ = "event_roles"
    __table_args__ = (
        UniqueConstraint("code", name="uq_event_roles_code"),
        {"comment": "Словарь ролей участников событий (actor, target, cause, effect и т.д.)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор роли.",
    )
    code: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
        comment="Машинный код роли: actor/target/cause/effect/instrument/location/etc.",
    )
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Отображаемое имя роли.",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Пояснение, как использовать роль.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата/время создания записи.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Дата/время последнего изменения.",
    )

    participants: Mapped[list["EventParticipant"]] = relationship(
        "EventParticipant",
        back_populates="role",
    )


# ---------------------------------------------------------------------------
# Сюжеты событий (theme-scoped)
# ---------------------------------------------------------------------------


class EventPlot(Base):
    """
    Сюжеты событий в рамках темы. Пользователь одобряет/редактирует сюжеты внутри темы.
    """

    __tablename__ = "event_plots"
    __table_args__ = (
        UniqueConstraint("theme_id", "code", name="uq_event_plots_theme_id_code"),
        Index("idx_event_plots_theme_status", "theme_id", "status", "code"),
        Index(
            "idx_event_plots_theme_updated",
            "theme_id",
            "updated_at",
            postgresql_ops={"updated_at": "DESC"},
        ),
        Index("gin_event_plots_required_roles", "required_roles", postgresql_using="gin"),
        Index("gin_event_plots_allowed_attributes", "allowed_attributes", postgresql_using="gin"),
        {"comment": "Сюжеты событий в рамках темы (theme-scoped)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор сюжета.",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Тема, к которой относится сюжет.",
    )
    code: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Код сюжета уникален в рамках темы.",
    )
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Название сюжета.",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Описание сюжета.",
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'draft'"),
        comment="Статус сюжета: draft / approved / archived.",
    )
    required_roles: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Список обязательных ролей (по role.code), например ['actor','target'].",
    )
    optional_roles: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Список опциональных ролей.",
    )
    required_attributes: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Список обязательных атрибутов (по attribute_def.code).",
    )
    allowed_attributes: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Список разрешённых атрибутов.",
    )
    aliases: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Синонимы/варианты названия сюжета.",
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Пользователь, создавший сюжет.",
    )
    approved_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Пользователь, одобривший сюжет.",
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата/время одобрения.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата/время создания.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Дата/время последнего изменения.",
    )

    events: Mapped[list["Event"]] = relationship(
        "Event",
        back_populates="plot",
        foreign_keys=[Event.plot_id],
    )


# ---------------------------------------------------------------------------
# Словарь характеристик (theme-scoped)
# ---------------------------------------------------------------------------


class EventAttributeDef(Base):
    """
    Словарь характеристик событий (канонизация ключей), theme-scoped.
    """

    __tablename__ = "event_attribute_defs"
    __table_args__ = (
        UniqueConstraint("theme_id", "code", name="uq_event_attribute_defs_theme_id_code"),
        Index("idx_event_attr_defs_theme", "theme_id", "code"),
        {"comment": "Словарь характеристик событий в рамках темы"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор определения атрибута.",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Тема, к которой относится определение.",
    )
    code: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Канонический ключ атрибута: price/currency/stake_percent/value_before/etc.",
    )
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Отображаемое название атрибута.",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Пояснение к атрибуту.",
    )
    value_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Тип значения: number/text/bool/date/json.",
    )
    unit_kind: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'none'"),
        comment="Единица измерения: none/currency/percent/time/length/mass/temperature/etc.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата/время создания.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Дата/время последнего изменения.",
    )

    attribute_values: Mapped[list["EventAttribute"]] = relationship(
        "EventAttribute",
        back_populates="def_",
    )


# ---------------------------------------------------------------------------
# Участники события (hyperedge: сущность + роль)
# ---------------------------------------------------------------------------


class EventParticipant(Base):
    """
    Участник события (сущность + роль) — реализация hyperedge.
    """

    __tablename__ = "event_participants"
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "role_id",
            "entity_id",
            name="uq_event_participants_event_role_entity",
        ),
        Index("idx_event_participants_event", "event_id"),
        Index("idx_event_participants_entity_id", "entity_id"),
        Index("idx_event_participants_role", "role_id"),
        Index("idx_event_participants_entity_role", "entity_id", "role_id"),
        Index("idx_event_participants_event_role", "event_id", "role_id"),
        {"comment": "Участники события (связь событие–сущность–роль); не дублировать одну сущность в одной роли в рамках события."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор записи участника.",
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        comment="Событие.",
    )
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
        comment="Ссылка на сущность.",
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("event_roles.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Роль участника.",
    )
    confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Уверенность извлечения связи участника с ролью (0..1).",
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата/время добавления участника.",
    )

    event: Mapped["Event"] = relationship("Event", back_populates="participants")
    role: Mapped["EventRole"] = relationship("EventRole", back_populates="participants")


# ---------------------------------------------------------------------------
# Значения характеристик события
# ---------------------------------------------------------------------------


class EventAttribute(Base):
    """
    Значение характеристики конкретного события.
    """

    __tablename__ = "event_attributes"
    __table_args__ = (
        UniqueConstraint("event_id", "attribute_def_id", name="uq_event_attributes_event_def"),
        CheckConstraint(
            """NOT (
                value_num IS NULL AND value_text IS NULL AND value_bool IS NULL
                AND value_ts IS NULL AND (value_json IS NULL OR value_json = '{}'::jsonb)
            )""",
            name="ck_event_attributes_at_least_one_value",
        ),
        Index("idx_event_attributes_event", "event_id"),
        Index("idx_event_attributes_def", "attribute_def_id"),
        Index("idx_event_attributes_def_num", "attribute_def_id", "value_num"),
        Index("idx_event_attributes_def_ts", "attribute_def_id", "value_ts"),
        Index("gin_event_attributes_value_json", "value_json", postgresql_using="gin"),
        {"comment": "Значения характеристик события; хотя бы одно value_* или непустой value_json."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор записи атрибута.",
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        comment="Событие.",
    )
    attribute_def_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("event_attribute_defs.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Определение атрибута.",
    )
    value_num: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 6),
        nullable=True,
        comment="Числовое значение.",
    )
    value_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Текстовое значение.",
    )
    value_bool: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="Булево значение.",
    )
    value_ts: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Значение даты/времени.",
    )
    value_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Произвольное JSON-значение.",
    )
    unit: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Единица измерения (если применимо).",
    )
    currency: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Валюта (если применимо).",
    )
    confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Уверенность извлечения значения (0..1).",
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата/время добавления.",
    )

    event: Mapped["Event"] = relationship("Event", back_populates="attributes")
    def_: Mapped["EventAttributeDef"] = relationship(
        "EventAttributeDef",
        back_populates="attribute_values",
        foreign_keys=[attribute_def_id],
    )
