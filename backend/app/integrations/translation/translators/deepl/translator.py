"""
DeepL переводчик через REST API.
Передаём source_lang и target_lang явно (без автоопределения).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.integrations.translation.ports import TranslationCost, TranslationResult, TranslatorPort

logger = logging.getLogger(__name__)

DEEPL_API_BASE_URL = "https://api-free.deepl.com"
# Pro: https://api.deepl.com/v2/translate
MAX_SEGMENTS_PER_REQUEST = 50
MAX_REQUEST_BODY_BYTES = 120 * 1024  # чуть меньше 128 KiB


def _to_deepl_lang(code: str) -> str:
    """Код языка в формат DeepL (uppercase, например EN, RU)."""
    if not code or not code.strip():
        return "EN"
    return code.strip().upper()[:2]


def _flatten_items(
    items: list[tuple[int, str, str, list[str]]],
) -> tuple[list[str], list[tuple[int, str, int | None]]]:
    """
    Разворачиваем кванты в плоский список текстов для API.
    layout[i] = (index, field_type, kp_index) где field_type: "title"|"summary"|"kp", kp_index только для key_points.
    """
    texts: list[str] = []
    layout: list[tuple[int, str, int | None]] = []
    for idx, title, summary, key_points in items:
        texts.append(title or "")
        layout.append((idx, "title", None))
        texts.append(summary or "")
        layout.append((idx, "summary", None))
        for ki, kp in enumerate(key_points or []):
            texts.append(kp if isinstance(kp, str) else str(kp))
            layout.append((idx, "kp", ki))
    return texts, layout


def _reassemble(
    layout: list[tuple[int, str, int | None]],
    translated_texts: list[str],
) -> dict[int, dict[str, Any]]:
    """Собираем переводы по индексу из плоского списка в формате для save_quanta_from_search."""
    by_index: dict[int, dict[str, Any]] = {}
    for pos, (idx, field, kp_i) in enumerate(layout):
        if pos >= len(translated_texts):
            break
        text = translated_texts[pos]
        if idx not in by_index:
            by_index[idx] = {
                "title_translated": "",
                "summary_text_translated": "",
                "key_points_translated": [],
            }
        if field == "title":
            by_index[idx]["title_translated"] = text
        elif field == "summary":
            by_index[idx]["summary_text_translated"] = text
        elif field == "kp" and kp_i is not None:
            kp_list = by_index[idx]["key_points_translated"]
            while len(kp_list) <= kp_i:
                kp_list.append("")
            kp_list[kp_i] = text
    return by_index


class DeepLTranslator:
    """Переводчик через DeepL REST API. Исходный и целевой язык передаются явно."""

    def __init__(self, api_key: str, base_url: str = DEEPL_API_BASE_URL, timeout_s: float = 30.0) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    @property
    def name(self) -> str:
        return "deepl"

    async def translate(
        self,
        items: list[tuple[int, str, str, list[str]]],
        source_lang: str,
        target_lang: str,
    ) -> TranslationResult:
        """
        Перевести поля квантов. items: (index, title, summary_text, key_points).
        Возвращает переводы по индексу и количество входящих символов.
        """
        if not items:
            return TranslationResult(translations_by_index={}, cost=TranslationCost(input_characters=0))
        if not (self._api_key or self._api_key.strip()):
            logger.warning("DeepL: API key не задан, перевод пропущен")
            texts, _ = _flatten_items(items)
            input_characters = sum(len(t) for t in texts)
            return TranslationResult(translations_by_index={}, cost=TranslationCost(input_characters=input_characters))

        texts, layout = _flatten_items(items)
        input_characters = sum(len(t) for t in texts)

        if not texts:
            return TranslationResult(translations_by_index={}, cost=TranslationCost(input_characters=0))

        src = _to_deepl_lang(source_lang)
        tgt = _to_deepl_lang(target_lang)

        # Батчи по количеству сегментов и по размеру
        all_translated: list[str] = []
        offset = 0
        while offset < len(texts):
            batch = texts[offset : offset + MAX_SEGMENTS_PER_REQUEST]
            batch_size_bytes = sum(len(t.encode("utf-8")) for t in batch)
            while batch_size_bytes > MAX_REQUEST_BODY_BYTES and len(batch) > 1:
                batch = batch[: len(batch) // 2]
                batch_size_bytes = sum(len(t.encode("utf-8")) for t in batch)
            if not batch:
                break

            body = {
                "text": batch,
                "source_lang": src,
                "target_lang": tgt,
            }
            headers = {
                "Authorization": f"DeepL-Auth-Key {self._api_key}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                try:
                    resp = await client.post(
                        f"{self._base_url}/v2/translate",
                        json=body,
                        headers=headers,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPStatusError as e:
                    logger.warning("DeepL API HTTP error: %s %s", e.response.status_code, e.response.text)
                    raise
                except httpx.RequestError as e:
                    logger.warning("DeepL API request error: %s", e)
                    raise

            translations = data.get("translations") or []
            for t in translations:
                if isinstance(t, dict) and "text" in t:
                    all_translated.append(t["text"])
                else:
                    all_translated.append("")

            offset += len(batch)

        # Сопоставляем layout с batch-ответами: layout и texts имеют одинаковую длину, all_translated — конкатенация в том же порядке
        batch_layout = layout
        translated_texts = all_translated
        translations_by_index = _reassemble(batch_layout, translated_texts)

        return TranslationResult(
            translations_by_index=translations_by_index,
            cost=TranslationCost(input_characters=input_characters),
        )
