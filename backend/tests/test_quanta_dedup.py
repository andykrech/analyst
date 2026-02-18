import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects import postgresql

from app.modules.quanta.crud import build_dedup_key, build_fingerprint, build_upsert_stmt


def test_build_dedup_key_prefers_doi() -> None:
    fp = "x" * 64
    key = build_dedup_key(
        identifiers=[
            {"scheme": "doi", "value": "10.1000/xyz123", "is_primary": True},
            {"scheme": "patent_number", "value": "US-123"},
        ],
        canonical_url="https://example.com/a",
        fingerprint=fp,
    )
    assert key == "doi:10.1000/xyz123"


def test_build_dedup_key_falls_back_to_patent_then_url_then_fp() -> None:
    fp = "f" * 64

    key_patent = build_dedup_key(
        identifiers=[{"scheme": "patent_number", "value": "EP-0001"}],
        canonical_url="https://example.com/a",
        fingerprint=fp,
    )
    assert key_patent == "patent:EP-0001"

    key_url = build_dedup_key(
        identifiers=[],
        canonical_url="https://example.com/a",
        fingerprint=fp,
    )
    assert key_url == "url:https://example.com/a"

    key_fp = build_dedup_key(
        identifiers=[],
        canonical_url=None,
        fingerprint=fp,
    )
    assert key_fp == f"fp:{fp}"


def test_build_fingerprint_normalizes_title_and_buckets_date() -> None:
    d = datetime(2025, 2, 17, 12, 0, tzinfo=timezone.utc)
    fp1 = build_fingerprint(
        entity_kind="publication",
        title="  Hello   WORLD  ",
        date_at=d,
        source_system="OpenAlex",
    )
    fp2 = build_fingerprint(
        entity_kind="publication",
        title="hello world",
        date_at=datetime(2025, 2, 1, 0, 0, tzinfo=timezone.utc),
        source_system="openalex",
    )
    assert fp1 == fp2
    assert len(fp1) == 64


def test_upsert_stmt_uses_unique_theme_id_dedup_key_on_conflict() -> None:
    values = {
        "theme_id": uuid.uuid4(),
        "run_id": None,
        "entity_kind": "webpage",
        "title": "t",
        "summary_text": "s",
        "key_points": [],
        "language": None,
        "date_at": None,
        "verification_url": "https://example.com",
        "canonical_url": None,
        "dedup_key": "url:https://example.com",
        "fingerprint": "f" * 64,
        "identifiers": [],
        "matched_terms": [],
        "matched_term_ids": [],
        "retriever_query": None,
        "rank_score": None,
        "source_system": "web",
        "site_id": None,
        "retriever_name": "retriever",
        "retriever_version": None,
        "attrs": {},
        "raw_payload_ref": None,
        "content_ref": None,
    }
    stmt = build_upsert_stmt(values=values)
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT" in sql
    assert "theme_id" in sql and "dedup_key" in sql

