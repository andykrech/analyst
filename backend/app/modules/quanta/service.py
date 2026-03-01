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
QUANTA_RELEVANCE_SCORE_PROMPT = "quanta.relevance_score.v1"
# Лимит токенов ответа на один батч перевода (чтобы не ждать бесконечно)
TRANSLATE_MAX_TOKENS = 8192
RELEVANCE_SCORE_MAX_TOKENS = 4096


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
    relevance_by_index: dict[int, dict[str, Any]] | None = None,
) -> list[Quantum]:
    """
    Сохранить кванты, полученные поиском, в БД (upsert по theme_id + dedup_key).
    Если передан translations_by_index (индекс в items -> переводы), заполняются
    title_translated, summary_text_translated, key_points_translated.
    Если передан relevance_by_index (индекс -> {opinion_score, total_score}), заполняются
    opinion_score и total_score.
    Возвращает список созданных/обновлённых Quantum в том же порядке, что и items (пропуски не возвращаются).
    """
    logger = logging.getLogger(__name__)
    n_with_translation = sum(1 for i in range(len(items)) if (translations_by_index or {}).get(i))
    logger.info(
        "search/save_quanta: на запись передано квантов=%s, с переводами=%s",
        len(items),
        n_with_translation,
    )
    created: list[Quantum] = []
    trans = translations_by_index or {}
    rel_by_idx = relevance_by_index or {}
    for i, q in enumerate(items):
        theme_id = _uuid_or_none(q.theme_id)
        if not theme_id:
            continue
        identifiers_dict = [x.model_dump() for x in q.identifiers] if q.identifiers else []
        t = trans.get(i)
        rel = rel_by_idx.get(i)
        opinion_score = rel.get("opinion_score") if isinstance(rel, dict) else None
        total_score = rel.get("total_score") if isinstance(rel, dict) else None
        if opinion_score is not None and not isinstance(opinion_score, list):
            opinion_score = None
        row = await create_quantum(
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
            opinion_score=opinion_score,
            total_score=total_score if isinstance(total_score, (int, float)) else None,
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
        created.append(row)
    logger.info("search/save_quanta: записано квантов=%s", len(created))
    return created


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
    opinion_score: list[dict[str, Any]] | None = None,
    total_score: float | None = None,
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
        opinion_score=opinion_score,
        total_score=total_score,
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


def _clamp_score(value: Any) -> float | None:
    """Привести значение к float в [0, 1] или None."""
    if value is None:
        return None
    try:
        x = float(value)
        if 0 <= x <= 1:
            return x
        return max(0.0, min(1.0, x))
    except (TypeError, ValueError):
        return None


async def score_quanta_relevance(
    theme_description: str,
    items: list[QuantumCreate],
    model_names: list[str],
    llm_service: LLMService,
    prompt_service: PromptService,
) -> list[dict[str, Any]]:
    """
    Оценка релевантности квантов теме от нескольких моделей ИИ.

    В запрос к ИИ передаются только описание темы и нумерованный список заголовков (title).
    Ответ модели — JSON вида {"1": 0.5, "2": 0.1, ...}. Номер соответствует индексу кванта (1-based).

    Возвращает список той же длины, что и items: для каждого кванта
    {"opinion_score": [{"model": str, "score": float}, ...], "total_score": float}.
    total_score — среднее арифметическое rank_score (если есть) и всех score из opinion_score.
    """
    logger = logging.getLogger(__name__)
    if not items or not model_names:
        return [{"opinion_score": [], "total_score": None} for _ in items] if items else []

    titles_list = "\n".join(f"{i}. { (q.title or '').strip() or '(без заголовка)' }" for i, q in enumerate(items, 1))
    vars_for_prompt = {
        "theme_description": (theme_description or "").strip() or "(описание темы не задано)",
        "titles_list": titles_list,
    }

    # По каждой модели — один вызов, ответ {"1": 0.5, "2": 0.1, ...}
    scores_by_model: list[tuple[str, dict[str, float]]] = []  # (model_name, {index_str -> score})
    for model_name in model_names:
        model_key = (model_name or "").strip().lower()
        if not model_key:
            continue
        try:
            response = await llm_service.generate_from_prompt(
                QUANTA_RELEVANCE_SCORE_PROMPT,
                vars_for_prompt,
                prompt_service,
                provider=model_key,
                generation={"max_tokens": RELEVANCE_SCORE_MAX_TOKENS},
            )
        except Exception as e:
            logger.warning(
                "score_quanta_relevance: вызов модели %s не удался: %s",
                model_key,
                e,
            )
            continue

        text = (response.text or "").strip()
        if not text:
            continue
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
            logger.warning("score_quanta_relevance: модель %s вернула не JSON: %s", model_key, e)
            continue

        parsed: dict[str, float] = {}
        for k, v in (data if isinstance(data, dict) else {}).items():
            key = str(k).strip()
            if not key.isdigit():
                continue
            s = _clamp_score(v)
            if s is not None:
                parsed[key] = s
        scores_by_model.append((model_key, parsed))

    # Собираем opinion_score и total_score для каждого кванта (по индексу 0..len(items)-1)
    result: list[dict[str, Any]] = []
    for i in range(len(items)):
        q = items[i]
        idx_str = str(i + 1)
        opinion_score: list[dict[str, Any]] = []
        for model_key, scores in scores_by_model:
            s = scores.get(idx_str)
            if s is not None:
                opinion_score.append({"model": model_key, "score": s})

        values_for_mean: list[float] = []
        if q.rank_score is not None:
            try:
                r = float(q.rank_score)
                if 0 <= r <= 1:
                    values_for_mean.append(r)
                else:
                    values_for_mean.append(max(0.0, min(1.0, r)))
            except (TypeError, ValueError):
                pass
        for o in opinion_score:
            sc = o.get("score")
            if sc is not None:
                values_for_mean.append(float(sc))

        total_score: float | None = None
        if values_for_mean:
            total_score = sum(values_for_mean) / len(values_for_mean)

        result.append({"opinion_score": opinion_score, "total_score": total_score})

    return result

