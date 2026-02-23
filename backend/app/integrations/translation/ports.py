"""
Порт (интерфейс) переводчиков.
Верхний слой (TranslationService) вызывает выбранный переводчик по имени.
"""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class TranslationCost:
    """Оценка стоимости перевода (пока — число входящих символов)."""

    input_characters: int


@dataclass
class TranslationResult:
    """Результат перевода полей квантов."""

    # индекс в исходном списке -> {title_translated, summary_text_translated, key_points_translated}
    translations_by_index: dict[int, dict[str, Any]]
    cost: TranslationCost


class TranslatorPort(Protocol):
    """Абстракция переводчика: переводит поля с source_lang на target_lang."""

    @property
    def name(self) -> str:
        """Имя переводчика (например 'deepl')."""
        ...

    async def translate(
        self,
        items: list[tuple[int, str, str, list[str]]],
        source_lang: str,
        target_lang: str,
    ) -> TranslationResult:
        """
        Перевести поля квантов на целевой язык.

        Args:
            items: список (index, title, summary_text, key_points) для перевода.
            source_lang: код языка исходного текста (например "en", "ru").
            target_lang: код языка перевода (например "ru", "en").

        Returns:
            TranslationResult с словарём переводов по индексу и метрикой cost.
        """
        ...
