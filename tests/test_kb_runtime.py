import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def hdfc_input(tmp_path):
    """Synthetic HDFC data tests orchestration, not an investment opinion."""
    data = {
        "entity": "HDFC Bank",
        "cutoff_timestamp": "2026-09-27T17:00:00+05:30",
        "source_ids": ["TEST_EXCHANGE_FILING_1"],
        "test_fixture": True,
        "research": {
            "price": 735.6,
            "benchmark": "NIFTY 50",
            "business_quality": "Test assessment",
            "quality_trajectory": "Test assessment",
            "market_implied_expectations": "Test assumption",
            "most_likely_path": "Test assumption",
            "expectation_gap": "Test assumption",
            "valuation": {"fair_value": 930},
            "valuation_fragility": "Test assessment",
            "multiple_compression_risk": "Test assessment",
            "catalysts": ["Test catalyst"],
            "probabilities": {"test_debate": 0.65},
            "timing": "12 months",
            "downside_mechanism": "Test downside",
            "premortem": "Test premortem",
            "score": 76.9,
            "score_error_band": 6,
            "evidence_grade": "B",
            "poker_hand": "TT",
            "poker_draw": "No draw",
            "critical_gaps": ["Test gap disclosed"],
            "falsifiers": ["Test falsifier"],
        },
    }
    path = tmp_path / "hdfc.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def invoke(path, state_dir, *extra):
    return subprocess.run(
        [sys.executable, "-m", "src.kb_runtime", "company-research",
         "--entity", "HDFC Bank", "--input", str(path),
         "--state-dir", str(state_dir), "--run-id", "hdfc-test", *extra],
        cwd=ROOT, capture_output=True, text=True,
    )


def test_hdfc_cli_persists_manifest_and_frozen_case(hdfc_input, tmp_path):
    state_dir = tmp_path / "state"
    result = invoke(hdfc_input, state_dir)
    assert result.returncode == 0, result.stderr

    manifest = json.loads((state_dir / "runs/hdfc-test/manifest.json").read_text())
    state = json.loads((state_dir / "runs/hdfc-test/state.json").read_text())
    case = json.loads((state_dir / "cases/hdfc-test.json").read_text())
    assert state["status"] == "CASE_OPENED"
    assert manifest["publication_status"] == "COMPLETE"
    assert manifest["source_cutoff"] == "2026-09-27T17:00:00+05:30"
    assert case["inception"]["entity"] == "HDFC Bank"
    assert case["inception"]["snapshot_id"] == manifest["snapshot_id"]
    assert case["inception"]["test_fixture"] is True


def test_failed_case_creation_resumes_without_repeating_completed_steps(hdfc_input, tmp_path):
    state_dir = tmp_path / "state"
    first = invoke(hdfc_input, state_dir, "--fail-once", "CASE_OPENED")
    assert first.returncode != 0
    state_path = state_dir / "runs/hdfc-test/state.json"
    state = json.loads(state_path.read_text())
    manifest_path = state_dir / "runs/hdfc-test/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert state["status"] == "FAILED_RUNTIME"
    assert state["completed_steps"][-1] == "PUBLISHED"
    assert manifest["publication_status"] == "PENDING_CASE"
    assert not (state_dir / "cases/hdfc-test.json").exists()
    completed_at = state["completed_at"].copy()

    second = invoke(hdfc_input, state_dir, "--fail-once", "CASE_OPENED")
    assert second.returncode == 0, second.stderr
    resumed = json.loads(state_path.read_text())
    assert resumed["status"] == "CASE_OPENED"
    assert resumed["completed_at"]["PUBLISHED"] == completed_at["PUBLISHED"]
    assert len(resumed["completed_steps"]) == len(set(resumed["completed_steps"]))


def test_missing_research_blocks_publication(hdfc_input, tmp_path):
    data = json.loads(hdfc_input.read_text())
    del data["research"]["premortem"]
    hdfc_input.write_text(json.dumps(data))
    state_dir = tmp_path / "state"
    result = invoke(hdfc_input, state_dir)
    assert result.returncode != 0
    state = json.loads((state_dir / "runs/hdfc-test/state.json").read_text())
    assert state["status"] == "BLOCKED_VALIDATION"
    assert not (state_dir / "cases").exists()


def test_completed_run_recovers_missing_case(hdfc_input, tmp_path):
    state_dir = tmp_path / "state"
    assert invoke(hdfc_input, state_dir).returncode == 0
    case_path = state_dir / "cases/hdfc-test.json"
    case_path.unlink()

    result = invoke(hdfc_input, state_dir)
    assert result.returncode == 0, result.stderr
    assert case_path.exists()
    assert json.loads(case_path.read_text())["inception"]["entity"] == "HDFC Bank"
