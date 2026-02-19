"""
OpenAlexPublicationAdapter: поиск публикаций через OpenAlex API.
Принимает QueryModel + language (обязательно) + time_slice (опционально),
возвращает list[InfoQuantum]. Дедуп и мультиязычность — не здесь.
"""
import logging
from typing import Any

from app.integrations.search.schemas import QueryModel, TimeSlice
from app.modules.quanta.schemas import QuantumCreate

from app.integrations.search.retrievers.publication.openalex.client import (
    openalex_search_works,
)
from app.integrations.search.retrievers.publication.openalex.query_compiler import (
    compile_openalex_query,
)
from app.integrations.search.retrievers.publication.openalex.local_filter import (
    passes_must_exclude,
)
from app.integrations.search.retrievers.publication.openalex.mapper import (
    map_openalex_work_to_quantum,
)

logger = logging.getLogger(__name__)

# Тип возвращаемого кванта (совместим с QuantumCreate)
InfoQuantum = QuantumCreate


class OpenAlexPublicationAdapter:
    """Адаптер поиска публикаций в OpenAlex. Не делает дедуп, не занимается многими языками."""

    def __init__(self, api_key: str = "", timeout_s: float = 30.0) -> None:
        self._api_key = api_key or ""
        self._timeout_s = timeout_s

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
    ) -> list[InfoQuantum]:
        """
        Поиск публикаций в OpenAlex по QueryModel.

        - language обязателен; если не передан — ValueError.
        - theme_id обязателен (передаётся из верхнего слоя поиска через retriever/контекст).
        - run_id опционален (ID прогона поиска, передаётся из контекста).
        - time_slice опционален (filter from_publication_date / to_publication_date).
        - Возвращает только публикации с summary_text (abstract), если require_abstract=True.
        - Локальная фильтрация MUST/EXCLUDE по title + summary_text.
        - Дедуп не выполняется.
        """
        if not language or not isinstance(language, str) or not language.strip():
            raise ValueError("language is required for OpenAlex publication search")
        if not theme_id or not isinstance(theme_id, str) or not theme_id.strip():
            raise ValueError("theme_id is required for OpenAlex publication search")

        compiled = compile_openalex_query(query_model, terms_by_id, language)
        from_date: str | None = None
        to_date: str | None = None
        if time_slice:
            from_date = time_slice.published_from.strftime("%Y-%m-%d")
            to_date = time_slice.published_to.strftime("%Y-%m-%d")

        try:
            data = await openalex_search_works(
                search=compiled,
                api_key=self._api_key,
                per_page=min(limit, 200),
                page=1,
                from_publication_date=from_date,
                to_publication_date=to_date,
                timeout_s=self._timeout_s,
            )
        except Exception as e:
            logger.exception("OpenAlex search failed (request_id=%s): %s", request_id, e)
            return []

        results_raw = data.get("results") or []
        quanta: list[InfoQuantum] = []
        for work in results_raw:
            if not isinstance(work, dict):
                continue
            q = map_openalex_work_to_quantum(
                work,
                compiled,
                language,
                theme_id=theme_id,
                run_id=run_id,
                require_abstract=require_abstract,
            )
            if q is None:
                continue
            if not passes_must_exclude(q, query_model, terms_by_id, language):
                continue
            quanta.append(q)
            if len(quanta) >= limit:
                break

        return quanta
