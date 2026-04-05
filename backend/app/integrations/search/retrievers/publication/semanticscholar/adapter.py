"""
SemanticScholarPublicationAdapter: поиск публикаций через Semantic Scholar API.

Не возвращает строки биллинга (здесь нет платных вызовов).
"""

from __future__ import annotations

import logging
from typing import Any

from app.integrations.search.ports import RetrieverResult
from app.integrations.search.schemas import QueryModel, TimeSlice

from app.integrations.search.retrievers.publication.semanticscholar.client import (
    semanticscholar_search_papers,
)
from app.integrations.search.retrievers.publication.semanticscholar.mapper import (
    map_semanticscholar_paper_to_quantum,
)
from app.integrations.search.retrievers.publication.semanticscholar.query_compiler import (
    compile_semanticscholar_query,
)


logger = logging.getLogger(__name__)


class SemanticScholarPublicationAdapter:
    def __init__(
        self,
        *,
        timeout_s: float = 30.0,
        retries: int = 10,
        retry_delay_s: float = 2.0,
    ) -> None:
        self._timeout_s = timeout_s
        self._retries = retries
        self._retry_delay_s = retry_delay_s

    async def search_publications(
        self,
        query_model: QueryModel,
        terms_by_id: dict[str, Any],
        *,
        language: str,
        theme_id: str,
        run_id: str | None = None,
        time_slice: TimeSlice | None = None,
        limit: int = 50,
        require_abstract: bool = True,
        request_id: str | None = None,
        retriever_name: str = "publication_retriever",
    ) -> RetrieverResult:
        if not language or not isinstance(language, str) or not language.strip():
            raise ValueError("language is required for Semantic Scholar publication search")
        if not theme_id or not isinstance(theme_id, str) or not theme_id.strip():
            raise ValueError("theme_id is required for Semantic Scholar publication search")

        compiled = compile_semanticscholar_query(query_model, terms_by_id, language)
        logger.info(
            "search/adapter: provider=%s compiled_query=%s (request_id=%s)",
            "semantic_scholar",
            compiled,
            request_id,
        )

        # Ограничиваем число квантов после маппинга (bulk может вернуть до ~1000 записей за вызов).
        hard_limit = max(1, min(int(limit), 100))

        fields = (
            "title,abstract,url,venue,publicationVenue,journal,year,publicationDate,"
            "authors,externalIds,isOpenAccess,openAccessPdf,citationCount,fieldsOfStudy,"
            "publicationTypes"
        )

        logger.info(
            "search/adapter: provider=%s endpoint=bulk max_mapped_quanta=%s (request_id=%s)",
            "semantic_scholar",
            hard_limit,
            request_id,
        )

        data = await semanticscholar_search_papers(
            query=compiled,
            fields=fields,
            token=None,
            timeout_s=self._timeout_s,
            retries=self._retries,
            retry_delay_s=self._retry_delay_s,
            max_sleep_s=240.0,
            give_up_retry_after_s=240.0,
            total_timeout_s=240.0,
        )
        if not data:
            return RetrieverResult(items=[], billing_lines=[])

        items_raw = data.get("data") or []
        logger.info(
            "search/adapter: provider=%s response api_results=%s (request_id=%s)",
            "semantic_scholar",
            len(items_raw) if isinstance(items_raw, list) else 0,
            request_id,
        )

        quanta = []
        skipped_not_dict = 0
        skipped_mapper_none = 0
        if isinstance(items_raw, list):
            for p in items_raw:
                if not isinstance(p, dict):
                    skipped_not_dict += 1
                    continue
                q = map_semanticscholar_paper_to_quantum(
                    p,
                    compiled,
                    language,
                    theme_id=theme_id,
                    run_id=run_id,
                    require_abstract=require_abstract,
                    retriever_name=retriever_name,
                )
                if q is None:
                    skipped_mapper_none += 1
                    continue
                quanta.append(q)
                if len(quanta) >= hard_limit:
                    break

        logger.info(
            "search/adapter: provider=%s mapped_quanta=%s (request_id=%s); skipped: not_dict=%s, mapper_none=%s",
            "semantic_scholar",
            len(quanta),
            request_id,
            skipped_not_dict,
            skipped_mapper_none,
        )
        return RetrieverResult(items=quanta, billing_lines=[])

