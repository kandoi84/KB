import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from src.kb_runtime.identity_store import register_identity, resolve_symbol
from src.kb_runtime.source_store import record_source


def setup(tmp_path):
    project = tmp_path / "project"
    catalog = tmp_path / "identity.sqlite"
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({
        "source_id": "SBI_IDENT", "entity": "SBI", "source_kind": "EXCHANGE_SECURITY_FILE",
        "url": "https://example.org/security-file", "source_date": "2026-09-28",
        "observed_at": "2026-09-28T09:00:00+05:30",
        "retrieved_at": "2026-09-28T09:05:00+05:30",
    }))
    raw = tmp_path / "raw.txt"
    raw.write_text("SBI INE062A01020")
    version = record_source(metadata, raw, project)
    request = tmp_path / "identity.json"
    payload = {
        "issuer_id": "SBI", "legal_name": "State Bank of India",
        "isin": "INE062A01020", "security_type": "EQUITY",
        "listed_from": "1995-01-01", "listed_to": None,
        "exchange": "NSE", "symbol": "SBIN",
        "valid_from": "1995-01-01", "valid_to": None,
        "announced_at": "2026-09-28T09:00:00+05:30",
        "first_seen_at": "2026-09-28T09:05:00+05:30",
        "source_id": version["source_id"], "version_id": version["version_id"],
        "reviewer_id": "analyst-1", "reviewed_at": "2026-09-28T09:06:00+05:30",
        "review_decision": "CONFIRMED", "evidence_locator": "security file row 1",
    }
    request.write_text(json.dumps(payload))
    return project, catalog, request, payload


def test_register_and_resolve_only_when_known(tmp_path):
    project, catalog, request, _ = setup(tmp_path)
    first = register_identity(request, project, catalog)
    assert register_identity(request, project, catalog) == first
    assert resolve_symbol(catalog, project, "NSE", "SBIN", "2026-09-28", "2026-09-28T09:04:00+05:30") is None
    assert resolve_symbol(catalog, project, "NSE", "SBIN", "2026-09-28", "2026-09-28T09:05:30+05:30") is None
    assert resolve_symbol(catalog, project, "NSE", "SBIN", "2026-09-28", "2026-09-28T09:06:00+05:30") == "INE062A01020"
    with sqlite3.connect(catalog) as db:
        assert db.execute("SELECT review_decision FROM symbol_history").fetchone()[0] == "CONFIRMED"


def test_bad_isin_and_conflicting_security_fail(tmp_path):
    project, catalog, request, payload = setup(tmp_path)
    payload["isin"] = "INE062A01021"
    request.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="ISIN"):
        register_identity(request, project, catalog)
    payload["isin"] = "INE062A01020"
    request.write_text(json.dumps(payload))
    register_identity(request, project, catalog)
    payload["security_type"] = "DEBT"
    request.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="security identity conflicts"):
        register_identity(request, project, catalog)


def test_symbol_overlap_fails_and_future_mapping_stays_hidden(tmp_path):
    project, catalog, request, payload = setup(tmp_path)
    register_identity(request, project, catalog)
    payload["isin"] = "INE062A01020"
    payload["valid_from"] = "2026-01-01"
    payload["valid_to"] = "2026-12-31"
    request.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="overlaps"):
        register_identity(request, project, catalog)


def test_damaged_source_blocks_identity_registration(tmp_path):
    project, catalog, request, payload = setup(tmp_path)
    blob = project / "data/raw/sha256"
    list(blob.iterdir())[0].write_text("tampered")
    with pytest.raises(ValueError, match="source"):
        register_identity(request, project, catalog)


def test_damaged_source_blocks_resolution(tmp_path):
    project, catalog, request, payload = setup(tmp_path)
    register_identity(request, project, catalog)
    (project / "data/raw/sha256" / record_sha(project, payload)).write_text("tampered")
    with pytest.raises(ValueError, match="source"):
        resolve_symbol(catalog, project, "NSE", "SBIN", "2026-09-28", "2026-09-28T09:07:00+05:30")


def record_sha(project, payload):
    version = project / "data/registry/sources" / payload["source_id"] / f"{payload['version_id']}.json"
    return json.loads(version.read_text())["raw_sha256"]


def test_identity_needs_review_and_known_labels(tmp_path):
    project, catalog, request, payload = setup(tmp_path)
    payload["review_decision"] = "UNREVIEWED"
    request.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="review_decision"):
        register_identity(request, project, catalog)
    payload["review_decision"] = "CONFIRMED"
    payload["exchange"] = "NSEE"
    request.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="exchange"):
        register_identity(request, project, catalog)
    payload["exchange"] = "NSE"
    payload["security_type"] = "EQUITYY"
    request.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="security_type"):
        register_identity(request, project, catalog)


def test_cannot_resolve_future_effective_date_at_old_cutoff(tmp_path):
    project, catalog, request, _ = setup(tmp_path)
    register_identity(request, project, catalog)
    with pytest.raises(ValueError, match="effective_date after cutoff"):
        resolve_symbol(catalog, project, "NSE", "SBIN", "2026-10-01", "2026-09-28T09:07:00+05:30")


def test_identity_cli(tmp_path):
    project, catalog, request, _ = setup(tmp_path)
    registered = subprocess.run([
        sys.executable, "-m", "src.kb_runtime", "register-identity",
        "--request", str(request), "--project-dir", str(project),
        "--catalog", str(catalog),
    ], capture_output=True, text=True)
    assert registered.returncode == 0, registered.stderr
    resolved = subprocess.run([
        sys.executable, "-m", "src.kb_runtime", "resolve-symbol",
        "--catalog", str(catalog), "--exchange", "NSE", "--symbol", "SBIN",
        "--project-dir", str(project),
        "--effective-date", "2026-09-28", "--cutoff", "2026-09-28T09:06:00+05:30",
    ], capture_output=True, text=True)
    assert resolved.returncode == 0, resolved.stderr
    assert json.loads(resolved.stdout)["isin"] == "INE062A01020"
