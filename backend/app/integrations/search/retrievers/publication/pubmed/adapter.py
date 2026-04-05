"""
PubMedPublicationAdapter: поиск через NCBI E-utilities (esearch + efetch).

Биллинга нет (бесплатный API).
"""

from __future__ import annotations

import logging
from typing import Any

from app.integrations.search.ports import RetrieverResult
from app.integrations.search.schemas import QueryModel, TimeSlice
from app.modules.quanta.schemas import QuantumCreate

from app.integrations.search.retrievers.publication.pubmed.client import (
    _EFETCH_BATCH,
    pubmed_efetch_xml,
    pubmed_esearch,
)
from app.integrations.search.retrievers.publication.pubmed.mapper import (
    iter_pubmed_medline_citations,
    map_pubmed_article_to_quantum,
)
from app.integrations.search.retrievers.publication.pubmed.query_compiler import (
    compile_pubmed_term,
)

logger = logging.getLogger(__name__)


class PubMedPublicationAdapter:
    def __init__(
        self,
        *,
        tool: str,
        email: str,
        api_key: str = "",
        timeout_esearch_s: float = 60.0,
        timeout_efetch_s: float = 120.0,
    ) -> None:
        self._tool = (tool or "").strip()
        self._email = (email or "").strip()
        self._api_key = (api_key or "").strip()
        self._timeout_esearch_s = timeout_esearch_s
        self._timeout_efetch_s = timeout_efetch_s

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
            raise ValueError("language is required for PubMed publication search")
        if not theme_id or not isinstance(theme_id, str) or not theme_id.strip():
            raise ValueError("theme_id is required for PubMed publication search")

        if not self._tool:
            logger.warning(
                "search/adapter: provider=%s skip — NCBI_TOOL пуст (request_id=%s)",
                "pubmed",
                request_id,
            )
            return RetrieverResult(items=[], billing_lines=[])
        if not self._email:
            logger.warning(
                "search/adapter: provider=%s skip — NCBI_EMAIL пуст (request_id=%s)",
                "pubmed",
                request_id,
            )
            return RetrieverResult(items=[], billing_lines=[])

        compiled = compile_pubmed_term(
            query_model, terms_by_id, language, time_slice=time_slice
        ).strip()
        cq_log = compiled[:2000] + ("…" if len(compiled) > 2000 else "")
        logger.info(
            "search/adapter: provider=%s compiled_query=%s (request_id=%s)",
            "pubmed",
            cq_log,
            request_id,
        )

        if not compiled:
            logger.info(
                "search/adapter: provider=%s empty term, skip (request_id=%s)",
                "pubmed",
                request_id,
            )
            return RetrieverResult(items=[], billing_lines=[])

        # Как у arXiv: добираем страницы esearch+efetch, пока не наберём limit валидных квантов
        # (с абстрактом), либо пока выдача не кончится.
        want = max(1, int(limit))
        quanta: list[QuantumCreate] = []
        skipped_mapper_none = 0
        retstart = 0
        total_hint: int | None = None
        seen_pmids: set[str] = set()
        esearch_pages = 0
        # Защита от бесконечного цикла при сбоях API
        _max_retstart = 50_000

        logger.info(
            "search/adapter: provider=%s target_mapped_quanta=%s (request_id=%s)",
            "pubmed",
            want,
            request_id,
        )

        while len(quanta) < want and retstart < _max_retstart:
            deficit = want - len(quanta)
            # Одна страница esearch: до 200 PMID, как типичный батч efetch
            batch_need = min(_EFETCH_BATCH, max(deficit, 1))

            chunk, tot = await pubmed_esearch(
                term=compiled,
                retstart=retstart,
                retmax=batch_need,
                tool=self._tool,
                email=self._email,
                api_key=self._api_key,
                timeout_s=self._timeout_esearch_s,
            )
            esearch_pages += 1
            if total_hint is None:
                total_hint = tot
            if not chunk:
                break

            new_ids: list[str] = []
            for p in chunk:
                if p not in seen_pmids:
                    seen_pmids.add(p)
                    new_ids.append(p)
            retstart += len(chunk)

            if not new_ids:
                if len(chunk) < batch_need:
                    break
                continue

            xml = await pubmed_efetch_xml(
                pmids=new_ids,
                tool=self._tool,
                email=self._email,
                api_key=self._api_key,
                timeout_s=self._timeout_efetch_s,
            )
            citations = iter_pubmed_medline_citations(xml)
            logger.info(
                "search/adapter: provider=%s page=%s esearch_retstart=%s pmids=%s efetch_citations=%s mapped_so_far=%s (request_id=%s)",
                "pubmed",
                esearch_pages,
                retstart - len(chunk),
                len(new_ids),
                len(citations),
                len(quanta),
                request_id,
            )
            for mc in citations:
                q = map_pubmed_article_to_quantum(
                    mc,
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
                if len(quanta) >= want:
                    break

            if len(chunk) < batch_need:
                break

        logger.info(
            "search/adapter: provider=%s esearch_pages=%s total_hint=%s seen_pmids=%s (request_id=%s)",
            "pubmed",
            esearch_pages,
            total_hint,
            len(seen_pmids),
            request_id,
        )
        logger.info(
            "search/adapter: provider=%s mapped_quanta=%s (request_id=%s); skipped mapper_none=%s",
            "pubmed",
            len(quanta),
            request_id,
            skipped_mapper_none,
        )
        return RetrieverResult(items=quanta[:want], billing_lines=[])
