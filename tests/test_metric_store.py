import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from src.kb_runtime.identity_store import register_identity
from src.kb_runtime.source_store import record_source


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _source(tmp_path, project, source_id, raw_text, observed, retrieved, source_kind="EXCHANGE_FILING"):
    metadata = _write(tmp_path / f"{source_id}-source.json", {
        "source_id": source_id, "entity": "SBI", "source_kind": source_kind,
        "url": f"https://example.org/{source_id}", "source_date": "2026-09-28",
        "observed_at": observed, "retrieved_at": retrieved,
    })
    raw = tmp_path / f"{source_id}.txt"
    raw.write_text(raw_text, encoding="utf-8")
    return record_source(metadata, raw, project)


def _setup(tmp_path):
    project = tmp_path / "project"
    catalog = tmp_path / "catalog.sqlite"
    identity_source = _source(tmp_path, project, "IDENT", "SBI INE062A01020", "2026-09-28T08:00:00+05:30", "2026-09-28T08:01:00+05:30")
    identity = {
        "issuer_id": "SBI", "legal_name": "State Bank of India", "isin": "INE062A01020",
        "security_type": "EQUITY", "listed_from": "1995-01-01", "listed_to": None,
        "exchange": "NSE", "symbol": "SBIN", "valid_from": "1995-01-01", "valid_to": None,
        "announced_at": "2026-09-28T08:00:00+05:30", "first_seen_at": "2026-09-28T08:01:00+05:30",
        "source_id": "IDENT", "version_id": identity_source["version_id"],
        "reviewer_id": "analyst-1", "reviewed_at": "2026-09-28T08:02:00+05:30",
        "review_decision": "CONFIRMED", "evidence_locator": "identity row 1",
    }
    register_identity(_write(tmp_path / "identity.json", identity), project, catalog)
    source = _source(tmp_path, project, "RESULTS1", "Revenue 12.50 crore", "2026-09-28T09:00:00+05:30", "2026-09-28T09:02:00+05:30")
    request = {
        "filing_id": "F1", "issuer_id": "SBI", "isin": "INE062A01020",
        "source_id": "RESULTS1", "version_id": source["version_id"],
        "document_type": "RESULTS", "period_end": "2026-06-30",
        "published_at": "2026-09-28T09:00:00+05:30",
        "first_seen_at": "2026-09-28T09:02:00+05:30",
        "rights_status": "REVIEWED", "reviewer_id": "analyst-1",
        "reviewed_at": "2026-09-28T09:03:00+05:30",
        "review_decision": "CONFIRMED", "evidence_locator": "exchange result row 1",
        "supersedes_filing_id": None,
        "metrics": [{
            "metric_id": "M1", "metric_name": "revenue", "value_decimal": "12.50",
            "unit": "INR_CRORE", "period_end": "2026-06-30",
            "period_kind": "QUARTER", "reporting_scope": "CONSOLIDATED",
            "value_kind": "REPORTED", "evidence_locator": "page 1 table 2",
            "supersedes_metric_id": None,
        }],
    }
    return project, catalog, tmp_path / "filing.json", request


def test_registers_atomic_reviewed_filing_and_metric(tmp_path):
    from src.kb_runtime.metric_store import register_filing_metrics

    project, catalog, path, request = _setup(tmp_path)
    result = register_filing_metrics(_write(path, request), project, catalog)
    assert result == {"filing_id": "F1", "metric_ids": ["M1"], "publication_allowed": False}
    assert register_filing_metrics(path, project, catalog) == result
    with sqlite3.connect(catalog) as db:
        assert db.execute("SELECT count(*) FROM filings").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM metrics").fetchone()[0] == 1
        with pytest.raises(sqlite3.DatabaseError):
            db.execute("UPDATE metrics SET value_decimal='99' WHERE metric_id='M1'")


def test_transcript_filing_can_register_without_metrics(tmp_path):
    from src.kb_runtime.metric_store import register_filing, register_filing_metrics

    project, catalog, path, request = _setup(tmp_path)
    request["document_type"] = "CONCALL_TRANSCRIPT"
    request["metrics"] = []
    with pytest.raises(ValueError, match="metrics"):
        register_filing_metrics(_write(path, request), project, catalog)
    result = register_filing(path, project, catalog)
    assert result == {"filing_id": "F1", "metric_ids": [], "publication_allowed": False}
    assert register_filing(path, project, catalog) == result
    with sqlite3.connect(catalog) as db:
        assert db.execute("SELECT count(*) FROM filings").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM metrics").fetchone()[0] == 0


