"""
Pydantic-схемы для поискового интеграционного слоя.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    """Параметры поискового запроса."""

    text: str | None = None
    keywords: list[str] = []
    must_have: list[str] = []
    exclude: list[str] = []
    language: str | None = None
    region: str | None = None
    time_window_days: int = 7
    target_links: int = 50
    enabled_retrievers: list[str] | None = None  # override списка retriever'ов


class LinkCandidate(BaseModel):
    """Кандидат-ссылка от retriever'а."""

    url: str
    title: str | None = None
    snippet: str | None = None
    published_at: datetime | None = None
    provider: str
    rank: int | None = None
    provider_meta: dict = Field(default_factory=dict)
    normalized_url: str | None = None
    url_hash: str | None = None


class QueryStep(BaseModel):
    """Шаг плана: поисковый запрос к retriever'у."""

    kind: Literal["query"] = "query"
    step_id: str
    retriever: str  # имя retriever'а (например "yandex")
    query: SearchQuery
    max_results: int


# Discriminated union по kind (сейчас только QueryStep)
PlanStep = QueryStep


class SearchPlan(BaseModel):
    """План поиска: последовательность шагов."""

    plan_version: int = 1
    mode: Literal["discovery", "monitoring"] = "discovery"
    steps: list[PlanStep]


class StepResult(BaseModel):
    """Результат выполнения одного шага плана."""

    step_id: str
    status: Literal["done", "failed", "skipped"]
    found: int
    returned: int
    error: str | None = None
    meta: dict = Field(default_factory=dict)


class LinkCollectResult(BaseModel):
    """Итоговый результат сбора ссылок."""

    items: list[LinkCandidate]
    plan: SearchPlan
    step_results: list[StepResult]
    total_found: int
    total_returned: int
