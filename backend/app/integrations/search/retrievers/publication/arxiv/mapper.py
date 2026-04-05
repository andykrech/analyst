"""
Парсинг ответа arXiv (Atom) и маппинг entry -> QuantumCreate (publication).
"""

from __future__ import annotations

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

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
OPENSEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"

_ABS_ID_RE = re.compile(r"arxiv\.org/abs/([^/?#]+)", re.I)


def parse_arxiv_atom(xml_text: str) -> tuple[list[dict[str, Any]], int | None]:
    """
    Разобрать Atom-ленту arXiv. Возвращает список словарей (поля entry) и totalResults при наличии.
    """
    if not xml_text or not xml_text.strip():
        return [], None
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning("arXiv Atom parse error: %s", e)
        return [], None

    total: int | None = None
    tr = root.find(f"{OPENSEARCH}totalResults")
    if tr is not None and tr.text and tr.text.strip().isdigit():
        total = int(tr.text.strip())

    entries_out: list[dict[str, Any]] = []
    for entry in root.findall(f"{ATOM}entry"):
        d = _entry_to_dict(entry)
        if d:
            entries_out.append(d)
    return entries_out, total


def _text(el: ET.Element | None) -> str:
    if el is None or el.text is None:
        return ""
    return " ".join((el.text or "").split())


def _entry_to_dict(entry: ET.Element) -> dict[str, Any] | None:
    title = _text(entry.find(f"{ATOM}title"))
    summary = _text(entry.find(f"{ATOM}summary"))
    published = _text(entry.find(f"{ATOM}published"))
    id_url = _text(entry.find(f"{ATOM}id"))

    authors: list[str] = []
    for auth in entry.findall(f"{ATOM}author"):
        n = _text(auth.find(f"{ATOM}name"))
        if n:
            authors.append(n)

    primary_el = entry.find(f"{ARXIV}primary_category")
    primary_category = (primary_el.get("term") or "").strip() if primary_el is not None else ""

    categories: list[str] = []
    for cat in entry.findall(f"{ATOM}category"):
        t = (cat.get("term") or "").strip()
        if t:
            categories.append(t)

    doi_el = entry.find(f"{ARXIV}doi")
    doi = _text(doi_el).strip() or None
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")

    abs_url = ""
    pdf_url = ""
    for link in entry.findall(f"{ATOM}link"):
        href = (link.get("href") or "").strip()
        rel = (link.get("rel") or "").strip()
        typ = (link.get("type") or "").strip()
        if rel == "alternate" and href:
            abs_url = href
        if typ == "application/pdf" and href:
            pdf_url = href

    arxiv_id = ""
    m = _ABS_ID_RE.search(id_url) or _ABS_ID_RE.search(abs_url)
    if m:
        arxiv_id = m.group(1).strip()
    if not arxiv_id and id_url:
        arxiv_id = id_url.rstrip("/").split("/")[-1]

    if not title:
        return None

    return {
        "title": title,
        "summary": summary,
        "published": published,
        "id_url": id_url,
        "arxiv_id": arxiv_id,
        "doi": doi,
        "abs_url": abs_url or (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""),
        "pdf_url": pdf_url,
        "authors": authors,
        "primary_category": primary_category,
        "categories": categories,
    }


def _parse_published(s: str) -> datetime | None:
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt)
        except Exception:
            continue
    return None


def map_arxiv_entry_to_quantum(
    entry: dict[str, Any],
    compiled_query_string: str,
    language: str,
    *,
    theme_id: str,
    run_id: str | None,
    require_abstract: bool,
    retriever_name: str,
) -> QuantumCreate | None:
    title = (entry.get("title") or "").strip()
    if not title:
        return None

    abstract = (entry.get("summary") or "").strip()
    if require_abstract and not abstract:
        return None

    summary_text = abstract or title
    arxiv_id = (entry.get("arxiv_id") or "").strip()
    doi = entry.get("doi")
    doi = doi.strip() if isinstance(doi, str) and doi.strip() else None

    abs_url = (entry.get("abs_url") or "").strip()
    if not abs_url and arxiv_id:
        abs_url = f"https://arxiv.org/abs/{arxiv_id}"
    if not abs_url:
        return None

    verification_url = abs_url
    if doi:
        verification_url = f"https://doi.org/{doi}"

    identifiers: list[QuantumIdentifier] = []
    if doi:
        identifiers.append(QuantumIdentifier(scheme="doi", value=doi, is_primary=True))
    if arxiv_id:
        identifiers.append(
            QuantumIdentifier(scheme="arxiv", value=arxiv_id, is_primary=not bool(doi))
        )

    date_at = _parse_published(str(entry.get("published") or ""))

    contributors: list[PublicationContributors] = []
    for name in entry.get("authors") or []:
        if isinstance(name, str) and name.strip():
            contributors.append(
                PublicationContributors(
                    author=PublicationAuthor(display_name=name.strip()),
                    author_position=None,
                    institutions=[],
                )
            )

    primary = (entry.get("primary_category") or "").strip()
    venue_obj = PublicationVenue(display_name="arXiv")
    work_type = primary or "preprint"

    pdf_url = (entry.get("pdf_url") or "").strip()
    access_obj = PublicationAccess(
        is_oa=True,
        oa_status="open",
        oa_url=pdf_url or abs_url,
        any_repository_has_fulltext=True,
    )

    topics: list[PublicationTopic] = []
    for t in entry.get("categories") or []:
        if isinstance(t, str) and t.strip():
            topics.append(PublicationTopic(id=t.strip(), display_name=t.strip()))
    classification_obj = PublicationClassification(topics=topics) if topics else None

    source_ids: dict[str, Any] = {"arxiv": {}}
    if arxiv_id:
        source_ids["arxiv"]["id"] = arxiv_id
    if doi:
        source_ids["arxiv"]["doi"] = doi
    if primary:
        source_ids["arxiv"]["primary_category"] = primary
    id_url = (entry.get("id_url") or "").strip()
    if id_url:
        source_ids["arxiv"]["atom_id"] = id_url

    source_extras = PublicationSourceExtras(source_ids=source_ids)

    attrs_obj = PublicationAttrs(
        work_type=work_type,
        venue=venue_obj,
        biblio=PublicationBiblio(),
        contributors=contributors,
        access=access_obj,
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
        retriever_query=compiled_query_string,
        rank_score=None,
        opinion_score=None,
        total_score=None,
        source_system="arxiv",
        site_id=None,
        retriever_name=retriever_name,
        retriever_version=None,
        attrs={"publication": attrs_dict},
        raw_payload_ref=None,
        content_ref=None,
    )
