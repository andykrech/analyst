"""
Утилиты для нормализации URL, фильтрации и дедупликации.
Поддержка квантов (QuantumCreate) и legacy LinkCandidate.
"""
import hashlib
from urllib.parse import urlparse, urlunparse

from app.integrations.search.schemas import LinkCandidate
from app.modules.quanta.schemas import QuantumCreate


def _text_for_filtering(item: LinkCandidate) -> str:
    """Текст для проверки must_have/exclude по LinkCandidate (title + snippet + url)."""
    parts = [
        item.title or "",
        item.snippet or "",
        item.url or "",
    ]
    return " ".join(parts).lower()


def _text_for_filtering_quantum(q: QuantumCreate) -> str:
    """Текст для проверки MUST/EXCLUDE по кванту (title + summary_text)."""
    return f"{(q.title or '')} {(q.summary_text or '')}".lower()


def filter_by_must_have(items: list[LinkCandidate], must_have: list[str]) -> list[LinkCandidate]:
    """Оставить только элементы, содержащие все фразы из must_have (LinkCandidate)."""
    if not must_have:
        return items
    result: list[LinkCandidate] = []
    for item in items:
        text = _text_for_filtering(item)
        if all(phrase.lower() in text for phrase in must_have if phrase):
            result.append(item)
    return result


def filter_by_exclude(items: list[LinkCandidate], exclude: list[str]) -> list[LinkCandidate]:
    """Убрать элементы, содержащие любую фразу из exclude (LinkCandidate)."""
    if not exclude:
        return items
    result: list[LinkCandidate] = []
    for item in items:
        text = _text_for_filtering(item)
        if not any(phrase.lower() in text for phrase in exclude if phrase):
            result.append(item)
    return result


def filter_by_must_have_quanta(
    items: list[QuantumCreate],
    must_have: list[str],
    *,
    mode: str = "ALL",
) -> list[QuantumCreate]:
    """Оставить кванты, удовлетворяющие MUST: mode ALL — все фразы, ANY — хотя бы одна."""
    if not must_have:
        return items
    result: list[QuantumCreate] = []
    for q in items:
        text = _text_for_filtering_quantum(q)
        if mode == "ALL":
            if all(phrase.lower() in text for phrase in must_have if phrase):
                result.append(q)
        else:
            if any(phrase.lower() in text for phrase in must_have if phrase):
                result.append(q)
    return result


def filter_by_exclude_quanta(items: list[QuantumCreate], exclude: list[str]) -> list[QuantumCreate]:
    """Убрать кванты, содержащие любую фразу из exclude."""
    if not exclude:
        return items
    result: list[QuantumCreate] = []
    for q in items:
        text = _text_for_filtering_quantum(q)
        if not any(phrase.lower() in text for phrase in exclude if phrase):
            result.append(q)
    return result


def normalize_url(url: str) -> str:
    """
    Нормализовать URL: trim, убрать fragment, привести scheme/host к lower,
    добавить https:// если нет scheme.
    """
    s = (url or "").strip()
    if not s:
        return ""

    # Убрать fragment (#...)
    parsed = urlparse(s)
    # Схема и хост к lower
    scheme = (parsed.scheme or "").lower()
    netloc = (parsed.netloc or "").lower()
    path = parsed.path or "/"
    params = parsed.params
    query = parsed.query

    if not scheme:
        scheme = "https"
        # Если netloc пустой, но path начинается с чего-то вроде example.com
        if not netloc and path:
            # Простой случай: "example.com/path" -> https://example.com/path
            if "/" in path:
                first, rest = path.split("/", 1)
                netloc = first
                path = "/" + rest if rest else "/"
            else:
                netloc = path.lstrip("/")
                path = "/"

    return urlunparse((scheme, netloc, path, params, query, ""))


def url_hash(normalized_url: str) -> str:
    """SHA256 hex от нормализованного URL."""
    return hashlib.sha256((normalized_url or "").encode("utf-8")).hexdigest()


def dedup_by_hash(items: list[LinkCandidate]) -> list[LinkCandidate]:
    """Дедупликация по url_hash: сохранить первый встреченный (legacy)."""
    seen: set[str] = set()
    result: list[LinkCandidate] = []
    for item in items:
        h = item.url_hash
        if h is None:
            result.append(item)
            continue
        if h in seen:
            continue
        seen.add(h)
        result.append(item)
    return result


def _quantum_dedup_key(q: QuantumCreate) -> str:
    """Ключ дедупа для кванта: dedup_key или fp:fingerprint (fingerprint при необходимости строим)."""
    if q.dedup_key and q.dedup_key.strip():
        return q.dedup_key.strip()
    from app.modules.quanta.crud import build_dedup_key, build_fingerprint

    fp = q.fingerprint
    if not fp:
        fp = build_fingerprint(
            entity_kind=q.entity_kind,
            title=q.title,
            date_at=q.date_at,
            source_system=q.source_system,
        )
    ids = [x.model_dump() for x in q.identifiers]
    return build_dedup_key(identifiers=ids, canonical_url=q.canonical_url, fingerprint=fp)


def dedup_quanta(items: list[QuantumCreate]) -> list[QuantumCreate]:
    """Дедупликация квантов по (theme_id, dedup_key): сохранить первый встречный."""
    seen: set[tuple[str, str]] = set()
    result: list[QuantumCreate] = []
    for q in items:
        key = (q.theme_id, _quantum_dedup_key(q))
        if key in seen:
            continue
        seen.add(key)
        result.append(q)
    return result
