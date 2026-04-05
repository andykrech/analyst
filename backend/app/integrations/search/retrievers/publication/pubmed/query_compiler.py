"""
Компиляция QueryModel в строку term для NCBI ESearch (db=pubMed).

Синтаксис PubMed: AND, OR, NOT; фразы в двойных кавычках.
Диапазон дат: ("YYYY/MM/DD"[PDAT] : "YYYY/MM/DD"[PDAT]) при наличии time_slice.
"""
from __future__ import annotations

import logging
from typing import Any

from app.integrations.search.schemas import QueryModel, TimeSlice

logger = logging.getLogger(__name__)


def _term_text(term: str, terms_by_id: dict[str, Any], language: str) -> str | None:
    if not term or not isinstance(term, str):
        return None
    raw = terms_by_id.get(term) if terms_by_id else None
    if raw is None:
        return term.strip() or None
    if isinstance(raw, dict):
        trans = (raw.get("translations") or {}).get(language)
        if trans and isinstance(trans, str) and trans.strip():
            return trans.strip()
        txt = raw.get("text")
        if txt and isinstance(txt, str) and txt.strip():
            return txt.strip()
        logger.debug("Term %r has no text for language %s, using id as fallback", term, language)
        return term.strip() or None
    return term.strip() if isinstance(raw, str) else None


def _sanitize_phrase(s: str) -> str:
    return " ".join((s or "").replace('"', " ").split())


def _format_pubmed_token(text: str) -> str:
    """Один токен/фраза для term: многословные — в кавычках."""
    s = _sanitize_phrase(text).strip()
    if not s:
        return ""
    if " " in s:
        return f'"{s}"'
    return s


def _clause_from_terms(terms: list[str], op: str) -> str:
    parts: list[str] = []
    for t in terms:
        ft = _format_pubmed_token(t)
        if ft:
            parts.append(ft)
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    inner = f" {op} ".join(parts)
    return f"({inner})"


def _pdat_range(time_slice: TimeSlice) -> str | None:
    pf = time_slice.published_from
    pt = time_slice.published_to
    if pf is None or pt is None:
        return None

    def fmt(d: Any) -> str:
        if hasattr(d, "strftime"):
            return d.strftime("%Y/%m/%d")
        return ""

    a, b = fmt(pf), fmt(pt)
    if not a or not b:
        return None
    return f'("{a}"[PDAT] : "{b}"[PDAT])'


def compile_pubmed_term(
    query_model: QueryModel,
    terms_by_id: dict[str, Any],
    language: str,
    time_slice: TimeSlice | None = None,
) -> str:
    blocks: list[str] = []

    group_strs: list[str] = []
    for group in query_model.keywords.groups:
        term_parts: list[str] = []
        for t in group.terms:
            text = _term_text(t, terms_by_id, language)
            if text:
                ft = _format_pubmed_token(text)
                if ft:
                    term_parts.append(ft)
        if not term_parts:
            continue
        inner_op = " OR " if group.op == "OR" else " AND "
        group_strs.append(f"({inner_op.join(term_parts)})")

    if group_strs:
        expr = group_strs[0]
        for idx, conn in enumerate(query_model.keywords.connectors, start=1):
            if idx < len(group_strs):
                connector = " AND " if conn == "AND" else " OR "
                expr = f"{expr}{connector}{group_strs[idx]}"
        blocks.append(f"({expr})")

    must_parts: list[str] = []
    for t in query_model.must.terms:
        text = _term_text(t, terms_by_id, language)
        if text:
            ft = _format_pubmed_token(text)
            if ft:
                must_parts.append(ft)
    if must_parts:
        if query_model.must.mode == "ALL":
            blocks.append("(" + " AND ".join(must_parts) + ")")
        else:
            blocks.append("(" + " OR ".join(must_parts) + ")")

    if time_slice is not None:
        dr = _pdat_range(time_slice)
        if dr:
            blocks.append(f"({dr})")

    core = " AND ".join(blocks).strip() if blocks else ""

    exclude_parts: list[str] = []
    for t in query_model.exclude.terms:
        text = _term_text(t, terms_by_id, language)
        if text:
            ft = _format_pubmed_token(text)
            if ft:
                exclude_parts.append(ft)

    if exclude_parts:
        ex = "(" + " OR ".join(exclude_parts) + ")"
        if core:
            return f"{core} NOT {ex}".strip()
        return ""

    return core.strip()
