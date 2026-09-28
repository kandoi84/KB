import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.kb_runtime.claim_lineage import evaluate_claims
from src.kb_runtime.source_refresh import evaluate_sources
from src.kb_runtime.source_store import record_source


ROOT = Path(__file__).resolve().parents[1]
CUTOFF = "2026-09-28T18:00:00+05:30"


def fixture(tmp_path):
    project = tmp_path / "project"
    state = tmp_path / "state"
    metadata = tmp_path / "source.json"
    metadata.write_text(json.dumps({
        "source_id": "SBI_Q1FY27", "entity": "SBI",
        "source_kind": "COMPANY_PRESENTATION", "url": "https://example.org/sbi.pdf",
        "source_date": "2026-08-07",
        "observed_at": "2026-09-28T10:00:00+05:30",
        "retrieved_at": "2026-09-28T10:05:00+05:30",
    }), encoding="utf-8")
    raw = tmp_path / "filing.pdf"
    raw.write_bytes(b"source bytes")
    version = record_source(metadata, raw, project)
    source_request = tmp_path / "source_request.json"
    source_request.write_text(json.dumps({
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "required_sources": [{"source_id": "SBI_Q1FY27", "max_age_days": 60}],
    }), encoding="utf-8")
    evaluate_sources(source_request, project, state, "sources-1")
    source_report = state / "refresh_runs/sources-1.json"
    claim_request = tmp_path / "claims.json"
    claim_request.write_text(json.dumps({
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "claims": [{
            "claim_id": "sbi-deposit-growth", "claim_type": "REPORTED_FACT",
            "statement": "Deposits grew.", "as_of": "2026-06-30",
            "source_id": "SBI_Q1FY27", "version_id": version["version_id"],
            "passage_locator": "page 12, deposits table",
        }],
    }), encoding="utf-8")
    return project, state, source_report, claim_request, version


def change_claim(request_path, **changes):
    request = json.loads(request_path.read_text())
    request["claims"][0].update(changes)
    request_path.write_text(json.dumps(request), encoding="utf-8")


def test_linked_claim_is_still_unverified_and_has_open_gap(tmp_path):
    project, state, source_report, claim_request, version = fixture(tmp_path)
    report = evaluate_claims(claim_request, source_report, project, state, "claim-1")
    claim = report["claims"][0]
    assert report["status"] == "CLAIMS_BLOCKED"
    assert claim["status"] == "LINEAGE_LINKED"
    assert claim["passage_status"] == "UNVERIFIED"
    assert claim["raw_sha256"] == version["raw_sha256"]
    gap = report["gaps"][0]
    assert set(gap) == {
        "gap_id", "claim_id", "status", "resolution_type", "web_resolvable",
        "preferred_source", "fallback_source", "last_attempt", "reason_unresolved",
    }
    assert gap["resolution_type"] == "INTERNAL_RESEARCH"
    assert gap["status"] == "OPEN"
    assert json.loads((state / "claim_runs/claim-1.json").read_text()) == report


@pytest.mark.parametrize("change,expected", [
    ({"version_id": "0" * 64}, "VERSION_MISMATCH"),
    ({"as_of": "2026-09-29"}, "AFTER_CUTOFF"),
    ({"claim_type": "DERIVED"}, "NEEDS_DERIVATION"),
    ({"claim_type": "INFERENCE"}, "NEEDS_DERIVATION"),
])
def test_invalid_lineage_has_classified_gap(tmp_path, change, expected):
    project, state, source_report, claim_request, _ = fixture(tmp_path)
    change_claim(claim_request, **change)
    report = evaluate_claims(claim_request, source_report, project, state, "blocked")
    assert report["claims"][0]["status"] == expected
    assert report["gaps"][0]["resolution_type"] == "UNCLASSIFIED"
    assert report["gaps"][0]["web_resolvable"] is False


@pytest.mark.parametrize("damage", ["corrupt_raw", "missing_raw", "tampered_record"])
def test_damaged_source_after_source_refresh_blocks_claim(tmp_path, damage):
    project, state, source_report, claim_request, version = fixture(tmp_path)
    blob = project / "data/raw/sha256" / version["raw_sha256"]
    if damage == "corrupt_raw":
        blob.write_bytes(b"corrupt")
    elif damage == "missing_raw":
        blob.unlink()
    else:
        record_path = project / "data/registry/sources/SBI_Q1FY27" / f'{version["version_id"]}.json'
        record = json.loads(record_path.read_text())
        record["source_date"] = "2026-08-08"
        record_path.write_text(json.dumps(record), encoding="utf-8")
    report = evaluate_claims(claim_request, source_report, project, state, "raw-corrupt")
    assert report["claims"][0]["status"] == "INVALID_SOURCE"


