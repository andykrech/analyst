"""
SearchService: единая точка входа для сбора релевантных ссылок.
"""
import logging
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.integrations.search.exec import SearchExecutor
from app.integrations.search.plan import SearchPlanner
from app.integrations.search.ports import RetrieverContext
from app.integrations.search.retrievers.yandex.yandex_retriever import YandexRetriever
from app.integrations.search.schemas import LinkCollectResult, SearchQuery

if TYPE_CHECKING:
    from app.integrations.search.ports import LinkRetrieverPort

logger = logging.getLogger(__name__)

# TODO: поддержка source-based steps (rss/section/crosslinks)
# TODO: параллельное выполнение steps


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

    async def collect_links(
        self,
        query: SearchQuery,
        mode: str = "discovery",
        request_id: str | None = None,
    ) -> LinkCollectResult:
        """
        Собрать релевантные ссылки по запросу.

        Args:
            query: Параметры поиска.
            mode: Режим ("discovery" | "monitoring").
            request_id: Идентификатор запроса для трассировки.

        Returns:
            LinkCollectResult с items, plan, step_results.
        """
        ctx = RetrieverContext(
            settings=self._settings,
            logger=logger,
            request_id=request_id,
        )
        plan = self._planner.build_plan(query, mode=mode)
        return await self._executor.execute(plan, query, ctx)
