"""
Pydantic-схемы для поискового интеграционного слоя.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.quanta.schemas import QuantumCreate

MAX_KEYWORD_GROUPS = 10
MAX_TERMS_PER_GROUP = 50
MAX_TERM_LENGTH = 120


# --- TimeSlice: универсальный параметр выполнения поиска ---
# Используется и для исторического backfill (много запусков с разными периодами),
# и для текущего мониторинга (один запуск со "скользящим" TimeSlice).
# Логика генерации TimeSlice (месяцы, последние N дней) — в отдельных функциях,
# не в SearchService.
class TimeSlice(BaseModel):
    """Временной срез для фильтрации результатов по дате публикации."""

    published_from: datetime
    published_to: datetime
    label: str | None = None


class ThemeSearchCollectRequest(BaseModel):
    """Запрос на сбор ссылок по теме."""

    theme_id: UUID
    published_from: datetime | None = None
    published_to: datetime | None = None
    target_links: int | None = None
    run_id: str | None = None


class SearchQuery(BaseModel):
    """Параметры поискового запроса (legacy, для обратной совместимости)."""

    text: str | None = None
    keywords: list[str] = []
    must_have: list[str] = []
    exclude: list[str] = []
    language: str | None = None
    region: str | None = None
    time_window_days: int = 7
    target_links: int = 50
    enabled_retrievers: list[str] | None = None  # override списка retriever'ов


# --- Структурная модель запроса (QueryModel) ---


class KeywordGroup(BaseModel):
    """Группа ключевых слов с логическим оператором между термами."""

    title: str | None = Field(
        default=None,
        description="Опциональное имя группы для UI",
    )
    op: Literal["OR", "AND"] = Field(
        default="OR",
        description="Логический оператор между термами внутри группы",
    )
    terms: list[str] = Field(
        default_factory=list,
        description="Список уже нормализованных термов",
    )

    @field_validator("terms", mode="before")
    @classmethod
    def _normalize_terms_before(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return v
        # допускаем одиночную строку
        return [v]

    @field_validator("terms")
    @classmethod
    def _validate_terms(cls, v: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in v:
            if not isinstance(raw, str):
                continue
            s = raw.strip()
            if not s:
                continue
            if len(s) > MAX_TERM_LENGTH:
                s = s[:MAX_TERM_LENGTH]
            cleaned.append(s)

        # удаляем дубликаты, сохраняя порядок
        seen: set[str] = set()
        unique: list[str] = []
        for term in cleaned:
            if term not in seen:
                seen.add(term)
                unique.append(term)

        if not unique:
            raise ValueError("group.terms не может быть пустым")
        if len(unique) > MAX_TERMS_PER_GROUP:
            raise ValueError(
                f"Слишком много термов в группе (>{MAX_TERMS_PER_GROUP})",
            )
        return unique


class KeywordsBlock(BaseModel):
    """Блок ключевых слов: группы + коннекторы между ними."""

    groups: list[KeywordGroup] = Field(
        ...,
        description="Непустой список групп ключевых слов",
    )
    connectors: list[Literal["OR", "AND"]] = Field(
        default_factory=list,
        description="Логические коннекторы между группами, длина = len(groups) - 1",
    )

    @field_validator("groups")
    @classmethod
    def _validate_groups(cls, v: list[KeywordGroup]) -> list[KeywordGroup]:
        if not v:
            raise ValueError("keywords.groups не может быть пустым")
        if len(v) > MAX_KEYWORD_GROUPS:
            raise ValueError(
                f"Слишком много групп ключевых слов (>{MAX_KEYWORD_GROUPS})",
            )
        return v

    @model_validator(mode="after")
    def _validate_connectors_len(self) -> "KeywordsBlock":
        expected = max(len(self.groups) - 1, 0)
        if len(self.connectors) != expected:
            raise ValueError(
                f"Длина connectors должна быть равна len(groups)-1 (ожидалось {expected}, получено {len(self.connectors)})",
            )
        return self


class MustBlock(BaseModel):
    """Обязательные термы для пост-фильтрации и/или запроса."""

    mode: Literal["ALL", "ANY"] = Field(
        default="ALL",
        description="Режим интерпретации must-термов: ALL (все) или ANY (хотя бы один)",
    )
    terms: list[str] = Field(
        default_factory=list,
        description="Список обязательных термов (может быть пустым)",
    )

    @field_validator("terms", mode="before")
    @classmethod
    def _normalize_terms_before(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return [v]

    @field_validator("terms")
    @classmethod
    def _validate_terms(cls, v: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in v:
            if not isinstance(raw, str):
                continue
            s = raw.strip()
            if not s:
                continue
            if len(s) > MAX_TERM_LENGTH:
                s = s[:MAX_TERM_LENGTH]
            cleaned.append(s)

        # удаляем дубликаты, сохраняя порядок
        seen: set[str] = set()
        unique: list[str] = []
        for term in cleaned:
            if term not in seen:
                seen.add(term)
                unique.append(term)

        if len(unique) > MAX_TERMS_PER_GROUP:
            raise ValueError(
                f"Слишком много must-термов (>{MAX_TERMS_PER_GROUP})",
            )
        return unique


class ExcludeBlock(BaseModel):
    """Минус-слова/фразы."""

    terms: list[str] = Field(
        default_factory=list,
        description="Список минус-слов/фраз (может быть пустым)",
    )

    @field_validator("terms", mode="before")
    @classmethod
    def _normalize_terms_before(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return [v]

    @field_validator("terms")
    @classmethod
    def _validate_terms(cls, v: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in v:
            if not isinstance(raw, str):
                continue
            s = raw.strip()
            if not s:
                continue
            if len(s) > MAX_TERM_LENGTH:
                s = s[:MAX_TERM_LENGTH]
            cleaned.append(s)

        seen: set[str] = set()
        unique: list[str] = []
        for term in cleaned:
            if term not in seen:
                seen.add(term)
                unique.append(term)

        if len(unique) > MAX_TERMS_PER_GROUP:
            raise ValueError(
                f"Слишком много exclude-термов (>{MAX_TERMS_PER_GROUP})",
            )
        return unique


class QueryModel(BaseModel):
    """Структурная модель поискового запроса."""

    keywords: KeywordsBlock
    must: MustBlock = Field(
        default_factory=MustBlock,
        description="Обязательные термы (ALL/ANY)",
    )
    exclude: ExcludeBlock = Field(
        default_factory=ExcludeBlock,
        description="Минус-слова/фразы",
    )


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
    """
    Шаг плана: поисковый запрос к retriever'у.

    Planner не знает про время. Retriever не знает про время.
    Временная фильтрация (TimeSlice) применяется в Executor после поиска.
    language задаёт язык шага (для мультиязычного плана); если None — ретривер использует ctx.language.
    """

    kind: Literal["query"] = "query"
    step_id: str
    retriever: str  # имя retriever'а (например "openalex")
    source_query_id: UUID  # id из theme_search_queries
    order_index: int
    query_model: QueryModel
    max_results: int
    language: str | None = None


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
    source_query_id: UUID | None = None
    retriever: str | None = None
    order_index: int | None = None
    status: Literal["done", "failed", "skipped"]
    found: int
    returned: int
    error: str | None = None
    meta: dict = Field(default_factory=dict)


class LinkCollectResult(BaseModel):
    """Итоговый результат сбора ссылок (deprecated: используйте QuantumCollectResult)."""

    items: list[LinkCandidate]
    plan: SearchPlan
    step_results: list[StepResult]
    total_found: int
    total_returned: int


class QuantumCollectResult(BaseModel):
    """Итоговый результат сбора квантов от retriever'ов."""

    items: list[QuantumCreate]
    plan: SearchPlan
    step_results: list[StepResult]
    total_found: int
    total_returned: int
