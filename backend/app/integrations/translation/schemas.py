"""Схемы интеграции перевода."""

from dataclasses import dataclass


@dataclass
class ItemToTranslate:
    """Один элемент для перевода: индекс в исходном списке и поля кванта."""

    index: int
    title: str
    summary_text: str
    key_points: list[str]
    source_lang: str
