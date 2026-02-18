"""CRUD для theme_sites, sites, user_sites."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.site.models import Site, ThemeSite, UserSite
from app.modules.site.schemas import ThemeSiteCreate, ThemeSiteUpdate
from app.modules.site.service import get_or_create_site, normalize_domain


def _build_site_out(site: Site, user_site: UserSite | None) -> dict:
    """Собирает effective_* поля для SiteOut."""
    return {
        "id": str(site.id),
        "domain": site.domain,
        "default_language": site.default_language,
        "country": site.country,
        "effective_display_name": (
            (user_site.display_name if user_site else None) or site.domain
        ),
        "effective_description": user_site.description if user_site else None,
        "effective_homepage_url": user_site.homepage_url if user_site else None,
        "effective_trust_score": user_site.trust_score if user_site else None,
        "effective_quality_tier": user_site.quality_tier if user_site else None,
    }


async def _get_user_sites_by_site_ids(
    session: AsyncSession,
    user_id: uuid.UUID,
    site_ids: list[uuid.UUID],
) -> dict[uuid.UUID, UserSite]:
    """Загружает UserSite для (user_id, site_ids)."""
    if not site_ids:
        return {}
    result = await session.execute(
        select(UserSite)
        .where(UserSite.user_id == user_id, UserSite.site_id.in_(site_ids))
    )
    return {us.site_id: us for us in result.scalars().all()}


async def list_theme_sites(
    session: AsyncSession,
    theme_id: uuid.UUID,
    user_id: uuid.UUID,
    status: str | None = None,
    mode: str | None = None,
) -> list[dict]:
    """
    Список theme_sites для темы с effective_* полями.
    LEFT JOIN user_sites по user_id.
    Возвращает список dict для сериализации в ThemeSiteOut.
    """
    q = (
        select(ThemeSite)
        .options(selectinload(ThemeSite.site))
        .where(ThemeSite.theme_id == theme_id)
    )
    if status is not None:
        q = q.where(ThemeSite.status == status)
    if mode is not None:
        q = q.where(ThemeSite.mode == mode)
    q = q.join(Site, ThemeSite.site_id == Site.id).order_by(Site.domain)
    result = await session.execute(q)
    theme_sites = list(result.scalars().all())

    site_ids = [ts.site_id for ts in theme_sites]
    user_sites_map = await _get_user_sites_by_site_ids(session, user_id, site_ids)

    out = []
    for ts in theme_sites:
        user_site = user_sites_map.get(ts.site_id)
        site_out = _build_site_out(ts.site, user_site)
        out.append({
            "id": str(ts.id),
            "theme_id": str(ts.theme_id),
            "site_id": str(ts.site_id),
            "mode": ts.mode,
            "source": ts.source,
            "status": ts.status,
            "confidence": ts.confidence,
            "reason": ts.reason,
            "created_by_user_id": str(ts.created_by_user_id) if ts.created_by_user_id else None,
            "site": site_out,
        })
    return out


def _user_site_columns() -> set[str]:
    return {"display_name", "description", "homepage_url", "trust_score", "quality_tier"}


async def upsert_user_site(
    session: AsyncSession,
    user_id: uuid.UUID,
    site_id: uuid.UUID,
    **kwargs: object,
) -> UserSite:
    """Создаёт или обновляет UserSite для (user_id, site_id). Передаются только поля для обновления."""
    allowed = _user_site_columns()
    updates = {k: v for k, v in kwargs.items() if k in allowed}

    result = await session.execute(
        select(UserSite).where(
            UserSite.user_id == user_id,
            UserSite.site_id == site_id,
        )
    )
    user_site = result.scalar_one_or_none()
    if user_site:
        for k, v in updates.items():
            setattr(user_site, k, v)
        await session.flush()
        await session.refresh(user_site)
    else:
        user_site = UserSite(
            user_id=user_id,
            site_id=site_id,
            **updates,
        )
        session.add(user_site)
        await session.flush()
        await session.refresh(user_site)
    return user_site


class ThemeSiteAlreadyExistsError(ValueError):
    """Связь theme_sites(theme_id, site_id) уже существует."""

    pass


async def create_theme_site(
    session: AsyncSession,
    theme_id: uuid.UUID,
    user_id: uuid.UUID,
    domain: str,
    mode: str,
    source: str,
    status: str = "active",
    created_by_user_id: uuid.UUID | None = None,
    confidence: float | None = None,
    reason: str | None = None,
    user_site_data: dict | None = None,
) -> ThemeSite:
    """
    Создаёт ThemeSite или снимает mute: если связь уже есть со status='muted',
    обновляет её (status=active и переданные поля) и возвращает. Иначе при существующей
    связи выбрасывает ThemeSiteAlreadyExistsError.
    """
    domain_norm = normalize_domain(domain)
    if not domain_norm:
        raise ValueError("Некорректный домен")

    site = await get_or_create_site(session, domain_norm)

    result = await session.execute(
        select(ThemeSite).where(
            ThemeSite.theme_id == theme_id,
            ThemeSite.site_id == site.id,
        )
    )
    theme_site = result.scalar_one_or_none()

    if theme_site:
        if theme_site.status == "muted":
            user_site_data = user_site_data or {}
            await upsert_user_site(
                session, user_id=user_id, site_id=site.id, **user_site_data
            )
            theme_site.mode = mode
            theme_site.source = source
            theme_site.status = status
            if confidence is not None:
                theme_site.confidence = confidence
            if reason is not None:
                theme_site.reason = reason
            if created_by_user_id is not None:
                theme_site.created_by_user_id = created_by_user_id
            await session.flush()
            await session.refresh(theme_site)
            return theme_site
        raise ThemeSiteAlreadyExistsError("Источник уже добавлен в тему")

    user_site_data = user_site_data or {}
    await upsert_user_site(session, user_id=user_id, site_id=site.id, **user_site_data)

    theme_site = ThemeSite(
        theme_id=theme_id,
        site_id=site.id,
        mode=mode,
        source=source,
        status=status,
        confidence=confidence,
        reason=reason,
        created_by_user_id=created_by_user_id,
    )
    session.add(theme_site)
    await session.flush()
    await session.refresh(theme_site)
    return theme_site


async def upsert_theme_site(
    session: AsyncSession,
    theme_id: uuid.UUID,
    user_id: uuid.UUID,
    domain: str,
    mode: str,
    source: str,
    status: str = "active",
    created_by_user_id: uuid.UUID | None = None,
    confidence: float | None = None,
    reason: str | None = None,
    user_site_data: dict | None = None,
) -> ThemeSite:
    """
    Создаёт или обновляет ThemeSite.
    - get_or_create Site (только domain)
    - upsert UserSite для user_id
    - upsert ThemeSite
    """
    domain_norm = normalize_domain(domain)
    if not domain_norm:
        raise ValueError("Некорректный домен")

    site = await get_or_create_site(session, domain_norm)

    user_site_data = user_site_data or {}
    await upsert_user_site(session, user_id=user_id, site_id=site.id, **user_site_data)

    result = await session.execute(
        select(ThemeSite).where(
            ThemeSite.theme_id == theme_id,
            ThemeSite.site_id == site.id,
        )
    )
    theme_site = result.scalar_one_or_none()

    if theme_site:
        theme_site.mode = mode
        theme_site.source = source
        theme_site.status = status
        if confidence is not None:
            theme_site.confidence = confidence
        if reason is not None:
            theme_site.reason = reason
        if created_by_user_id is not None:
            theme_site.created_by_user_id = created_by_user_id
        await session.flush()
        await session.refresh(theme_site)
    else:
        theme_site = ThemeSite(
            theme_id=theme_id,
            site_id=site.id,
            mode=mode,
            source=source,
            status=status,
            confidence=confidence,
            reason=reason,
            created_by_user_id=created_by_user_id,
        )
        session.add(theme_site)
        await session.flush()
        await session.refresh(theme_site)

    return theme_site


async def set_theme_site_status(
    session: AsyncSession,
    theme_id: uuid.UUID,
    site_id: uuid.UUID,
    status: str,
) -> ThemeSite | None:
    """Обновляет статус theme_site. Возвращает обновлённую запись или None."""
    result = await session.execute(
        select(ThemeSite).where(
            ThemeSite.theme_id == theme_id,
            ThemeSite.site_id == site_id,
        )
    )
    theme_site = result.scalar_one_or_none()
    if not theme_site:
        return None
    theme_site.status = status
    await session.flush()
    await session.refresh(theme_site)
    return theme_site


async def mute_theme_site(
    session: AsyncSession,
    theme_id: uuid.UUID,
    site_id: uuid.UUID,
) -> ThemeSite | None:
    """Переводит theme_site в status='muted' (вместо удаления)."""
    return await set_theme_site_status(session, theme_id, site_id, "muted")


async def get_theme_site(
    session: AsyncSession,
    theme_id: uuid.UUID,
    site_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> tuple[ThemeSite | None, dict | None]:
    """
    Получить ThemeSite по theme_id и site_id.
    Возвращает (theme_site, site_out) или (None, None).
    site_out содержит effective_* (если передан user_id).
    """
    result = await session.execute(
        select(ThemeSite)
        .options(selectinload(ThemeSite.site))
        .where(
            ThemeSite.theme_id == theme_id,
            ThemeSite.site_id == site_id,
        )
    )
    theme_site = result.scalar_one_or_none()
    if not theme_site:
        return None, None

    user_site = None
    if user_id:
        us_result = await session.execute(
            select(UserSite).where(
                UserSite.user_id == user_id,
                UserSite.site_id == site_id,
            )
        )
        user_site = us_result.scalar_one_or_none()

    site_out = _build_site_out(theme_site.site, user_site)
    return theme_site, site_out
