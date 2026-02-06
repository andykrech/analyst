"""
Типы для интеграции промптов: метаданные шаблона, шаблон, отрендеренный промпт.
"""
from typing import Literal

from pydantic import BaseModel, Field


class PromptTemplateMeta(BaseModel):
    """Метаданные шаблона промпта (без контента)."""

    name: str
    description: str
    version: int | None = None
    category: str | None = None
    response_format: Literal["text", "json"] = "text"
    placeholders: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)


class PromptTemplate(PromptTemplateMeta):
    """Шаблон промпта с контентом."""

    content: str


class RenderedPrompt(BaseModel):
    """Результат рендеринга: текст + мета для LLM."""

    name: str
    version: int | None = None
    response_format: Literal["text", "json"] = "text"
    text: str
    warnings: list[str] = Field(default_factory=list)
