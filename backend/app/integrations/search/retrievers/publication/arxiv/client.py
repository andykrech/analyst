"""
HTTP-клиент arXiv API (Atom XML).

Рекомендация arXiv: ~3 с между последовательными вызовами — соблюдаем перед каждым запросом.
Длинный search_query: POST с form-data.
"""
from __future__ import annotations

import asyncio
import logging
import time
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
MIN_INTERVAL_S = 3.0
POST_QUERY_THRESHOLD = 1800


def _encode_arxiv_query_params(search_query: str, start: int, max_results: int) -> str:
    """
    Кодирование параметров в стиле руководства arXiv: пробелы как «+», скобки и пр. — %XX.

    См. https://info.arxiv.org/help/api/user-manual.html#query_details
    (urlencode с quote_plus по умолчанию).
    """
    return urlencode(
        {
            "search_query": search_query,
            "start": str(start),
            "max_results": str(max_results),
        },
    )


class _ArxivRateLimiter:
    _lock = asyncio.Lock()
    _last_request_end: float = 0.0

    @classmethod
    async def wait_turn(cls) -> None:
        async with cls._lock:
            now = time.monotonic()
            wait = MIN_INTERVAL_S - (now - cls._last_request_end)
            if wait > 0:
                await asyncio.sleep(wait)

    @classmethod
    def mark_done(cls) -> None:
        cls._last_request_end = time.monotonic()


async def arxiv_search_query(
    *,
    search_query: str,
    start: int = 0,
    max_results: int = 50,
    timeout_s: float = 60.0,
    retries: int = 5,
) -> str | None:
    """
    Выполнить запрос к arXiv API, вернуть тело ответа (XML) или None.

    Между повторными попытками — пауза MIN_INTERVAL_S (этика arXiv).
    """
    sq = (search_query or "").strip()
    if not sq or sq == " ":
        return None

    mr = max(1, min(int(max_results), 2000))
    st = max(0, int(start))

    last_err: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        await _ArxivRateLimiter.wait_turn()
        try:
            encoded = _encode_arxiv_query_params(sq, st, mr)
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                if len(sq) > POST_QUERY_THRESHOLD:
                    resp = await client.post(
                        ARXIV_API_URL,
                        content=encoded,
                        headers={
                            "Content-Type": "application/x-www-form-urlencoded",
                        },
                    )
                else:
                    resp = await client.get(f"{ARXIV_API_URL}?{encoded}")
            _ArxivRateLimiter.mark_done()
            if resp.status_code >= 500:
                raise RuntimeError(f"arXiv API server error ({resp.status_code})")
            if resp.status_code >= 400:
                logger.warning(
                    "arXiv API request rejected (status=%s): %s",
                    resp.status_code,
                    (resp.text or "")[:500],
                )
                return None
            return resp.text
        except Exception as e:
            last_err = e
            _ArxivRateLimiter.mark_done()
            if attempt >= retries:
                break
            logger.warning("arXiv API call failed (will retry after %ss): %s", MIN_INTERVAL_S, e)
            await asyncio.sleep(MIN_INTERVAL_S)

    logger.warning("arXiv API failed after retries: %s", last_err)
    return None
