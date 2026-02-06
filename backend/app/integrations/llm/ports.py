"""
Порт (интерфейс) LLM-провайдера: провайдер возвращает сырой результат без расчёта стоимости.
"""
from typing import Protocol

from app.integrations.llm.types import LLMRequest


class LLMProviderPort(Protocol):
    """Абстракция для вызова LLM-провайдера."""

    async def generate(self, request: LLMRequest) -> dict:
        """
        Вызвать провайдера и вернуть сырой результат.

        Возвращаемый dict должен содержать:
        - text: str — текст ответа
        - raw: str | None — сырой ответ (ограниченный по длине)
        - model: str | None — модель
        - usage: dict | None — при наличии от провайдера: prompt_tokens, completion_tokens, total_tokens
        - finish_reason: str | None
        """
        ...
