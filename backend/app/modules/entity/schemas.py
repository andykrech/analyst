"""Pydantic-схемы для кластеров сущностей (API)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ClusterOut(BaseModel):
    """Кластер сущности для API."""

    id: str
    theme_id: str
    type: str
    normalized_text: str
    display_text: str
    global_df: int = 0
    global_score: float = 0.0


class EntityOut(BaseModel):
    """Сущность для API (совместимость: кластер как сущность)."""

    id: str
    theme_id: str
    entity_type: str
    canonical_name: str
    normalized_name: str
    mention_count: int = 0
    importance: float | None = None
    global_df: int = 0
    global_score: float = 0.0


class EntityListOut(BaseModel):
    """Список сущностей по теме."""

    items: list[EntityOut]
    total: int