def test_blocked_source_report_cannot_support_claim(tmp_path):
    project, state, source_report, claim_request, _ = fixture(tmp_path)
    source_request = tmp_path / "blocked_source.json"
    source_request.write_text(json.dumps({
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "required_sources": [{"source_id": "missing", "max_age_days": 60}],
    }), encoding="utf-8")
    evaluate_sources(source_request, project, state, "sources-blocked")
    blocked_report = state / "refresh_runs/sources-blocked.json"
    report = evaluate_claims(claim_request, blocked_report, project, state, "source-blocked")
    assert report["claims"][0]["status"] == "SOURCE_NOT_READY"


def test_frozen_run_rejects_changed_claims_or_source_report(tmp_path):
    project, state, source_report, claim_request, _ = fixture(tmp_path)
    first = evaluate_claims(claim_request, source_report, project, state, "claim-1")
    assert evaluate_claims(claim_request, source_report, project, state, "claim-1") == first
    change_claim(claim_request, statement="Deposits changed.")
    with pytest.raises(ValueError, match="run_id"):
        evaluate_claims(claim_request, source_report, project, state, "claim-1")


def test_new_run_rechecks_source_without_rewriting_old_report(tmp_path):
    project, state, source_report, claim_request, version = fixture(tmp_path)
    first = evaluate_claims(claim_request, source_report, project, state, "claim-1")
    (project / "data/raw/sha256" / version["raw_sha256"]).unlink()
    assert evaluate_claims(claim_request, source_report, project, state, "claim-1") == first
    newer = evaluate_claims(claim_request, source_report, project, state, "claim-2")
    assert newer["claims"][0]["status"] == "INVALID_SOURCE"


def test_run_id_rejects_another_source_report(tmp_path):
    project, state, source_report, claim_request, _ = fixture(tmp_path)
    evaluate_claims(claim_request, source_report, project, state, "claim-1")
    source_request = tmp_path / "second_source.json"
    source_request.write_text(json.dumps({
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "required_sources": [{"source_id": "SBI_Q1FY27", "max_age_days": 90}],
    }), encoding="utf-8")
    evaluate_sources(source_request, project, state, "sources-2")
    with pytest.raises(ValueError, match="run_id"):
        evaluate_claims(claim_request, state / "refresh_runs/sources-2.json",
                        project, state, "claim-1")


@pytest.mark.parametrize("damage", ["duplicate", "unsafe", "missing_locator", "type_list"])
def test_malformed_claim_request_fails_before_report(tmp_path, damage):
    project, state, source_report, claim_request, _ = fixture(tmp_path)
    request = json.loads(claim_request.read_text())
    if damage == "duplicate":
        request["claims"].append(request["claims"][0].copy())
    elif damage == "unsafe":
        request["claims"][0]["claim_id"] = "../escape"
    else:
        if damage == "missing_locator":
            request["claims"][0]["passage_locator"] = ""
        else:
            request["claims"][0]["claim_type"] = ["REPORTED_FACT"]
    claim_request.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(ValueError):
        evaluate_claims(claim_request, source_report, project, state, "bad")
    assert not (state / "claim_runs/bad.json").exists()


def test_mismatched_or_tampered_source_report_is_rejected(tmp_path):
    project, state, source_report, claim_request, _ = fixture(tmp_path)
    changed = json.loads(claim_request.read_text())
    changed["entity"] = "HDFC"
    claim_request.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="entity"):
        evaluate_claims(claim_request, source_report, project, state, "mismatch")
    changed["entity"] = "SBI"
    claim_request.write_text(json.dumps(changed), encoding="utf-8")
    source_report.write_text(source_report.read_text().replace("SOURCE_READY", "SOURCE_BLOCKED"))
    with pytest.raises(ValueError, match="digest"):
        evaluate_claims(claim_request, source_report, project, state, "tampered")


def test_changed_cutoff_and_tampered_frozen_claim_report_are_rejected(tmp_path):
    project, state, source_report, claim_request, _ = fixture(tmp_path)
    request = json.loads(claim_request.read_text())
    request["cutoff_timestamp"] = "2026-09-29T18:00:00+05:30"
    claim_request.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(ValueError, match="cutoff"):
        evaluate_claims(claim_request, source_report, project, state, "wrong-cutoff")
    request["cutoff_timestamp"] = CUTOFF
    claim_request.write_text(json.dumps(request), encoding="utf-8")
    evaluate_claims(claim_request, source_report, project, state, "claim-1")
    frozen = state / "claim_runs/claim-1.json"
    frozen.write_text(frozen.read_text().replace("LINEAGE_LINKED", "SOURCE_NOT_READY"))
    with pytest.raises(ValueError, match="digest"):
        evaluate_claims(claim_request, source_report, project, state, "claim-1")


def test_evaluate_claims_cli(tmp_path):
    project, state, source_report, claim_request, _ = fixture(tmp_path)
    result = subprocess.run([
        sys.executable, "-m", "src.kb_runtime", "evaluate-claims",
        "--claims", str(claim_request), "--source-report", str(source_report),
        "--project-dir", str(project), "--state-dir", str(state),
        "--run-id", "cli-claim",
    ], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "CLAIMS_BLOCKED"
