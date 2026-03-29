"""
PublicationRetriever: оркестратор поиска публикаций через OpenAlex (и в будущем другие адаптеры).
Реализует RetrieverPort — возвращает RetrieverResult (кванты + строки биллинга).
"""
import logging
from typing import Any

from app.integrations.search.ports import RetrieverContext, RetrieverPort, RetrieverResult
from app.integrations.search.schemas import QueryStep

from app.integrations.search.retrievers.publication.openalex.adapter import (
    OpenAlexPublicationAdapter,
)

logger = logging.getLogger(__name__)


class PublicationRetriever:
    """
    Ретривер публикаций: вызывает OpenAlex-адаптер.
    Требует theme_id в контексте; language и terms_by_id задаются в ctx (из темы).
    """

    @property
    def name(self) -> str:
        return "openalex"

    async def retrieve(self, step: QueryStep, ctx: RetrieverContext) -> RetrieverResult:
        if ctx.theme_id is None:
            logger.warning("PublicationRetriever: theme_id missing in context, skipping")
            return RetrieverResult(items=[], billing_lines=[])

        theme_id = str(ctx.theme_id)
        run_id = ctx.run_id
        terms_by_id: dict[str, Any] = ctx.terms_by_id or {}
        language = (step.language or ctx.language or "en").strip() or "en"
        time_slice = ctx.time_slice

        logger.info(
            "search/retriever: шаг step_id=%s, запрашиваем max_results=%s",
            step.step_id,
            step.max_results,
        )
        settings = ctx.settings
        adapter = OpenAlexPublicationAdapter(
            api_key=settings.OPENALEX_API_KEY,
            timeout_s=30.0,
        )
        result = await adapter.search_publications(
            step.query_model,
            terms_by_id,
            language=language,
            theme_id=theme_id,
            run_id=run_id,
            time_slice=time_slice,
            limit=step.max_results,
            require_abstract=True,
            request_id=ctx.request_id,
            step_id=str(step.step_id),
            source_query_id=str(step.source_query_id),
        )
        logger.info(
            "search/retriever: шаг step_id=%s, вернулось квантов=%s, строк биллинга=%s",
            step.step_id,
            len(result.items),
            len(result.billing_lines),
        )
        return result
