"""
Единый LLMService: вызов провайдера, нормализация ответа, подсчёт токенов и стоимости.
"""
import json
import math
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal

import httpx
from fastapi import Request

if TYPE_CHECKING:
    from app.integrations.prompts.service import PromptService

from app.core.config import ProviderPricing, Settings, get_settings
from app.integrations.llm.factory import get_provider
from app.integrations.llm.policies.retry import with_retry
from app.integrations.llm.types import (
    CostBreakdown,
    GenerationParams,
    LLMRequest,
    LLMResponse,
    Message,
    TokenUsage,
)

OVERHEAD_TOTAL = 12
OVERHEAD_PER_MESSAGE = 8
CHARS_PER_TOKEN_ESTIMATE = 4


class LLMService:
    """
    Единый сервис вызова LLM: провайдер, нормализация, токены, стоимость.

    Пример использования (без реального запроса):

        settings = get_settings()
        service = LLMService(settings)
        messages = [
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="Hello!"),
        ]
        response = await service.generate_text(messages)
        print(response.text, response.usage.total_tokens, response.cost.total_cost)
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def generate_text(
        self,
        messages: list[dict[str, Any]] | list[Message],
        provider: str | None = None,
        task: str | None = None,
        generation: dict[str, Any] | GenerationParams | None = None,
        response_format: Literal["text", "json"] = "text",
    ) -> LLMResponse:
        """
        Вызвать LLM и вернуть нормализованный ответ с usage и стоимостью.

        Если провайдер не вернул usage — токены оцениваются локально, в response.warnings
        добавляются предупреждения.
        """
        provider_name = (provider or self._settings.LLM_DEFAULT_PROVIDER).strip().lower()
        if provider_name not in self._settings.llm_registry:
            raise ValueError(f"Unknown LLM provider: {provider_name}")
        provider_config = self._settings.llm_registry[provider_name]

        msg_list: list[Message] = [
            m if isinstance(m, Message) else Message(role=m["role"], content=m["content"])
            for m in messages
        ]
        gen_params: GenerationParams | None = None
        if generation is not None:
            if isinstance(generation, GenerationParams):
                gen_params = generation
            else:
                gen_params = GenerationParams(
                    temperature=generation.get("temperature"),
                    max_tokens=generation.get("max_tokens"),
                    top_p=generation.get("top_p"),
                )

        request = LLMRequest(
            task=task,
            messages=msg_list,
            response_format=response_format,
            generation=gen_params,
        )

        async with httpx.AsyncClient() as client:
            provider_impl = get_provider(provider_name, self._settings, client)

            async def _call() -> dict:
                return await provider_impl.generate(request)

            start = time.perf_counter()
            raw_result = await with_retry(_call)
            latency_ms = int((time.perf_counter() - start) * 1000)

        text = raw_result.get("text") or ""
        model = raw_result.get("model")
        raw = raw_result.get("raw")
        finish_reason = raw_result.get("finish_reason")
        usage_from_provider = raw_result.get("usage")
        warnings: list[str] = []

        if usage_from_provider and isinstance(usage_from_provider, dict):
            pt = int(usage_from_provider.get("prompt_tokens", 0))
            ct = int(usage_from_provider.get("completion_tokens", 0))
            tt = int(usage_from_provider.get("total_tokens", pt + ct))
            usage = TokenUsage(
                prompt_tokens=pt,
                completion_tokens=ct,
                total_tokens=tt,
                source="provider",
            )
        else:
            usage = self._estimate_usage(msg_list, text)
            usage = TokenUsage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                source="estimated",
            )
            warnings.append("usage_estimated_locally_no_provider_usage")
            warnings.append("token_estimation_heuristic_chars_per_token_4")

        cost = self._calculate_cost(usage, provider_config.pricing)

        return LLMResponse(
            text=text,
            provider=provider_name,
            model=model,
            usage=usage,
            cost=cost,
            raw=raw,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            warnings=warnings,
        )

    async def generate_from_prompt(
        self,
        prompt_name: str,
        vars: dict[str, Any],
        prompt_service: "PromptService",
        provider: str | None = None,
        task: str | None = None,
        generation: dict[str, Any] | GenerationParams | None = None,
    ) -> LLMResponse:
        """
        Сгенерировать ответ по имени промпта и переменным.

        Рендерит промпт через PromptService, формирует одно system-сообщение,
        вызывает generate_text и возвращает ответ. При response_format=json
        добавляет warning "response_not_valid_json", если текст не парсится как JSON.
        """
        rendered = await prompt_service.render(prompt_name, vars)
        messages: list[Message] = [Message(role="system", content=rendered.text)]
        task_val = task or prompt_name
        response = await self.generate_text(
            messages,
            provider=provider,
            task=task_val,
            generation=generation,
            response_format=rendered.response_format,
        )
        response.warnings = list(rendered.warnings) + list(response.warnings)
        if rendered.response_format == "json" and response.text.strip():
            try:
                json.loads(response.text.strip())
            except (ValueError, json.JSONDecodeError):
                response.warnings.append("response_not_valid_json")
        return response

    def _estimate_usage(self, messages: list[Message], answer_text: str) -> TokenUsage:
        """Оценка токенов: ~chars/4 + overhead."""
        prompt_chars = sum(len(m.content) for m in messages)
        n_messages = len(messages)
        prompt_tokens = math.ceil(prompt_chars / CHARS_PER_TOKEN_ESTIMATE) + OVERHEAD_TOTAL + OVERHEAD_PER_MESSAGE * n_messages
        completion_tokens = math.ceil(len(answer_text) / CHARS_PER_TOKEN_ESTIMATE)
        total_tokens = prompt_tokens + completion_tokens
        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            source="estimated",
        )

    def _calculate_cost(self, usage: TokenUsage, pricing: ProviderPricing) -> CostBreakdown:
        """Стоимость по тарифу за 1M токенов."""
        prompt_cost = Decimal(usage.prompt_tokens) / Decimal(1_000_000) * pricing.prompt_per_1m
        completion_cost = Decimal(usage.completion_tokens) / Decimal(1_000_000) * pricing.completion_per_1m
        total_cost = prompt_cost + completion_cost
        return CostBreakdown(
            currency=pricing.currency,
            prompt_cost=prompt_cost,
            completion_cost=completion_cost,
            total_cost=total_cost,
            unit="per_1m",
            usage_source=usage.source,
        )


def get_llm_service(request: Request) -> LLMService:
    """
    Dependency: вернуть LLMService из app.state (регистрируется при старте в lifespan).

    Использование в роутере: llm_service: LLMService = Depends(get_llm_service).
    """
    return request.app.state.llm_service
