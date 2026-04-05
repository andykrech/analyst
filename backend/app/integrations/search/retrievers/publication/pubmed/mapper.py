"""
Парсинг XML efetch (PubmedArticleSet) и маппинг в QuantumCreate (publication).
"""
from __future__ import annotations

import calendar
import logging
import re
import xml.etree.ElementTree as ET
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

logger = logging.getLogger(__name__)


def _local_tag(tag: str) -> str:
    if not tag:
        return ""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find(parent: ET.Element | None, name: str) -> ET.Element | None:
    if parent is None:
        return None
    for c in parent:
        if _local_tag(c.tag) == name:
            return c
    return None


def _findall(parent: ET.Element | None, name: str) -> list[ET.Element]:
    if parent is None:
        return []
    return [c for c in parent if _local_tag(c.tag) == name]


def _findall_recursive(parent: ET.Element | None, name: str) -> list[ET.Element]:
    if parent is None:
        return []
    out: list[ET.Element] = []
    for el in parent.iter():
        if _local_tag(el.tag) == name:
            out.append(el)
    return out


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


def _month_to_num(m: str) -> int | None:
    if not m:
        return None
    if m.isdigit():
        v = int(m)
        return v if 1 <= v <= 12 else None
    m = m.strip()[:3].lower()
    for i, name in enumerate(calendar.month_abbr):
        if i > 0 and name.lower().startswith(m):
            return i
    return None


def _parse_pub_date(pub_date_el: ET.Element | None) -> datetime | None:
    if pub_date_el is None:
        return None
    year_s = _text(_find(pub_date_el, "Year"))
    month_s = _text(_find(pub_date_el, "Month"))
    day_s = _text(_find(pub_date_el, "Day"))
    if not year_s or not year_s.isdigit():
        return None
    year = int(year_s)
    month = _month_to_num(month_s) if month_s else 1
    if month is None:
        month = 1
    day = int(day_s) if day_s and day_s.isdigit() else 1
    try:
        return datetime(year, month, day)
    except ValueError:
        try:
            return datetime(year, month, 1)
        except ValueError:
            return None


def _abstract_texts(article_el: ET.Element) -> str:
    ab = _find(article_el, "Abstract")
    if ab is None:
        return ""
    chunks: list[str] = []
    for node in _findall(ab, "AbstractText"):
        label = (node.get("Label") or "").strip()
        tx = _text(node)
        if not tx:
            continue
        if label:
            chunks.append(f"{label}: {tx}")
        else:
            chunks.append(tx)
    return "\n\n".join(chunks).strip()


def _extract_doi(article_el: ET.Element) -> str | None:
    for aid in _findall_recursive(article_el, "ArticleId"):
        if (aid.get("IdType") or "").lower() == "doi":
            d = _text(aid)
            if d:
                return d.replace("https://doi.org/", "").replace("http://doi.org/", "")
    for eloc in _findall(article_el, "ELocationID"):
        if (eloc.get("EIdType") or "").lower() == "doi":
            d = _text(eloc)
            if d:
                return d.replace("https://doi.org/", "").replace("http://doi.org/", "")
    return None


