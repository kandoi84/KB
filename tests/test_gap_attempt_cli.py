import json
import subprocess
import sys
from pathlib import Path

from src.kb_runtime.claim_lineage import evaluate_claims
from src.kb_runtime.source_refresh import evaluate_sources


ROOT = Path(__file__).resolve().parents[1]
CUTOFF = "2026-09-28T18:00:00+05:30"
URL = "https://www.bseindia.com/filings/sbi.pdf"


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _fixture(tmp_path, classification):
    project, state = tmp_path / "project", tmp_path / "state"
    source_request = _write(tmp_path / "source.json", {
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "required_sources": [{"source_id": "SBI_FILING", "max_age_days": 60}],
    })
    source = evaluate_sources(source_request, project, state, "source-one")
    claim_request = _write(tmp_path / "claims.json", {
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "claims": [{"claim_id": "deposit", "claim_type": "REPORTED_FACT",
                    "statement": "Deposit growth", "as_of": "2026-06-30",
                    "source_id": "SBI_FILING", "version_id": "0" * 64,
                    "passage_locator": "page 2"}],
    })
    claim = evaluate_claims(claim_request, state / "refresh_runs/source-one.json",
                            project, state, "claim-one")
    packet = _write(tmp_path / "packet.json", {
        "gap_id": claim["gaps"][0]["gap_id"], "claim_report_id": claim["report_id"],
        "source_report_id": source["report_id"], "entity": "SBI",
        "cutoff_timestamp": CUTOFF, "classification": classification,
        "operator_id": "researcher-1", "reviewer_id": "reviewer-1",
        "reviewed_at": "2026-09-28T23:00:00+05:30",
        "classification_reason": "Reviewed primary source gap",
        "adapter_id": "reviewed_local_primary_v1", "source_id": "SBI_FILING",
        "source_url": URL, "rights_use": "LOCAL_RESEARCH_COLLECTION_ALLOWED",
        "rights_evidence_ref": "agreement-2026-1", "rights_scope_actor": "researcher-1",
        "rights_scope_method": "manual local download",
        "rights_scope_storage": "local KB raw store",
        "rights_scope_purpose": "internal equity research",
        "rights_reviewed_by": "reviewer-1",
        "rights_reviewed_at": "2026-09-28T23:00:00+05:30",
    })
    metadata = _write(tmp_path / "metadata.json", {
        "source_id": "SBI_FILING", "entity": "SBI", "source_kind": "EXCHANGE_FILING",
        "url": URL, "source_date": "2026-09-27",
        "observed_at": "2026-09-28T23:00:00+05:30",
        "retrieved_at": "2026-09-28T23:00:00+05:30",
    })
    raw = tmp_path / "filing.pdf"
    raw.write_bytes(b"synthetic fixture only")
    args = [sys.executable, "-m", "src.kb_runtime", "attempt-gap",
            "--packet", str(packet),
            "--claim-report", str(state / "claim_runs/claim-one.json"),
            "--source-report", str(state / "refresh_runs/source-one.json"),
            "--source-request", str(source_request), "--claims", str(claim_request),
            "--project-dir", str(project), "--state-dir", str(state),
            "--attempt-id", "attempt-one"]
    return project, state, args, raw, metadata


def test_cli_records_local_primary_source_and_keeps_gap_open(tmp_path):
    project, state, args, raw, metadata = _fixture(tmp_path, "PUBLIC_PRIMARY_MISSING")
    completed = subprocess.run(args + ["--raw-file", str(raw), "--metadata", str(metadata)],
                               cwd=ROOT, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    receipt = json.loads(completed.stdout)
    assert receipt["status"] == "RECORDED"
    assert receipt["gap_status"] == "OPEN"
    assert receipt["publication_allowed"] is False
    assert (project / "data/registry/sources/SBI_FILING" / f'{receipt["version_id"]}.json').is_file()
    assert (state / "gap_attempts/attempt-one/result.json").is_file()


def test_cli_blocks_internal_gap_without_raw_or_network(tmp_path):
    project, _, args, _, _ = _fixture(tmp_path, "INTERNAL_RESEARCH")
    completed = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    receipt = json.loads(completed.stdout)
    assert receipt["status"] == "HUMAN_WORK_REQUIRED"
    assert receipt["version_id"] is None
    assert receipt["publication_allowed"] is False
    assert not (project / "data/registry/sources/SBI_FILING").exists()
