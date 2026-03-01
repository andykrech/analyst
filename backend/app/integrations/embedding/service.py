"""
Верхний слой эмбеддингов.
Выбирает провайдера по имени из конфига и делегирует ему построение вектора.
Возвращает JSONB-совместимый dict (vector + cost).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from app.core.config import Settings
from app.integrations.embedding.ports import EmbeddingCost, EmbeddingProviderPort, EmbeddingResult
from app.integrations.embedding.providers.openai import OpenAIEmbeddingProvider

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Сервис эмбеддингов: реестр провайдеров и имя текущего берутся из конфига.
    Вызывает провайдера с переданными моделью, размерностью, стоимостью за токен и текстом.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._registry: dict[str, EmbeddingProviderPort] = {
            "openai": OpenAIEmbeddingProvider(
                api_key=settings.OPENAI_API_KEY.get_secret_value(),
                base_url=settings.OPENAI_BASE_URL,
                timeout_s=settings.OPENAI_EMBEDDING_TIMEOUT_S,
                settings=settings,
            ),
        }
        self._provider_name = (settings.EMBEDDING_PROVIDER or "").strip() or "openai"

    def _get_provider(self, provider_name: str | None) -> EmbeddingProviderPort | None:
        name = (provider_name or self._provider_name).strip() or self._provider_name
        return self._registry.get(name)

    async def embed(
        self,
        text: str,
        *,
        provider_name: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
        cost_per_token: Decimal | None = None,
    ) -> dict[str, Any]:
        """
        Построить эмбеддинг для текста и вернуть JSONB-совместимый результат.

        Args:
            text: текст для эмбеддинга.
            provider_name: имя провайдера (если None — из конфига EMBEDDING_PROVIDER).
            model: модель (если None — из конфига EMBEDDING_MODEL).
            dimensions: размерность вектора (если None — из конфига EMBEDDING_DIMENSIONS).
            cost_per_token: стоимость за 1 токен (если None — из конфига EMBEDDING_COST_PER_TOKEN).

        Returns:
            Dict для JSONB: vector (list[float]), cost (dict с total_tokens, total_cost),
            при необходимости model, dimensions, provider.
            Стоимость берётся из ответа провайдера; если провайдер не вернул usage —
            считается как токены_оценка * cost_per_token.
        """
        provider = self._get_provider(provider_name)
        if not provider:
            logger.warning(
                "embedding: провайдер '%s' не найден в реестре",
                provider_name or self._provider_name,
            )
            raise ValueError(f"Embedding provider not found: {provider_name or self._provider_name}")

        model_val = (model or self._settings.EMBEDDING_MODEL or "").strip() or "text-embedding-3-small"
        dims_val = dimensions if dimensions is not None else self._settings.EMBEDDING_DIMENSIONS
        cost_per = cost_per_token if cost_per_token is not None else self._settings.EMBEDDING_COST_PER_TOKEN

        result = await provider.embed(
            text=text,
            model=model_val,
            dimensions=dims_val,
            cost_per_token=cost_per,
        )

        return _result_to_jsonb(result, provider.name, model_val, dims_val)


def _result_to_jsonb(
    result: EmbeddingResult,
    provider: str,
    model: str,
    dimensions: int,
) -> dict[str, Any]:
    """Преобразовать EmbeddingResult в dict, пригодный для JSONB (Decimal → float)."""
    cost = result.cost
    return {
        "vector": result.vector,
        "cost": {
            "total_tokens": cost.total_tokens,
            "total_cost": float(cost.total_cost),
        },
        "provider": provider,
        "model": model,
        "dimensions": dimensions,
    }
