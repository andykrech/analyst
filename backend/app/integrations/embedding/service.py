"""
Верхний слой эмбеддингов.
Выбирает провайдера по имени из конфига и делегирует ему построение вектора.
Возвращает JSONB-совместимый dict (vector + cost).
Опционально пишет billing_usage_events (service_type=embedding, unit_code=total_tokens).
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from app.core.config import Settings
from app.integrations.embedding.ports import EmbeddingCost, EmbeddingProviderPort, EmbeddingResult
from app.integrations.embedding.providers.openai import OpenAIEmbeddingProvider
from app.modules.billing.constants import (
    BillingQuantityUnitCode,
    BillingServiceType,
    embedding_tariff_service_impl,
)

if TYPE_CHECKING:
    from app.modules.billing.service import BillingService

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Сервис эмбеддингов: реестр провайдеров и имя текущего берутся из конфига.
    Вызывает провайдера с переданными моделью, размерностью, стоимостью за токен и текстом.
    """

    def __init__(self, settings: Settings, *, billing_service: "BillingService | None" = None) -> None:
        self._settings = settings
        self._billing_service = billing_service
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
        billing_session: Any | None = None,
        billing_theme_id: uuid.UUID | None = None,
        billing_task_type: str | None = None,
        billing_extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Построить эмбеддинг для текста и вернуть JSONB-совместимый результат.

        Args:
            text: текст для эмбеддинга.
            provider_name: имя провайдера (если None — из конфига EMBEDDING_PROVIDER).
            model: модель (если None — из конфига EMBEDDING_MODEL).
            dimensions: размерность вектора (если None — из конфига EMBEDDING_DIMENSIONS).
            cost_per_token: стоимость за 1 токен (если None — из конфига EMBEDDING_COST_PER_TOKEN).
            billing_session: AsyncSession — при наличии с billing_theme_id и billing_service пишется биллинг.
            billing_theme_id: тема для события расхода.
            billing_task_type: тип задачи (например theme_relevance_embedding, search_quantum_embedding).
            billing_extra: дополнительные поля в JSON события.

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

        await self._record_embedding_billing(
            provider_name=provider.name,
            model_val=model_val,
            total_tokens=result.cost.total_tokens,
            billing_session=billing_session,
            billing_theme_id=billing_theme_id,
            billing_task_type=billing_task_type,
            billing_extra=billing_extra,
        )

        return _result_to_jsonb(result, provider.name, model_val, dims_val)

    async def _record_embedding_billing(
        self,
        *,
        provider_name: str,
        model_val: str,
        total_tokens: int,
        billing_session: Any | None,
        billing_theme_id: uuid.UUID | None,
        billing_task_type: str | None,
        billing_extra: dict[str, Any] | None,
    ) -> None:
        if (
            self._billing_service is None
            or billing_session is None
            or billing_theme_id is None
            or billing_task_type is None
            or total_tokens <= 0
        ):
            return
        service_impl = embedding_tariff_service_impl(provider_name, model_val)
        extra: dict[str, Any] = {
            "provider": provider_name,
            "model": model_val,
            **(billing_extra or {}),
        }
        await self._billing_service.record_usage(
            billing_session,
            theme_id=billing_theme_id,
            task_type=billing_task_type,
            service_type=BillingServiceType.EMBEDDING.value,
            service_impl=service_impl,
            quantity=Decimal(total_tokens),
            quantity_unit_code=BillingQuantityUnitCode.TOTAL_TOKENS.value,
            extra=extra,
        )


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
