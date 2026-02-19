"""
Компиляция QueryModel в boolean-запрос для OpenAlex (search=...).
AND/OR/NOT в верхнем регистре, фразы в кавычках.
"""
import logging
from typing import Any

from app.integrations.search.schemas import QueryModel

logger = logging.getLogger(__name__)


def _term_text(term: str, terms_by_id: dict[str, Any], language: str) -> str | None:
    """Текст терма для языка: translations[language] или text, иначе None с логированием."""
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
    """Фраза в кавычках; если пробелы — двойные кавычки."""
    s = (s or "").strip()
    if not s:
        return ""
    if " " in s:
        return f'"{s}"'
    return s


def compile_openalex_query(
    query_model: QueryModel,
    terms_by_id: dict[str, Any],
    language: str,
) -> str:
    """
    Собрать boolean-строку для OpenAlex search=.

    - MUST ALL -> AND, MUST ANY -> OR.
    - EXCLUDE -> NOT ( ... ).
    - Используется только текст терма для переданного language.
    """
    parts: list[str] = []

    # Keywords: группы в скобках, между термами op (OR/AND), между группами connectors
    group_strs: list[str] = []
    for group in query_model.keywords.groups:
        term_parts: list[str] = []
        for t in group.terms:
            text = _term_text(t, terms_by_id, language)
            if text:
                term_parts.append(_quote_phrase(text))
            else:
                logger.debug("Skipping term %r (no text for language %s)", t, language)
        if not term_parts:
            continue
        op = " OR " if group.op == "OR" else " AND "
        group_strs.append(f"({op.join(term_parts)})")

    if group_strs:
        expr = group_strs[0]
        for idx, conn in enumerate(query_model.keywords.connectors, start=1):
            connector = " AND " if conn == "AND" else " OR "
            if idx < len(group_strs):
                expr = f"{expr}{connector}{group_strs[idx]}"
        parts.append(expr)

    # Must: ALL -> AND, ANY -> OR
    must_terms: list[str] = []
    for t in query_model.must.terms:
        text = _term_text(t, terms_by_id, language)
        if text:
            must_terms.append(_quote_phrase(text))
    if must_terms:
        if query_model.must.mode == "ALL":
            parts.append(" AND ".join(must_terms))
        else:
            parts.append(f"({' OR '.join(must_terms)})")

    # Exclude -> NOT ( ... )
    exclude_terms: list[str] = []
    for t in query_model.exclude.terms:
        text = _term_text(t, terms_by_id, language)
        if text:
            exclude_terms.append(_quote_phrase(text))
    if exclude_terms:
        parts.append(f"NOT ({' OR '.join(exclude_terms)})")

    return " ".join(p for p in parts if p).strip() or " "
