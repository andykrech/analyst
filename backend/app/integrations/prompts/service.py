"""
PromptService: получение шаблона, рендеринг с проверкой placeholders.
"""
from typing import Any

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.integrations.prompts.factory import get_prompt_provider
from app.integrations.prompts.ports import PromptProviderPort
from app.integrations.prompts.render.simple_template import render
from app.integrations.prompts.types import PromptTemplateMeta, RenderedPrompt, PromptTemplate


class PromptService:
    """Централизованное получение и рендеринг промптов по имени."""

    def __init__(self, provider: PromptProviderPort) -> None:
        self._provider = provider

    async def list_templates(self, category: str | None = None) -> list[PromptTemplateMeta]:
        """Список метаданных шаблонов (без контента), опционально по категории."""
        return await self._provider.list(category)

    async def get(self, name: str) -> PromptTemplate:
        """Получить шаблон по имени или алиасу."""
        return await self._provider.get(name)

    async def render(self, name: str, vars: dict[str, Any]) -> RenderedPrompt:
        """
        Получить шаблон, проверить placeholders, отрендерить content.
        Возвращает RenderedPrompt (name, version, response_format, text, warnings).
        """
        template = await self._provider.get(name)
        warnings: list[str] = []
        if not template.placeholders and vars:
            warnings.append("vars_ignored_no_placeholders")
        text = render(template.content, vars, template.placeholders)
        return RenderedPrompt(
            name=template.name,
            version=template.version,
            response_format=template.response_format,
            text=text,
            warnings=warnings,
        )


def get_prompt_service(settings: Settings = Depends(get_settings)) -> PromptService:
    """
    Dependency: вернуть PromptService с провайдером из настроек.

    Использование: prompt_service: PromptService = Depends(get_prompt_service).
    """
    provider = get_prompt_provider(settings)
    return PromptService(provider)
