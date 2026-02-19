"""
Интеграция поиска: SearchService, retriever'ы, единая точка входа collect_links / collect_links_for_theme.
Результат — кванты (QuantumCollectResult).
"""
from app.integrations.search.schemas import (
    LinkCandidate,
    LinkCollectResult,
    QuantumCollectResult,
    SearchPlan,
    SearchQuery,
)
from app.integrations.search.service import SearchService

__all__ = [
    "SearchService",
    "SearchQuery",
    "LinkCollectResult",
    "QuantumCollectResult",
    "LinkCandidate",
    "SearchPlan",
]
