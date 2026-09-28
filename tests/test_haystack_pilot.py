"""The optional retriever must preserve the KB evidence gates."""

import json
import sqlite3

import pytest

pytest.importorskip("haystack")

from test_filtered_retrieval import _cutoff, _setup_filings
from test_metric_store import _setup, _source, _write
from src.kb_runtime.identity_store import register_identity
from src.kb_runtime.haystack_pilot import search_haystack_pilot
from src.kb_runtime.metric_store import register_filing
from src.kb_runtime.source_store import record_source
from src.kb_runtime.text_chunks import extract_text_filing


def test_filters_citations_and_stable_top_k(tmp_path):
    project, catalog = _setup_filings(tmp_path)
    cutoff = _cutoff()
    found = search_haystack_pilot(catalog, project, "SBI", "demand", cutoff)
    assert {row["filing_id"] for row in found} == {"TEXT1", "PDF1"}
    assert all(row["issuer_id"] == "SBI" and row["publication_allowed"] is False for row in found)
    assert all(row["chunk_id"] and row["raw_sha256"] and row["version_id"] for row in found)
    assert {row["offset_basis"] for row in found} == {"RAW_UTF8", "DERIVED_PAGE_UTF8"}
    assert search_haystack_pilot(catalog, project, "SBI", "demand", cutoff, limit=1) == found[:1]
    assert search_haystack_pilot(catalog, project, "SBI", "demand", cutoff) == found
    assert {r["filing_id"] for r in search_haystack_pilot(catalog, project, "SBI", "demand", cutoff,
                   isin="INE062A01020", document_types=["CONCALL_TRANSCRIPT"], speaker_role="UNKNOWN")} == {"TEXT1", "PDF1"}
    assert search_haystack_pilot(catalog, project, "SBI", "demand", cutoff,
                                  speaker_role="MANAGEMENT") == []
    assert search_haystack_pilot(catalog, project, "SBI", "absentword", cutoff) == []


def test_cutoff_and_identity_binding(tmp_path):
    project, catalog = _setup_filings(tmp_path)
    assert search_haystack_pilot(catalog, project, "SBI", "demand", "2026-09-28T09:03:00+05:30") == []
    assert search_haystack_pilot(catalog, project, "OTHER", "demand", _cutoff()) == []
    with pytest.raises(ValueError, match="ISIN does not belong"):
        search_haystack_pilot(catalog, project, "OTHER", "demand", _cutoff(), isin="INE062A01020")


def test_revision_cutoff_and_damaged_source(tmp_path):
    project, catalog = _setup_filings(tmp_path)
    (tmp_path / "revision").mkdir()
    _, _, path, request = _setup(tmp_path / "revision")
    source = _source(tmp_path, project, "TEXT2", "Management demand revised\n",
                     "2026-09-28T09:05:00+05:30", "2026-09-28T09:06:00+05:30")
    request.update(filing_id="TEXT2", source_id="TEXT2", version_id=source["version_id"],
                   document_type="CONCALL_TRANSCRIPT", metrics=[], supersedes_filing_id="TEXT1",
                   published_at="2026-09-28T09:05:00+05:30",
                   first_seen_at="2026-09-28T09:06:00+05:30",
                   reviewed_at="2026-09-28T09:07:00+05:30")
    register_filing(_write(path, request), project, catalog)
    extract_text_filing(catalog, project, "TEXT2")
    found = search_haystack_pilot(catalog, project, "SBI", "demand", _cutoff())
    assert {r["filing_id"] for r in found} == {"PDF1", "TEXT2"}
    old = search_haystack_pilot(catalog, project, "SBI", "demand", "2026-09-28T09:04:00+05:30")
    assert {r["filing_id"] for r in old} <= {"PDF1", "TEXT1"}
    source_text = next((project / "data/registry/sources/TEXT2").glob("*.json"))
    raw_hash = json.loads(source_text.read_text())["raw_sha256"]
    (project / "data/raw/sha256" / raw_hash).write_text("damaged")
    with pytest.raises(ValueError, match="source|digest"):
        search_haystack_pilot(catalog, project, "SBI", "demand", _cutoff())


