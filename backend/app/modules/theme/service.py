"""Сервис тем: сохранение темы и поисковых запросов, загрузка по id."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.theme.model import Theme, ThemeSearchQuery
from app.modules.theme.schemas import (
    TermIn,
    ThemeCreateRequest,
    ThemePatchRequest,
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


async def create_theme_minimal(
    session: AsyncSession,
    user_id: uuid.UUID,
    payload: ThemeCreateRequest,
) -> Theme:
    """Создать тему с минимальным набором: title, description, languages. Остальное — null."""
    theme = Theme(
        user_id=user_id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        keywords=None,
        must_have=None,
        exclude=None,
        languages=payload.languages,
    )
    session.add(theme)
    await session.flush()
    return theme


def _apply_terms_delta(current_list: list | None, add_or_update: list[TermIn], delete_ids: list[str]) -> list[dict]:
    """Применить дельту к списку терминов: merge add_or_update по id, убрать delete_ids."""
    by_id: dict[str, dict] = {}
    for t in current_list or []:
        if isinstance(t, dict) and t.get("id"):
            by_id[str(t["id"])] = t
    for t in add_or_update:
        by_id[t.id] = _term_to_json(t)
    for tid in delete_ids:
        by_id.pop(tid, None)
    return list(by_id.values())


async def patch_theme(
    session: AsyncSession,
    theme_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: ThemePatchRequest,
) -> Theme | None:
    """Частично обновить тему. Передаются только изменённые поля."""
    theme, _ = await get_theme_with_queries(session, theme_id, user_id)
    if not theme:
        return None

    if payload.title is not None:
        theme.title = payload.title.strip()
    if payload.description is not None:
        theme.description = payload.description.strip()
    if payload.languages is not None:
        theme.languages = payload.languages

    if payload.keyword_terms is not None:
        theme.keywords = _apply_terms_delta(
            theme.keywords,
            payload.keyword_terms.add_or_update,
            payload.keyword_terms.delete_ids,
        )
    if payload.must_have_terms is not None:
        theme.must_have = _apply_terms_delta(
            theme.must_have,
            payload.must_have_terms.add_or_update,
            payload.must_have_terms.delete_ids,
        )
    if payload.exclude_terms is not None:
        theme.exclude = _apply_terms_delta(
            theme.exclude,
            payload.exclude_terms.add_or_update,
            payload.exclude_terms.delete_ids,
        )

    if payload.search_queries is not None:
        await session.execute(delete(ThemeSearchQuery).where(ThemeSearchQuery.theme_id == theme_id))
        for order_key, qm in payload.search_queries.items():
            try:
                order_index = int(order_key)
            except (ValueError, TypeError):
                continue
            if order_index < 1 or order_index > 3:
                continue
            if qm is None:
                continue
            query_model = qm if isinstance(qm, dict) else getattr(qm, "model_dump", lambda: qm)()
            if not isinstance(query_model, dict):
                continue
            query_row = ThemeSearchQuery(
                id=uuid.uuid4(),
                theme_id=theme.id,
                order_index=order_index,
                title=None,
                query_model=query_model,
                time_window_days=None,
                target_links=None,
                enabled_retrievers=None,
                is_enabled=True,
            )
            session.add(query_row)

    await session.flush()
    return theme


async def get_theme_by_id(
    session: AsyncSession,
    theme_id: uuid.UUID,
) -> Theme | None:
    """Получить тему по id (без проверки владельца). Для внутреннего использования (например, поиск)."""
    result = await session.execute(
        select(Theme).where(
            Theme.id == theme_id,
            Theme.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


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