def test_filing_only_path_rejects_metrics_and_results(tmp_path):
    from src.kb_runtime.metric_store import register_filing

    project, catalog, path, request = _setup(tmp_path)
    with pytest.raises(ValueError, match="metrics"):
        register_filing(_write(path, request), project, catalog)
    request["metrics"] = []
    with pytest.raises(ValueError, match="document_type"):
        register_filing(_write(path, request), project, catalog)


def test_rejects_wrong_issuer_and_damaged_source_without_partial_write(tmp_path):
    from src.kb_runtime.metric_store import register_filing_metrics

    project, catalog, path, request = _setup(tmp_path)
    request["issuer_id"] = "OTHER"
    with pytest.raises(ValueError, match="source|issuer"):
        register_filing_metrics(_write(path, request), project, catalog)
    request["issuer_id"] = "SBI"
    version_path = project / "data/registry/sources/RESULTS1" / f"{request['version_id']}.json"
    raw_hash = json.loads(version_path.read_text())["raw_sha256"]
    (project / "data/raw/sha256" / raw_hash).write_text("tampered")
    with pytest.raises(ValueError, match="source"):
        register_filing_metrics(_write(path, request), project, catalog)
    with sqlite3.connect(catalog) as db:
        assert db.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='filings'").fetchone()[0] == 0


@pytest.mark.parametrize("change", [
    {"value_decimal": "NaN"}, {"value_decimal": "1e99999"},
    {"unit": "CRORES"}, {"value_kind": "CONSENSUS"},
    {"reporting_scope": "UNKNOWN"}, {"period_kind": "MISC"},
])
def test_rejects_invalid_metric_fields(tmp_path, change):
    from src.kb_runtime.metric_store import register_filing_metrics

    project, catalog, path, request = _setup(tmp_path)
    request["metrics"][0].update(change)
    with pytest.raises(ValueError):
        register_filing_metrics(_write(path, request), project, catalog)
    with sqlite3.connect(catalog) as db:
        assert db.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='filings'").fetchone()[0] == 0


def test_strict_cutoff_and_comparative_period(tmp_path):
    from src.kb_runtime.metric_store import query_metrics, register_filing_metrics

    project, catalog, path, request = _setup(tmp_path)
    request["metrics"][0]["period_end"] = "2025-06-30"
    register_filing_metrics(_write(path, request), project, catalog)
    query = lambda cutoff: query_metrics(catalog, project, "INE062A01020", "revenue", "2025-06-30", cutoff)
    assert query("2026-09-28T09:01:00+05:30") == []
    assert query("2026-09-28T09:02:30+05:30") == []
    found = query("2026-09-28T09:03:00+05:30")
    assert [(row["metric_id"], row["value_decimal"], row["availability_mode"]) for row in found] == [
        ("M1", "12.5", "LIVE_STRICT")]
    assert found[0]["period_end"] == "2025-06-30"
    assert found[0]["published_at"] == "2026-09-28T03:30:00+00:00"


def test_long_decimal_keeps_every_supplied_digit(tmp_path):
    from src.kb_runtime.metric_store import query_metrics, register_filing_metrics

    project, catalog, path, request = _setup(tmp_path)
    request["metrics"][0]["value_decimal"] = "0.12345678901234567890123456789012345"
    register_filing_metrics(_write(path, request), project, catalog)
    rows = query_metrics(catalog, project, "INE062A01020", "revenue", "2026-06-30", "2026-09-28T09:03:00+05:30")
    assert rows[0]["value_decimal"] == "0.12345678901234567890123456789012345"


@pytest.mark.parametrize("field,bad", [
    ("document_type", []), ("rights_status", {}), ("unit", []),
    ("reporting_scope", {}), ("value_kind", []),
])
def test_malformed_json_types_raise_controlled_error(tmp_path, field, bad):
    from src.kb_runtime.metric_store import register_filing_metrics

    project, catalog, path, request = _setup(tmp_path)
    target = request if field in request else request["metrics"][0]
    target[field] = bad
    with pytest.raises(ValueError):
        register_filing_metrics(_write(path, request), project, catalog)


