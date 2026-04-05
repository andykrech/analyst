"""
Порт (интерфейс) retriever'ов поиска.
Ретриверы возвращают кванты и строки для биллинга (одна строка на каждый успешный платный вызов API).
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

from app.integrations.search.schemas import QueryStep, TimeSlice
from app.modules.quanta.schemas import QuantumCreate

if TYPE_CHECKING:
    from logging import Logger

    from app.core.config import Settings


@dataclass(frozen=True)
class SearchBillingUsageLine:
    """
    Одна платная операция поиска: executor передаёт в BillingService.record_usage.
    service_type / service_impl задаются в адаптере/ретривере и должны совпадать с billing_tariffs.
    """

    service_type: str
    service_impl: str
    quantity: Decimal
    quantity_unit_code: str
    extra: dict[str, Any] | None = None


@dataclass
class RetrieverResult:
    """Ответ retriever'а: кванты и необязательные строки биллинга."""

    items: list[QuantumCreate]
    billing_lines: list[SearchBillingUsageLine] = field(default_factory=list)


@dataclass
class RetrieverContext:
    """Контекст выполнения retriever'а."""

    settings: "Settings"
    logger: "Logger | None" = None
    request_id: str | None = None
    theme_id: UUID | None = None
    run_id: str | None = None
    terms_by_id: dict[str, Any] | None = None
    language: str | None = None
    time_slice: TimeSlice | None = None
    theme_relevance_vector: list[float] | None = None
    billing_session: Any | None = None
    billing_theme_id: UUID | None = None
    billing_service: Any | None = None
    #: dedup_key уже сохранённых квантов темы — не гонять повторно
    existing_theme_dedup_keys: frozenset[str] = field(default_factory=frozenset)
    #: пары (entity_kind, dedup_key) из rejected_quanta_candidates
    rejected_quanta_candidate_keys: frozenset[tuple[str, str]] = field(default_factory=frozenset)


class RetrieverPort(Protocol):
    """Абстракция для retriever'а: выполняет шаг плана и возвращает кванты + биллинг."""

    @property
    def name(self) -> str:
        """Имя retriever'а (например 'publication_retriever', 'yandex')."""
        ...

    async def retrieve(self, step: QueryStep, ctx: RetrieverContext) -> RetrieverResult:
        """
        Выполнить поиск по шагу плана.

        Args:
            step: Шаг плана с query_model и max_results.
            ctx: Контекст (settings, theme_id, run_id, ...).

        Returns:
            RetrieverResult: кванты и по одной строке биллинга на каждый успешный (не 5xx) вызов API.
        """
        ...
