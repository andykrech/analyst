"""
Компиляция QueryModel в query-строку для Semantic Scholar paper search.

Синтаксис Semantic Scholar:
- +  AND
- |  OR
- -  negate term/group
- "..." phrases
- ( ) precedence
"""

from __future__ import annotations

import logging
from typing import Any

from app.integrations.search.schemas import QueryModel


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


def _quote_phrase(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    if " " in s:
        return f"\"{s}\""
    return s


def compile_semanticscholar_query(
    query_model: QueryModel,
    terms_by_id: dict[str, Any],
    language: str,
) -> str:
    """
    Полный запрос для Semantic Scholar paper/search (MUST/EXCLUDE учитываются):
    - keywords: каждая группа в скобках; внутри оп = (OR -> |, AND -> +)
    - соединение групп: keywords.connectors (AND -> +, OR -> |)
    - MUST:
      - mode=ALL: все must-термы через +
      - mode=ANY: must-термы через (t1 | t2 | ...)
    - EXCLUDE:
      - термы через (t1 | t2 | ...) и всё экранируем через -(...).
    """

    parts: list[str] = []

    # keywords groups
    groups = query_model.keywords.groups or []
    group_strs: list[str] = []
    for group in groups:
        term_parts: list[str] = []
        for t in getattr(group, "terms", []) or []:
            text = _term_text(t, terms_by_id, language)
            if text:
                term_parts.append(_quote_phrase(text))
        if not term_parts:
            continue
        op = " | " if getattr(group, "op", "OR") == "OR" else " + "
        group_strs.append(f"({op.join(term_parts)})")

    if group_strs:
        expr = group_strs[0]
        for idx, conn in enumerate(query_model.keywords.connectors or [], start=1):
            if idx < len(group_strs):
                connector = " + " if conn == "AND" else " | "
                expr = f"{expr}{connector}{group_strs[idx]}"
        parts.append(expr)

    # MUST
    must_terms: list[str] = []
    for t in query_model.must.terms:
        text = _term_text(t, terms_by_id, language)
        if text:
            must_terms.append(_quote_phrase(text))
    if must_terms:
        if query_model.must.mode == "ALL":
            parts.append(" + ".join(must_terms))
        else:
            parts.append(f"({' | '.join(must_terms)})")

    # EXCLUDE
    exclude_terms: list[str] = []
    for t in query_model.exclude.terms:
        text = _term_text(t, terms_by_id, language)
        if text:
            exclude_terms.append(_quote_phrase(text))
    if exclude_terms:
        parts.append(f"-({' | '.join(exclude_terms)})")

    cleaned = [p for p in parts if isinstance(p, str) and p.strip()]
    if not cleaned:
        return " "

    # Явное AND между блоками (и keywords/MUST/EXCLUDE).
    return " + ".join(cleaned).strip() or " "