def test_rejects_non_filing_source_and_future_observation(tmp_path):
    from src.kb_runtime.metric_store import register_filing_metrics

    project, catalog, path, request = _setup(tmp_path)
    web = _source(tmp_path, project, "WEB", "Revenue 12.50", "2026-09-28T09:00:00+05:30",
                  "2026-09-28T09:02:00+05:30", "WEB_PAGE")
    request.update(source_id="WEB", version_id=web["version_id"])
    with pytest.raises(ValueError, match="source"):
        register_filing_metrics(_write(path, request), project, catalog)
    future = _source(tmp_path, project, "FUTURE", "Revenue 12.50", "2027-01-01T09:00:00+05:30",
                     "2026-09-28T09:02:00+05:30")
    request.update(source_id="FUTURE", version_id=future["version_id"])
    with pytest.raises(ValueError, match="source"):
        register_filing_metrics(_write(path, request), project, catalog)


def test_sql_cannot_insert_untyped_value_kind(tmp_path):
    from src.kb_runtime.metric_store import register_filing_metrics

    project, catalog, path, request = _setup(tmp_path)
    register_filing_metrics(_write(path, request), project, catalog)
    with sqlite3.connect(catalog) as db, pytest.raises(sqlite3.IntegrityError):
        db.execute("""INSERT INTO metrics SELECT 'M_BAD', filing_id, isin, metric_name,
            value_decimal, unit, period_end, period_kind, reporting_scope, 'CONSENSUS',
            evidence_locator, NULL FROM metrics WHERE metric_id='M1'""")


def test_read_rejects_direct_sql_cross_series_revision(tmp_path):
    from src.kb_runtime.metric_store import query_metrics, register_filing_metrics

    project, catalog, path, request = _setup(tmp_path)
    register_filing_metrics(_write(path, request), project, catalog)
    with sqlite3.connect(catalog) as db:
        db.execute("""INSERT INTO metrics SELECT 'M_BAD', filing_id, isin, 'profit',
            value_decimal, unit, period_end, period_kind, reporting_scope, value_kind,
            evidence_locator, 'M1' FROM metrics WHERE metric_id='M1'""")
    with pytest.raises(ValueError, match="revision"):
        query_metrics(catalog, project, "INE062A01020", "profit", "2026-06-30", "2026-09-28T09:03:00+05:30")


def _revision(tmp_path, project, request, source_id="RESULTS2"):
    source = _source(tmp_path, project, source_id, "Revenue revised 13.75 crore",
                     "2026-09-28T10:00:00+05:30", "2026-09-28T10:02:00+05:30")
    revised = json.loads(json.dumps(request))
    revised.update({
        "filing_id": "F2", "source_id": source_id, "version_id": source["version_id"],
        "published_at": "2026-09-28T10:00:00+05:30",
        "first_seen_at": "2026-09-28T10:02:00+05:30",
        "reviewed_at": "2026-09-28T10:03:00+05:30",
        "supersedes_filing_id": "F1",
    })
    revised["metrics"][0].update({
        "metric_id": "M2", "value_decimal": "13.75", "supersedes_metric_id": "M1",
    })
    return revised


def test_later_restatement_does_not_rewrite_earlier_cutoff(tmp_path):
    from src.kb_runtime.metric_store import query_metrics, register_filing_metrics

    project, catalog, path, request = _setup(tmp_path)
    register_filing_metrics(_write(path, request), project, catalog)
    revision = _revision(tmp_path, project, request)
    register_filing_metrics(_write(path, revision), project, catalog)
    query = lambda cutoff: query_metrics(catalog, project, "INE062A01020", "revenue", "2026-06-30", cutoff)
    assert [row["metric_id"] for row in query("2026-09-28T09:30:00+05:30")] == ["M1"]
    assert [(row["metric_id"], row["value_decimal"]) for row in query("2026-09-28T10:03:00+05:30")] == [("M2", "13.75")]


