"""Backfill is research-only and needs reviewed, exact archive evidence."""

import json
import sqlite3

import pytest

from src.kb_runtime.identity_store import register_identity
from src.kb_runtime.metric_store import query_metrics, register_filing_metrics
from src.kb_runtime.source_store import record_source


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _source(tmp_path, project, name, raw, observed, retrieved, kind):
    metadata = _write(tmp_path / f"{name}.json", {
        "source_id": name, "entity": "SBI", "source_kind": kind,
        "url": f"https://www.nseindia.com/{name}", "source_date": "2025-08-01",
        "observed_at": observed, "retrieved_at": retrieved,
    })
    raw_path = tmp_path / f"{name}.raw"
    raw_path.write_bytes(raw if isinstance(raw, bytes) else raw.encode())
    return record_source(metadata, raw_path, project)


def _setup(tmp_path):
    project, catalog = tmp_path / "project", tmp_path / "catalog.sqlite"
    past, later = "2025-08-01T10:00:00+05:30", "2026-09-28T10:00:00+05:30"
    identity_source = _source(tmp_path, project, "IDENT", "SBI INE062A01020", past, later, "EXCHANGE_FILING")
    identity = {
        "issuer_id": "SBI", "legal_name": "State Bank of India", "isin": "INE062A01020",
        "security_type": "EQUITY", "listed_from": "1995-01-01", "listed_to": None,
        "exchange": "NSE", "symbol": "SBIN", "valid_from": "1995-01-01", "valid_to": None,
        "announced_at": past, "first_seen_at": later, "source_id": "IDENT",
        "version_id": identity_source["version_id"], "reviewer_id": "analyst-1",
        "reviewed_at": "2026-09-28T10:01:00+05:30", "review_decision": "CONFIRMED",
        "evidence_locator": "identity row 1",
    }
    register_identity(_write(tmp_path / "identity-request.json", identity), project, catalog)
    filing_source = _source(tmp_path, project, "FILE", "Revenue 12.5 crore", past, later, "EXCHANGE_FILING")
    filing = {
        "filing_id": "F1", "issuer_id": "SBI", "isin": "INE062A01020",
        "source_id": "FILE", "version_id": filing_source["version_id"],
        "document_type": "RESULTS", "period_end": "2025-06-30", "published_at": past,
        "first_seen_at": later, "rights_status": "REVIEWED", "reviewer_id": "analyst-1",
        "reviewed_at": "2026-09-28T10:02:00+05:30", "review_decision": "CONFIRMED",
        "evidence_locator": "result row 1", "supersedes_filing_id": None,
        "metrics": [{"metric_id": "M1", "metric_name": "revenue", "value_decimal": "12.5",
                     "unit": "INR_CRORE", "period_end": "2025-06-30", "period_kind": "QUARTER",
                     "reporting_scope": "CONSOLIDATED", "value_kind": "REPORTED",
                     "evidence_locator": "page 1", "supersedes_metric_id": None}],
    }
    register_filing_metrics(_write(tmp_path / "filing-request.json", filing), project, catalog)
    manifest = {
        "issuer_id": "SBI", "isin": "INE062A01020",
        "identity_source_id": "IDENT", "identity_version_id": identity_source["version_id"],
        "filing_source_id": "FILE", "filing_version_id": filing_source["version_id"],
        "filing_raw_sha256": filing_source["raw_sha256"], "published_at": past,
    }
    archive = _source(tmp_path, project, "ARCHIVE", json.dumps(manifest), past, past, "EXCHANGE_ARCHIVE")
    identity_manifest = {
        "issuer_id": "SBI", "isin": "INE062A01020",
        "company_source_id": "IDENT", "company_version_id": identity_source["version_id"],
        "security_source_id": "IDENT", "security_version_id": identity_source["version_id"],
        "announced_at": past,
    }
    identity_archive = _source(tmp_path, project, "IDENTARCHIVE", json.dumps(identity_manifest),
                               past, past, "EXCHANGE_ARCHIVE")
    proof = {
        "proof_id": "P1", "filing_id": "F1", "archive_source_id": "ARCHIVE",
        "archive_version_id": archive["version_id"], "evidence_locator": "archive row 1",
        "identity_proof_id": "IP1", "identity_archive_source_id": "IDENTARCHIVE",
        "identity_archive_version_id": identity_archive["version_id"],
        "identity_evidence_locator": "identity archive row 1",
        "reviewer_id": "analyst-2", "reviewed_at": "2026-09-28T10:03:00+05:30",
        "review_decision": "CONFIRMED", "proof_category": "MANUAL_REVIEWED_ARCHIVE_ATTESTATION",
    }
    return project, catalog, filing, manifest, proof


