"""Стабильные коды для биллинга (типы сервисов, задач, единиц объёма).

Значения согласуются с записями в БД и админкой; при добавлении новых —
расширять перечисления здесь.
"""

import re
from enum import StrEnum
from typing import Literal


class BillingServiceType(StrEnum):
    """Тип сервиса, расходующего ресурсы (примерные значения)."""

    LLM = "llm"
    EMBEDDING = "embedding"
    RETRIEVER = "retriever"
    TRANSLATOR = "translator"
    TRANSLATION = "translation"
    SEARCH = "search"
    OTHER = "other"


class BillingServiceImpl(StrEnum):
    """Идентификаторы реализаций для не-LLM сервисов (совпадают с billing_tariffs.service_impl).

    Для вызовов через LLMService используйте llm_tariff_service_impl().
    """

    OPENAI_TEXT_EMBEDDING_3_SMALL = "openai_text-embedding-3-small"
    YANDEX_TRANSLATOR = "yandex_translator"
    OPENALEX_FULLTEXT_SEARCH = "openalex_fulltext-search"


def _slug_billing_segment(value: str) -> str:
    """Нормализация сегмента ключа тарифа: нижний регистр, только a-z0-9 и _."""
    t = (value or "").strip().lower()
    t = re.sub(r"[^a-z0-9]+", "_", t)
    t = re.sub(r"_+", "_", t).strip("_")
    return t or "default"


def embedding_tariff_service_impl(provider: str, model: str | None) -> str:
    """
    Ключ service_impl для эмбеддинга — совпадает с billing_tariffs (сид: openai_text-embedding-3-small).

    При добавлении модели в продукт нужна новая строка тарифа и ветка здесь.
    """
    p = (provider or "").strip().lower()
    m = (model or "").strip()
    if p == "openai" and m == "text-embedding-3-small":
        return BillingServiceImpl.OPENAI_TEXT_EMBEDDING_3_SMALL.value
    raise ValueError(
        f"Нет сопоставления тарифа для embedding: provider={provider!r} model={model!r}. "
        "Добавьте запись в billing_tariffs и ветку в embedding_tariff_service_impl().",
    )


def llm_tariff_service_impl(
    provider: str,
    model: str | None,
    direction: Literal["in", "out"],
) -> str:
    """
    Ключ service_impl для LLM: {provider}_{model}_{in|out}.

    model опционален; при отсутствии подставляется сегмент ``default``.
    Единицы объёма в событии всегда input_tokens / output_tokens для двух вызовов.
    """
    p = _slug_billing_segment(provider)
    m = _slug_billing_segment(model or "")
    if direction not in ("in", "out"):
        raise ValueError("direction must be 'in' or 'out'")
    return f"{p}_{m}_{direction}"


class BillingTaskType(StrEnum):
    """Тип задачи в продукте (примерные значения)."""

    QUANTUM_EXTRACTION = "quantum_extraction"
    TRANSLATION = "translation"
    EMBEDDING = "embedding"
    LANDSCAPE = "landscape"
    SEARCH = "search"
    OTHER = "other"


class BillingQuantityUnitCode(StrEnum):
    """Код основного измеримого параметра события."""

    INPUT_TOKENS = "input_tokens"
    OUTPUT_TOKENS = "output_tokens"
    TOTAL_TOKENS = "total_tokens"
    CHARS = "chars"
    REQUESTS = "requests"
    OTHER = "other"