def test_revision_series_mismatch_and_branch_are_rejected(tmp_path):
    from src.kb_runtime.metric_store import register_filing_metrics

    project, catalog, path, request = _setup(tmp_path)
    register_filing_metrics(_write(path, request), project, catalog)
    revision = _revision(tmp_path, project, request)
    revision["metrics"][0]["unit"] = "PERCENT"
    with pytest.raises(ValueError, match="revision"):
        register_filing_metrics(_write(path, revision), project, catalog)
    revision["metrics"][0]["unit"] = "INR_CRORE"
    register_filing_metrics(_write(path, revision), project, catalog)
    branch = _revision(tmp_path, project, request, "RESULTS3")
    branch["filing_id"] = "F3"
    branch["metrics"][0]["metric_id"] = "M3"
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        register_filing_metrics(_write(path, branch), project, catalog)
    with sqlite3.connect(catalog) as db:
        assert db.execute("SELECT count(*) FROM filings").fetchone()[0] == 2


def test_damaged_source_blocks_cutoff_read(tmp_path):
    from src.kb_runtime.metric_store import query_metrics, register_filing_metrics

    project, catalog, path, request = _setup(tmp_path)
    register_filing_metrics(_write(path, request), project, catalog)
    version_path = project / "data/registry/sources/RESULTS1" / f"{request['version_id']}.json"
    raw_hash = json.loads(version_path.read_text())["raw_sha256"]
    (project / "data/raw/sha256" / raw_hash).write_text("tampered")
    with pytest.raises(ValueError, match="source"):
        query_metrics(catalog, project, "INE062A01020", "revenue", "2026-06-30", "2026-09-28T09:05:00+05:30")


def test_filing_metric_cli_returns_strict_json(tmp_path):
    project, catalog, path, request = _setup(tmp_path)
    _write(path, request)
    registered = subprocess.run([
        sys.executable, "-m", "src.kb_runtime", "register-filing-metrics",
        "--request", str(path), "--project-dir", str(project), "--catalog", str(catalog),
    ], capture_output=True, text=True)
    assert registered.returncode == 0, registered.stderr
    assert json.loads(registered.stdout)["publication_allowed"] is False
    queried = subprocess.run([
        sys.executable, "-m", "src.kb_runtime", "query-metrics",
        "--project-dir", str(project), "--catalog", str(catalog),
        "--isin", "INE062A01020", "--metric-name", "revenue",
        "--period-end", "2026-06-30", "--cutoff", "2026-09-28T09:03:00+05:30",
    ], capture_output=True, text=True)
    assert queried.returncode == 0, queried.stderr
    assert [row["metric_id"] for row in json.loads(queried.stdout)["metrics"]] == ["M1"]


def test_filing_only_cli_registers_transcript(tmp_path):
    project, catalog, path, request = _setup(tmp_path)
    request["document_type"] = "CONCALL_TRANSCRIPT"
    request["metrics"] = []
    _write(path, request)
    result = subprocess.run([
        sys.executable, "-m", "src.kb_runtime", "register-filing",
        "--request", str(path), "--project-dir", str(project), "--catalog", str(catalog),
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "filing_id": "F1", "metric_ids": [], "publication_allowed": False,
    }


def test_text_chunk_cli_extracts_and_queries_strictly(tmp_path):
    project, catalog, path, request = _setup(tmp_path)
    request["document_type"] = "CONCALL_TRANSCRIPT"
    request["metrics"] = []
    _write(path, request)
    registered = subprocess.run([
        sys.executable, "-m", "src.kb_runtime", "register-filing",
        "--request", str(path), "--project-dir", str(project), "--catalog", str(catalog),
    ], capture_output=True, text=True)
    assert registered.returncode == 0, registered.stderr
    extracted = subprocess.run([
        sys.executable, "-m", "src.kb_runtime", "extract-text-filing",
        "--filing-id", "F1", "--project-dir", str(project), "--catalog", str(catalog),
    ], capture_output=True, text=True)
    assert extracted.returncode == 0, extracted.stderr
    chunk_ids = json.loads(extracted.stdout)["chunk_ids"]
    queried = subprocess.run([
        sys.executable, "-m", "src.kb_runtime", "query-text-chunks",
        "--filing-id", "F1", "--cutoff", "2026-09-28T09:03:00+05:30",
        "--project-dir", str(project), "--catalog", str(catalog),
    ], capture_output=True, text=True)
    assert queried.returncode == 0, queried.stderr
    assert [row["chunk_id"] for row in json.loads(queried.stdout)["chunks"]] == chunk_ids
