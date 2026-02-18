"""Роутер сайтов темы: CRUD theme_sites, рекомендация источников (ИИ)."""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.integrations.llm import LLMService, get_llm_service
from app.integrations.prompts import PromptService, get_prompt_service
from app.modules.auth.router import get_current_user
from app.modules.site.crud import (
    ThemeSiteAlreadyExistsError,
    create_theme_site,
    get_theme_site,
    list_theme_sites,
    mute_theme_site,
    upsert_user_site,
)
from app.modules.site.schemas import (
    RecommendedSiteItem,
    SiteOut,
    SourcesRecommendLLMMeta,
    SourcesRecommendRequest,
    SourcesRecommendResponse,
    ThemeSiteCreate,
    ThemeSiteOut,
    ThemeSiteUpdate,
)
from app.modules.site.service import normalize_domain
from app.modules.theme.service import get_theme_with_queries
from app.modules.user.model import User

router = APIRouter(prefix="/api/v1/themes", tags=["themes-sites"])
logger = logging.getLogger(__name__)

SOURCES_RECOMMEND_PROMPT = "sources.recommend"
DETAIL_TRUNCATE = 300


def _theme_site_row_to_out(row: dict) -> ThemeSiteOut:
    """Преобразует строку из list_theme_sites в ThemeSiteOut."""
    return ThemeSiteOut(
        id=row["id"],
        theme_id=row["theme_id"],
        site_id=row["site_id"],
        mode=row["mode"],
        source=row["source"],
        status=row["status"],
        confidence=row["confidence"],
        reason=row["reason"],
        created_by_user_id=row["created_by_user_id"],
        site=SiteOut(**row["site"]),
    )


