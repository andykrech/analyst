"""SQLAlchemy-модель для таблицы тем аналитического сервиса."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
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


class ThemeSearchQuery(Base):
    """
    Явный поисковый запрос по теме (составляющая темы).

    theme_search_queries — источник истины для планировщика поиска.
    Keywords, must_have, exclude из themes — лишь подсказки для пользователя.
    """

    __tablename__ = "theme_search_queries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        comment="Уникальный идентификатор поискового запроса",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        comment="Ссылка на тему",
    )
    order_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Порядок выполнения запроса внутри темы",
    )
    title: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Короткое название запроса для UI",
    )
    query_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Явный текст поискового запроса",
    )
    must_have: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Список обязательных слов/фраз",
    )
    exclude: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Список слов/фраз-исключений",
    )
    time_window_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Ограничение по давности в днях, NULL = по умолчанию",
    )
    target_links: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Максимум ссылок с этого запроса, NULL = без ограничения",
    )
    enabled_retrievers: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Ограничение retriever'ов для этого запроса",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Включён ли запрос в план поиска",
    )
