"""Сервис сайтов: нормализация доменов, get_or_create_site."""

from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.site.models import Site


def normalize_domain(url_or_domain: str) -> str | None:
    """
    Извлекает нормализованный домен из URL или строки домена.
    - Принимает URL (https://example.com/path) или домен (example.com)
    - Убирает www.
    - Приводит к нижнему регистру
    - Возвращает None если пусто/невалидно
    """
    s = (url_or_domain or "").strip()
    if not s:
        return None

    # Попытка распарсить как URL
    if "://" in s or s.startswith("//"):
        parsed = urlparse(s if "://" in s else f"https://{s}")
        host = parsed.netloc or parsed.path
    else:
        host = s.split("/")[0] if "/" in s else s

    if not host:
        return None

    # Убираем порт
    if ":" in host:
        host = host.split(":")[0]

    # Убираем www.
    if host.lower().startswith("www."):
        host = host[4:]

    host = host.lower()
    if not host or "." not in host:
        return None

    return host


async def get_or_create_site(
    session: AsyncSession,
    domain: str,
) -> Site:
    """
    Находит Site по domain или создаёт новый.
    sites хранит только глобальные поля (domain, default_language, country).
    """
    domain_lower = domain.lower()

    result = await session.execute(select(Site).where(Site.domain == domain_lower))
    site = result.scalar_one_or_none()
    if site:
        return site

    site = Site(domain=domain_lower)
    session.add(site)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        result = await session.execute(select(Site).where(Site.domain == domain_lower))
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        raise

    return site
