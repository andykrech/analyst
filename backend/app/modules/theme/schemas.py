"""
Схемы API для тем: подготовка (theme.init) и др.
"""
from pydantic import BaseModel, Field


class ThemePrepareRequest(BaseModel):
    """Запрос на подготовку темы по сырому вводу (промпт theme.init)."""

    user_input: str = Field(..., min_length=1, description="Сырой ввод пользователя о теме")


class ThemePrepareResult(BaseModel):
    """Результат обработки: название, ключевые слова, обязательные слова, минус-слова."""

    title: str = Field(..., description="Предложенное название темы")
    keywords: list[str] = Field(default_factory=list, description="Ключевые слова")
    must_have: list[str] = Field(default_factory=list, description="Обязательные слова (должны быть в результатах)")
    excludes: list[str] = Field(default_factory=list, description="Минус-слова (исключения)")


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
