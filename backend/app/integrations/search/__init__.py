"""
Интеграция поиска: SearchService, retriever'ы, единая точка входа collect_links.
"""
from app.integrations.search.schemas import (
    LinkCandidate,
    LinkCollectResult,
    SearchPlan,
    SearchQuery,
)
from app.integrations.search.service import SearchService

__all__ = [
    "SearchService",
    "SearchQuery",
    "LinkCollectResult",
    "LinkCandidate",
    "SearchPlan",
]
