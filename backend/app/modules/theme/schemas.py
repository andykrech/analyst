"""
Схемы API для тем: подготовка (theme.init) и др.
"""
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ThemePrepareRequest(BaseModel):
    """Запрос на подготовку темы по сырому вводу (промпт theme.init)."""

    user_input: str = Field(..., min_length=1, description="Сырой ввод пользователя о теме")


class TermDTO(BaseModel):
    """Термин с текстом и контекстом."""

    text: str = Field(..., description="Текст термина")
    context: str = Field(default="", description="Контекст использования")


class ThemePrepareResult(BaseModel):
    """Результат обработки: название, ключевые слова, обязательные слова, минус-слова."""

    title: str = Field(..., description="Предложенное название темы")
    keywords: list[TermDTO] = Field(default_factory=list, description="Ключевые слова")
    must_have: list[TermDTO] = Field(default_factory=list, description="Обязательные слова (должны быть в результатах)")
    excludes: list[TermDTO] = Field(default_factory=list, description="Минус-слова (исключения)")


class ThemePrepareLLMMeta(BaseModel):
    """Мета LLM-вызова для отладки/аналитики."""

    provider: str
    model: str | None = None
    usage: dict  # prompt_tokens, completion_tokens, total_tokens, source
    cost: dict  # currency, total_cost, ...
    warnings: list[str] = Field(default_factory=list)


class ThemePrepareResponse(BaseModel):
    """Ответ эндпоинта prepare: результат + мета LLM."""

    result: ThemePrepareResult
    llm: ThemePrepareLLMMeta | None = Field(default=None, description="Мета вызова LLM")


# --- Terms translate ---


class TermTranslateIn(BaseModel):
    """Один термин для перевода: id, text, context."""

    id: str = Field(..., min_length=1, max_length=80, description="Идентификатор термина")
    text: str = Field(..., min_length=1, max_length=120, description="Текст для перевода")
    context: str = Field(default="", description="Контекст использования")

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("context", mode="before")
    @classmethod
    def strip_context(cls, v: str | None) -> str:
        if v is None:
            return ""
        if isinstance(v, str):
            return v.strip()
        return ""


class TermsTranslateRequest(BaseModel):
    """Запрос на перевод терминов через LLM."""

    source_language: str = Field(..., min_length=2, max_length=16, description="Исходный язык")
    target_language: str = Field(..., min_length=2, max_length=16, description="Целевой язык")
    terms: list[TermTranslateIn] = Field(..., description="Список терминов для перевода (не пустой)")


class TermTranslationOut(BaseModel):
    """Результат перевода одного термина."""

    id: str = Field(..., description="Идентификатор термина")
    translation: str = Field(..., description="Перевод")


class TermsTranslateLLMMeta(BaseModel):
    """Мета LLM-вызова для terms.translate."""

    provider: Optional[str] = None
    model: Optional[str] = None
    usage: dict = Field(..., description="prompt_tokens, completion_tokens, total_tokens, source")
    cost: dict = Field(..., description="currency, total_cost, ...")
    warnings: list[str] = Field(default_factory=list)


class TermsTranslateResponse(BaseModel):
    """Ответ эндпоинта terms/translate: переводы + мета LLM."""

    translations: list[TermTranslationOut] = Field(..., description="Переводы в порядке входных terms")
    llm: TermsTranslateLLMMeta = Field(..., description="Мета вызова LLM")