def test_reviewed_archive_proof_backfills_later_ingested_metric_without_changing_live(tmp_path):
    from src.kb_runtime.historical_backfill import query_backfilled_metrics, register_backfill_proof

    project, catalog, _, _, proof = _setup(tmp_path)
    request = _write(tmp_path / "proof.json", proof)
    assert register_backfill_proof(request, project, catalog)["proof_id"] == "P1"
    assert register_backfill_proof(request, project, catalog)["proof_id"] == "P1"
    cutoff = "2025-08-01T10:01:00+05:30"
    assert query_metrics(catalog, project, "INE062A01020", "revenue", "2025-06-30", cutoff) == []
    rows = query_backfilled_metrics(catalog, project, "INE062A01020", "revenue", "2025-06-30", cutoff)
    assert [(row["metric_id"], row["availability_mode"], row["proof_id"]) for row in rows] == [
        ("M1", "BACKFILLED", "P1")]
    assert rows[0]["publication_allowed"] is False
    assert rows[0]["proof_category"] == "MANUAL_REVIEWED_ARCHIVE_ATTESTATION"
    assert rows[0]["identity_proof_id"] == "IP1"
    assert rows[0]["archive_captured_at"] == "2025-08-01T04:30:00+00:00"
    assert "not independently verified" in rows[0]["trust_limit"]


def test_late_archive_capture_and_digest_mismatch_fail_closed(tmp_path):
    from src.kb_runtime.historical_backfill import register_backfill_proof

    project, catalog, _, manifest, proof = _setup(tmp_path)
    manifest["filing_raw_sha256"] = "0" * 64
    bad = _source(tmp_path, project, "BAD", json.dumps(manifest),
                  "2025-08-01T10:00:00+05:30", "2026-09-28T10:00:00+05:30", "EXCHANGE_ARCHIVE")
    proof["archive_source_id"], proof["archive_version_id"] = "BAD", bad["version_id"]
    with pytest.raises(ValueError, match="archive|digest|filing"):
        register_backfill_proof(_write(tmp_path / "bad-proof.json", proof), project, catalog)
    with sqlite3.connect(catalog) as db:
        assert db.execute("SELECT count(*) FROM backfill_proofs").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM backfill_identity_proofs").fetchone()[0] == 0


def _revision(tmp_path, project, catalog, filing, published, name, value):
    source = _source(tmp_path, project, name, f"Revenue {value} crore", published,
                     "2026-09-28T10:04:00+05:30", "EXCHANGE_FILING")
    revised = {**filing, "filing_id": name, "source_id": name,
               "version_id": source["version_id"], "published_at": published,
               "first_seen_at": "2026-09-28T10:04:00+05:30",
               "reviewed_at": "2026-09-28T10:05:00+05:30",
               "supersedes_filing_id": filing["filing_id"],
               "metrics": [{**filing["metrics"][0], "metric_id": f"M{name}",
                            "value_decimal": value,
                            "supersedes_metric_id": filing["metrics"][0]["metric_id"]}]}
    register_filing_metrics(_write(tmp_path / f"{name}-request.json", revised), project, catalog)
    return revised, source


def test_future_revision_does_not_replace_proven_past_metric(tmp_path):
    from src.kb_runtime.historical_backfill import query_backfilled_metrics, register_backfill_proof

    project, catalog, filing, _, proof = _setup(tmp_path)
    register_backfill_proof(_write(tmp_path / "proof.json", proof), project, catalog)
    _revision(tmp_path, project, catalog, filing, "2025-08-02T10:00:00+05:30", "F2", "14")
    rows = query_backfilled_metrics(catalog, project, "INE062A01020", "revenue", "2025-06-30",
                                    "2025-08-01T10:01:00+05:30")
    assert [row["metric_id"] for row in rows] == ["M1"]


def test_missing_proof_for_old_revision_blocks_newer_revision(tmp_path):
    from src.kb_runtime.historical_backfill import query_backfilled_metrics, register_backfill_proof

    project, catalog, filing, manifest, proof = _setup(tmp_path)
    revised, source = _revision(tmp_path, project, catalog, filing,
                                "2025-08-01T10:00:30+05:30", "F2", "14")
    manifest.update(filing_source_id="F2", filing_version_id=source["version_id"],
                    filing_raw_sha256=source["raw_sha256"],
                    published_at="2025-08-01T10:00:30+05:30")
    archive = _source(tmp_path, project, "ARCHIVE2", json.dumps(manifest),
                      "2025-08-01T10:00:30+05:30", "2025-08-01T10:00:40+05:30", "EXCHANGE_ARCHIVE")
    proof.update(proof_id="P2", filing_id="F2", archive_source_id="ARCHIVE2",
                 archive_version_id=archive["version_id"])
    register_backfill_proof(_write(tmp_path / "proof2.json", proof), project, catalog)
    with pytest.raises(ValueError, match="lacks archive proof"):
        query_backfilled_metrics(catalog, project, "INE062A01020", "revenue", "2025-06-30",
                                 "2025-08-01T10:01:00+05:30")