def test_damaged_revision_blocks(tmp_path):
    project, catalog = _setup_filings(tmp_path)
    with sqlite3.connect(catalog) as db:
        db.execute("DROP TRIGGER filings_no_update")
        db.execute("UPDATE filings SET supersedes_filing_id='PDF1' WHERE filing_id='TEXT1'")
    with pytest.raises(ValueError, match="filing revision is invalid"):
        search_haystack_pilot(catalog, project, "SBI", "demand", _cutoff())


def test_unreviewed_rights_block_indexing(tmp_path):
    project, catalog = _setup_filings(tmp_path)
    with sqlite3.connect(catalog) as db:
        db.execute("PRAGMA ignore_check_constraints=ON")
        db.execute("DROP TRIGGER filings_no_update")
        db.execute("UPDATE filings SET rights_status='PENDING' WHERE filing_id='TEXT1'")
    with pytest.raises(ValueError, match="rights or review"):
        search_haystack_pilot(catalog, project, "SBI", "demand", _cutoff())


def test_mixed_issuer_corpus_never_crosses_identity(tmp_path):
    project, catalog = _setup_filings(tmp_path)
    raw = tmp_path / "hdfc-identity.txt"
    raw.write_text("HDFC INE040A01034")
    metadata = {"source_id": "HDFCIDENT", "entity": "HDFC", "source_kind": "EXCHANGE_FILING",
                "url": "https://example.org/hdfc-identity", "source_date": "2026-09-28",
                "observed_at": "2026-09-28T08:00:00+05:30",
                "retrieved_at": "2026-09-28T08:01:00+05:30"}
    source = record_source(_write(tmp_path / "hdfc-metadata.json", metadata), raw, project)
    identity = {"issuer_id": "HDFC", "legal_name": "HDFC Bank", "isin": "INE040A01034",
                "security_type": "EQUITY", "listed_from": "1995-01-01", "listed_to": None,
                "exchange": "NSE", "symbol": "HDFCBANK", "valid_from": "1995-01-01", "valid_to": None,
                "announced_at": "2026-09-28T08:00:00+05:30", "first_seen_at": "2026-09-28T08:01:00+05:30",
                "source_id": "HDFCIDENT", "version_id": source["version_id"], "reviewer_id": "analyst-1",
                "reviewed_at": "2026-09-28T08:02:00+05:30", "review_decision": "CONFIRMED",
                "evidence_locator": "identity row 1"}
    register_identity(_write(tmp_path / "hdfc-identity.json", identity), project, catalog)
    raw = tmp_path / "hdfc-filing.txt"
    raw.write_text("HDFC demand guidance")
    metadata.update(source_id="HDFCTEXT", url="https://example.org/hdfc-filing",
                    observed_at="2026-09-28T09:00:00+05:30",
                    retrieved_at="2026-09-28T09:02:00+05:30")
    filing_source = record_source(_write(tmp_path / "hdfc-filing-source.json", metadata), raw, project)
    (tmp_path / "other").mkdir()
    _, _, path, request = _setup(tmp_path / "other")
    request.update(filing_id="HDFCTEXT", issuer_id="HDFC", isin="INE040A01034",
                   source_id="HDFCTEXT", version_id=filing_source["version_id"],
                   document_type="CONCALL_TRANSCRIPT", metrics=[])
    register_filing(_write(path, request), project, catalog)
    extract_text_filing(catalog, project, "HDFCTEXT")
    assert {r["filing_id"] for r in search_haystack_pilot(catalog, project, "SBI", "demand", _cutoff())} == {"TEXT1", "PDF1"}
    assert {r["filing_id"] for r in search_haystack_pilot(catalog, project, "HDFC", "demand", _cutoff())} == {"HDFCTEXT"}


@pytest.mark.parametrize("query,limit", [("", 5), ("...", 5), ("demand", 0), ("demand", 21)])
def test_invalid_search_input(tmp_path, query, limit):
    project, catalog = _setup_filings(tmp_path)
    with pytest.raises(ValueError):
        search_haystack_pilot(catalog, project, "SBI", query, _cutoff(), limit=limit)
