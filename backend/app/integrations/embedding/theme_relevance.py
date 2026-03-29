"""
Сервис создания/обновления вектора релевантности темы для поиска.
Формирует текстовое описание темы, считает hash, при необходимости вызывает эмбеддинг и пишет в БД.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.sql import literal
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.embedding.service import EmbeddingService
from app.integrations.embedding.model import Embedding
from app.modules.theme.model import ThemeSearchQuery

logger = logging.getLogger(__name__)


def _langs_primary_and_extra(theme: Any) -> tuple[str, list[str]]:
    """Первый язык — основной, остальные — дополнительные. Коды без кавычек."""
    langs = theme.languages or []
    if not langs or not isinstance(langs, list):
        return "en", []
    clean = [x.strip() for x in langs if isinstance(x, str) and x.strip()]
    if not clean:
        return "en", []
    return clean[0], clean[1:]


def _format_terms_block(terms: list[Any], primary_lang: str, extra_langs: list[str]) -> str:
    """Один блок терминов: для каждого терма строки 'код: текст' и при наличии 'Context: ...'."""
    lines: list[str] = []
    for t in terms or []:
        if not isinstance(t, dict):
            continue
        text_primary = (t.get("text") or "").strip()
        translations = t.get("translations") or {}
        if not isinstance(translations, dict):
            translations = {}
        context = (t.get("context") or "").strip()

        parts: list[str] = [f"{primary_lang}: {text_primary}"]
        for lang in extra_langs:
            parts.append(f"{lang}: {(translations.get(lang) or '').strip()}")
        lines.append("\n".join(parts))
        if context:
            lines.append(f"Context: {context}")
    return "\n\n".join(lines) if lines else ""


def _must_have_term_ids_from_queries(queries: list[Any]) -> set[str]:
    """Собрать id обязательных терминов, которые встречаются хотя бы в одном запросе."""
    ids: set[str] = set()
    for q in queries or []:
        qm = getattr(q, "query_model", None) or {}
        if not isinstance(qm, dict):
            continue
        must = qm.get("must") or {}
        if not isinstance(must, dict):
            continue
        for tid in must.get("termIds") or []:
            if tid:
                ids.add(str(tid))
    return ids


def build_theme_description(theme: Any, must_have_term_ids: set[str] | None = None) -> str:
    """
    Собрать одну текстовую строку описания темы для эмбеддинга.

    Только название, описание и обязательные слова (must_have), причём только те,
    которые есть хотя бы в одном поисковом запросе темы. Ключевые слова не включаются.

    Формат:
      Theme: <title>
      Description: <description>
      Required context: <must_have по языкам + context> (только термины из запросов)
    """
    primary, extra = _langs_primary_and_extra(theme)
    title = (theme.title or "").strip()
    description = (theme.description or "").strip()

    must_have_all = theme.must_have or []
    if must_have_term_ids is not None:
        must_have_all = [
            t for t in must_have_all
            if isinstance(t, dict) and str(t.get("id") or "") in must_have_term_ids
        ]
    required_block = _format_terms_block(must_have_all, primary, extra)
    parts = [f"Theme:\n{title}\n\n", f"Description:\n{description}"]
    if required_block:
        parts.append(f"\n\nRequired context:\n\n{required_block}")
    return "".join(parts)


def theme_description_hash(description: str) -> str:
    """SHA-256 hash строки в hex (до 128 символов влезает в text_hash)."""
    return hashlib.sha256(description.encode("utf-8")).hexdigest()


async def ensure_theme_relevance_embedding(
    session: AsyncSession,
    theme: Any,
    embedding_service: EmbeddingService,
    settings: Settings,
) -> None:
    """
    Убедиться, что для темы есть актуальный вектор релевантности (embedding_kind=relevance).
    Если записи нет или text_hash не совпадает с текущим описанием — вызвать эмбеддинг и создать/обновить запись.
    В текст для эмбеддинга входят только название, описание и обязательные слова из поисковых запросов.
    """
    theme_id = getattr(theme, "id", None)
    if not theme_id:
        return

    # Обязательные термины только из запросов темы
    q_result = await session.execute(
        select(ThemeSearchQuery).where(ThemeSearchQuery.theme_id == theme_id)
    )
    queries = list(q_result.scalars().all())
    must_ids = _must_have_term_ids_from_queries(queries)

    description = build_theme_description(theme, must_have_term_ids=must_ids)
    text_hash = theme_description_hash(description)
    model_name = (settings.EMBEDDING_MODEL or "").strip() or "text-embedding-3-small"
    dims = settings.EMBEDDING_DIMENSIONS or 1536

    # Найти существующую запись по (theme_id, object_type=theme, object_id=theme_id, embedding_kind=relevance, model)
    stmt = (
        select(Embedding)
        .where(Embedding.theme_id == theme_id)
        .where(Embedding.object_type == "theme")
        .where(Embedding.object_id == theme_id)
        .where(Embedding.embedding_kind == "relevance")
        .where(Embedding.model == literal(model_name))
        .limit(1)
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing and existing.text_hash == text_hash:
        return

    # Вызвать эмбеддинг (биллинг — при наличии BillingService на EmbeddingService)
    try:
        embed_result = await embedding_service.embed(
            description,
            billing_session=session,
            billing_theme_id=theme_id,
            billing_task_type="theme_relevance_embedding",
            billing_extra={
                "embedding_kind": "relevance",
                "object_type": "theme",
            },
        )
    except Exception as e:
        logger.warning(
            "embedding: не удалось построить вектор релевантности для темы %s: %s",
            theme_id,
            e,
        )
        return

    vector = embed_result.get("vector")
    if not vector or not isinstance(vector, list):
        logger.warning("embedding: пустой или неверный вектор для темы %s", theme_id)
        return

    if existing:
        existing.embedding = vector
        existing.text_hash = text_hash
        existing.dims = dims
        existing.updated_at = datetime.now(timezone.utc)
        session.add(existing)
        logger.debug("embedding: обновлён вектор релевантности для темы %s", theme_id)
    else:
        new_embedding = Embedding(
            theme_id=theme_id,
            object_type="theme",
            object_id=theme_id,
            embedding_kind="relevance",
            model=model_name,
            dims=dims,
            embedding=vector,
            text_hash=text_hash,
        )
        session.add(new_embedding)
        logger.debug("embedding: создан вектор релевантности для темы %s", theme_id)

    await session.flush()
