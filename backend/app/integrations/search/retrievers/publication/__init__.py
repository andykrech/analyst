"""
Publication retrievers: адаптеры к источникам научных публикаций
(OpenAlex, Semantic Scholar, arXiv, PubMed и т.д.).

PublicationRetriever — оркестратор (RetrieverPort).
"""

from app.integrations.search.retrievers.publication.arxiv.adapter import (
    ArxivPublicationAdapter,
)
from app.integrations.search.retrievers.publication.openalex.adapter import (
    OpenAlexPublicationAdapter,
)
from app.integrations.search.retrievers.publication.pubmed.adapter import (
    PubMedPublicationAdapter,
)
from app.integrations.search.retrievers.publication.retriever import (
    PublicationRetriever,
)

__all__ = [
    "ArxivPublicationAdapter",
    "OpenAlexPublicationAdapter",
    "PubMedPublicationAdapter",
    "PublicationRetriever",
]
