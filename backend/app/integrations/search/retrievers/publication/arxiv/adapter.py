"""
ArxivPublicationAdapter: поиск публикаций через arXiv API (Atom).

Не возвращает строки биллинга (бесплатный API).
"""

from __future__ import annotations

import logging
from typing import Any

from app.integrations.search.ports import RetrieverResult
from app.modules.quanta.schemas import QuantumCreate
from app.integrations.search.schemas import QueryModel, TimeSlice

from app.integrations.search.retrievers.publication.arxiv.client import arxiv_search_query
from app.integrations.search.retrievers.publication.arxiv.mapper import (
    map_arxiv_entry_to_quantum,
    parse_arxiv_atom,
)
from app.integrations.search.retrievers.publication.arxiv.query_compiler import (
    compile_arxiv_query,
)

logger = logging.getLogger(__name__)

# arXiv: не более 2000 результатов за один запрос; общий лимит выдачи ~30000 по start.
_ARXIV_PAGE_MAX = 2000
_ARXIV_START_CAP = 28000


class ArxivPublicationAdapter:
    def __init__(
        self,
        *,
        timeout_s: float = 60.0,
        retries: int = 5,
    ) -> None:
        self._timeout_s = timeout_s
        self._retries = retries

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
            raise ValueError("language is required for arXiv publication search")
        if not theme_id or not isinstance(theme_id, str) or not theme_id.strip():
            raise ValueError("theme_id is required for arXiv publication search")

        compiled = compile_arxiv_query(
            query_model, terms_by_id, language, time_slice=time_slice
        ).strip()
        logger.info(
            "search/adapter: provider=%s compiled_query=%s (request_id=%s)",
            "arxiv",
            compiled[:2000] + ("…" if len(compiled) > 2000 else ""),
            request_id,
        )

        if not compiled or compiled == " ":
            logger.info(
                "search/adapter: provider=%s empty query, skip (request_id=%s)",
                "arxiv",
                request_id,
            )
            return RetrieverResult(items=[], billing_lines=[])

        want = max(1, int(limit))
        quanta: list[QuantumCreate] = []
        start = 0
        skipped_mapper_none = 0

        while len(quanta) < want and start <= _ARXIV_START_CAP:
            batch = min(_ARXIV_PAGE_MAX, want - len(quanta))
            xml = await arxiv_search_query(
                search_query=compiled,
                start=start,
                max_results=batch,
                timeout_s=self._timeout_s,
                retries=self._retries,
            )
            if not xml:
                break

            entries, total_hint = parse_arxiv_atom(xml)
            logger.info(
                "search/adapter: provider=%s page start=%s raw_entries=%s total_hint=%s (request_id=%s)",
                "arxiv",
                start,
                len(entries),
                total_hint,
                request_id,
            )

            if not entries:
                break

            for e in entries:
                q = map_arxiv_entry_to_quantum(
                    e,
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

            if len(entries) < batch:
                break
            start += len(entries)

        logger.info(
            "search/adapter: provider=%s mapped_quanta=%s (request_id=%s); skipped mapper_none=%s",
            "arxiv",
            len(quanta),
            request_id,
            skipped_mapper_none,
        )
        return RetrieverResult(items=quanta, billing_lines=[])
