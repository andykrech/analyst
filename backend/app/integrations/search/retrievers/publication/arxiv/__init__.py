"""Адаптер поиска публикаций через arXiv API."""

from app.integrations.search.retrievers.publication.arxiv.adapter import (
    ArxivPublicationAdapter,
)

__all__ = ["ArxivPublicationAdapter"]
