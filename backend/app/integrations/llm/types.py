"""
Типы для интеграции с LLM: сообщения, параметры генерации, usage, стоимость, запрос/ответ.
"""
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Одно сообщение в диалоге."""

    role: Literal["system", "user", "assistant"]
    content: str


class GenerationParams(BaseModel):
    """Параметры генерации (temperature, max_tokens, top_p)."""

    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None


class TokenUsage(BaseModel):
    """Использование токенов (от провайдера или оценка)."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    source: Literal["provider", "estimated"]


class CostBreakdown(BaseModel):
    """Разбивка стоимости вызова."""

    currency: str
    prompt_cost: Decimal = Field(description="Стоимость входных токенов")
    completion_cost: Decimal = Field(description="Стоимость выходных токенов")
    total_cost: Decimal = Field(description="Общая стоимость")
    unit: Literal["per_1m"] = "per_1m"
    usage_source: Literal["provider", "estimated"]


class LLMRequest(BaseModel):
    """Запрос к LLM."""

    task: str | None = None
    messages: list[Message]
    response_format: Literal["text", "json"] = "text"
    generation: GenerationParams | None = None
    trace: dict | None = None


class LLMResponse(BaseModel):
    """Нормализованный ответ от LLM-сервиса."""

    text: str
    provider: str
    model: str | None = None
    usage: TokenUsage
    cost: CostBreakdown
    raw: str | None = None
    latency_ms: int | None = None
    finish_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
