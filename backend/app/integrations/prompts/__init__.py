"""
Интеграция промптов: PromptService, провайдеры (file), рендеринг.
"""
from app.integrations.prompts.factory import get_prompt_provider
from app.integrations.prompts.ports import PromptProviderPort
from app.integrations.prompts.service import PromptService, get_prompt_service
from app.integrations.prompts.types import (
    PromptTemplate,
    PromptTemplateMeta,
    RenderedPrompt,
)

__all__ = [
    "PromptService",
    "get_prompt_service",
    "get_prompt_provider",
    "PromptProviderPort",
    "PromptTemplate",
    "PromptTemplateMeta",
    "RenderedPrompt",
]
