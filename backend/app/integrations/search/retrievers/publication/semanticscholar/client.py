"""
HTTP-клиент для Semantic Scholar Academic Graph API.

MVP: используем неавторизованный вызов (без API key), с ретраями и задержкой,
чтобы не получить бан по IP при 429/перегрузке.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

import httpx


logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_BASE_URL = "https://api.semanticscholar.org/graph/v1"


async def semanticscholar_search_papers(
    *,
    query: str,
    fields: str,
    token: str | None = None,
    timeout_s: float = 30.0,
    retries: int = 10,
    retry_delay_s: float = 2.0,
    max_sleep_s: float = 120.0,
    give_up_retry_after_s: float = 120.0,
    total_timeout_s: float = 240.0,
) -> dict[str, Any] | None:
    """
    GET /paper/search/bulk

    Bulk-поиск: до ~1000 записей за вызов, синтаксис query (+|-|()|"|*).
    Пагинация через token в ответе (опционально).
    Возвращает JSON или None при ошибке после ретраев.
    """
    url = f"{SEMANTIC_SCHOLAR_BASE_URL}/paper/search/bulk"
    params: dict[str, Any] = {
        "query": query,
        "fields": fields,
    }
    if token and str(token).strip():
        params["token"] = str(token).strip()
    headers: dict[str, str] = {
        "accept": "application/json",
        # Semantic Scholar просит contact email/user-agent для трейсинга (best practice).
        "user-agent": "analyst/1.0 (no-api-key)",
    }

    def _retry_after_seconds(resp: httpx.Response) -> float | None:
        ra = resp.headers.get("retry-after")
        if not ra:
            return None
        try:
            # Обычно это секунды (int/float).
            return float(str(ra).strip())
        except Exception:
            return None

    # Ограничение по числу попыток не используем: прекращаем только по total_timeout_s
    # (параметр retries оставлен для совместимости сигнатуры).
    max_attempts = 10**9
    last_err: Exception | None = None
    last_status: int | None = None
    last_sleep_s: float | None = None
    long_sleep_logged = False
    prev_backoff_s: float | None = None
    start_ts = time.monotonic()
    for attempt in range(1, max_attempts + 1):
        if total_timeout_s and total_timeout_s > 0:
            elapsed = time.monotonic() - start_ts
            if elapsed >= float(total_timeout_s):
                logger.warning(
                    "Semantic Scholar API total timeout exceeded: total_timeout_s=%s, elapsed_s=%.3f",
                    total_timeout_s,
                    elapsed,
                )
                return None
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.get(url, params=params, headers=headers)
            last_status = resp.status_code
            if resp.status_code == 429:
                ra_s = _retry_after_seconds(resp)
                if ra_s is not None and ra_s > 0:
                    if ra_s > float(give_up_retry_after_s):
                        logger.warning(
                            "Semantic Scholar API Retry-After is too large (%ss > %ss); giving up",
                            ra_s,
                            give_up_retry_after_s,
                        )
                        return None
                    last_sleep_s = ra_s
                    raise RuntimeError(f"Semantic Scholar API rate limit (429); retry-after={ra_s}s")
                raise RuntimeError("Semantic Scholar API rate limit (429)")
            if resp.status_code >= 500:
                raise RuntimeError(f"Semantic Scholar API server error ({resp.status_code})")
            if resp.status_code >= 400:
                logger.warning(
                    "Semantic Scholar API request rejected (status=%s): %s",
                    resp.status_code,
                    resp.text[:500],
                )
                return None
            try:
                data = resp.json()
                if attempt > 1:
                    logger.info(
                        "Semantic Scholar API call succeeded after retries (last_status=%s, last_sleep_s=%s)",
                        last_status,
                        last_sleep_s,
                    )
                return data
            except Exception as e:
                raise RuntimeError("Semantic Scholar API: failed to parse JSON") from e
        except Exception as e:
            last_err = e
            # Не спамим лог на каждую попытку — ждём и пробуем снова.
            # Если есть Retry-After — соблюдаем его. Иначе: экспоненциальный backoff от retry_delay_s.
            if "retry-after=" in str(e) and last_sleep_s is not None and last_sleep_s > 0:
                sleep_s = last_sleep_s
            else:
                base = float(retry_delay_s) if retry_delay_s and retry_delay_s > 0 else 1.0
                if prev_backoff_s is None:
                    sleep_s = base
                else:
                    sleep_s = prev_backoff_s * 1.5
                # jitter 0..25% от sleep_s, чтобы не долбиться синхронно
                sleep_s += random.random() * (sleep_s * 0.25)
                prev_backoff_s = sleep_s
                last_sleep_s = sleep_s
            # Ограничиваем паузу, чтобы запрос не выглядел как "завис".
            cap = float(max_sleep_s) if isinstance(max_sleep_s, (int, float)) and max_sleep_s > 0 else 30.0
            if sleep_s > cap:
                sleep_s = cap
            # Уважаем общий таймаут: не спим дольше оставшегося времени.
            if total_timeout_s and total_timeout_s > 0:
                elapsed = time.monotonic() - start_ts
                remaining = float(total_timeout_s) - elapsed
                if remaining <= 0:
                    logger.warning(
                        "Semantic Scholar API total timeout exceeded before sleep: total_timeout_s=%s, elapsed_s=%.3f",
                        total_timeout_s,
                        elapsed,
                    )
                    return None
                if sleep_s > remaining:
                    sleep_s = max(0.0, remaining)
            if sleep_s >= 10 and not long_sleep_logged:
                long_sleep_logged = True
                logger.warning(
                    "Semantic Scholar API retry sleep is long: sleep_s=%s",
                    sleep_s,
                )
            await asyncio.sleep(sleep_s)

    # До сюда теоретически не дойдём: цикл бесконечный, но ограничен total_timeout_s.
    logger.warning("Semantic Scholar API failed: %s", str(last_err) if last_err else "unknown error")
    return None

