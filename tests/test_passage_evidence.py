import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.kb_runtime.claim_lineage import evaluate_claims
from src.kb_runtime.passage_evidence import evaluate_passages
from src.kb_runtime.source_refresh import evaluate_sources
from src.kb_runtime.source_store import record_source


CUTOFF = "2026-09-28T18:00:00+05:30"


def inputs(tmp_path, raw_bytes=b"Deposits grew by 12 percent.\n"):
    project = tmp_path / "project"
    state = tmp_path / "state"
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({
        "source_id": "SBI_TEXT", "entity": "SBI",
        "source_kind": "COMPANY_PRESENTATION",
        "url": "https://example.org/sbi.txt", "source_date": "2026-08-07",
        "observed_at": "2026-09-28T10:00:00+05:30",
        "retrieved_at": "2026-09-28T10:05:00+05:30",
    }), encoding="utf-8")
    raw = tmp_path / "raw.txt"
    raw.write_bytes(raw_bytes)
    version = record_source(metadata, raw, project)
    request = tmp_path / "sources.json"
    request.write_text(json.dumps({
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "required_sources": [{"source_id": "SBI_TEXT", "max_age_days": 60}],
    }), encoding="utf-8")
    evaluate_sources(request, project, state, "source-1")
    claims = tmp_path / "claims.json"
    claims.write_text(json.dumps({
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "claims": [{
            "claim_id": "deposit-growth", "claim_type": "REPORTED_FACT",
            "statement": "Deposits grew.", "as_of": "2026-06-30",
            "source_id": "SBI_TEXT", "version_id": version["version_id"],
            "passage_locator": "sentence 1",
        }],
    }), encoding="utf-8")
    evaluate_claims(claims, state / "refresh_runs/source-1.json", project, state, "claim-1")
    packet = tmp_path / "packet.json"
    packet.write_text(json.dumps({
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "quotes": [{"claim_id": "deposit-growth", "verbatim_quote": "Deposits grew"}],
    }), encoding="utf-8")
    return project, state, packet, version


def evaluate(data, run_id="passage-1"):
    project, state, packet, _ = data
    return evaluate_passages(packet, state / "claim_runs/claim-1.json", project, state, run_id)


def test_quote_presence_is_frozen_without_semantic_approval(tmp_path):
    data = inputs(tmp_path)
    report = evaluate(data)
    result = report["results"][0]
    assert report["status"] == "PASSAGES_UNVERIFIED"
    assert report["publication_allowed"] is False
    assert result["status"] == "QUOTE_PRESENT"
    assert result["byte_offset"] == 0
    assert result["semantic_status"] == "UNVERIFIED"
    assert json.loads((data[1] / "passage_runs/passage-1.json").read_text()) == report
    assert evaluate(data) == report


def test_absent_and_missing_quotes_stay_open(tmp_path):
    data = inputs(tmp_path)
    packet = data[2]
    payload = json.loads(packet.read_text())
    payload["quotes"][0]["verbatim_quote"] = "Loan growth"
    packet.write_text(json.dumps(payload))
    assert evaluate(data)["results"][0]["status"] == "QUOTE_ABSENT"
    payload["quotes"] = []
    packet.write_text(json.dumps(payload))
    assert evaluate(data, "passage-2")["results"][0]["status"] == "MISSING_QUOTE"


@pytest.mark.parametrize("raw", [b"%PDF-1.7 Deposits grew", b"Deposits grew\x00", b"Deposits grew\xff"])
def test_unsupported_raw_does_not_approve_quote(tmp_path, raw):
    report = evaluate(inputs(tmp_path, raw))
    assert report["results"][0]["status"] == "UNSUPPORTED_FORMAT"
    assert report["publication_allowed"] is False


def test_tampered_raw_is_blocked(tmp_path):
    data = inputs(tmp_path)
    blob = data[0] / "data/raw/sha256" / data[3]["raw_sha256"]
    blob.write_bytes(b"Deposits grew by 99 percent.\n")
    assert evaluate(data)["results"][0]["status"] == "INVALID_SOURCE"


