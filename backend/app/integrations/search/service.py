"""
SearchService: единая точка входа для сбора квантов (публикации, веб).

theme_search_queries — источник истины для планирования поиска.
TimeSlice — универсальный параметр выполнения (backfill и мониторинг).
"""
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.search.exec import SearchExecutor
from app.integrations.search.plan import SearchPlanner
from app.integrations.search.ports import RetrieverContext
from app.integrations.search.retrievers.publication.retriever import PublicationRetriever
from app.integrations.search.schemas import (
    QuantumCollectResult,
    SearchQuery,
    TimeSlice,
)
from app.modules.theme.model import Theme

if TYPE_CHECKING:
    from app.integrations.search.ports import RetrieverPort

logger = logging.getLogger(__name__)


def _theme_to_terms_by_id(theme: Theme) -> dict[str, Any]:
    """Собрать terms_by_id из theme.keywords, must_have, exclude (id -> {text, translations})."""
    out: dict[str, Any] = {}
    for term_list in (theme.keywords or [], theme.must_have or [], theme.exclude or []):
        for t in term_list:
            if not isinstance(t, dict):
                continue
            tid = t.get("id")
            if not tid or not isinstance(tid, str):
                continue
            out[tid] = {
                "text": t.get("text") or "",
                "translations": t.get("translations") or {},
            }
    return out


def _theme_language(theme: Theme) -> str:
    """Первый язык темы или 'en'."""
    langs = theme.languages or []
    if langs and isinstance(langs, list) and len(langs) > 0:
        first = langs[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    return "en"


class SearchService:
    """
    Единый сервис сбора квантов: planner + executor + registry retriever'ов.
    По умолчанию используется ретривер публикаций (OpenAlex).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._registry: dict[str, "RetrieverPort"] = {
            "openalex": PublicationRetriever(),
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
        run_id: str | None = None,
    ) -> QuantumCollectResult:
        """
        Собрать кванты по теме из theme_search_queries.

        Args:
            session: Сессия БД для чтения theme_search_queries и темы.
            theme_id: ID темы (передаётся в контекст и в retriever'ы публикаций).
            time_slice: Временной срез (опционально). Передаётся в контекст и в Executor.
            target_links: Лимит квантов. Иначе — settings.SEARCH_DEFAULT_TARGET_LINKS.
            mode: Режим ("default" | "discovery" | "monitoring").
            request_id: Идентификатор запроса для трассировки.
            run_id: ID прогона поиска (опционально, передаётся в контекст).

        Returns:
            QuantumCollectResult с items (кванты), plan, step_results.
        """
        terms_by_id: dict[str, Any] = {}
        language = "en"
        languages_for_plan: list[str] = []
        theme_row = await session.execute(select(Theme).where(Theme.id == theme_id).limit(1))
        theme = theme_row.scalar_one_or_none()
        if theme:
            terms_by_id = _theme_to_terms_by_id(theme)
            language = _theme_language(theme)
            languages_for_plan = [
                x for x in (theme.languages or [])
                if isinstance(x, str) and x.strip()
            ]
            if not languages_for_plan:
                languages_for_plan = ["en"]

        ctx = RetrieverContext(
            settings=self._settings,
            logger=logger,
            request_id=request_id,
            theme_id=theme_id,
            run_id=run_id,
            terms_by_id=terms_by_id,
            language=language,
            time_slice=time_slice,
        )
        plan = await self._planner.build_plan_for_theme(
            session, theme_id, mode=mode, languages=languages_for_plan
        )
        limit = target_links or self._settings.SEARCH_DEFAULT_TARGET_LINKS
        return await self._executor.execute(plan, time_slice, limit, ctx)

    async def collect_links(
        self,
        query: SearchQuery,
        mode: str = "discovery",
        request_id: str | None = None,
    ) -> QuantumCollectResult:
        """
        Legacy: собрать кванты по SearchQuery (для обратной совместимости).
        """
        ctx = RetrieverContext(
            settings=self._settings,
            logger=logger,
            request_id=request_id,
        )
        plan = self._planner.build_plan(query, mode=mode)
        limit = query.target_links or self._settings.SEARCH_DEFAULT_TARGET_LINKS
        return await self._executor.execute(plan, None, limit, ctx)
