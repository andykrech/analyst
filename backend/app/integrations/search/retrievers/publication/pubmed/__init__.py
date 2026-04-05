"""Адаптер поиска публикаций через NCBI PubMed (E-utilities)."""

from app.integrations.search.retrievers.publication.pubmed.adapter import (
    PubMedPublicationAdapter,
)

__all__ = ["PubMedPublicationAdapter"]
