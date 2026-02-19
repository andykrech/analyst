"""
PublicationRetriever: оркестратор поиска публикаций через OpenAlex (и в будущем другие адаптеры).
Реализует RetrieverPort — получает QueryStep и RetrieverContext, возвращает list[QuantumCreate].
"""
import logging
from typing import Any

from app.integrations.search.ports import RetrieverContext, RetrieverPort
from app.integrations.search.schemas import QueryStep
from app.modules.quanta.schemas import QuantumCreate

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

    async def retrieve(self, step: QueryStep, ctx: RetrieverContext) -> list[QuantumCreate]:
        if ctx.theme_id is None:
            logger.warning("PublicationRetriever: theme_id missing in context, skipping")
            return []

        theme_id = str(ctx.theme_id)
        run_id = ctx.run_id
        terms_by_id: dict[str, Any] = ctx.terms_by_id or {}
        language = (step.language or ctx.language or "en").strip() or "en"
        time_slice = ctx.time_slice

        settings = ctx.settings
        adapter = OpenAlexPublicationAdapter(
            api_key=settings.OPENALEX_API_KEY,
            timeout_s=30.0,
        )
        return await adapter.search_publications(
            step.query_model,
            terms_by_id,
            language=language,
            theme_id=theme_id,
            run_id=run_id,
            time_slice=time_slice,
            limit=step.max_results,
            require_abstract=True,
            request_id=ctx.request_id,
        )