def map_pubmed_article_to_quantum(
    medline_el: ET.Element,
    compiled_term: str,
    language: str,
    *,
    theme_id: str,
    run_id: str | None,
    require_abstract: bool,
    retriever_name: str,
) -> QuantumCreate | None:
    pmid_el = _find(medline_el, "PMID")
    pmid = _text(pmid_el)
    if not pmid or not re.fullmatch(r"\d+", pmid):
        return None

    article_el = _find(medline_el, "Article")
    if article_el is None:
        return None

    title = _text(_find(article_el, "ArticleTitle"))
    if not title:
        return None

    abstract = _abstract_texts(article_el)
    if require_abstract and not abstract.strip():
        return None

    summary_text = abstract.strip() or title
    doi = _extract_doi(article_el)

    ji = _find(_find(article_el, "Journal"), "JournalIssue")
    pub_date = _find(ji, "PubDate") if ji is not None else None
    date_at = _parse_pub_date(pub_date)
    if date_at is None:
        ad = _find(article_el, "ArticleDate")
        if ad is not None and (ad.get("DateType") or "") == "Electronic":
            date_at = _parse_pub_date(ad)

    verification_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    if doi:
        verification_url = f"https://doi.org/{doi}"

    identifiers: list[QuantumIdentifier] = [
        QuantumIdentifier(scheme="pubmed", value=pmid, is_primary=not bool(doi)),
    ]
    if doi:
        identifiers.insert(0, QuantumIdentifier(scheme="doi", value=doi, is_primary=True))

    contributors: list[PublicationContributors] = []
    al = _find(article_el, "AuthorList")
    if al is not None:
        for auth in _findall(al, "Author"):
            coll = _text(_find(auth, "CollectiveName"))
            if coll:
                name = coll
            else:
                ln = _text(_find(auth, "LastName"))
                fn = _text(_find(auth, "ForeName"))
                initials = _text(_find(auth, "Initials"))
                if fn:
                    name = f"{fn} {ln}".strip() if ln else fn
                elif initials and ln:
                    name = f"{initials} {ln}".strip()
                else:
                    name = ln or initials
            if not name:
                continue
            affs: list[PublicationAffiliation] = []
            for ainfo in _findall(auth, "AffiliationInfo"):
                an = _text(_find(ainfo, "Affiliation"))
                if an:
                    affs.append(PublicationAffiliation(display_name=an))
            contributors.append(
                PublicationContributors(
                    author=PublicationAuthor(display_name=name),
                    author_position=None,
                    institutions=affs,
                )
            )

    journal = _find(article_el, "Journal")
    venue_name = _text(_find(journal, "Title")) if journal is not None else None
    venue_obj = PublicationVenue(display_name=venue_name) if venue_name else None

    issn = None
    if journal is not None:
        issn_el = _find(journal, "ISSN")
        if issn_el is not None:
            issn = _text(issn_el) or None

    volume = issue = None
    if ji is not None:
        volume = _text(_find(ji, "Volume")) or None
        issue = _text(_find(ji, "Issue")) or None

    pmc = None
    for aid in _findall_recursive(article_el, "ArticleId"):
        if (aid.get("IdType") or "").lower() == "pmc":
            pmc = _text(aid)
            break

    topics: list[PublicationTopic] = []
    mhl = _find(medline_el, "MeshHeadingList")
    if mhl is not None:
        for mh in _findall(mhl, "MeshHeading"):
            desc = _find(mh, "DescriptorName")
            if desc is None:
                continue
            dn = _text(desc)
            if dn:
                topics.append(PublicationTopic(display_name=dn))

    classification_obj = PublicationClassification(topics=topics) if topics else None

    source_ids: dict[str, Any] = {"pubmed": {"pmid": pmid}}
    if doi:
        source_ids["pubmed"]["doi"] = doi
    if pmc:
        source_ids["pubmed"]["pmc"] = pmc
    if issn:
        source_ids["pubmed"]["issn"] = issn

    source_extras = PublicationSourceExtras(source_ids=source_ids)

    attrs_obj = PublicationAttrs(
        work_type="journal_article",
        venue=venue_obj,
        biblio=PublicationBiblio(volume=volume, issue=issue),
        contributors=contributors,
        access=PublicationAccess(),
        metrics=PublicationMetrics(),
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
        retriever_query=compiled_term,
        rank_score=None,
        opinion_score=None,
        total_score=None,
        source_system="pubmed",
        site_id=None,
        retriever_name=retriever_name,
        retriever_version=None,
        attrs={"publication": attrs_dict},
        raw_payload_ref=None,
        content_ref=None,
    )


def iter_pubmed_medline_citations(xml_text: str) -> list[ET.Element]:
    if not xml_text or not xml_text.strip():
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning("PubMed XML parse error: %s", e)
        return []
    out: list[ET.Element] = []
    for el in root.iter():
        if _local_tag(el.tag) == "PubmedArticle":
            mc = _find(el, "MedlineCitation")
            if mc is not None:
                out.append(mc)
    return out
