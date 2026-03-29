"""
Единый LLMService: вызов провайдера, нормализация ответа, подсчёт токенов.
Биллинг LLM: service_type=llm, service_impl={provider}_{model}_{in|out}, единицы input/output_tokens.
"""
import json
import math
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal

import httpx
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.integrations.prompts.service import PromptService
    from app.modules.billing.service import BillingService

from app.core.config import Settings
from app.integrations.llm.factory import get_provider
from app.integrations.llm.policies.retry import with_retry
from app.integrations.llm.types import (
    GenerationParams,
    LLMRequest,
    LLMResponse,
    Message,
    TokenUsage,
)
from app.modules.billing.constants import (
    BillingQuantityUnitCode,
    BillingServiceType,
    llm_tariff_service_impl,
)

OVERHEAD_TOTAL = 12
OVERHEAD_PER_MESSAGE = 8
CHARS_PER_TOKEN_ESTIMATE = 4


class LLMService:
    """
    Единый сервис вызова LLM: провайдер, нормализация, токены.

    Для записи в биллинг передайте billing_session и billing_theme_id (и зарегистрируйте BillingService в приложении).
    """

    def __init__(
        self,
        settings: Settings,
        *,
        billing_service: "BillingService | None" = None,
    ) -> None:
        self._settings = settings
        self._billing_service = billing_service

    async def generate_text(
        self,
        messages: list[dict[str, Any]] | list[Message],
        provider: str | None = None,
        task: str | None = None,
        generation: dict[str, Any] | GenerationParams | None = None,
        response_format: Literal["text", "json"] = "text",
        *,
        billing_session: AsyncSession | None = None,
        billing_theme_id: uuid.UUID | None = None,
    ) -> LLMResponse:
        """
        Вызвать LLM и вернуть нормализованный ответ с usage.

        Если провайдер не вернул usage — токены оцениваются локально, в response.warnings
        добавляются предупреждения.

        billing_session + billing_theme_id: запись в billing_usage_events для любого провайдера из реестра
        по фактическому или оценочному usage.
        """
        provider_name = (provider or self._settings.LLM_DEFAULT_PROVIDER).strip().lower()
        if provider_name not in self._settings.llm_registry:
            raise ValueError(f"Unknown LLM provider: {provider_name}")

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

        billing_on = (
            self._billing_service is not None
            and billing_session is not None
            and billing_theme_id is not None
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

        if billing_on:
            bs = self._billing_service
            if bs is not None and billing_session is not None and billing_theme_id is not None:
                model_str = model if isinstance(model, str) else (str(model) if model is not None else None)
                reg = self._settings.llm_registry.get(provider_name)
                fallback_model = reg.model if reg else None
                await self._record_llm_billing(
                    bs,
                    billing_session,
                    theme_id=billing_theme_id,
                    provider_name=provider_name,
                    task=task,
                    model=model_str or fallback_model,
                    usage=usage,
                )

        return LLMResponse(
            text=text,
            provider=provider_name,
            model=model,
            usage=usage,
            cost=None,
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
        *,
        billing_session: AsyncSession | None = None,
        billing_theme_id: uuid.UUID | None = None,
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
            billing_session=billing_session,
            billing_theme_id=billing_theme_id,
        )
        response.warnings = list(rendered.warnings) + list(response.warnings)
        if rendered.response_format == "json" and response.text.strip():
            try:
                json.loads(response.text.strip())
            except (ValueError, json.JSONDecodeError):
                response.warnings.append("response_not_valid_json")
        return response

    async def _record_llm_billing(
        self,
        billing_service: "BillingService",
        session: AsyncSession,
        *,
        theme_id: uuid.UUID,
        provider_name: str,
        task: str | None,
        model: str | None,
        usage: TokenUsage,
    ) -> None:
        """Две строки: input_tokens / output_tokens, service_impl = provider_model_in|out."""
        task_type = (task or "").strip() or BillingServiceType.OTHER.value
        occurred_at = datetime.now(timezone.utc)
        correlation_id = str(uuid.uuid4())
        base_extra: dict[str, Any] = {
            "provider": provider_name,
            "model": model or "",
            "correlation_id": correlation_id,
            "usage_source": usage.source,
        }
        pt = usage.prompt_tokens
        ct = usage.completion_tokens
        impl_in = llm_tariff_service_impl(provider_name, model, "in")
        impl_out = llm_tariff_service_impl(provider_name, model, "out")
        if pt > 0:
            await billing_service.record_usage(
                session,
                theme_id=theme_id,
                task_type=task_type,
                service_type=BillingServiceType.LLM.value,
                service_impl=impl_in,
                quantity=Decimal(pt),
                quantity_unit_code=BillingQuantityUnitCode.INPUT_TOKENS.value,
                occurred_at=occurred_at,
                extra={**base_extra, "leg": "input"},
            )
        if ct > 0:
            await billing_service.record_usage(
                session,
                theme_id=theme_id,
                task_type=task_type,
                service_type=BillingServiceType.LLM.value,
                service_impl=impl_out,
                quantity=Decimal(ct),
                quantity_unit_code=BillingQuantityUnitCode.OUTPUT_TOKENS.value,
                occurred_at=occurred_at,
                extra={**base_extra, "leg": "output"},
            )

    def _estimate_usage(self, messages: list[Message], answer_text: str) -> TokenUsage:
        """Оценка токенов: ~chars/4 + overhead."""
        prompt_chars = sum(len(m.content) for m in messages)
        n_messages = len(messages)
        prompt_tokens = (
            math.ceil(prompt_chars / CHARS_PER_TOKEN_ESTIMATE)
            + OVERHEAD_TOTAL
            + OVERHEAD_PER_MESSAGE * n_messages
        )
        completion_tokens = math.ceil(len(answer_text) / CHARS_PER_TOKEN_ESTIMATE)
        total_tokens = prompt_tokens + completion_tokens
        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            source="estimated",
        )


def get_llm_service(request: Request) -> LLMService:
    """
    Dependency: вернуть LLMService из app.state (регистрируется при старте в lifespan).

    Использование в роутере: llm_service: LLMService = Depends(get_llm_service).
    """
    return request.app.state.llm_service
