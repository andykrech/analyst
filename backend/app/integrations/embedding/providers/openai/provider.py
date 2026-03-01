"""
Провайдер эмбеддингов OpenAI (REST API).
Запросы идут через туннель (get_httpx_proxy).
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal

import httpx

from app.core.config import Settings
from app.integrations.embedding.ports import EmbeddingCost, EmbeddingResult, EmbeddingProviderPort
from app.integrations.tunnel import get_httpx_proxy

logger = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    """Грубая оценка числа токенов (~4 символа на токен для английского)."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


class OpenAIEmbeddingProvider:
    """Провайдер эмбеддингов через OpenAI Embeddings API."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout_s: int | float,
        settings: Settings,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_s = float(timeout_s)
        self._settings = settings

    @property
    def name(self) -> str:
        return "openai"

    async def embed(
        self,
        text: str,
        model: str,
        dimensions: int,
        cost_per_token: Decimal,
    ) -> EmbeddingResult:
        """
        Построить эмбеддинг через POST /v1/embeddings.
        Стоимость: из usage.total_tokens, если есть; иначе оценка по тексту * cost_per_token.
        """
        if not (self._api_key or self._api_key.strip()):
            raise ValueError("OpenAI API key is not set")

        body: dict = {
            "model": model,
            "input": text.strip() or " ",
        }
        if dimensions > 0:
            body["dimensions"] = dimensions

        proxy = get_httpx_proxy(self._settings)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self._base_url}/v1/embeddings"
        max_retries = getattr(self._settings, "OPENAI_EMBEDDING_MAX_RETRIES", 3)
        retry_delay_s = getattr(self._settings, "OPENAI_EMBEDDING_RETRY_DELAY_S", 2.0)
        logger.debug(
            "OpenAI Embeddings request: url=%s model=%s dimensions=%s input_len=%s proxy=%s timeout=%s retries=%s",
            url,
            model,
            dimensions,
            len(body.get("input", "")),
            proxy if proxy else "none",
            self._timeout_s,
            max_retries,
        )

        async with httpx.AsyncClient(proxy=proxy, timeout=self._timeout_s) as client:
            for attempt in range(max_retries):
                try:
                    resp = await client.post(
                        url,
                        json=body,
                        headers=headers,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    break
                except httpx.HTTPStatusError as e:
                    # 429 (rate limit) или 5xx — повторяем; 4xx (кроме 429) — не повторяем
                    if e.response.status_code == 429 or e.response.status_code >= 500:
                        if attempt < max_retries - 1:
                            logger.warning(
                                "OpenAI Embeddings API HTTP error (attempt %s/%s): status=%s, retry in %.1fs",
                                attempt + 1,
                                max_retries,
                                e.response.status_code,
                                retry_delay_s,
                            )
                            await asyncio.sleep(retry_delay_s)
                            continue
                    logger.warning(
                        "OpenAI Embeddings API HTTP error: url=%s status=%s body=%s",
                        url,
                        e.response.status_code,
                        (e.response.text or "")[:2000],
                    )
                    raise
                except httpx.RequestError as e:
                    cause = getattr(e, "__cause__", None)
                    if attempt < max_retries - 1:
                        logger.warning(
                            "OpenAI Embeddings API request error (attempt %s/%s): %s, retry in %.1fs",
                            attempt + 1,
                            max_retries,
                            e,
                            retry_delay_s,
                        )
                        await asyncio.sleep(retry_delay_s)
                        continue
                    logger.warning(
                        "OpenAI Embeddings API request error: url=%s proxy=%s error=%s (%s)%s",
                        url,
                        proxy if proxy else "none",
                        type(e).__name__,
                        e,
                        f" cause={cause!r}" if cause else "",
                    )
                    if cause:
                        logger.debug("OpenAI Embeddings request cause: %s", cause, exc_info=True)
                    raise

        # Вектор из data.data[0].embedding
        items = data.get("data") or []
        if not items or "embedding" not in items[0]:
            raise ValueError("OpenAI response missing data[0].embedding")
        vector = list(items[0]["embedding"])

        # Токены и стоимость
        usage = data.get("usage") or {}
        total_tokens = int(usage.get("total_tokens") or usage.get("prompt_tokens") or 0)
        if total_tokens <= 0:
            total_tokens = _estimate_tokens(text)
        total_cost = cost_per_token * total_tokens

        return EmbeddingResult(
            vector=vector,
            cost=EmbeddingCost(total_tokens=total_tokens, total_cost=total_cost),
        )
