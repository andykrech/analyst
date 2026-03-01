"""
Yandex Cloud Translate переводчик через REST API.
POST https://translate.api.cloud.yandex.net/translate/v2/translate
Исходный и целевой язык передаём явно; folder_id — из конфига (тот же, что для поиска).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.integrations.translation.ports import TranslationCost, TranslationResult, TranslatorPort

logger = logging.getLogger(__name__)

MAX_CHARS_PER_REQUEST = 10_000  # лимит API


def _to_iso_lang(code: str) -> str:
    """Код языка в ISO 639-1 (ru, en) для API Яндекса."""
    if not code or not code.strip():
        return "en"
    return code.strip().lower()[:3]


def _flatten_items(
    items: list[tuple[int, str, str, list[str]]],
) -> tuple[list[str], list[tuple[int, str, int | None]]]:
    """
    Разворачиваем кванты в плоский список текстов для API.
    layout[i] = (index, field_type, kp_index).
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
    """Собираем переводы по индексу в формате для save_quanta_from_search."""
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


class YandexTranslator:
    """Переводчик через Yandex Cloud Translate REST API. folder_id и api_key из конфига."""

    def __init__(
        self,
        folder_id: str,
        api_key: str,
        base_url: str = "https://translate.api.cloud.yandex.net",
        timeout_s: float = 30.0,
    ) -> None:
        self._folder_id = (folder_id or "").strip()
        self._api_key = (api_key or "").strip()
        base = (base_url or "").rstrip("/")
        if not base.startswith("http"):
            base = f"https://{base}"
        self._url = f"{base}/translate/v2/translate"
        self._timeout_s = timeout_s

    @property
    def name(self) -> str:
        return "yandex_translator"

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
        if not self._api_key:
            logger.warning("Yandex Translate: API key не задан, перевод пропущен")
            texts, _ = _flatten_items(items)
            input_characters = sum(len(t) for t in texts)
            return TranslationResult(translations_by_index={}, cost=TranslationCost(input_characters=input_characters))
        if not self._folder_id:
            logger.warning("Yandex Translate: folder_id не задан, перевод пропущен")
            texts, _ = _flatten_items(items)
            input_characters = sum(len(t) for t in texts)
            return TranslationResult(translations_by_index={}, cost=TranslationCost(input_characters=input_characters))

        texts, layout = _flatten_items(items)
        input_characters = sum(len(t) for t in texts)

        if not texts:
            return TranslationResult(translations_by_index={}, cost=TranslationCost(input_characters=0))

        src = _to_iso_lang(source_lang)
        tgt = _to_iso_lang(target_lang)

        all_translated: list[str] = []
        offset = 0
        while offset < len(texts):
            batch: list[str] = []
            batch_chars = 0
            i = offset
            while i < len(texts) and batch_chars + len(texts[i]) <= MAX_CHARS_PER_REQUEST:
                batch.append(texts[i])
                batch_chars += len(texts[i])
                i += 1
            if not batch:
                batch = [texts[offset]]
                offset += 1
            else:
                offset = i

            body = {
                "sourceLanguageCode": src,
                "targetLanguageCode": tgt,
                "texts": batch,
                "folderId": self._folder_id,
                "format": "PLAIN_TEXT",
            }
            headers = {
                "Authorization": f"Api-Key {self._api_key}",
                "Content-Type": "application/json",
            }
            logger.debug(
                "Yandex Translate request: url=%s source=%s target=%s batch_size=%s batch_chars=%s",
                self._url,
                src,
                tgt,
                len(batch),
                batch_chars,
            )
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                try:
                    resp = await client.post(self._url, json=body, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPStatusError as e:
                    logger.warning(
                        "Yandex Translate API HTTP error: url=%s status=%s body=%s",
                        self._url,
                        e.response.status_code,
                        (e.response.text or "")[:2000],
                    )
                    raise
                except httpx.RequestError as e:
                    cause = getattr(e, "__cause__", None)
                    logger.warning(
                        "Yandex Translate API request error: url=%s error=%s (%s)%s",
                        self._url,
                        type(e).__name__,
                        e,
                        f" cause={cause!r}" if cause else "",
                    )
                    if cause:
                        logger.debug("Yandex Translate request cause: %s", cause, exc_info=True)
                    raise

            for t in data.get("translations") or []:
                if isinstance(t, dict) and "text" in t:
                    all_translated.append(t["text"])
                else:
                    all_translated.append("")

        translations_by_index = _reassemble(layout, all_translated)

        return TranslationResult(
            translations_by_index=translations_by_index,
            cost=TranslationCost(input_characters=input_characters),
        )
