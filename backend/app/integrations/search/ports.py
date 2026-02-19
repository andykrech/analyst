"""
Порт (интерфейс) retriever'ов поиска.
Все ретриверы возвращают кванты (QuantumCreate).
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

from app.integrations.search.schemas import QueryStep, TimeSlice
from app.modules.quanta.schemas import QuantumCreate

if TYPE_CHECKING:
    from logging import Logger

    from app.core.config import Settings


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


class RetrieverPort(Protocol):
    """Абстракция для retriever'а: выполняет шаг плана и возвращает кванты."""

    @property
    def name(self) -> str:
        """Имя retriever'а (например 'yandex', 'openalex')."""
        ...

    async def retrieve(self, step: QueryStep, ctx: RetrieverContext) -> list[QuantumCreate]:
        """
        Выполнить поиск по шагу плана и вернуть список квантов.

        Args:
            step: Шаг плана с query_model и max_results.
            ctx: Контекст (settings, theme_id, run_id, ...).

        Returns:
            Список QuantumCreate (theme_id/run_id из ctx, entity_kind по типу источника).
        """
        ...
