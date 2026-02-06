"""
Порт провайдера промптов: получение шаблона по имени, список по категории.
"""
from typing import Protocol

from app.integrations.prompts.types import PromptTemplate, PromptTemplateMeta


class PromptProviderPort(Protocol):
    """Абстракция источника промптов (файлы, БД и т.д.)."""

    async def get(self, name: str) -> PromptTemplate:
        """Вернуть шаблон по имени (или алиасу)."""
        ...

    async def list(self, category: str | None = None) -> list[PromptTemplateMeta]:
        """Список метаданных шаблонов, опционально по категории. Без контента."""
        ...
