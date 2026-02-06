"""
Retry-политика для вызовов LLM: ретраи на RequestError, 429, 5xx с async backoff.
"""
import asyncio
import logging
import random
from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import Any, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def with_retry(
    coro_factory: Callable[[], Coroutine[Any, Any, T]],
    retries: int = 3,
    base_delay: float = 0.5,
    jitter: float = 0.1,
) -> T:
    """
    Выполнить корутину с ретраями при httpx.RequestError и HTTP 429/5xx.

    coro_factory вызывается при каждой попытке (должен возвращать новую корутину).
    backoff: base_delay * (2 ** attempt) + jitter.
    """
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            coro = coro_factory()
            result = await coro
            return result
        except httpx.RequestError as e:
            last_exc = e
            logger.warning("LLM request error (attempt %s/%s): %s", attempt + 1, retries, e)
        except httpx.HTTPStatusError as e:
            last_exc = e
            if e.response.status_code == 429 or e.response.status_code >= 500:
                logger.warning(
                    "LLM HTTP %s (attempt %s/%s)",
                    e.response.status_code,
                    attempt + 1,
                    retries,
                )
            else:
                raise
        if attempt == retries - 1:
            break
        delay = base_delay * (2**attempt) + random.uniform(0, jitter)
        await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]
