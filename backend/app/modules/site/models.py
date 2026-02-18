"""SQLAlchemy-модели для справочника сайтов (доменов) и привязки сайтов к темам."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.modules.theme.model import Theme
    from app.modules.user.model import User


class Site(Base):
    """Глобальный справочник доменов (только глобальные свойства)."""

    __tablename__ = "sites"
    __table_args__ = (
        CheckConstraint("domain = lower(domain)", name="ck_sites_domain_lower"),
        {"comment": "Глобальный справочник доменов (сайтов)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Идентификатор сайта (домен как сущность).",
    )
    domain: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
        comment="Домен сайта в нижнем регистре, без схемы и пути (пример: example.com).",
    )
    default_language: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Основной язык сайта (например: ru, en).",
    )
    country: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Страна/регион (например: RU, LV, US), если известно.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата создания записи.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Дата последнего обновления.",
    )

    user_overrides: Mapped[list["UserSite"]] = relationship(
        "UserSite",
        back_populates="site",
        cascade="all, delete-orphan",
    )
    theme_sites: Mapped[list["ThemeSite"]] = relationship(
        "ThemeSite",
        back_populates="site",
        cascade="all, delete-orphan",
    )


class UserSite(Base):
    """Пользовательские атрибуты сайта (display_name, description и т.д.)."""

    __tablename__ = "user_sites"
    __table_args__ = (
        UniqueConstraint("user_id", "site_id", name="uq_user_sites_user_id_site_id"),
        Index("ix_user_sites_user_id", "user_id"),
        Index("ix_user_sites_site_id", "site_id"),
        {"comment": "Пользовательские атрибуты сайтов"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Идентификатор записи.",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Пользователь.",
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        comment="Сайт (домен).",
    )
    display_name: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Пользовательское отображаемое имя сайта.",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Пользовательское описание тематики сайта.",
    )
    homepage_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Пользовательский URL.",
    )
    trust_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 3),
        nullable=True,
        comment="Пользовательская оценка доверия (0..1).",
    )
    quality_tier: Mapped[Optional[int]] = mapped_column(
        SmallInteger,
        nullable=True,
        comment="Пользовательская категория качества.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата создания.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Дата изменения.",
    )

    site: Mapped["Site"] = relationship("Site", back_populates="user_overrides")
    user: Mapped["User"] = relationship(
        "User",
        back_populates="user_sites",
        foreign_keys=[user_id],
    )


class ThemeSite(Base):
    """Связь тема-сайт: сайт в контексте темы с режимом и статусом."""

    __tablename__ = "theme_sites"
    __table_args__ = (
        UniqueConstraint("theme_id", "site_id", name="uq_theme_sites_theme_id_site_id"),
        CheckConstraint(
            "mode IN ('include','exclude','prefer')",
            name="ck_theme_sites_mode",
        ),
        CheckConstraint(
            "source IN ('ai_recommended','user_added','discovered','admin_seed')",
            name="ck_theme_sites_source",
        ),
        CheckConstraint(
            "status IN ('active','muted','pending_review')",
            name="ck_theme_sites_status",
        ),
        Index("ix_theme_sites_theme_id_mode", "theme_id", "mode"),
        Index("ix_theme_sites_theme_id_status", "theme_id", "status"),
        {"comment": "Связь тема-сайт: режим, источник, статус"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Идентификатор связи 'тема-сайт'.",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Ссылка на тему.",
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Ссылка на сайт (домен).",
    )
    mode: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Режим: include|exclude|prefer (включить, исключить, предпочесть).",
    )
    source: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Источник добавления: ai_recommended|user_added|discovered|admin_seed.",
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Статус: active|muted|pending_review.",
    )
    confidence: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 3),
        nullable=True,
        comment="Уверенность (0..1) для рекомендаций/автообнаружения.",
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Причина/пояснение (почему сайт добавлен, откуда взят).",
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Если добавил пользователь — кто именно.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата создания.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Дата изменения.",
    )

    site: Mapped["Site"] = relationship("Site", back_populates="theme_sites")
    theme: Mapped["Theme"] = relationship(
        "Theme",
        back_populates="theme_sites",
        foreign_keys=[theme_id],
    )
    created_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
    )
