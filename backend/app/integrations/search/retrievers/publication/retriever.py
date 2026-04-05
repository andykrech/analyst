"""
PublicationRetriever: оркестратор поиска публикаций через несколько адаптеров
(OpenAlex, Semantic Scholar, arXiv, PubMed).

Реализует RetrieverPort — возвращает RetrieverResult (кванты + строки биллинга).
"""
import logging
from typing import Any

from app.integrations.search.ports import RetrieverContext, RetrieverPort, RetrieverResult
from app.integrations.search.schemas import QueryStep

from app.integrations.search.retrievers.publication.openalex.adapter import (
    OpenAlexPublicationAdapter,
)
from app.integrations.search.retrievers.publication.semanticscholar.adapter import (
    SemanticScholarPublicationAdapter,
)
from app.integrations.search.retrievers.publication.arxiv.adapter import (
    ArxivPublicationAdapter,
)
from app.integrations.search.retrievers.publication.pubmed.adapter import (
    PubMedPublicationAdapter,
)

logger = logging.getLogger(__name__)


class PublicationRetriever:
    """
    Ретривер публикаций: OpenAlex, Semantic Scholar, arXiv, PubMed (по порядку).
    Требует theme_id в контексте; language и terms_by_id задаются в ctx (из темы).
    """

    @property
    def name(self) -> str:
        return "publication_retriever"

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
        retriever_name = self.name

        oa_adapter = OpenAlexPublicationAdapter(
            api_key=settings.OPENALEX_API_KEY,
            timeout_s=30.0,
        )
        s2_adapter = SemanticScholarPublicationAdapter(
            timeout_s=30.0,
            retries=10,
            retry_delay_s=2.0,
        )
        arxiv_adapter = ArxivPublicationAdapter(
            timeout_s=60.0,
            retries=5,
        )
        pubmed_adapter = PubMedPublicationAdapter(
            tool=settings.NCBI_TOOL,
            email=settings.NCBI_EMAIL,
            api_key=settings.NCBI_API_KEY,
            timeout_esearch_s=60.0,
            timeout_efetch_s=120.0,
        )

        oa_result = await oa_adapter.search_publications(
            step.query_model,
            terms_by_id,
            language=language,
            theme_id=theme_id,
            run_id=run_id,
            time_slice=time_slice,
            limit=step.max_results,
            require_abstract=True,
            retriever_name=retriever_name,
            request_id=ctx.request_id,
            step_id=str(step.step_id),
            source_query_id=str(step.source_query_id),
        )

        s2_result = await s2_adapter.search_publications(
            step.query_model,
            terms_by_id,
            language=language,
            theme_id=theme_id,
            run_id=run_id,
            time_slice=time_slice,
            limit=step.max_results,
            require_abstract=True,
            retriever_name=retriever_name,
            request_id=ctx.request_id,
        )

        arxiv_result = await arxiv_adapter.search_publications(
            step.query_model,
            terms_by_id,
            language=language,
            theme_id=theme_id,
            run_id=run_id,
            time_slice=time_slice,
            limit=step.max_results,
            require_abstract=True,
            retriever_name=retriever_name,
            request_id=ctx.request_id,
        )

        pubmed_result = await pubmed_adapter.search_publications(
            step.query_model,
            terms_by_id,
            language=language,
            theme_id=theme_id,
            run_id=run_id,
            time_slice=time_slice,
            limit=step.max_results,
            require_abstract=True,
            retriever_name=retriever_name,
            request_id=ctx.request_id,
        )

        result = RetrieverResult(
            items=[
                *(oa_result.items or []),
                *(s2_result.items or []),
                *(arxiv_result.items or []),
                *(pubmed_result.items or []),
            ],
            billing_lines=[*(oa_result.billing_lines or [])],
        )
        logger.info(
            "search/retriever: шаг step_id=%s, вернулось квантов=%s, строк биллинга=%s",
            step.step_id,
            len(result.items),
            len(result.billing_lines),
        )
        return result
