"""Pydantic-схемы для сущностей и алиасов."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EntityAliasOut(BaseModel):
    """Алиас сущности для API."""

    alias_value: str
    kind: str = "surface"
    source: str = "ai"
    lang: str | None = None
    confidence: float | None = None


class EntityOut(BaseModel):
    """Сущность для API (с алиасами)."""

    id: str
    theme_id: str
    entity_type: str
    canonical_name: str
    normalized_name: str
    mention_count: int = 0
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    importance: float | None = None
    confidence: float | None = None
    status: str = "active"
    is_user_pinned: bool = False
    aliases: list[EntityAliasOut] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EntityListOut(BaseModel):
    """Список сущностей по теме."""

    items: list[EntityOut]
    total: int
