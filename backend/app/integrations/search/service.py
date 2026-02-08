"""
SearchService: единая точка входа для сбора релевантных ссылок.

theme_search_queries — источник истины для планирования поиска.
TimeSlice — универсальный параметр выполнения (backfill и мониторинг).
SearchService не генерирует TimeSlice, только принимает его.
"""
import logging
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.search.exec import SearchExecutor
from app.integrations.search.plan import SearchPlanner
from app.integrations.search.ports import RetrieverContext
from app.integrations.search.retrievers.yandex.yandex_retriever import YandexRetriever
from app.integrations.search.schemas import (
    LinkCollectResult,
    SearchQuery,
    TimeSlice,
)

if TYPE_CHECKING:
    from app.integrations.search.ports import LinkRetrieverPort

logger = logging.getLogger(__name__)


class SearchService:
    """
    Единый сервис сбора ссылок: planner + executor + registry retriever'ов.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._registry: dict[str, "LinkRetrieverPort"] = {
            "yandex": YandexRetriever(),
        }
        self._planner = SearchPlanner(settings)
        self._executor = SearchExecutor(self._registry, settings)

    async def collect_links_for_theme(
        self,
        session: AsyncSession,
        theme_id: UUID,
        time_slice: TimeSlice | None = None,
        target_links: int | None = None,
        mode: str = "default",
        request_id: str | None = None,
    ) -> LinkCollectResult:
        """
        Собрать ссылки по теме из theme_search_queries.

        Args:
            session: Сессия БД для чтения theme_search_queries.
            theme_id: ID темы.
            time_slice: Временной срез (опционально). Применяется как фильтр в Executor.
            target_links: Лимит ссылок. Иначе — settings.SEARCH_DEFAULT_TARGET_LINKS.
            mode: Режим ("default" | "discovery" | "monitoring").
            request_id: Идентификатор запроса для трассировки.

        Returns:
            LinkCollectResult с items, plan, step_results.
        """
        ctx = RetrieverContext(
            settings=self._settings,
            logger=logger,
            request_id=request_id,
        )
        plan = await self._planner.build_plan_for_theme(session, theme_id, mode=mode)
        limit = target_links or self._settings.SEARCH_DEFAULT_TARGET_LINKS
        return await self._executor.execute(plan, time_slice, limit, ctx)

    async def collect_links(
        self,
        query: SearchQuery,
        mode: str = "discovery",
        request_id: str | None = None,
    ) -> LinkCollectResult:
        """
        Legacy: собрать ссылки по SearchQuery (для обратной совместимости).
        """
        ctx = RetrieverContext(
            settings=self._settings,
            logger=logger,
            request_id=request_id,
        )
        plan = self._planner.build_plan(query, mode=mode)
        limit = query.target_links or self._settings.SEARCH_DEFAULT_TARGET_LINKS
        return await self._executor.execute(plan, None, limit, ctx)
