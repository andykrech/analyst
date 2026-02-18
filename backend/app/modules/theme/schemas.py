"""
Схемы API для тем: подготовка (theme.init), сохранение темы и запросов и др.
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


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


# --- Сохранение темы и поисковых запросов (строгая валидация) ---

TERM_ID_MAX_LEN = 80
TERM_TEXT_MAX_LEN = 500
TERM_CONTEXT_MAX_LEN = 2000
TRANSLATIONS_KEY_MAX_LEN = 20
TRANSLATIONS_VALUE_MAX_LEN = 500
TITLE_MAX_LEN = 500
DESCRIPTION_MAX_LEN = 10000
LANGUAGE_CODE_MAX_LEN = 20
MAX_SEARCH_QUERIES = 3
VALID_UPDATE_INTERVALS = ("daily", "3d", "weekly")
VALID_STATUSES = ("draft", "active", "paused", "archived")
VALID_BACKFILL_STATUSES = ("not_started", "running", "done", "failed")


class TermIn(BaseModel):
    """Термин для сохранения в пуле темы (ключевые, обязательные, минус-слова)."""

    id: str = Field(..., min_length=1, max_length=TERM_ID_MAX_LEN)
    text: str = Field(..., min_length=1, max_length=TERM_TEXT_MAX_LEN)
    context: str = Field(default="", max_length=TERM_CONTEXT_MAX_LEN)
    translations: dict[str, str] = Field(default_factory=dict)

    @field_validator("text", "context", mode="before")
    @classmethod
    def strip_string(cls, v: str) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @field_validator("text")
    @classmethod
    def text_non_empty_after_strip(cls, v: str) -> str:
        if not v:
            raise ValueError("text не может быть пустым после обрезки пробелов")
        return v

    @field_validator("translations", mode="before")
    @classmethod
    def normalize_translations(cls, v: Any) -> dict[str, str]:
        if v is None or not isinstance(v, dict):
            return {}
        result: dict[str, str] = {}
        for k, val in v.items():
            if isinstance(k, str) and isinstance(val, str):
                k_ = k.strip()[:TRANSLATIONS_KEY_MAX_LEN]
                val_ = val.strip()[:TRANSLATIONS_VALUE_MAX_LEN]
                if k_:
                    result[k_] = val_
        return result


class ThemeSaveIn(BaseModel):
    """Данные темы для сохранения (заголовок, описание, пулы терминов, языки)."""

    title: str = Field(..., min_length=1, max_length=TITLE_MAX_LEN)
    description: str = Field(..., min_length=1, max_length=DESCRIPTION_MAX_LEN)
    keywords: list[TermIn] = Field(default_factory=list)
    must_have: list[TermIn] = Field(default_factory=list)
    exclude: list[TermIn] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    update_interval: Literal["daily", "3d", "weekly"] = Field(default="weekly")
    status: Literal["draft", "active", "paused", "archived"] = Field(default="draft")
    backfill_status: Literal["not_started", "running", "done", "failed"] = Field(
        default="not_started"
    )
    backfill_horizon_months: int = Field(default=12, ge=1, le=120)
    region: str | None = Field(default=None, max_length=100)

    @field_validator("title", "description", mode="before")
    @classmethod
    def strip_string(cls, v: str) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @field_validator("title")
    @classmethod
    def title_non_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("title не может быть пустым")
        return v

    @field_validator("description")
    @classmethod
    def description_non_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("description не может быть пустым")
        return v

    @field_validator("languages")
    @classmethod
    def validate_language_codes(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for item in v:
            if not isinstance(item, str):
                continue
            s = item.strip()[:LANGUAGE_CODE_MAX_LEN]
            if s and s.lower() not in seen:
                seen.add(s.lower())
                out.append(s)
        return out

    @field_validator("keywords", "must_have", "exclude")
    @classmethod
    def unique_term_ids(cls, v: list[TermIn]) -> list[TermIn]:
        seen: set[str] = set()
        for t in v:
            if t.id in seen:
                raise ValueError(f"Дублирующийся id термина: {t.id!r}")
            seen.add(t.id)
        return v


class SavedQueryIn(BaseModel):
    """Поисковый запрос в формате фронта (termIds, без текстов)."""

    keywords: dict[str, Any] = Field(..., alias="keywords")
    must: dict[str, Any] = Field(..., alias="must")
    exclude: dict[str, Any] = Field(..., alias="exclude")

    @field_validator("keywords", mode="before")
    @classmethod
    def validate_keywords(cls, v: Any) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("keywords должен быть объектом")
        groups = v.get("groups")
        connectors = v.get("connectors")
        if groups is not None and not isinstance(groups, list):
            raise ValueError("keywords.groups должен быть массивом")
        if connectors is not None and not isinstance(connectors, list):
            raise ValueError("keywords.connectors должен быть массивом")
        if isinstance(groups, list) and isinstance(connectors, list):
            if len(connectors) != max(len(groups) - 1, 0):
                raise ValueError(
                    "keywords.connectors должен иметь длину len(groups)-1"
                )
        return v

    @field_validator("must", mode="before")
    @classmethod
    def validate_must(cls, v: Any) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("must должен быть объектом")
        mode = v.get("mode")
        if mode is not None and mode not in ("ALL", "ANY"):
            raise ValueError("must.mode должен быть ALL или ANY")
        return v

    @field_validator("exclude", mode="before")
    @classmethod
    def validate_exclude(cls, v: Any) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("exclude должен быть объектом")
        return v

    model_config = {"populate_by_name": True}


class ThemeSearchQueryIn(BaseModel):
    """Один поисковый запрос темы для сохранения."""

    order_index: int = Field(..., ge=1, le=MAX_SEARCH_QUERIES)
    query_model: SavedQueryIn = Field(...)
    title: str | None = Field(default=None, max_length=200)
    time_window_days: int | None = Field(default=None, ge=1, le=3650)
    target_links: int | None = Field(default=None, ge=1, le=10000)
    enabled_retrievers: list[str] | None = Field(default=None, max_length=20)
    is_enabled: bool = Field(default=True)


class ThemeSaveRequest(BaseModel):
    """
    Тело запроса на сохранение темы и поисковых запросов.
    Общее название: позже сюда могут войти источники, наборы ссылок и т.д.
    """

    theme: ThemeSaveIn = Field(...)
    search_queries: list[ThemeSearchQueryIn] = Field(
        default_factory=list,
        max_length=MAX_SEARCH_QUERIES,
        description="До 3 сохранённых поисковых запросов",
    )

    @field_validator("search_queries")
    @classmethod
    def unique_order_index(cls, v: list[ThemeSearchQueryIn]) -> list[ThemeSearchQueryIn]:
        seen: set[int] = set()
        for q in v:
            if q.order_index in seen:
                raise ValueError(
                    f"Дублирующийся order_index в поисковых запросах: {q.order_index}"
                )
            seen.add(q.order_index)
        return v

    @model_validator(mode="after")
    def term_ids_refer_to_pools(self) -> "ThemeSaveRequest":
        """Все termIds в поисковых запросах должны ссылаться на id в пулах темы."""
        keyword_ids = {t.id for t in self.theme.keywords}
        must_ids = {t.id for t in self.theme.must_have}
        exclude_ids = {t.id for t in self.theme.exclude}

        for q in self.search_queries:
            qm = q.query_model
            # keywords.groups[].termIds
            groups = (qm.keywords or {}).get("groups") or []
            for g in groups:
                if not isinstance(g, dict):
                    continue
                for tid in (g.get("termIds") or []):
                    if tid and tid not in keyword_ids:
                        raise ValueError(
                            f"termId {tid!r} в ключевых словах запроса не найден в theme.keywords"
                        )
            # must.termIds
            must_term_ids = (qm.must or {}).get("termIds") or []
            for tid in must_term_ids:
                if tid and tid not in must_ids:
                    raise ValueError(
                        f"termId {tid!r} в must запроса не найден в theme.must_have"
                    )
            # exclude.termIds
            ex_term_ids = (qm.exclude or {}).get("termIds") or []
            for tid in ex_term_ids:
                if tid and tid not in exclude_ids:
                    raise ValueError(
                        f"termId {tid!r} в exclude запроса не найден в theme.exclude"
                    )
        return self


class ThemeListItem(BaseModel):
    """Элемент списка тем (для GET списка)."""

    id: str = Field(..., description="UUID темы")
    title: str = Field(..., description="Название темы")


class ThemeListResponse(BaseModel):
    """Ответ GET /themes — список тем текущего пользователя."""

    themes: list[ThemeListItem] = Field(default_factory=list)


class ThemeSaveResponse(BaseModel):
    """Ответ после успешного сохранения темы."""

    id: str = Field(..., description="Идентификатор темы (UUID)")
    message: str = Field(default="ok", description="Статус сохранения")


# --- Загрузка темы по id (GET) ---


class ThemeGetTermOut(BaseModel):
    """Термин в ответе GET темы."""

    id: str = Field(...)
    text: str = Field(...)
    context: str = Field(default="")
    translations: dict[str, str] = Field(default_factory=dict)


class ThemeGetOut(BaseModel):
    """Данные темы в ответе GET."""

    id: str = Field(..., description="UUID темы")
    title: str = Field(...)
    description: str = Field(...)
    keywords: list[ThemeGetTermOut] = Field(default_factory=list)
    must_have: list[ThemeGetTermOut] = Field(default_factory=list)
    exclude: list[ThemeGetTermOut] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


class ThemeSearchQueryOut(BaseModel):
    """Один поисковый запрос в ответе GET темы."""

    order_index: int = Field(..., ge=1, le=3)
    query_model: dict = Field(..., description="keywords, must, exclude (как при сохранении)")


class ThemeGetResponse(BaseModel):
    """Ответ GET /themes/{theme_id}: тема и поисковые запросы."""

    theme: ThemeGetOut = Field(...)
    search_queries: list[ThemeSearchQueryOut] = Field(default_factory=list)
