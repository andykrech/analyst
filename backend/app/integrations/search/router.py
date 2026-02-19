"""
Роутер поиска: POST /api/v1/search/collect, POST /api/v1/search/collect-by-theme.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.integrations.search.schemas import (
    QuantumCollectResult,
    SearchQuery,
    ThemeSearchCollectRequest,
    TimeSlice,
)
from app.integrations.search.service import SearchService

router = APIRouter(prefix="/api/v1/search", tags=["search"])


def get_search_service(request: Request) -> SearchService:
    """Возвращает SearchService из app.state (инициализируется при старте)."""
    return request.app.state.search_service


@router.post("/collect", response_model=QuantumCollectResult)
async def collect_links(
    body: SearchQuery,
    search_service: SearchService = Depends(get_search_service),
) -> QuantumCollectResult:
    """
    Legacy: собрать релевантные ссылки по поисковому запросу (SearchQuery).
    """
    return await search_service.collect_links(
        query=body,
        mode="discovery",
        request_id=None,
    )


@router.post("/collect-by-theme", response_model=QuantumCollectResult)
async def collect_links_by_theme(
    body: ThemeSearchCollectRequest,
    db: AsyncSession = Depends(get_db),
    search_service: SearchService = Depends(get_search_service),
) -> QuantumCollectResult:
    """
    Собрать ссылки по теме из theme_search_queries.

    Если переданы published_from и published_to — создаётся TimeSlice,
    иначе time_slice = None (без фильтра по дате).
    """
    time_slice = None
    if body.published_from is not None and body.published_to is not None:
        time_slice = TimeSlice(
            published_from=body.published_from,
            published_to=body.published_to,
        )
    return await search_service.collect_links_for_theme(
        session=db,
        theme_id=body.theme_id,
        time_slice=time_slice,
        target_links=body.target_links,
        mode="default",
        request_id=None,
        run_id=body.run_id,
    )
