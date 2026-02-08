"""
Утилиты для нормализации URL и дедупликации.
"""
import hashlib
from urllib.parse import urlparse, urlunparse

from app.integrations.search.schemas import LinkCandidate


def _text_for_filtering(item: LinkCandidate) -> str:
    """Текст для проверки must_have/exclude (title + snippet + url)."""
    parts = [
        item.title or "",
        item.snippet or "",
        item.url or "",
    ]
    return " ".join(parts).lower()


def filter_by_must_have(items: list[LinkCandidate], must_have: list[str]) -> list[LinkCandidate]:
    """Оставить только элементы, содержащие все фразы из must_have."""
    if not must_have:
        return items
    result: list[LinkCandidate] = []
    for item in items:
        text = _text_for_filtering(item)
        if all(phrase.lower() in text for phrase in must_have if phrase):
            result.append(item)
    return result


def filter_by_exclude(items: list[LinkCandidate], exclude: list[str]) -> list[LinkCandidate]:
    """Убрать элементы, содержащие любую фразу из exclude."""
    if not exclude:
        return items
    result: list[LinkCandidate] = []
    for item in items:
        text = _text_for_filtering(item)
        if not any(phrase.lower() in text for phrase in exclude if phrase):
            result.append(item)
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
    """Дедупликация по url_hash: сохранить первый встреченный."""
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
