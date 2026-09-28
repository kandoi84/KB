import sqlite3

import pytest

from test_metric_store import _setup, _source, _write
from src.kb_runtime.metric_store import register_filing
from src.kb_runtime.text_chunks import extract_text_filing, query_text_chunks


def _filing(tmp_path, text="नमस्ते SBI\n" * 300):
    project, catalog, path, request = _setup(tmp_path)
    request["document_type"] = "CONCALL_TRANSCRIPT"
    request["metrics"] = []
    source = _source(tmp_path, project, "TRANSCRIPT", text, "2026-09-28T09:00:00+05:30",
                     "2026-09-28T09:02:00+05:30")
    request["source_id"] = "TRANSCRIPT"
    request["version_id"] = source["version_id"]
    register_filing(_write(path, request), project, catalog)
    return project, catalog, request, project / "data/raw/sha256" / source["raw_sha256"]


def test_multibyte_chunks_cover_exact_raw_bytes_and_replay(tmp_path):
    project, catalog, request, raw = _filing(tmp_path)
    first = extract_text_filing(catalog, project, "F1")
    second = extract_text_filing(catalog, project, "F1")
    assert first == second
    rows = query_text_chunks(catalog, project, "F1", "2026-09-28T09:03:00+05:30")
    assert len(rows) > 1
    assert b"".join(row["text"].encode("utf-8") for row in rows) == raw.read_bytes()
    assert all(row["byte_end"] - row["byte_start"] <= 2048 for row in rows)
    assert all(row["speaker_role"] == "UNKNOWN" and row["page_number"] is None for row in rows)
    assert all(row["period_end"] == "2026-06-30" for row in rows)
    assert all(row["publication_allowed"] is False for row in rows)
    assert query_text_chunks(catalog, project, "F1", "2026-09-28T09:02:30+05:30") == []


def test_only_implemented_parser_version_is_allowed_and_missing_chunks_are_rejected(tmp_path):
    project, catalog, _, _ = _filing(tmp_path)
    old = extract_text_filing(catalog, project, "F1", "plain_utf8_v1")
    with pytest.raises(ValueError, match="parser_version"):
        extract_text_filing(catalog, project, "F1", "plain_utf8_v2")
    with sqlite3.connect(catalog) as db:
        db.execute("DROP TRIGGER text_chunks_no_delete")
        db.execute("DELETE FROM text_chunks WHERE chunk_id=?", (old["chunk_ids"][0],))
    with pytest.raises(ValueError, match="chunk|extraction"):
        query_text_chunks(catalog, project, "F1", "2026-09-28T09:03:00+05:30", "plain_utf8_v1")


def test_rejects_tampered_text_and_raw_source(tmp_path):
    project, catalog, _, raw = _filing(tmp_path)
    extract_text_filing(catalog, project, "F1")
    with sqlite3.connect(catalog) as db:
        db.execute("DROP TRIGGER text_chunks_no_update")
        db.execute("UPDATE text_chunks SET text='BAD' WHERE chunk_index=0")
    with pytest.raises(ValueError, match="chunk"):
        query_text_chunks(catalog, project, "F1", "2026-09-28T09:03:00+05:30")
    raw.write_text("tampered")
    with pytest.raises(ValueError, match="source|digest"):
        extract_text_filing(catalog, project, "F1")


def test_append_only_rows_and_receipt_replay_guard(tmp_path):
    project, catalog, _, _ = _filing(tmp_path)
    extract_text_filing(catalog, project, "F1")
    with sqlite3.connect(catalog) as db:
        with pytest.raises(sqlite3.DatabaseError):
            db.execute("UPDATE text_chunks SET byte_start=1 WHERE chunk_index=0")
        with pytest.raises(sqlite3.DatabaseError):
            db.execute("DELETE FROM text_extractions WHERE filing_id='F1'")
        db.execute("DROP TRIGGER text_extractions_no_update")
        db.execute("UPDATE text_extractions SET chunk_count=99 WHERE filing_id='F1'")
    with pytest.raises(ValueError, match="extraction"):
        extract_text_filing(catalog, project, "F1")


def test_rejects_invalid_parser_version(tmp_path):
    project, catalog, _, _ = _filing(tmp_path)
    with pytest.raises(ValueError, match="parser_version"):
        extract_text_filing(catalog, project, "F1", "../../../escape")


@pytest.mark.parametrize("text", ["", " \n\t ", "%PDF-1.7\nabc", " \n%PDF-1.7\nabc", "hello\x00world",
                                  "hello\x01world", "hello\x7fworld", "hello\u0085world",
                                  "x" * (8 * 1024 * 1024 + 1)])
def test_rejects_empty_pdf_binary_or_oversize(tmp_path, text):
    project, catalog, _, _ = _filing(tmp_path, text)
    with pytest.raises(ValueError, match="text|PDF|binary|size"):
        extract_text_filing(catalog, project, "F1")
