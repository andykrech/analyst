"""
HTTP-клиент для OpenAlex API (GET /works).
Поддержка search, filter по датам, api_key в query.
"""
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OPENALEX_WORKS_URL = "https://api.openalex.org/works"


async def openalex_search_works(
    *,
    search: str,
    api_key: str = "",
    per_page: int = 200,
    page: int = 1,
    from_publication_date: str | None = None,
    to_publication_date: str | None = None,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """
    GET https://api.openalex.org/works с параметрами search, filter, pagination.

    - search: boolean-запрос (компилированный).
    - api_key: query-параметр (обязателен с 2026).
    - from_publication_date / to_publication_date: YYYY-MM-DD для filter.
    Возвращает сырой JSON ответа (meta + results).
    При ошибке сети/API логирует и пробрасывает исключение.
    """
    params: dict[str, str | int] = {
        "search": search,
        "per-page": min(per_page, 200),
        "page": page,
    }
    if api_key:
        params["api_key"] = api_key

    filters: list[str] = []
    if from_publication_date:
        filters.append(f"from_publication_date:{from_publication_date}")
    if to_publication_date:
        filters.append(f"to_publication_date:{to_publication_date}")
    if filters:
        params["filter"] = ",".join(filters)

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            resp = await client.get(OPENALEX_WORKS_URL, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning("OpenAlex API HTTP error: %s %s", e.response.status_code, e.response.text)
            raise
        except httpx.RequestError as e:
            logger.warning("OpenAlex API request error: %s", e)
            raise
