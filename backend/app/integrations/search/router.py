"""
Роутер поиска: POST /api/v1/search/collect.
"""
from fastapi import APIRouter, Depends, Request

from app.core.config import get_settings
from app.integrations.search.schemas import LinkCollectResult, SearchQuery
from app.integrations.search.service import SearchService

router = APIRouter(prefix="/api/v1/search", tags=["search"])


def get_search_service(request: Request) -> SearchService:
    """Возвращает SearchService из app.state (инициализируется при старте)."""
    return request.app.state.search_service


@router.post("/collect", response_model=LinkCollectResult)
async def collect_links(
    body: SearchQuery,
    search_service: SearchService = Depends(get_search_service),
) -> LinkCollectResult:
    """
    Собрать релевантные ссылки по поисковому запросу.

    Использует target_links из запроса, если задан; иначе — настройки по умолчанию.
    """
    return await search_service.collect_links(
        query=body,
        mode="discovery",
        request_id=None,
    )
