"""
Интеграция эмбеддингов.
Верхний слой — EmbeddingService; провайдеры в providers/ (openai, ...).
"""

from app.integrations.embedding.ports import (
    EmbeddingCost,
    EmbeddingProviderPort,
    EmbeddingResult,
)
from app.integrations.embedding.service import EmbeddingService

__all__ = [
    "EmbeddingCost",
    "EmbeddingProviderPort",
    "EmbeddingResult",
    "EmbeddingService",
]
