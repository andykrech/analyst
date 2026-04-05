"""
Компиляция QueryModel в search_query для arXiv API (Lucene-подобный синтаксис).

Поля: префикс all: для термов (title+abstract+…).
Логика: AND / OR / скобки; исключения через ANDNOT (как в руководстве arXiv).
Опционально: submittedDate:[YYYYMMDD0000 TO YYYYMMDD2359] (GMT), если передан time_slice.
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


def _sanitize(s: str) -> str:
    """Убрать кавычки и лишние пробелы — ломают all:\"…\"."""
    return " ".join((s or "").replace('"', " ").split())


def _quote_phrase(s: str) -> str:
    s = _sanitize(s).strip()
    if not s:
        return ""
    if " " in s:
        return f'"{s}"'
    return s


def _all_clause(text: str) -> str:
    q = _quote_phrase(text)
    if not q:
        return ""
    return f"all:{q}"


def _submitted_date_range(time_slice: TimeSlice) -> str | None:
    """Фрагмент AND submittedDate:[… TO …] в формате мануала arXiv (GMT, минуты)."""
    pf = time_slice.published_from
    pt = time_slice.published_to
    if pf is None or pt is None:
        return None
    def _ymd_hhmm(dt: Any, end_of_day: bool) -> str:
        if hasattr(dt, "timetuple"):
            y, m, d = dt.year, dt.month, dt.day
        else:
            return ""
        hhmm = "2359" if end_of_day else "0000"
        return f"{y:04d}{m:02d}{d:02d}{hhmm}"

    start = _ymd_hhmm(pf, end_of_day=False)
    end = _ymd_hhmm(pt, end_of_day=True)
    if not start or not end:
        return None
    return f"submittedDate:[{start} TO {end}]"


def compile_arxiv_query(
    query_model: QueryModel,
    terms_by_id: dict[str, Any],
    language: str,
    time_slice: TimeSlice | None = None,
) -> str:
    """
    Собрать search_query для arXiv.

    - keywords: группы в скобках, внутри OR/AND; между группами — connectors.
    - MUST: ALL — AND между all:…; ANY — (all:… OR …).
    - EXCLUDE: ANDNOT (all:e1 OR all:e2 OR …).
    """
    blocks: list[str] = []

    group_strs: list[str] = []
    for group in query_model.keywords.groups:
        term_parts: list[str] = []
        for t in group.terms:
            text = _term_text(t, terms_by_id, language)
            if text:
                c = _all_clause(text)
                if c:
                    term_parts.append(c)
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
            c = _all_clause(text)
            if c:
                must_parts.append(c)
    if must_parts:
        if query_model.must.mode == "ALL":
            blocks.append("(" + " AND ".join(must_parts) + ")")
        else:
            blocks.append("(" + " OR ".join(must_parts) + ")")

    if time_slice is not None:
        dr = _submitted_date_range(time_slice)
        if dr:
            blocks.append(f"({dr})")

    core = " AND ".join(blocks).strip() if blocks else ""

    exclude_parts: list[str] = []
    for t in query_model.exclude.terms:
        text = _term_text(t, terms_by_id, language)
        if text:
            c = _all_clause(text)
            if c:
                exclude_parts.append(c)

    if exclude_parts:
        ex = "(" + " OR ".join(exclude_parts) + ")"
        if core:
            return f"{core} ANDNOT {ex}".strip()
        # Без позитивных условий arXiv не запрашиваем (избегаем семантики «всё минус …»).
        return ""

    return core.strip() or " "