def test_replay_rejects_changed_input_and_tampered_report(tmp_path):
    data = inputs(tmp_path)
    evaluate(data)
    packet = data[2]
    payload = json.loads(packet.read_text())
    payload["quotes"][0]["verbatim_quote"] = "by 12 percent"
    packet.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="run_id cannot be reused"):
        evaluate(data)
    frozen = data[1] / "passage_runs/passage-1.json"
    report = json.loads(frozen.read_text())
    report["publication_allowed"] = True
    frozen.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="differs from its digest"):
        evaluate(data)


def test_packet_rejects_unknown_or_duplicate_claims(tmp_path):
    data = inputs(tmp_path)
    packet = data[2]
    payload = json.loads(packet.read_text())
    payload["quotes"][0]["claim_id"] = "unknown"
    packet.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="duplicate or unknown"):
        evaluate(data)
    payload["quotes"] = [{"claim_id": "deposit-growth", "verbatim_quote": "Deposits"}] * 2
    packet.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="duplicate or unknown"):
        evaluate(data)


def test_evaluate_passages_cli(tmp_path):
    project, state, packet, _ = inputs(tmp_path)
    result = subprocess.run([
        sys.executable, "-m", "src.kb_runtime", "evaluate-passages",
        "--packet", str(packet), "--claim-report", str(state / "claim_runs/claim-1.json"),
        "--project-dir", str(project), "--state-dir", str(state), "--run-id", "cli-1",
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["results"][0]["status"] == "QUOTE_PRESENT"


def test_cutoff_mismatch_is_rejected(tmp_path):
    data = inputs(tmp_path)
    packet = data[2]
    payload = json.loads(packet.read_text())
    payload["cutoff_timestamp"] = "2026-09-29T18:00:00+05:30"
    packet.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="cutoff differs"):
        evaluate(data)


def test_blocked_lineage_stays_blocked(tmp_path):
    project, state, packet, _ = inputs(tmp_path)
    claims = tmp_path / "late-claims.json"
    payload = {
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "claims": [{
            "claim_id": "deposit-growth", "claim_type": "REPORTED_FACT",
            "statement": "Deposits grew.", "as_of": "2026-10-01",
            "source_id": "SBI_TEXT", "version_id": "0" * 64,
            "passage_locator": "sentence 1",
        }],
    }
    claims.write_text(json.dumps(payload))
    evaluate_claims(claims, state / "refresh_runs/source-1.json", project, state, "claim-2")
    report = evaluate_passages(packet, state / "claim_runs/claim-2.json", project, state, "passage-2")
    assert report["results"][0]["status"] == "LINEAGE_BLOCKED"


def test_oversized_text_is_unsupported(tmp_path):
    data = inputs(tmp_path, b"Deposits grew" + b"a" * (16 * 1024 * 1024))
    assert evaluate(data)["results"][0]["status"] == "UNSUPPORTED_FORMAT"


def test_control_character_is_unsupported(tmp_path):
    data = inputs(tmp_path, "Deposits grew\u0085".encode("utf-8"))
    assert evaluate(data)["results"][0]["status"] == "UNSUPPORTED_FORMAT"


def test_replay_rejects_self_consistent_safety_edit(tmp_path):
    data = inputs(tmp_path)
    evaluate(data)
    frozen = data[1] / "passage_runs/passage-1.json"
    report = json.loads(frozen.read_text())
    report["publication_allowed"] = True
    report["status"] = "PASSAGES_APPROVED"
    report["results"][0]["semantic_status"] = "APPROVED"
    report.pop("report_id")
    from src.kb_runtime.passage_evidence import _hash_json
    report["report_id"] = _hash_json(report)
    frozen.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="safety fields"):
        evaluate(data)


def test_replay_rejects_different_run_id(tmp_path):
    data = inputs(tmp_path)
    evaluate(data)
    first = data[1] / "passage_runs/passage-1.json"
    second = data[1] / "passage_runs/passage-2.json"
    second.write_bytes(first.read_bytes())
    with pytest.raises(ValueError, match="run_id differs"):
        evaluate(data, "passage-2")


def test_lone_surrogate_quote_is_invalid_input(tmp_path):
    data = inputs(tmp_path)
    packet = data[2]
    payload = json.loads(packet.read_text())
    payload["quotes"][0]["verbatim_quote"] = "\ud800"
    packet.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="valid UTF-8"):
        evaluate(data)
