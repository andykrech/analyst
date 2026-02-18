"""Сервис тем: сохранение темы и поисковых запросов, загрузка по id."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.theme.model import Theme, ThemeSearchQuery
from app.modules.theme.schemas import (
    TermIn,
    ThemeSaveRequest,
    ThemeSearchQueryIn,
)


def _term_to_json(t: TermIn) -> dict:
    return {
        "id": t.id,
        "text": t.text,
        "context": t.context,
        "translations": t.translations,
    }


async def create_theme_with_queries(
    session: AsyncSession,
    user_id: uuid.UUID,
    payload: ThemeSaveRequest,
) -> Theme:
    """Создать тему и её поисковые запросы."""
    theme_data = payload.theme
    theme = Theme(
        user_id=user_id,
        title=theme_data.title.strip(),
        description=theme_data.description.strip(),
        keywords=[_term_to_json(t) for t in theme_data.keywords],
        must_have=[_term_to_json(t) for t in theme_data.must_have],
        exclude=[_term_to_json(t) for t in theme_data.exclude],
        languages=theme_data.languages,
        update_interval=theme_data.update_interval,
        status=theme_data.status,
        backfill_status=theme_data.backfill_status,
        backfill_horizon_months=theme_data.backfill_horizon_months,
        region=theme_data.region.strip() if theme_data.region else None,
    )
    session.add(theme)
    await session.flush()

    for q in payload.search_queries:
        query_row = ThemeSearchQuery(
            id=uuid.uuid4(),
            theme_id=theme.id,
            order_index=q.order_index,
            title=q.title.strip() if q.title else None,
            query_model=q.query_model.model_dump(),
            time_window_days=q.time_window_days,
            target_links=q.target_links,
            enabled_retrievers=q.enabled_retrievers,
            is_enabled=q.is_enabled,
        )
        session.add(query_row)

    await session.flush()
    return theme


async def list_themes(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> list[Theme]:
    """Список тем пользователя (без удалённых), по убыванию updated_at."""
    result = await session.execute(
        select(Theme)
        .where(
            Theme.user_id == user_id,
            Theme.deleted_at.is_(None),
        )
        .order_by(Theme.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_theme_with_queries(
    session: AsyncSession,
    theme_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[Theme | None, list[ThemeSearchQuery]]:
    """
    Получить тему и её поисковые запросы по id.
    Тема должна принадлежать пользователю. Запросы возвращаются отсортированными по order_index.
    """
    result = await session.execute(
        select(Theme).where(
            Theme.id == theme_id,
            Theme.user_id == user_id,
            Theme.deleted_at.is_(None),
        )
    )
    theme = result.scalar_one_or_none()
    if not theme:
        return None, []

    q_result = await session.execute(
        select(ThemeSearchQuery)
        .where(ThemeSearchQuery.theme_id == theme_id)
        .order_by(ThemeSearchQuery.order_index)
    )
    queries = list(q_result.scalars().all())
    return theme, queries


async def update_theme_with_queries(
    session: AsyncSession,
    theme_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: ThemeSaveRequest,
) -> Theme | None:
    """Обновить тему и заменить поисковые запросы. Возвращает тему или None, если не найдена/не принадлежит пользователю."""
    result = await session.execute(
        select(Theme).where(
            Theme.id == theme_id,
            Theme.user_id == user_id,
            Theme.deleted_at.is_(None),
        )
    )
    theme = result.scalar_one_or_none()
    if not theme:
        return None

    theme_data = payload.theme
    theme.title = theme_data.title.strip()
    theme.description = theme_data.description.strip()
    theme.keywords = [_term_to_json(t) for t in theme_data.keywords]
    theme.must_have = [_term_to_json(t) for t in theme_data.must_have]
    theme.exclude = [_term_to_json(t) for t in theme_data.exclude]
    theme.languages = theme_data.languages
    theme.update_interval = theme_data.update_interval
    theme.status = theme_data.status
    theme.backfill_status = theme_data.backfill_status
    theme.backfill_horizon_months = theme_data.backfill_horizon_months
    theme.region = theme_data.region.strip() if theme_data.region else None

    await session.execute(delete(ThemeSearchQuery).where(ThemeSearchQuery.theme_id == theme_id))

    for q in payload.search_queries:
        query_row = ThemeSearchQuery(
            id=uuid.uuid4(),
            theme_id=theme.id,
            order_index=q.order_index,
            title=q.title.strip() if q.title else None,
            query_model=q.query_model.model_dump(),
            time_window_days=q.time_window_days,
            target_links=q.target_links,
            enabled_retrievers=q.enabled_retrievers,
            is_enabled=q.is_enabled,
        )
        session.add(query_row)

    await session.flush()
    return theme
