"""Сервисный слой для квантов (пока минимальный)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quanta.crud import create_quantum
from app.modules.quanta.models import Quantum


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

