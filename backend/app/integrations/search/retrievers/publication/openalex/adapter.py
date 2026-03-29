"""
OpenAlexPublicationAdapter: поиск публикаций через OpenAlex API.
Принимает QueryModel + language (обязательно) + time_slice (опционально),
возвращает кванты и строки биллинга (одна строка на успешный HTTP-запрос, не 5xx).
"""
import logging
from decimal import Decimal
from typing import Any

from app.integrations.search.ports import RetrieverResult, SearchBillingUsageLine
from app.integrations.search.schemas import QueryModel, TimeSlice
from app.modules.quanta.schemas import QuantumCreate

from app.integrations.search.retrievers.publication.openalex.client import (
    openalex_search_works,
)
from app.integrations.search.retrievers.publication.openalex.query_compiler import (
    compile_openalex_query,
)
from app.integrations.search.retrievers.publication.openalex.mapper import (
    map_openalex_work_to_quantum,
)

logger = logging.getLogger(__name__)

# Совпадает с billing_tariffs (сид): service_type=search, unit_code=requests
OPENALEX_SEARCH_SERVICE_TYPE = "search"
OPENALEX_SEARCH_SERVICE_IMPL = "openalex_fulltext-search"
OPENALEX_SEARCH_UNIT_CODE = "requests"

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
        step_id: str | None = None,
        source_query_id: str | None = None,
    ) -> RetrieverResult:
        """
        Поиск публикаций в OpenAlex по QueryModel.

        Биллинг: одна строка на успешный ответ API (статус < 500), даже если results пусты.
        Исключение или 5xx — без строк биллинга, кванты пустые.
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

        logger.info(
            "search/adapter: OpenAlex запрос, limit=%s, per_page=%s (request_id=%s)",
            limit,
            min(limit, 200),
            request_id,
        )
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
            return RetrieverResult(items=[], billing_lines=[])

        if data is None:
            return RetrieverResult(items=[], billing_lines=[])

        billing_extra: dict[str, Any] = {
            "provider": "openalex",
            "request_id": request_id,
        }
        if step_id is not None:
            billing_extra["step_id"] = step_id
        if source_query_id is not None:
            billing_extra["source_query_id"] = source_query_id

        billing_lines = [
            SearchBillingUsageLine(
                service_type=OPENALEX_SEARCH_SERVICE_TYPE,
                service_impl=OPENALEX_SEARCH_SERVICE_IMPL,
                quantity=Decimal(1),
                quantity_unit_code=OPENALEX_SEARCH_UNIT_CODE,
                extra=billing_extra,
            )
        ]

        results_raw = data.get("results") or []
        logger.info(
            "search/adapter: OpenAlex ответ, пришло результатов из API=%s (request_id=%s)",
            len(results_raw),
            request_id,
        )
        quanta: list[InfoQuantum] = []
        skipped_not_dict = 0
        skipped_mapper_none = 0
        for work in results_raw:
            if not isinstance(work, dict):
                skipped_not_dict += 1
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
                skipped_mapper_none += 1
                continue
            quanta.append(q)
            if len(quanta) >= limit:
                break

        logger.info(
            "search/adapter: OpenAlex возврат квантов после фильтров=%s (request_id=%s); отсеяно: not_dict=%s, mapper_none=%s",
            len(quanta),
            request_id,
            skipped_not_dict,
            skipped_mapper_none,
        )
        return RetrieverResult(items=quanta, billing_lines=billing_lines)
