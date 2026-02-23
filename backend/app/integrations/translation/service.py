"""
Верхний слой перевода квантов.
Выбирает переводчик по имени из конфига и делегирует ему перевод.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from app.core.config import Settings
from app.integrations.translation.ports import TranslationCost, TranslatorPort
from app.integrations.translation.translators.deepl import DeepLTranslator
from app.integrations.translation.translators.yandex_translator import YandexTranslator
from app.modules.quanta.schemas import QuantumCreate

logger = logging.getLogger(__name__)


def _normalize_lang(lang: str | None) -> str:
    """Нормализация кода языка для сравнения."""
    if not lang or not str(lang).strip():
        return "en"
    return str(lang).strip().lower()


def _needs_translation(source_lang: str, target_lang: str) -> bool:
    return _normalize_lang(source_lang) != _normalize_lang(target_lang)


class TranslationService:
    """
    Сервис перевода: реестр переводчиков и имя текущего берутся из конфига.
    Группирует кванты по исходному языку и вызывает переводчик с явными source_lang, target_lang.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._registry: dict[str, TranslatorPort] = {
            "deepl": DeepLTranslator(api_key=settings.DEEPL_API_KEY.get_secret_value()),
            "yandex_translator": YandexTranslator(
                folder_id=settings.YANDEX_FOLDER_ID,
                api_key=settings.YANDEX_API_KEY_TRANSLATE.get_secret_value(),
            ),
        }
        self._translator_name = settings.TRANSLATOR.strip() or "deepl"

    def _get_translator(self) -> TranslatorPort | None:
        return self._registry.get(self._translator_name)

    async def translate_quanta_create_items(
        self,
        items: list[QuantumCreate],
        target_lang: str,
    ) -> tuple[dict[int, dict[str, Any]], TranslationCost]:
        """
        Перевести поля квантов (title, summary_text, key_points) на целевой язык.
        Исходный язык берётся из каждого кванта (q.language), передаётся в переводчик.

        Returns:
            (translations_by_index, cost) — словарь индекс -> переводы и оценка стоимости.
        """
        if not items:
            return {}, TranslationCost(input_characters=0)

        translator = self._get_translator()
        if not translator:
            logger.warning(
                "translation: переводчик '%s' не найден в реестре, перевод пропущен",
                self._translator_name,
            )
            return {}, TranslationCost(input_characters=0)

        # Кванты, требующие перевода; при лимите > 0 берём только первые N
        to_translate = [
            (i, q)
            for i, q in enumerate(items)
            if _needs_translation(_normalize_lang(q.language), target_lang)
        ]
        limit = self._settings.QUANTA_TRANSLATION_LIMIT
        if limit > 0:
            to_translate = to_translate[:limit]

        by_lang: dict[str, list[tuple[int, str, str, list[str]]]] = defaultdict(list)
        for i, q in to_translate:
            src = _normalize_lang(q.language)
            title = (q.title or "").strip()
            summary = (q.summary_text or "").strip()
            points = list(q.key_points) if q.key_points else []
            by_lang[src].append((i, title, summary, points))

        all_by_index: dict[int, dict[str, Any]] = {}
        total_input_chars = 0

        for source_lang, batch in by_lang.items():
            if not batch:
                continue
            try:
                result = await translator.translate(
                    items=batch,
                    source_lang=source_lang,
                    target_lang=target_lang,
                )
            except Exception as e:
                logger.warning(
                    "translation: ошибка перевода (source_lang=%s, batch_size=%s): %s",
                    source_lang,
                    len(batch),
                    e,
                )
                continue
            for idx, trans in result.translations_by_index.items():
                all_by_index[idx] = trans
            total_input_chars += result.cost.input_characters

        return all_by_index, TranslationCost(input_characters=total_input_chars)
