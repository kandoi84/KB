import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.kb_runtime.source_refresh import evaluate_sources
from src.kb_runtime.source_store import record_source


ROOT = Path(__file__).resolve().parents[1]


def setup_request(tmp_path, *, max_age_days=60, cutoff="2026-09-28T18:00:00+05:30"):
    project = tmp_path / "project"
    state = tmp_path / "state"
    request = tmp_path / "request.json"
    request.write_text(json.dumps({
        "entity": "SBI",
        "cutoff_timestamp": cutoff,
        "required_sources": [{"source_id": "SBI_Q1FY27", "max_age_days": max_age_days}],
    }), encoding="utf-8")
    return project, state, request


def add_source(tmp_path, project, *, retrieved_at="2026-09-28T10:05:00+05:30"):
    metadata = tmp_path / "source.json"
    metadata.write_text(json.dumps({
        "source_id": "SBI_Q1FY27",
        "entity": "SBI",
        "source_kind": "COMPANY_PRESENTATION",
        "url": "https://example.org/sbi.pdf",
        "source_date": "2026-08-07",
        "observed_at": "2026-09-28T10:00:00+05:30",
        "retrieved_at": retrieved_at,
    }), encoding="utf-8")
    raw = tmp_path / "filing.pdf"
    raw.write_bytes(b"filing bytes")
    return record_source(metadata, raw, project), metadata, raw


def test_current_source_produces_frozen_ready_report(tmp_path):
    project, state, request = setup_request(tmp_path)
    version, _, _ = add_source(tmp_path, project)
    report = evaluate_sources(request, project, state, "refresh-1")

    assert report["status"] == "SOURCE_READY"
    assert report["sources"][0]["status"] == "CURRENT"
    assert report["sources"][0]["version_id"] == version["version_id"]
    assert json.loads((state / "refresh_runs/refresh-1.json").read_text()) == report


def test_shared_source_can_support_another_entity(tmp_path):
    project, state, request = setup_request(tmp_path)
    add_source(tmp_path, project)
    changed = json.loads(request.read_text())
    changed["entity"] = "HDFC"
    request.write_text(json.dumps(changed), encoding="utf-8")
    report = evaluate_sources(request, project, state, "shared")
    assert report["status"] == "SOURCE_READY"


def test_missing_and_future_sources_block_readiness(tmp_path):
    project, state, request = setup_request(tmp_path)
    missing = evaluate_sources(request, project, state, "missing")
    assert missing["sources"][0]["status"] == "MISSING"

    add_source(tmp_path, project, retrieved_at="2026-09-29T10:05:00+05:30")
    future = evaluate_sources(request, project, state, "future")
    assert future["status"] == "SOURCE_BLOCKED"
    assert future["sources"][0]["status"] == "AFTER_CUTOFF"


def test_stale_source_blocks_readiness(tmp_path):
    project, state, request = setup_request(tmp_path, max_age_days=30)
    add_source(tmp_path, project)
    report = evaluate_sources(request, project, state, "stale")
    assert report["sources"][0]["status"] == "STALE"


@pytest.mark.parametrize("damage,expected", [
    ("missing", "MISSING_RAW"),
    ("corrupt", "CORRUPT_RAW"),
])
def test_missing_or_corrupt_raw_blocks_readiness(tmp_path, damage, expected):
    project, state, request = setup_request(tmp_path)
    version, _, _ = add_source(tmp_path, project)
    blob = project / "data/raw/sha256" / version["raw_sha256"]
    if damage == "missing":
        blob.unlink()
    else:
        blob.write_bytes(b"changed bytes")
    report = evaluate_sources(request, project, state, damage)
    assert report["sources"][0]["status"] == expected


def test_tampered_register_blocks_readiness(tmp_path):
    project, state, request = setup_request(tmp_path)
    version, _, _ = add_source(tmp_path, project)
    path = project / "data/registry/sources/SBI_Q1FY27" / f'{version["version_id"]}.json'
    record = json.loads(path.read_text())
    record["source_date"] = "2026-08-08"
    path.write_text(json.dumps(record), encoding="utf-8")
    report = evaluate_sources(request, project, state, "tampered")
    assert report["sources"][0]["status"] == "INVALID_REGISTRY"


def test_malformed_frozen_report_is_rejected(tmp_path):
    project, state, request = setup_request(tmp_path)
    evaluate_sources(request, project, state, "refresh-1")
    (state / "refresh_runs/refresh-1.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="existing refresh report is invalid"):
        evaluate_sources(request, project, state, "refresh-1")


def test_frozen_run_requires_new_id_after_source_update(tmp_path):
    project, state, request = setup_request(tmp_path)
    first = evaluate_sources(request, project, state, "refresh-1")
    assert first["status"] == "SOURCE_BLOCKED"
    add_source(tmp_path, project)
    assert evaluate_sources(request, project, state, "refresh-1") == first
    assert evaluate_sources(request, project, state, "refresh-2")["status"] == "SOURCE_READY"
    changed = json.loads(request.read_text())
    changed["required_sources"][0]["max_age_days"] = 30
    request.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="run_id"):
        evaluate_sources(request, project, state, "refresh-1")


def test_evaluate_sources_cli_reports_status(tmp_path):
    project, state, request = setup_request(tmp_path)
    add_source(tmp_path, project)
    result = subprocess.run([
        sys.executable, "-m", "src.kb_runtime", "evaluate-sources",
        "--request", str(request), "--project-dir", str(project),
        "--state-dir", str(state), "--run-id", "cli-1",
    ], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "SOURCE_READY"
