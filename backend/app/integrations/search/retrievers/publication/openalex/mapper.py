"""
Маппинг OpenAlex Work -> InfoQuantum (QuantumCreate).
Восстановление abstract из abstract_inverted_index.
"""
from datetime import datetime
from typing import Any

from app.modules.quanta.schemas import QuantumCreate, QuantumIdentifier
from app.integrations.search.retrievers.publication.schemas_publication_attrs import (
    PublicationAccess,
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


def _inverted_index_to_text(inverted: dict[str, list[int]] | None) -> str:
    """Восстановить текст из abstract_inverted_index (word -> positions)."""
    if not inverted or not isinstance(inverted, dict):
        return ""
    pairs: list[tuple[int, str]] = []
    for word, positions in inverted.items():
        for pos in positions:
            pairs.append((pos, word))
    pairs.sort(key=lambda x: x[0])
    return " ".join(w for _, w in pairs)


def _parse_date(value: Any) -> datetime | None:
    """publication_date (YYYY-MM-DD) или publication_year -> datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            pass
    if isinstance(value, int):
        try:
            return datetime(value, 1, 1)
        except Exception:
            pass
    return None


def _build_venue(work: dict[str, Any]) -> PublicationVenue | None:
    """primary_location.source или host_venue -> PublicationVenue."""
    pl = work.get("primary_location") or {}
    source = pl.get("source") if isinstance(pl, dict) else None
    if not source or not isinstance(source, dict):
        return None
    return PublicationVenue(
        id=source.get("id"),
        display_name=source.get("display_name"),
        issn_l=source.get("issn_l"),
        issn=source.get("issn") if isinstance(source.get("issn"), list) else None,
        type=source.get("type"),
    )


def _build_biblio(work: dict[str, Any]) -> PublicationBiblio | None:
    b = work.get("biblio")
    if not b or not isinstance(b, dict):
        return None
    return PublicationBiblio(
        volume=b.get("volume"),
        issue=b.get("issue"),
        first_page=b.get("first_page"),
        last_page=b.get("last_page"),
    )


def _build_contributors(work: dict[str, Any]) -> list[PublicationContributors]:
    from app.integrations.search.retrievers.publication.schemas_publication_attrs import (
        PublicationAffiliation,
        PublicationAuthor,
    )

    out: list[PublicationContributors] = []
    for a in work.get("authorships") or []:
        if not isinstance(a, dict):
            continue
        author = a.get("author")
        author_obj = None
        if isinstance(author, dict):
            author_obj = PublicationAuthor(
                id=author.get("id"),
                display_name=author.get("display_name"),
                orcid=author.get("orcid"),
            )
        inst_list = []
        for inst in a.get("institutions") or []:
            if isinstance(inst, dict):
                inst_list.append(
                    PublicationAffiliation(
                        id=inst.get("id"),
                        display_name=inst.get("display_name"),
                        ror=inst.get("ror"),
                        country_code=inst.get("country_code"),
                        type=inst.get("type"),
                    )
                )
        out.append(
            PublicationContributors(
                author=author_obj,
                author_position=a.get("author_position"),
                institutions=inst_list,
            )
        )
    return out


def _build_access(work: dict[str, Any]) -> PublicationAccess | None:
    oa = work.get("open_access")
    if not oa or not isinstance(oa, dict):
        return None
    return PublicationAccess(
        is_oa=oa.get("is_oa"),
        oa_status=oa.get("oa_status"),
        oa_url=oa.get("oa_url"),
        any_repository_has_fulltext=oa.get("any_repository_has_fulltext"),
    )


def _build_classification(work: dict[str, Any]) -> PublicationClassification | None:
    topics_raw = work.get("concepts") or work.get("topics") or []
    topics: list[PublicationTopic] = []
    for t in topics_raw:
        if isinstance(t, dict):
            topics.append(
                PublicationTopic(
                    id=t.get("id"),
                    display_name=t.get("display_name"),
                    score=t.get("score"),
                    level=t.get("level"),
                )
            )
    if not topics:
        return None
    return PublicationClassification(topics=topics)


def map_openalex_work_to_quantum(
    work_json: dict[str, Any],
    compiled_query_string: str,
    language: str,
    *,
    theme_id: str,
    run_id: str | None = None,
    require_abstract: bool = True,
) -> QuantumCreate | None:
    """
    Преобразует один Work из OpenAlex в QuantumCreate.

    - abstract восстанавливается из abstract_inverted_index.
    - Если abstract пустой и require_abstract=True -> None.
    - entity_kind="publication", source_system="openalex", retriever_query=compiled_query_string.
    - attrs.publication заполняется через PublicationAttrs.model_validate перед dump.
    """
    title = (work_json.get("display_name") or "").strip()
    if not title:
        return None

    abstract = _inverted_index_to_text(work_json.get("abstract_inverted_index"))
    if require_abstract and not abstract:
        return None

    summary_text = abstract or title

    date_at = _parse_date(work_json.get("publication_date")) or _parse_date(
        work_json.get("publication_year")
    )

    doi = work_json.get("doi")
    oa_id = work_json.get("id")
    verification_url = ""
    if doi:
        verification_url = doi if doi.startswith("http") else f"https://doi.org/{doi}"
    elif oa_id:
        verification_url = str(oa_id)
    if not verification_url:
        return None

    identifiers: list[QuantumIdentifier] = []
    if doi:
        identifiers.append(
            QuantumIdentifier(scheme="doi", value=doi.replace("https://doi.org/", ""), is_primary=True)
        )
    if oa_id:
        identifiers.append(
            QuantumIdentifier(scheme="openalex", value=str(oa_id), is_primary=False)
        )

    venue = _build_venue(work_json)
    biblio = _build_biblio(work_json)
    contributors = _build_contributors(work_json)
    access = _build_access(work_json)
    cited_by_count = work_json.get("cited_by_count")
    metrics = (
        PublicationMetrics(cited_by_count=cited_by_count, fwci=work_json.get("fwci"))
        if cited_by_count is not None or work_json.get("fwci") is not None
        else None
    )
    classification = _build_classification(work_json)
    source_extras = PublicationSourceExtras(
        openalex={"id": oa_id} if oa_id else None
    )
    attrs_obj = PublicationAttrs(
        work_type=work_json.get("type"),
        venue=venue,
        biblio=biblio,
        contributors=contributors,
        access=access,
        metrics=metrics,
        classification=classification,
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
        language=language or work_json.get("language"),
        date_at=date_at,
        verification_url=verification_url,
        canonical_url=doi if doi else None,
        identifiers=identifiers,
        matched_terms=[],
        matched_term_ids=[],
        retriever_query=compiled_query_string,
        rank_score=float(work_json["cited_by_count"]) if isinstance(work_json.get("cited_by_count"), (int, float)) else None,
        source_system="openalex",
        retriever_name="openalex",
        retriever_version=None,
        attrs={"publication": attrs_dict},
    )
