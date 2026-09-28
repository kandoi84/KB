import json
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from src.kb_runtime.evidence_refresh import refresh_evidence
from src.kb_runtime.source_store import record_source


ROOT = Path(__file__).resolve().parents[1]
CUTOFF = "2026-09-28T18:00:00+05:30"


def setup_inputs(tmp_path):
    project = tmp_path / "project"
    state = tmp_path / "state"
    raw = tmp_path / "filing.txt"
    raw.write_text("Deposit facts", encoding="utf-8")
    metadata = tmp_path / "source.json"
    metadata.write_text(json.dumps({
        "source_id": "SBI_Q1FY27", "entity": "SBI",
        "source_kind": "COMPANY_PRESENTATION", "url": "https://example.org/sbi.pdf",
        "source_date": "2026-08-07", "observed_at": "2026-09-28T10:00:00+05:30",
        "retrieved_at": "2026-09-28T10:05:00+05:30",
    }), encoding="utf-8")
    version = record_source(metadata, raw, project)
    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps({
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "required_sources": [{"source_id": "SBI_Q1FY27", "max_age_days": 60}],
    }), encoding="utf-8")
    claims = tmp_path / "claims.json"
    claims.write_text(json.dumps({
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "claims": [{
            "claim_id": "deposit-growth", "claim_type": "REPORTED_FACT",
            "statement": "Deposits grew.", "as_of": "2026-06-30",
            "source_id": "SBI_Q1FY27", "version_id": version["version_id"],
            "passage_locator": "page 12",
        }],
    }), encoding="utf-8")
    return project, state, metadata, raw, sources, claims, version


def run(inputs, run_id, previous=None):
    project, state, _, _, sources, claims, _ = inputs
    return refresh_evidence(sources, claims, project, state, run_id, previous)


def test_first_run_freezes_both_reports_and_open_gaps(tmp_path):
    inputs = setup_inputs(tmp_path)
    project, state, _, _, _, _, _ = inputs
    manifest = run(inputs, "evidence-1")
    assert manifest["source_status"] == "SOURCE_READY"
    assert manifest["claim_status"] == "CLAIMS_BLOCKED"
    assert manifest["publication_allowed"] is False
    assert manifest["source_changes"][0]["status"] == "INITIAL"
    assert manifest["claim_impacts"][0]["status"] == "INITIAL"
    assert manifest["open_gap_ids"] == ["evidence-1-deposit-growth"]
    assert json.loads((state / "evidence_runs/evidence-1.json").read_text()) == manifest
    assert (state / "refresh_runs/evidence-1.json").exists()
    assert (state / "claim_runs/evidence-1.json").exists()
    assert run(inputs, "evidence-1") == manifest


def test_new_source_version_triggers_claim_recheck(tmp_path):
    inputs = setup_inputs(tmp_path)
    project, state, metadata, raw, _, _, version = inputs
    first = run(inputs, "evidence-1")
    revised = json.loads(metadata.read_text())
    revised["retrieved_at"] = "2026-09-28T11:05:00+05:30"
    revised["observed_at"] = "2026-09-28T11:00:00+05:30"
    metadata.write_text(json.dumps(revised), encoding="utf-8")
    raw.write_text("Revised deposit facts", encoding="utf-8")
    newer = record_source(metadata, raw, project)
    second = run(inputs, "evidence-2", "evidence-1")
    assert second["source_changes"][0]["status"] == "UPDATED"
    assert second["source_changes"][0]["previous_version_id"] == version["version_id"]
    assert second["source_changes"][0]["current_version_id"] == newer["version_id"]
    assert second["claim_impacts"][0]["status"] == "BLOCKED_GAP"
    assert json.loads((state / "claim_runs/evidence-2.json").read_text())["claims"][0]["status"] == "VERSION_MISMATCH"
    assert json.loads((state / "evidence_runs/evidence-1.json").read_text()) == first


def test_unchanged_refresh_keeps_claim_impact_unchanged(tmp_path):
    inputs = setup_inputs(tmp_path)
    run(inputs, "evidence-1")
    second = run(inputs, "evidence-2", "evidence-1")
    assert second["source_changes"][0]["status"] == "UNCHANGED"
    assert second["claim_impacts"][0]["status"] == "UNCHANGED"
    assert second["publication_allowed"] is False


@pytest.mark.parametrize("field,value", [
    ("passage_locator", "page 13"),
    ("claim_type", "MANAGEMENT_GUIDANCE"),
    ("as_of", "2026-06-29"),
])
def test_changed_claim_contract_requires_recheck(tmp_path, field, value):
    inputs = setup_inputs(tmp_path)
    run(inputs, "evidence-1")
    claims = inputs[5]
    request = json.loads(claims.read_text())
    request["claims"][0][field] = value
    claims.write_text(json.dumps(request), encoding="utf-8")
    second = run(inputs, "evidence-2", "evidence-1")
    assert second["source_changes"][0]["status"] == "UNCHANGED"
    assert second["claim_impacts"][0]["status"] == "RECHECK_SOURCE"


