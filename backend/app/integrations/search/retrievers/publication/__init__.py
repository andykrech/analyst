"""
Publication retrievers: адаптеры к источникам научных публикаций (OpenAlex, Crossref, Lens и т.д.).

PublicationRetriever — оркестратор (RetrieverPort), вызывает OpenAlex-адаптер.
"""

from app.integrations.search.retrievers.publication.openalex.adapter import (
    OpenAlexPublicationAdapter,
)
from app.integrations.search.retrievers.publication.retriever import (
    PublicationRetriever,
)

__all__ = ["OpenAlexPublicationAdapter", "PublicationRetriever"]
