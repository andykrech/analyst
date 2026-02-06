"""
Порт (интерфейс) retriever'ов поисковых ссылок.
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.integrations.search.schemas import LinkCandidate, QueryStep

if TYPE_CHECKING:
    from logging import Logger

    from app.core.config import Settings


@dataclass
class RetrieverContext:
    """Контекст выполнения retriever'а."""

    settings: "Settings"
    logger: "Logger | None" = None
    request_id: str | None = None


class LinkRetrieverPort(Protocol):
    """Абстракция для retriever'а поисковых ссылок."""

    @property
    def name(self) -> str:
        """Имя retriever'а (например 'yandex')."""
        ...

    async def retrieve(self, step: QueryStep, ctx: RetrieverContext) -> list[LinkCandidate]:
        """
        Выполнить поиск по шагу плана и вернуть список кандидатов.

        Args:
            step: Шаг плана с query и max_results.
            ctx: Контекст (settings, logger, request_id).

        Returns:
            Список LinkCandidate (без normalized_url и url_hash — их заполняет executor).
        """
        ...
