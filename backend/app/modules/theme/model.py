"""SQLAlchemy-модель для таблицы тем аналитического сервиса."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Theme(Base):
    """Таблица пользовательских тем аналитического сервиса."""

    __tablename__ = "themes"
    __table_args__ = (
        # Индекс для выборки тем пользователя (в т.ч. с учётом soft-delete)
        {"comment": "Пользовательские темы аналитического сервиса"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Уникальный идентификатор темы",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Пользователь, которому принадлежит тема",
    )
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Краткое название темы, отображаемое в интерфейсе",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Исходное текстовое описание темы, сформулированное пользователем",
    )
    keywords: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Список ключевых слов и фраз для поиска информации по теме",
    )
    must_have: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Обязательные слова или сущности в найденных материалах",
    )
    exclude: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Минус-слова и фразы, исключаемые из поиска",
    )
    languages: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Список языков источников и поиска (например, [\"ru\", \"en\"])",
    )
    region: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Регион или географическая область интереса (например, RU, EU, US)",
    )
    update_interval: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="weekly",
        comment="Периодичность обновления темы (daily / 3d / weekly)",
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата и время последнего запуска обновления темы",
    )
    next_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Дата и время следующего планируемого обновления темы",
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="draft",
        comment="Текущее состояние темы (draft / active / paused / archived)",
    )
    backfill_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="not_started",
        comment="Статус первичного исторического сбора (not_started / running / done / failed)",
    )
    backfill_horizon_months: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="12",
        comment="Глубина первичного анализа в месяцах (например, 3 / 6 / 12)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата и время создания темы",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Дата и время последнего изменения темы",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата и время мягкого удаления темы (soft delete)",
    )
