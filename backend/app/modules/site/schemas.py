"""Схемы API для модуля site."""

from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


class SiteOut(BaseModel):
    """Поля сайта в ответах API (effective_* через join sites + user_sites)."""

    id: str = Field(..., description="UUID сайта")
    domain: str = Field(..., description="Домен в нижнем регистре")
    default_language: Optional[str] = Field(None, description="Основной язык (глобальный)")
    country: Optional[str] = Field(None, description="Страна/регион (глобальный)")
    effective_display_name: Optional[str] = Field(
        None,
        description="COALESCE(user_sites.display_name, sites.domain)",
    )
    effective_description: Optional[str] = Field(
        None,
        description="Пользовательское описание (user_sites.description)",
    )
    effective_homepage_url: Optional[str] = Field(
        None,
        description="Пользовательский URL (user_sites.homepage_url)",
    )
    effective_trust_score: Optional[Decimal] = Field(
        None,
        description="Пользовательская оценка 0..1 (user_sites.trust_score)",
    )
    effective_quality_tier: Optional[int] = Field(
        None,
        description="Пользовательская категория (user_sites.quality_tier)",
    )


class ThemeSiteOut(BaseModel):
    """Связь тема-сайт в ответах API."""

    id: str = Field(..., description="UUID связи")
    theme_id: str = Field(..., description="UUID темы")
    site_id: str = Field(..., description="UUID сайта")
    mode: str = Field(..., description="include|exclude|prefer")
    source: str = Field(..., description="Источник добавления")
    status: str = Field(..., description="active|muted|pending_review")
    confidence: Optional[Decimal] = Field(None, description="Уверенность 0..1")
    reason: Optional[str] = Field(None, description="Причина/пояснение")
    created_by_user_id: Optional[str] = Field(None, description="Кто добавил")
    site: SiteOut = Field(..., description="Данные сайта (effective_*)")


class ThemeSiteCreate(BaseModel):
    """Тело запроса на добавление сайта к теме."""

    domain: str = Field(..., min_length=1, description="Домен или URL")
    mode: Literal["include", "exclude", "prefer"] = Field(
        default="include",
        description="Режим",
    )
    source: Literal["ai_recommended", "user_added", "discovered", "admin_seed"] = Field(
        default="user_added",
        description="Источник",
    )
    status: Literal["active", "muted", "pending_review"] = Field(
        default="active",
        description="Статус",
    )
    confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    reason: Optional[str] = Field(None)
    description: Optional[str] = Field(None, description="Описание для UserSite")
    display_name: Optional[str] = Field(None, description="Отображаемое имя для UserSite")
    homepage_url: Optional[str] = Field(None, description="Домашняя страница для UserSite")
    trust_score: Optional[Decimal] = Field(None, ge=0, le=1)
    quality_tier: Optional[int] = Field(None)


class ThemeSiteUpdate(BaseModel):
    """Тело запроса на обновление связи тема-сайт и/или UserSite."""

    mode: Optional[Literal["include", "exclude", "prefer"]] = None
    status: Optional[Literal["active", "muted", "pending_review"]] = None
    confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    reason: Optional[str] = None
    description: Optional[str] = None
    display_name: Optional[str] = None
    homepage_url: Optional[str] = None
    trust_score: Optional[Decimal] = Field(None, ge=0, le=1)
    quality_tier: Optional[int] = None


# --- Рекомендация источников (ИИ) ---


class SourcesRecommendRequest(BaseModel):
    """Тело запроса на рекомендацию источников по контексту темы."""

    title: Optional[str] = Field(None, description="Название темы")
    description: Optional[str] = Field(None, description="Описание темы")
    keywords: Optional[list[str]] = Field(None, description="Ключевые слова темы")


class RecommendedSiteItem(BaseModel):
    """Один рекомендованный сайт в ответе ИИ."""

    domain: str = Field(..., description="Домен в нижнем регистре")
    display_name: Optional[str] = Field(None, description="Отображаемое имя")
    reason: Optional[str] = Field(None, description="Пояснение релевантности")


class SourcesRecommendLLMMeta(BaseModel):
    """Мета вызова LLM для рекомендации источников."""

    provider: str
    model: Optional[str] = None
    usage: dict
    cost: dict
    warnings: list[str] = Field(default_factory=list)


class SourcesRecommendResponse(BaseModel):
    """Ответ эндпоинта recommend: список рекомендованных сайтов + мета LLM."""

    result: list[RecommendedSiteItem] = Field(
        default_factory=list,
        description="Список рекомендованных сайтов",
    )
    llm: Optional[SourcesRecommendLLMMeta] = Field(default=None, description="Мета вызова LLM")