async def _ensure_theme_access(
    db: AsyncSession,
    theme_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Проверяет, что тема существует и принадлежит пользователю."""
    theme, _ = await get_theme_with_queries(db, theme_id, user_id)
    if not theme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тема не найдена или недоступна",
        )


@router.post(
    "/{theme_id}/sites/recommend",
    response_model=SourcesRecommendResponse,
)
async def recommend_sources_endpoint(
    request: Request,
    theme_id: str,
    body: SourcesRecommendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service),
    prompt_service: PromptService = Depends(get_prompt_service),
) -> SourcesRecommendResponse:
    """Рекомендация источников (сайтов) по контексту темы через ИИ."""
    try:
        tid = uuid.UUID(theme_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат theme_id (ожидается UUID)",
        )
    await _ensure_theme_access(db, tid, current_user.id)

    title = (body.title or "").strip()
    description = (body.description or "").strip()
    keywords_str = ", ".join(body.keywords) if body.keywords else ""
    if not title and not description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите название или описание темы для рекомендации источников",
        )

    try:
        response = await llm_service.generate_from_prompt(
            prompt_name=SOURCES_RECOMMEND_PROMPT,
            vars={
                "theme_title": title or "(не указано)",
                "theme_description": description or "(не указано)",
                "theme_keywords": keywords_str or "(не указано)",
            },
            prompt_service=prompt_service,
            task="sources_recommend",
            generation={"temperature": 0.2, "max_tokens": 2000},
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("sources_recommend LLM call failed: %s", e)
        msg = str(e)
        if "timeout" in msg.lower() or "timed out" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Таймаут при обращении к LLM. Попробуйте позже.",
            ) from e
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Ошибка при обращении к LLM. Проверьте настройки провайдера.",
        ) from e

    raw_text = (response.text or "").strip()
    if not raw_text:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM вернул пустой ответ для sources.recommend",
        )

    try:
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            raw_text = "\n".join(
                line for line in lines if line.strip() and not line.strip().startswith("```")
            )
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        snippet = raw_text[:DETAIL_TRUNCATE] + ("..." if len(raw_text) > DETAIL_TRUNCATE else "")
        logger.warning("sources_recommend invalid JSON: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM вернул невалидный JSON. {e!s}. Ответ (начало): {snippet!r}",
        ) from e

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Ожидался JSON-объект с полем sites (массив).",
        )

    sites_raw = data.get("sites")
    if not isinstance(sites_raw, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="В ответе LLM отсутствует поле sites (массив).",
        )

    result: list[RecommendedSiteItem] = []
    seen_domains: set[str] = set()
    for item in sites_raw:
        if not isinstance(item, dict):
            continue
        domain_val = item.get("domain")
        if not domain_val or not str(domain_val).strip():
            continue
        domain_norm = normalize_domain(str(domain_val).strip())
        if not domain_norm or domain_norm in seen_domains:
            continue
        seen_domains.add(domain_norm)
        display_name = item.get("display_name")
        if display_name is not None:
            display_name = str(display_name).strip() or None
        reason = item.get("reason")
        if reason is not None:
            reason = str(reason).strip() or None
        result.append(
            RecommendedSiteItem(
                domain=domain_norm,
                display_name=display_name,
                reason=reason,
            )
        )

    llm_meta = SourcesRecommendLLMMeta(
        provider=response.provider,
        model=response.model,
        usage=response.usage.model_dump(mode="json"),
        cost=response.cost.model_dump(mode="json"),
        warnings=response.warnings or [],
    )
    logger.info(
        "sources_recommend ok task=sources_recommend provider=%s usage_source=%s total_cost=%s",
        response.provider,
        response.usage.source,
        response.cost.total_cost,
    )
    return SourcesRecommendResponse(result=result, llm=llm_meta)


@router.get("/{theme_id}/sites", response_model=list[ThemeSiteOut])
async def list_theme_sites_endpoint(
    theme_id: str,
    mode: str | None = Query(None, description="Фильтр по режиму"),
    status_filter: str | None = Query(None, alias="status", description="Фильтр по статусу"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ThemeSiteOut]:
    """Список сайтов темы с effective_* полями (sites + user_sites)."""
    try:
        tid = uuid.UUID(theme_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат theme_id (ожидается UUID)",
        )
    await _ensure_theme_access(db, tid, current_user.id)

    rows = await list_theme_sites(
        db, tid, user_id=current_user.id, status=status_filter, mode=mode
    )
    return [_theme_site_row_to_out(r) for r in rows]


@router.post("/{theme_id}/sites", response_model=ThemeSiteOut, status_code=status.HTTP_201_CREATED)
async def create_theme_site_endpoint(
    theme_id: str,
    body: ThemeSiteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ThemeSiteOut:
    """Добавить сайт к теме. Создаёт Site, upsert UserSite, upsert ThemeSite."""
    try:
        tid = uuid.UUID(theme_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат theme_id (ожидается UUID)",
        )
    await _ensure_theme_access(db, tid, current_user.id)

    domain_norm = normalize_domain(body.domain)
    if not domain_norm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректный домен или URL",
        )

    user_site_data = {}
    if body.description is not None:
        user_site_data["description"] = body.description
    if body.display_name is not None:
        user_site_data["display_name"] = body.display_name
    if body.homepage_url is not None:
        user_site_data["homepage_url"] = body.homepage_url
    if body.trust_score is not None:
        user_site_data["trust_score"] = body.trust_score
    if body.quality_tier is not None:
        user_site_data["quality_tier"] = body.quality_tier

    try:
        theme_site = await create_theme_site(
        session=db,
        theme_id=tid,
        user_id=current_user.id,
        domain=domain_norm,
        mode=body.mode,
        source=body.source,
        status=body.status,
        created_by_user_id=current_user.id,
        confidence=body.confidence,
        reason=body.reason,
        user_site_data=user_site_data or None,
    )
    except ThemeSiteAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Источник уже добавлен в тему",
        ) from None

    _, site_out = await get_theme_site(db, tid, theme_site.site_id, user_id=current_user.id)
    return ThemeSiteOut(
        id=str(theme_site.id),
        theme_id=str(theme_site.theme_id),
        site_id=str(theme_site.site_id),
        mode=theme_site.mode,
        source=theme_site.source,
        status=theme_site.status,
        confidence=theme_site.confidence,
        reason=theme_site.reason,
        created_by_user_id=str(theme_site.created_by_user_id) if theme_site.created_by_user_id else None,
        site=SiteOut(**site_out),
    )


@router.patch("/{theme_id}/sites/{site_id}", response_model=ThemeSiteOut)
async def update_theme_site_endpoint(
    theme_id: str,
    site_id: str,
    body: ThemeSiteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ThemeSiteOut:
    """Обновить связь тема-сайт и/или UserSite."""
    try:
        tid = uuid.UUID(theme_id)
        sid = uuid.UUID(site_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат UUID",
        )
    await _ensure_theme_access(db, tid, current_user.id)

    theme_site, site_out = await get_theme_site(db, tid, sid, user_id=current_user.id)
    if not theme_site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сайт не найден в теме",
        )

    payload = body.model_dump(exclude_unset=True)
    theme_site_fields = {"mode", "status", "confidence", "reason"}
    user_site_fields = {"description", "display_name", "homepage_url", "trust_score", "quality_tier"}

    for k in theme_site_fields:
        if k in payload:
            setattr(theme_site, k, payload[k])

    user_site_updates = {k: payload[k] for k in user_site_fields if k in payload}
    if user_site_updates:
        await upsert_user_site(
            session=db,
            user_id=current_user.id,
            site_id=sid,
            **user_site_updates,
        )
        _, site_out = await get_theme_site(db, tid, sid, user_id=current_user.id)

    await db.flush()
    await db.refresh(theme_site)

    return ThemeSiteOut(
        id=str(theme_site.id),
        theme_id=str(theme_site.theme_id),
        site_id=str(theme_site.site_id),
        mode=theme_site.mode,
        source=theme_site.source,
        status=theme_site.status,
        confidence=theme_site.confidence,
        reason=theme_site.reason,
        created_by_user_id=str(theme_site.created_by_user_id) if theme_site.created_by_user_id else None,
        site=SiteOut(**site_out),
    )


@router.delete("/{theme_id}/sites/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_theme_site_endpoint(
    theme_id: str,
    site_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Мягкое удаление: переводит site в статус muted вместо удаления."""
    try:
        tid = uuid.UUID(theme_id)
        sid = uuid.UUID(site_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат UUID",
        )
    await _ensure_theme_access(db, tid, current_user.id)

    theme_site = await mute_theme_site(db, tid, sid)
    if not theme_site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сайт не найден в теме",
        )
