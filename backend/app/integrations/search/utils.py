"""
Утилиты для нормализации URL и дедупликации.
"""
import hashlib
from urllib.parse import urlparse, urlunparse

from app.integrations.search.schemas import LinkCandidate


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
