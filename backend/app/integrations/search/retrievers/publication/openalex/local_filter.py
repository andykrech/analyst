"""
Локальная фильтрация MUST/EXCLUDE по title + summary_text.
Keywords строго не проверяем (уже учтены в запросе к API).
"""
from typing import Any

from app.integrations.search.schemas import QueryModel


def _term_text(term: str, terms_by_id: dict[str, Any], language: str) -> str | None:
    """Текст терма для языка."""
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
        return term.strip() or None
    return term.strip() if isinstance(raw, str) else None


def _text_for_check(quantum: Any) -> str:
    """Объединённый текст для проверки (title + summary_text)."""
    title = getattr(quantum, "title", None) or (quantum.get("title") if isinstance(quantum, dict) else None)
    summary = (
        getattr(quantum, "summary_text", None)
        or (quantum.get("summary_text") if isinstance(quantum, dict) else None)
    )
    return f"{(title or '')} {(summary or '')}".lower()


def passes_must_exclude(
    quantum: Any,
    query_model: QueryModel,
    terms_by_id: dict[str, Any],
    language: str,
) -> bool:
    """
    Проверяет MUST (строго) и EXCLUDE (строго) по title + summary_text.
    Keywords не проверяем.
    """
    text = _text_for_check(quantum)

    # MUST: ALL — все термы должны встретиться; ANY — хотя бы один
    must_terms: list[str] = []
    for t in query_model.must.terms:
        tt = _term_text(t, terms_by_id, language)
        if tt:
            must_terms.append(tt.lower())
    if must_terms:
        if query_model.must.mode == "ALL":
            if not all(phrase in text for phrase in must_terms):
                return False
        else:
            if not any(phrase in text for phrase in must_terms):
                return False

    # EXCLUDE: ни один терм не должен встретиться
    for t in query_model.exclude.terms:
        tt = _term_text(t, terms_by_id, language)
        if tt and tt.lower() in text:
            return False

    return True
