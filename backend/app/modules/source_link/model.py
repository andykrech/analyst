"""SQLAlchemy-модель для таблицы источников (ссылок/документов) по темам."""

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
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.modules.digest.model import DigestSourceLink
    from app.modules.event.model import EventSourceLink
    from app.modules.site.models import Site


class SourceLink(Base):
    """
    Хранит найденные по теме ссылки/документы (доказательная база) + метаданные
    поиска/парсинга для дайджестов, дедупликации и показа первоисточников.
    """

    __tablename__ = "source_links"
    __table_args__ = (
        UniqueConstraint(
            "theme_id",
            "url_hash",
            name="uq_source_links_theme_id_url_hash",
        ),
        Index(
            "ix_source_links_theme_id_not_deleted",
            "theme_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_source_links_theme_id_read_at", "theme_id", "read_at"),
        {"comment": "Найденные по теме ссылки/документы и метаданные поиска/парсинга"},
    )

    # --- Идентификация и связь с темой ---
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор источника (ссылки/документа) в рамках БД.",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Идентификатор темы (themes.id), к которой относится источник.",
    )

    # --- Связь с запуском поиска/обработки ---
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Идентификатор запуска (SearchRun), в рамках которого источник был найден/обработан. В MVP может быть NULL.",
    )
    period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Начало периода, за который выполнялся поиск (например, первый день месяца при backfill).",
    )
    period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Конец периода, за который выполнялся поиск (например, последний день месяца при backfill).",
    )

    # --- URL и дедупликация ---
    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Исходный URL источника.",
    )
    url_normalized: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Нормализованный URL для дедупликации (без UTM/якорей, с приведением схемы/хоста и т.п.).",
    )
    url_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Хэш нормализованного URL (для быстрого поиска и уникальности).",
    )
    canonical_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Канонический URL страницы (если удалось определить при парсинге/загрузке). Может отличаться от исходного.",
    )
    domain: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
        comment="Домен источника (например, 'example.com') для фильтров и статистики.",
    )
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Ссылка на справочник sites для домена источника.",
    )

    # --- Метаданные источника ---
    title: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Заголовок материала (из поиска или со страницы).",
    )
    snippet: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Сниппет/краткое описание из поисковой выдачи.",
    )
    author: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Автор материала, если удалось определить.",
    )
    source_name: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Название источника/издания (если известно), например 'Reuters'.",
    )
    language: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Язык источника (ISO 639-1, например 'ru', 'en'), если определён.",
    )
    country: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Страна/регион источника, если определены (например 'RU', 'US', 'EU').",
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Дата/время публикации материала, если удалось определить.",
    )
    found_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="Дата/время, когда ссылка была найдена сервисом.",
    )

    # --- Классификация и качество ---
    source_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="web",
        comment="Тип источника: web/pdf/video/social/news/other (пока строкой, без enum).",
    )
    mime_type: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="MIME-тип контента (например 'text/html', 'application/pdf'), если известен.",
    )
    paywalled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Признак, что контент за paywall/ограничением доступа (если определено).",
    )
    relevance_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 3),
        nullable=True,
        comment="Оценка релевантности источника теме (поисковая/ИИ-оценка), если используется.",
    )
    rank_in_results: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Позиция в поисковой выдаче (если известна).",
    )

    # --- Контент и парсинг ---
    content_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="not_fetched",
        comment="Статус извлечения контента: not_fetched / fetched / failed / skipped.",
    )
    content_fetched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда контент в последний раз извлекался.",
    )
    content_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Извлечённый полный текст материала (если извлекали).",
    )
    content_excerpt: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Короткий фрагмент/выжимка текста (опционально), удобный для быстрого анализа.",
    )
    content_checksum: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Хэш/контрольная сумма извлечённого контента (для определения изменений при повторной загрузке).",
    )

    # --- Сырьё поискового провайдера ---
    provider: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Идентификатор провайдера поиска (например 'yandex', 'google', 'custom').",
    )
    provider_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Сырые данные/поля от провайдера поиска (для трассировки и улучшения качества).",
    )

    # --- Произвольные доп. метаданные ---
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Дополнительные метаданные источника (картинка, теги, категории, любые расширения).",
    )

    # --- Состояние для UI ---
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда пользователь открыл/просмотрел источник (для подсветки непрочитанного).",
    )
    pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Закреплён пользователем (важный источник) — для будущих UX-функций.",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Заметки пользователя по источнику (на будущее).",
    )

    # --- Технические поля ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата/время создания записи источника.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Дата/время последнего изменения записи источника.",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата/время мягкого удаления (soft delete).",
    )

    site: Mapped[Optional["Site"]] = relationship("Site", foreign_keys=[site_id])

    digest_source_links: Mapped[list["DigestSourceLink"]] = relationship(
        "DigestSourceLink",
        back_populates="source_link",
    )
    event_source_links: Mapped[list["EventSourceLink"]] = relationship(
        "EventSourceLink",
        back_populates="source_link",
    )
