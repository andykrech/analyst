"""
NCBI E-utilities: esearch + efetch для PubMed.

Лимиты: с api_key до ~10 запросов/с; без ключа — ~3/с. Соблюдаем паузу между запросами.
Длинный term — POST (application/x-www-form-urlencoded).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ESEARCH_URL = f"{EUTILS_BASE}/esearch.fcgi"
EFETCH_URL = f"{EUTILS_BASE}/efetch.fcgi"

# Интервал между последовательными вызовами (сек): с ключом чаще, без — реже.
_MIN_INTERVAL_WITH_KEY_S = 0.11
_MIN_INTERVAL_NO_KEY_S = 0.35
_POST_TERM_THRESHOLD = 1500
_EFETCH_BATCH = 200


class _NcbiRateLimiter:
    _lock = asyncio.Lock()
    _last_end: float = 0.0

    @classmethod
    async def wait_turn(cls, *, has_api_key: bool) -> None:
        interval = _MIN_INTERVAL_WITH_KEY_S if has_api_key else _MIN_INTERVAL_NO_KEY_S
        async with cls._lock:
            now = time.monotonic()
            wait = interval - (now - cls._last_end)
            if wait > 0:
                await asyncio.sleep(wait)

    @classmethod
    def mark_done(cls) -> None:
        cls._last_end = time.monotonic()


def _base_params(*, tool: str, email: str, api_key: str) -> dict[str, str]:
    p: dict[str, str] = {"tool": tool, "email": email}
    if api_key and api_key.strip():
        p["api_key"] = api_key.strip()
    return p


async def pubmed_esearch(
    *,
    term: str,
    retstart: int,
    retmax: int,
    tool: str,
    email: str,
    api_key: str,
    timeout_s: float = 60.0,
) -> tuple[list[str], int | None]:
    """
    ESearch db=pubmed. Возвращает (список PMID, total из result или None).
    """
    t = (term or "").strip()
    if not t:
        return [], None

    rm = max(1, min(int(retmax), 10_000))
    rs = max(0, int(retstart))

    params: dict[str, Any] = {
        **_base_params(tool=tool, email=email, api_key=api_key),
        "db": "pubmed",
        "term": t,
        "retstart": str(rs),
        "retmax": str(rm),
        "retmode": "json",
    }

    body = urlencode(params)
    has_key = bool(api_key and api_key.strip())

    await _NcbiRateLimiter.wait_turn(has_api_key=has_key)
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            if len(t) > _POST_TERM_THRESHOLD:
                resp = await client.post(
                    ESEARCH_URL,
                    content=body,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            else:
                resp = await client.get(f"{ESEARCH_URL}?{body}")
        _NcbiRateLimiter.mark_done()
        if resp.status_code >= 400:
            logger.warning(
                "PubMed esearch HTTP %s: %s",
                resp.status_code,
                (resp.text or "")[:500],
            )
            return [], None
        data = resp.json()
        r = data.get("esearchresult") or {}
        ids = r.get("idlist") or []
        if not isinstance(ids, list):
            ids = []
        total_s = r.get("count")
        total: int | None = None
        if isinstance(total_s, str) and total_s.isdigit():
            total = int(total_s)
        elif isinstance(total_s, int):
            total = total_s
        out = [str(x) for x in ids if x is not None]
        return out, total
    except Exception as e:
        _NcbiRateLimiter.mark_done()
        logger.warning("PubMed esearch failed: %s", e)
        return [], None


async def pubmed_efetch_xml(
    *,
    pmids: list[str],
    tool: str,
    email: str,
    api_key: str,
    timeout_s: float = 120.0,
) -> str:
    """EFetch db=pubmed, retmode=xml. pmids непустой список."""
    if not pmids:
        return ""
    params: dict[str, Any] = {
        **_base_params(tool=tool, email=email, api_key=api_key),
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }
    body = urlencode(params)
    has_key = bool(api_key and api_key.strip())

    await _NcbiRateLimiter.wait_turn(has_api_key=has_key)
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                EFETCH_URL,
                content=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        _NcbiRateLimiter.mark_done()
        if resp.status_code >= 400:
            logger.warning(
                "PubMed efetch HTTP %s: %s",
                resp.status_code,
                (resp.text or "")[:500],
            )
            return ""
        return resp.text or ""
    except Exception as e:
        _NcbiRateLimiter.mark_done()
        logger.warning("PubMed efetch failed: %s", e)
        return ""
