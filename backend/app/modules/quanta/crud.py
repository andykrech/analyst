"""CRUD и дедуп-утилиты для квантов информации (theme_quanta)."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime
from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quanta.models import Quantum, QuantumEntityKind


_WS_RE = re.compile(r"\s+")


def _norm_text(value: str) -> str:
    """Нормализация для fingerprint: lower/trim/collapse whitespace."""
    s = (value or "").strip().lower()
    s = _WS_RE.sub(" ", s)
    return s


def build_fingerprint(
    *,
    entity_kind: str | QuantumEntityKind,
    title: str,
    date_at: datetime | None,
    source_system: str | None,
) -> str:
    """
    sha256 от (entity_kind + normalized(title) + coalesce(date_bucket) + coalesce(source_system)).
    date_bucket: YYYY-MM (месяц публикации/выхода).
    """
    kind = entity_kind.value if isinstance(entity_kind, QuantumEntityKind) else str(entity_kind)
    kind = _norm_text(kind)
    norm_title = _norm_text(title)
    date_bucket = ""
    if date_at:
        date_bucket = f"{date_at.year:04d}-{date_at.month:02d}"
    src = _norm_text(source_system or "")
    raw = f"{kind}|{norm_title}|{date_bucket}|{src}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_dedup_key(
    *,
    identifiers: list[dict[str, Any]] | None,
    canonical_url: str | None,
    fingerprint: str,
) -> str:
    """
    Правило:
    - если identifiers содержит doi -> "doi:<value>"
    - elif identifiers содержит patent_number -> "patent:<value>"
    - elif canonical_url not null -> "url:<canonical_url>"
    - else -> "fp:<fingerprint>"
    """
    ids = identifiers or []
    doi_val: str | None = None
    patent_val: str | None = None
    for it in ids:
        if not isinstance(it, dict):
            continue
        scheme = (it.get("scheme") or "").strip().lower()
        value = (it.get("value") or "").strip()
        if not scheme or not value:
            continue
        if scheme == "doi" and doi_val is None:
            doi_val = value
        if scheme == "patent_number" and patent_val is None:
            patent_val = value

    if doi_val:
        return f"doi:{doi_val}"
    if patent_val:
        return f"patent:{patent_val}"
    if canonical_url:
        return f"url:{canonical_url}"
    return f"fp:{fingerprint}"


def build_upsert_stmt(
    *,
    values: dict[str, Any],
) -> sa.sql.dml.Insert:
    """
    Собрать Postgres INSERT ... ON CONFLICT для (theme_id, dedup_key).

    Политика обновления: максимально безопасная.
    - Обновляем только "пустые" или NULL поля в существующей записи.
    - Массивы JSONB заполняем только если в существующей записи массив пустой.
    - attrs заполняем только если в существующей записи {}.
    """
    excluded = sa.table("excluded")  # маркер для mypy; реальные excluded берём ниже
    stmt = pg_insert(Quantum).values(**values)
    excluded = stmt.excluded  # type: ignore[attr-defined]

    def fill_if_null(col: sa.ColumnElement, new_val: sa.ColumnElement) -> sa.ColumnElement:
        return sa.case((col.is_(None), new_val), else_=col)

    def fill_if_empty_text(col: sa.ColumnElement, new_val: sa.ColumnElement) -> sa.ColumnElement:
        return sa.case(((col == ""), new_val), else_=col)

    def fill_if_empty_array(col: sa.ColumnElement, new_val: sa.ColumnElement) -> sa.ColumnElement:
        return sa.case((sa.func.jsonb_array_length(col) == 0, new_val), else_=col)

    def fill_if_empty_object(col: sa.ColumnElement, new_val: sa.ColumnElement) -> sa.ColumnElement:
        return sa.case((sa.func.jsonb_object_length(col) == 0, new_val), else_=col)

    set_ = {
        # Текстовые поля: заполняем только если пусто/NULL.
        "summary_text": fill_if_empty_text(Quantum.summary_text, excluded.summary_text),
        "canonical_url": fill_if_null(Quantum.canonical_url, excluded.canonical_url),
        "language": fill_if_null(Quantum.language, excluded.language),
        "date_at": fill_if_null(Quantum.date_at, excluded.date_at),
        "retriever_query": fill_if_null(Quantum.retriever_query, excluded.retriever_query),
        "rank_score": fill_if_null(Quantum.rank_score, excluded.rank_score),
        "site_id": fill_if_null(Quantum.site_id, excluded.site_id),
        "retriever_version": fill_if_null(Quantum.retriever_version, excluded.retriever_version),
        "raw_payload_ref": fill_if_null(Quantum.raw_payload_ref, excluded.raw_payload_ref),
        "content_ref": fill_if_null(Quantum.content_ref, excluded.content_ref),
        # JSONB массивы: только если массив пустой
        "key_points": fill_if_empty_array(Quantum.key_points, excluded.key_points),
        "identifiers": fill_if_empty_array(Quantum.identifiers, excluded.identifiers),
        "matched_terms": fill_if_empty_array(Quantum.matched_terms, excluded.matched_terms),
        "matched_term_ids": fill_if_empty_array(Quantum.matched_term_ids, excluded.matched_term_ids),
        # attrs: только если пустой объект
        "attrs": fill_if_empty_object(Quantum.attrs, excluded.attrs),
        # updated_at всегда актуализируем при конфликте
        "updated_at": sa.func.now(),
    }

    return stmt.on_conflict_do_update(
        index_elements=["theme_id", "dedup_key"],
        set_=set_,
    )


async def create_quantum(
    session: AsyncSession,
    *,
    theme_id: uuid.UUID,
    run_id: uuid.UUID | None,
    entity_kind: str,
    title: str,
    summary_text: str,
    key_points: list[str] | None,
    language: str | None,
    date_at: datetime | None,
    verification_url: str,
    canonical_url: str | None,
    dedup_key: str | None,
    fingerprint: str | None,
    identifiers: list[dict[str, Any]] | None,
    matched_terms: list[str] | None,
    matched_term_ids: list[str] | None,
    retriever_query: str | None,
    rank_score: float | None,
    source_system: str,
    site_id: uuid.UUID | None,
    retriever_name: str,
    retriever_version: str | None,
    attrs: dict[str, Any] | None,
    raw_payload_ref: uuid.UUID | None,
    content_ref: str | None,
) -> Quantum:
    """
    Создать квант с дедупликацией по (theme_id, dedup_key).
    При конфликте заполняет только пустые/NULL поля и возвращает мастер-запись.
    """
    if fingerprint is None or not str(fingerprint).strip():
        fingerprint = build_fingerprint(
            entity_kind=entity_kind,
            title=title,
            date_at=date_at,
            source_system=source_system,
        )
    if dedup_key is None or not str(dedup_key).strip():
        dedup_key = build_dedup_key(
            identifiers=identifiers or [],
            canonical_url=canonical_url,
            fingerprint=fingerprint,
        )

    values = {
        "theme_id": theme_id,
        "run_id": run_id,
        "entity_kind": entity_kind,
        "title": title,
        "summary_text": summary_text,
        "key_points": key_points or [],
        "language": language,
        "date_at": date_at,
        "verification_url": verification_url,
        "canonical_url": canonical_url,
        "dedup_key": dedup_key,
        "fingerprint": fingerprint,
        "identifiers": identifiers or [],
        "matched_terms": matched_terms or [],
        "matched_term_ids": matched_term_ids or [],
        "retriever_query": retriever_query,
        "rank_score": rank_score,
        "source_system": source_system,
        "site_id": site_id,
        "retriever_name": retriever_name,
        "retriever_version": retriever_version,
        "attrs": attrs or {},
        "raw_payload_ref": raw_payload_ref,
        "content_ref": content_ref,
    }

    stmt = build_upsert_stmt(values=values).returning(Quantum.id)
    result = await session.execute(stmt)
    quantum_id = result.scalar_one()
    row = await session.get(Quantum, quantum_id)
    assert row is not None
    return row


async def get_quantum(
    session: AsyncSession,
    *,
    quantum_id: uuid.UUID,
) -> Quantum | None:
    result = await session.execute(
        sa.select(Quantum).where(Quantum.id == quantum_id)
    )
    return result.scalar_one_or_none()


async def list_quanta(
    session: AsyncSession,
    *,
    theme_id: uuid.UUID,
    entity_kind: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Quantum], int]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))

    q = sa.select(Quantum).where(Quantum.theme_id == theme_id)
    if entity_kind is not None:
        q = q.where(Quantum.entity_kind == entity_kind)
    if status is not None:
        q = q.where(Quantum.status == status)

    total_q = sa.select(sa.func.count()).select_from(q.subquery())

    q = q.order_by(Quantum.retrieved_at.desc()).limit(limit).offset(offset)

    total_res = await session.execute(total_q)
    total = int(total_res.scalar_one() or 0)

    res = await session.execute(q)
    items = list(res.scalars().all())
    return items, total


async def mark_duplicate(
    session: AsyncSession,
    *,
    quantum_id: uuid.UUID,
    master_id: uuid.UUID,
) -> Quantum | None:
    row = await get_quantum(session, quantum_id=quantum_id)
    if not row:
        return None
    row.status = "duplicate"
    row.duplicate_of_id = master_id
    await session.flush()
    await session.refresh(row)
    return row

