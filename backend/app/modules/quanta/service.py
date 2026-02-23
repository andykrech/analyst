"""Сервисный слой для квантов (пока минимальный)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm.service import LLMService
from app.integrations.prompts import PromptService
from app.modules.quanta.crud import create_quantum
from app.modules.quanta.models import Quantum
from app.modules.quanta.schemas import QuantumCreate

BATCH_SIZE = 5
QUANTA_TRANSLATE_PROMPT = "quanta.translate_fields.v1"
# Лимит токенов ответа на один батч перевода (чтобы не ждать бесконечно)
TRANSLATE_MAX_TOKENS = 8192


class _FakeQuantumForTranslate:
    """Обёртка QuantumCreate с id=index для вызова translate_quanta_fields до сохранения в БД."""

    __slots__ = ("id", "title", "summary_text", "key_points", "language")

    def __init__(self, index: int, q: QuantumCreate) -> None:
        self.id = str(index)
        self.title = q.title or ""
        self.summary_text = q.summary_text or ""
        self.key_points = q.key_points or []
        self.language = q.language


class _QuantumLike(Protocol):
    """Объект с полями, нужными для перевода (Quantum или совместимый)."""

    id: uuid.UUID
    title: str
    summary_text: str
    key_points: list
    language: str | None


def _uuid_or_none(s: str | None) -> uuid.UUID | None:
    if not s or not str(s).strip():
        return None
    try:
        return uuid.UUID(str(s))
    except (ValueError, TypeError):
        return None


async def save_quanta_from_search(
    session: AsyncSession,
    items: list[QuantumCreate],
    run_id: uuid.UUID | None = None,
    translations_by_index: dict[int, dict[str, Any]] | None = None,
) -> int:
    """
    Сохранить кванты, полученные поиском, в БД (upsert по theme_id + dedup_key).
    Если передан translations_by_index (индекс в items -> переводы), заполняются
    title_translated, summary_text_translated, key_points_translated.
    """
    logger = logging.getLogger(__name__)
    n_with_translation = sum(1 for i in range(len(items)) if (translations_by_index or {}).get(i))
    logger.info(
        "search/save_quanta: на запись передано квантов=%s, с переводами=%s",
        len(items),
        n_with_translation,
    )
    saved = 0
    trans = translations_by_index or {}
    for i, q in enumerate(items):
        theme_id = _uuid_or_none(q.theme_id)
        if not theme_id:
            continue
        identifiers_dict = [x.model_dump() for x in q.identifiers] if q.identifiers else []
        t = trans.get(i)
        await create_quantum(
            session,
            theme_id=theme_id,
            run_id=run_id or _uuid_or_none(q.run_id),
            entity_kind=q.entity_kind,
            title=q.title,
            summary_text=q.summary_text,
            key_points=q.key_points or [],
            language=q.language,
            date_at=q.date_at,
            verification_url=q.verification_url,
            canonical_url=q.canonical_url,
            dedup_key=q.dedup_key,
            fingerprint=q.fingerprint,
            identifiers=identifiers_dict,
            matched_terms=q.matched_terms or [],
            matched_term_ids=q.matched_term_ids or [],
            retriever_query=q.retriever_query,
            rank_score=q.rank_score,
            source_system=q.source_system,
            site_id=_uuid_or_none(q.site_id),
            retriever_name=q.retriever_name,
            retriever_version=q.retriever_version,
            attrs=q.attrs or {},
            raw_payload_ref=_uuid_or_none(q.raw_payload_ref),
            content_ref=q.content_ref,
            title_translated=t.get("title_translated") if t else None,
            summary_text_translated=t.get("summary_text_translated") if t else None,
            key_points_translated=t.get("key_points_translated") if t else None,
        )
        saved += 1
    logger.info("search/save_quanta: записано квантов=%s", saved)
    return saved


async def upsert_quantum_in_theme(
    session: AsyncSession,
    *,
    theme_id: uuid.UUID,
    run_id: uuid.UUID | None,
    entity_kind: str,
    title: str,
    summary_text: str,
    verification_url: str,
    source_system: str,
    retriever_name: str,
    key_points: list[str] | None = None,
    language: str | None = None,
    date_at: datetime | None = None,
    canonical_url: str | None = None,
    dedup_key: str | None = None,
    fingerprint: str | None = None,
    identifiers: list[dict[str, Any]] | None = None,
    matched_terms: list[str] | None = None,
    matched_term_ids: list[str] | None = None,
    retriever_query: str | None = None,
    rank_score: float | None = None,
    site_id: uuid.UUID | None = None,
    retriever_version: str | None = None,
    attrs: dict[str, Any] | None = None,
    raw_payload_ref: uuid.UUID | None = None,
    content_ref: str | None = None,
) -> Quantum:
    """Тонкая обёртка: сейчас это create+dedup по UNIQUE(theme_id,dedup_key)."""
    return await create_quantum(
        session,
        theme_id=theme_id,
        run_id=run_id,
        entity_kind=entity_kind,
        title=title,
        summary_text=summary_text,
        key_points=key_points,
        language=language,
        date_at=date_at,
        verification_url=verification_url,
        canonical_url=canonical_url,
        dedup_key=dedup_key,
        fingerprint=fingerprint,
        identifiers=identifiers,
        matched_terms=matched_terms,
        matched_term_ids=matched_term_ids,
        retriever_query=retriever_query,
        rank_score=rank_score,
        source_system=source_system,
        site_id=site_id,
        retriever_name=retriever_name,
        retriever_version=retriever_version,
        attrs=attrs,
        raw_payload_ref=raw_payload_ref,
        content_ref=content_ref,
    )


def _needs_translation(q: _QuantumLike, primary_language: str) -> bool:
    """Квант переводим, если язык не совпадает с основным языком темы (theme.languages[0])."""
    if not primary_language or not str(primary_language).strip():
        return True
    lang = q.language
    if lang is None or not str(lang).strip():
        return True
    return str(lang).strip().lower() != str(primary_language).strip().lower()


class _LangOnly:
    """Только language — для подсчёта батчей без создания полного фейкового кванта."""
    def __init__(self, language: str | None) -> None:
        self.language = language


def get_translate_batch_count(
    items: list[QuantumCreate],
    primary_language: str,
    limit: int = 0,
) -> int:
    """Число батчей для перевода (для расчёта таймаута). Батчи по BATCH_SIZE квантов. limit: 0 = все."""
    to_translate_count = sum(
        1 for q in items if _needs_translation(_LangOnly(q.language), primary_language)
    )
    if limit > 0:
        to_translate_count = min(to_translate_count, limit)
    if to_translate_count <= 0:
        return 0
    return (to_translate_count + BATCH_SIZE - 1) // BATCH_SIZE


async def translate_quanta_fields(
    quanta_list: list[_QuantumLike],
    primary_language: str,
    llm_service: LLMService,
    prompt_service: PromptService,
    limit: int = 0,
) -> list[dict[str, Any]]:
    """
    Перевести поля квантов (title, summary_text, key_points) на основной язык темы.

    Основной язык темы — theme.languages[0]; передаётся в primary_language.
    В пакет попадают только кванты, у которых язык не совпадает с основным.
    limit: 0 = все, >0 = только первые N квантов для перевода (для отладки).
    Батчи по BATCH_SIZE квантов, один вызов LLM на батч.

    Возвращает список словарей для применения вызывающим (вариант A):
    [{"id": str, "title_translated": str, "summary_text_translated": str, "key_points_translated": list[str]}, ...]
    """
    logger = logging.getLogger(__name__)
    to_translate = [q for q in quanta_list if _needs_translation(q, primary_language)]
    if limit > 0:
        to_translate = to_translate[:limit]
    if not to_translate:
        return []

    result: list[dict[str, Any]] = []
    for i in range(0, len(to_translate), BATCH_SIZE):
        batch = to_translate[i : i + BATCH_SIZE]
        items = [
            {
                "id": str(q.id),
                "title": q.title or "",
                "summary_text": q.summary_text or "",
                "key_points": list(q.key_points) if q.key_points else [],
            }
            for q in batch
        ]
        items_json = json.dumps(items, ensure_ascii=False)

        try:
            response = await llm_service.generate_from_prompt(
                QUANTA_TRANSLATE_PROMPT,
                {"target_language": primary_language, "items": items_json},
                prompt_service,
                generation={"max_tokens": TRANSLATE_MAX_TOKENS},
            )
        except Exception as e:
            logger.warning("translate_quanta_fields: LLM batch failed (batch size=%s): %s", len(batch), e)
            continue

        text = (response.text or "").strip()
        raw_preview_lines = (response.text or "").splitlines()[:30]
        raw_preview = "\n".join(raw_preview_lines)
        if not text:
            logger.warning(
                "translate_quanta_fields: пустой ответ от LLM (первые 30 строк сырого ответа):\n%s",
                raw_preview or "(пусто)",
            )
            continue
        # Убираем обёртку markdown (```json ... ```), если есть
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(
                "translate_quanta_fields: invalid JSON from LLM: %s; первые 30 строк ответа:\n%s",
                e,
                raw_preview,
            )
            continue

        translations = data.get("translations")
        if not isinstance(translations, list):
            continue
        for t in translations:
            if not isinstance(t, dict):
                continue
            tid = t.get("id")
            if tid is None:
                continue
            result.append({
                "id": str(tid),
                "title_translated": t.get("title_translated") if isinstance(t.get("title_translated"), str) else "",
                "summary_text_translated": t.get("summary_text_translated") if isinstance(t.get("summary_text_translated"), str) else "",
                "key_points_translated": t.get("key_points_translated") if isinstance(t.get("key_points_translated"), list) else [],
            })

    return result


async def translate_quanta_create_items(
    items: list[QuantumCreate],
    primary_language: str,
    llm_service: LLMService,
    prompt_service: PromptService,
    limit: int = 0,
) -> dict[int, dict[str, Any]]:
    """
    Перевести поля квантов (до сохранения в БД).
    Использует индекс в items как временный id для сопоставления с ответом LLM.
    limit: 0 = все, >0 = только первые N квантов, требующих перевода.
    Возвращает словарь индекс -> {title_translated, summary_text_translated, key_points_translated}.
    """
    if not items:
        return {}
    fake_list = [_FakeQuantumForTranslate(i, q) for i, q in enumerate(items)]
    translations = await translate_quanta_fields(
        fake_list,
        primary_language,
        llm_service,
        prompt_service,
        limit=limit,
    )
    by_index: dict[int, dict[str, Any]] = {}
    for t in translations:
        tid = t.get("id")
        if tid is not None and str(tid).isdigit():
            by_index[int(tid)] = t
    return by_index

