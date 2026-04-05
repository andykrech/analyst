"""
Маппинг Semantic Scholar FullPaper -> QuantumCreate (publication).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.integrations.search.retrievers.publication.schemas_publication_attrs import (
    PublicationAccess,
    PublicationAffiliation,
    PublicationAuthor,
    PublicationAttrs,
    PublicationBiblio,
    PublicationClassification,
    PublicationContributors,
    PublicationMetrics,
    PublicationRelations,
    PublicationSourceExtras,
    PublicationTopic,
    PublicationVenue,
)
from app.modules.quanta.schemas import QuantumCreate, QuantumIdentifier


def _parse_date(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        # Semantic Scholar обычно отдаёт YYYY-MM-DD
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            pass
        try:
            # fallback YYYY-MM-DD without tz
            return datetime.strptime(s, "%Y-%m-%d")
        except Exception:
            return None
    if isinstance(value, int):
        try:
            return datetime(value, 1, 1)
        except Exception:
            return None
    return None


def _extract_doi(external_ids: Any) -> str | None:
    if not external_ids or not isinstance(external_ids, dict):
        return None
    for key in ("DOI", "doi"):
        v = external_ids.get(key)
        if isinstance(v, str) and v.strip():
            doi = v.strip()
            return doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    return None


def map_semanticscholar_paper_to_quantum(
    paper: dict[str, Any],
    compiled_query_string: str,
    language: str,
    *,
    theme_id: str,
    run_id: str | None,
    require_abstract: bool,
    retriever_name: str,
) -> QuantumCreate | None:
    title = (paper.get("title") or "").strip()
    if not title:
        return None

    abstract = (paper.get("abstract") or "").strip()
    if require_abstract and not abstract:
        return None

    summary_text = abstract or title

    paper_id = paper.get("paperId")
    paper_id = str(paper_id).strip() if paper_id is not None else ""
    external_ids = paper.get("externalIds") if isinstance(paper.get("externalIds"), dict) else None
    doi = _extract_doi(external_ids)

    verification_url = ""
    if doi:
        verification_url = f"https://doi.org/{doi}"
    else:
        url = (paper.get("url") or "").strip()
        if url:
            verification_url = url
        elif paper_id:
            verification_url = f"https://www.semanticscholar.org/paper/{paper_id}"
    if not verification_url:
        return None

    identifiers: list[QuantumIdentifier] = []
    if doi:
        identifiers.append(QuantumIdentifier(scheme="doi", value=doi, is_primary=True))
    if paper_id:
        identifiers.append(QuantumIdentifier(scheme="semanticscholar", value=paper_id, is_primary=False))

    # date_at: publicationDate -> year
    date_at = _parse_date(paper.get("publicationDate")) or _parse_date(paper.get("year"))

    # contributors
    contributors: list[PublicationContributors] = []
    authors = paper.get("authors") or []
    if isinstance(authors, list):
        for a in authors:
            if not isinstance(a, dict):
                continue
            author = PublicationAuthor(
                id=str(a.get("authorId")).strip() if a.get("authorId") is not None else None,
                display_name=(a.get("name") or "").strip() or None,
                orcid=(a.get("orcid") or "").strip() or None,
            )
            insts: list[PublicationAffiliation] = []
            aff = a.get("affiliations")
            if isinstance(aff, list):
                for x in aff:
                    if isinstance(x, str) and x.strip():
                        insts.append(PublicationAffiliation(display_name=x.strip()))
            contributors.append(
                PublicationContributors(
                    author=author,
                    author_position=None,
                    institutions=insts,
                )
            )

    # venue
    venue_name = None
    pv = paper.get("publicationVenue")
    if isinstance(pv, dict):
        venue_name = (pv.get("name") or "").strip() or None
    if not venue_name:
        j = paper.get("journal")
        if isinstance(j, dict):
            venue_name = (j.get("name") or "").strip() or None
    if not venue_name:
        venue_name = (paper.get("venue") or "").strip() or None

    venue_obj = PublicationVenue(display_name=venue_name) if venue_name else None

    # access
    is_oa = paper.get("isOpenAccess")
    open_access_pdf = paper.get("openAccessPdf")
    oa_url = None
    if isinstance(open_access_pdf, dict):
        u = open_access_pdf.get("url")
        oa_url = u.strip() if isinstance(u, str) and u.strip() else None
    access_obj = (
        PublicationAccess(
            is_oa=bool(is_oa) if isinstance(is_oa, bool) else None,
            oa_status="open" if is_oa is True else None,
            oa_url=oa_url,
            any_repository_has_fulltext=True if oa_url else None,
        )
        if is_oa is not None or oa_url is not None
        else None
    )

    # metrics
    citation_count = paper.get("citationCount")
    metrics_obj = (
        PublicationMetrics(
            cited_by_count=int(citation_count) if isinstance(citation_count, int) else None,
            fwci=None,
        )
        if citation_count is not None
        else None
    )

    # classification
    topics: list[PublicationTopic] = []
    fos = paper.get("fieldsOfStudy")
    if isinstance(fos, list):
        for x in fos:
            if isinstance(x, str) and x.strip():
                topics.append(PublicationTopic(display_name=x.strip()))
    classification_obj = PublicationClassification(topics=topics) if topics else None

    # source extras (универсально)
    source_ids: dict[str, Any] = {"semantic_scholar": {}}
    if paper_id:
        source_ids["semantic_scholar"]["paperId"] = paper_id
    corpus_id = paper.get("corpusId")
    if corpus_id is not None:
        source_ids["semantic_scholar"]["corpusId"] = corpus_id
    if external_ids:
        source_ids["semantic_scholar"]["externalIds"] = external_ids
    pub_types = paper.get("publicationTypes")
    if pub_types is not None:
        source_ids["semantic_scholar"]["publicationTypes"] = pub_types
    source_extras = PublicationSourceExtras(source_ids=source_ids)

    attrs_obj = PublicationAttrs(
        work_type=(paper.get("publicationTypes")[0] if isinstance(paper.get("publicationTypes"), list) and paper.get("publicationTypes") else None),
        venue=venue_obj,
        biblio=PublicationBiblio(),
        contributors=contributors,
        access=access_obj,
        metrics=metrics_obj,
        classification=classification_obj,
        relations=PublicationRelations(),
        source_extras=source_extras,
    )
    attrs_dict = attrs_obj.model_dump(mode="json")

    return QuantumCreate(
        theme_id=theme_id,
        run_id=run_id,
        entity_kind="publication",
        title=title,
        summary_text=summary_text,
        key_points=[],
        language=language,
        date_at=date_at,
        verification_url=verification_url,
        canonical_url=f"https://doi.org/{doi}" if doi else None,
        dedup_key=None,
        fingerprint=None,
        identifiers=identifiers,
        matched_terms=[],
        matched_term_ids=[],
        retriever_query=compiled_query_string,
        rank_score=None,
        opinion_score=None,
        total_score=None,
        source_system="semantic_scholar",
        site_id=None,
        retriever_name=retriever_name,
        retriever_version=None,
        attrs={"publication": attrs_dict},
        raw_payload_ref=None,
        content_ref=None,
    )