def test_blocked_source_stays_blocked_in_manifest(tmp_path):
    inputs = setup_inputs(tmp_path)
    project, _, _, _, _, _, version = inputs
    (project / "data/raw/sha256" / version["raw_sha256"]).unlink()
    manifest = run(inputs, "evidence-blocked")
    assert manifest["source_status"] == "SOURCE_BLOCKED"
    assert manifest["source_changes"][0]["status"] == "BLOCKED"
    assert manifest["claim_impacts"][0]["status"] == "INITIAL"
    assert manifest["publication_allowed"] is False


def test_changed_input_cannot_reuse_run_id(tmp_path):
    inputs = setup_inputs(tmp_path)
    run(inputs, "evidence-1")
    sources = inputs[4]
    request = json.loads(sources.read_text())
    request["required_sources"][0]["max_age_days"] = 90
    sources.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(ValueError, match="run_id"):
        run(inputs, "evidence-1")


def test_changed_claim_cannot_reuse_run_id(tmp_path):
    inputs = setup_inputs(tmp_path)
    run(inputs, "evidence-1")
    claims = inputs[5]
    request = json.loads(claims.read_text())
    request["claims"][0]["statement"] = "A changed claim."
    claims.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(ValueError, match="run_id"):
        run(inputs, "evidence-1")


def test_removed_required_source_is_visible_and_blocked(tmp_path):
    inputs = setup_inputs(tmp_path)
    run(inputs, "evidence-1")
    sources = inputs[4]
    request = json.loads(sources.read_text())
    request["required_sources"] = [{"source_id": "NEW_MISSING", "max_age_days": 60}]
    sources.write_text(json.dumps(request), encoding="utf-8")
    second = run(inputs, "evidence-2", "evidence-1")
    changes = {item["source_id"]: item["status"] for item in second["source_changes"]}
    assert changes == {"SBI_Q1FY27": "REMOVED", "NEW_MISSING": "BLOCKED"}
    assert second["claim_impacts"][0]["status"] == "BLOCKED_GAP"


def test_previous_cutoff_cannot_be_after_current_cutoff(tmp_path):
    inputs = setup_inputs(tmp_path)
    for request_path in (inputs[4], inputs[5]):
        request = json.loads(request_path.read_text())
        request["cutoff_timestamp"] = "2026-09-29T18:00:00+05:30"
        request_path.write_text(json.dumps(request), encoding="utf-8")
    run(inputs, "evidence-later")
    for request_path in (inputs[4], inputs[5]):
        request = json.loads(request_path.read_text())
        request["cutoff_timestamp"] = CUTOFF
        request_path.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(ValueError, match="cutoff"):
        run(inputs, "evidence-earlier", "evidence-later")
    assert not (inputs[1] / "refresh_runs/evidence-earlier.json").exists()


def test_mismatched_requests_fail_before_any_state(tmp_path):
    inputs = setup_inputs(tmp_path)
    claims = inputs[5]
    request = json.loads(claims.read_text())
    request["cutoff_timestamp"] = "2026-09-29T18:00:00+05:30"
    claims.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(ValueError, match="cutoff"):
        run(inputs, "mismatch")
    assert not (inputs[1] / "refresh_runs/mismatch.json").exists()


def test_missing_or_tampered_previous_run_fails_closed(tmp_path):
    inputs = setup_inputs(tmp_path)
    with pytest.raises(ValueError, match="previous"):
        run(inputs, "evidence-2", "missing")
    run(inputs, "evidence-1")
    path = inputs[1] / "evidence_runs/evidence-1.json"
    path.write_text(path.read_text().replace("SOURCE_READY", "SOURCE_BLOCKED"))
    with pytest.raises(ValueError, match="digest"):
        run(inputs, "evidence-2", "evidence-1")


def test_changed_previous_report_must_match_manifest(tmp_path):
    inputs = setup_inputs(tmp_path)
    run(inputs, "evidence-1")
    path = inputs[1] / "refresh_runs/evidence-1.json"
    report = json.loads(path.read_text())
    report["run_id"] = "different"
    report.pop("report_id")
    report["report_id"] = hashlib.sha256(json.dumps(
        report, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="reports do not match"):
        run(inputs, "evidence-2", "evidence-1")


def test_refresh_evidence_cli(tmp_path):
    project, state, _, _, sources, claims, _ = setup_inputs(tmp_path)
    result = subprocess.run([
        sys.executable, "-m", "src.kb_runtime", "refresh-evidence",
        "--source-request", str(sources), "--claims", str(claims),
        "--project-dir", str(project), "--state-dir", str(state),
        "--run-id", "cli-1",
    ], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["publication_allowed"] is False