def test_late_capture_and_tampered_archive_block_query(tmp_path):
    from src.kb_runtime.historical_backfill import query_backfilled_metrics, register_backfill_proof

    project, catalog, _, manifest, proof = _setup(tmp_path)
    late = _source(tmp_path, project, "ARCHIVELATE", json.dumps(manifest),
                   "2025-08-01T10:00:00+05:30", "2025-08-01T10:02:00+05:30", "EXCHANGE_ARCHIVE")
    proof.update(archive_source_id="ARCHIVELATE", archive_version_id=late["version_id"])
    register_backfill_proof(_write(tmp_path / "proof.json", proof), project, catalog)
    query = lambda cutoff: query_backfilled_metrics(
        catalog, project, "INE062A01020", "revenue", "2025-06-30", cutoff)
    with pytest.raises(ValueError, match="cutoff availability"):
        query("2025-08-01T10:01:00+05:30")
    with sqlite3.connect(catalog) as db:
        archive_digest = db.execute("SELECT archive_raw_sha256 FROM backfill_proofs").fetchone()[0]
    (project / "data/raw/sha256" / archive_digest).write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="archive source"):
        query("2025-08-01T10:03:00+05:30")


def test_conflicting_receipt_replay_and_mutation_are_rejected(tmp_path):
    from src.kb_runtime.historical_backfill import register_backfill_proof

    project, catalog, _, _, proof = _setup(tmp_path)
    register_backfill_proof(_write(tmp_path / "proof.json", proof), project, catalog)
    changed = {**proof, "evidence_locator": "different row"}
    with pytest.raises(ValueError, match="replay conflicts"):
        register_backfill_proof(_write(tmp_path / "changed.json", changed), project, catalog)
    with sqlite3.connect(catalog) as db:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            db.execute("UPDATE backfill_proofs SET evidence_locator='fake' WHERE proof_id='P1'")


def test_injected_revision_branch_fails_closed(tmp_path):
    from src.kb_runtime.historical_backfill import query_backfilled_metrics, register_backfill_proof

    project, catalog, _, _, proof = _setup(tmp_path)
    register_backfill_proof(_write(tmp_path / "proof.json", proof), project, catalog)
    with sqlite3.connect(catalog) as db:
        db.execute("""INSERT INTO metrics SELECT 'M2', filing_id, isin, metric_name,
                   '99', unit, period_end, period_kind, reporting_scope, value_kind,
                   evidence_locator, NULL FROM metrics WHERE metric_id='M1'""")
    with pytest.raises(ValueError, match="ambiguously"):
        query_backfilled_metrics(catalog, project, "INE062A01020", "revenue", "2025-06-30",
                                 "2025-08-01T10:01:00+05:30")


def test_identity_announced_after_archive_capture_is_not_proof(tmp_path):
    from src.kb_runtime.historical_backfill import query_backfilled_metrics, register_backfill_proof

    project, catalog, _, _, proof = _setup(tmp_path)
    register_backfill_proof(_write(tmp_path / "proof.json", proof), project, catalog)
    with sqlite3.connect(catalog) as db:
        db.execute("DROP TRIGGER securities_no_update")
        db.execute("UPDATE securities SET announced_at='2025-08-01T04:30:30+00:00'")
    with pytest.raises(ValueError, match="identity|archive"):
        query_backfilled_metrics(catalog, project, "INE062A01020", "revenue", "2025-06-30",
                                 "2025-08-01T10:01:00+05:30")


def test_missing_or_tampered_identity_receipt_blocks_backfill(tmp_path):
    from src.kb_runtime.historical_backfill import query_backfilled_metrics, register_backfill_proof

    project, catalog, _, _, proof = _setup(tmp_path)
    register_backfill_proof(_write(tmp_path / "proof.json", proof), project, catalog)
    query = lambda: query_backfilled_metrics(catalog, project, "INE062A01020", "revenue",
                                              "2025-06-30", "2025-08-01T10:01:00+05:30")
    with sqlite3.connect(catalog) as db:
        identity_digest = db.execute("SELECT archive_raw_sha256 FROM backfill_identity_proofs").fetchone()[0]
    (project / "data/raw/sha256" / identity_digest).write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="archive source"):
        query()


def test_identity_archive_must_bind_exact_isin_and_source_version(tmp_path):
    from src.kb_runtime.historical_backfill import register_backfill_proof

    project, catalog, _, _, proof = _setup(tmp_path)
    identity_manifest = {
        "issuer_id": "SBI", "isin": "INE062A01020", "company_source_id": "IDENT",
        "company_version_id": "0" * 64, "security_source_id": "IDENT",
        "security_version_id": "0" * 64,
        "announced_at": "2025-08-01T10:00:00+05:30",
    }
    bad = _source(tmp_path, project, "BADIDENTARCHIVE", json.dumps(identity_manifest),
                  "2025-08-01T10:00:00+05:30", "2025-08-01T10:00:00+05:30",
                  "EXCHANGE_ARCHIVE")
    proof.update(identity_archive_source_id="BADIDENTARCHIVE",
                 identity_archive_version_id=bad["version_id"])
    with pytest.raises(ValueError, match="identity archive binding"):
        register_backfill_proof(_write(tmp_path / "bad-identity-proof.json", proof), project, catalog)
