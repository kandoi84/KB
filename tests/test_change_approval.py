"""Human change decisions cannot promote a synthetic regression."""

import json

import pytest

from test_case_snapshot import _write
from test_change_regression import _run_fixture
from src.kb_runtime.change_regression import run_change_regression
from src.kb_runtime.change_approval import classify_change_scope, record_change_approval


def _approval_fixture(tmp_path, *, scope="STRUCTURAL", decision="REJECTED"):
    run_path, run_packet, _, _, kwargs, state = _run_fixture(tmp_path)
    run = run_change_regression(run_path, **kwargs)
    approval = {"approval_id": "approval-1", "proposal_id": run_packet["proposal_id"],
                "proposal_digest": run_packet["proposal_digest"],
                "regression_run_id": run_packet["run_id"],
                "regression_digest": run["regression_digest"],
                "baseline_sha256": run_packet["baseline_sha256"],
                "candidate_sha256": run_packet["candidate_sha256"],
                "reviewer_id": "reviewer-2", "decided_at": "2026-09-28T12:00:00+05:30",
                "decision": decision, "scope": scope,
                "rationale": "The candidate requires more independent validation before adoption"}
    path = _write(tmp_path / "approval.json", approval)
    return path, approval, state


def test_rejection_is_immutable_and_never_activates(tmp_path):
    packet_path, _, state = _approval_fixture(tmp_path)
    active = tmp_path / "active-version.txt"
    active.write_bytes(b"version-1")
    receipt = record_change_approval(packet_path, state_dir=state)
    assert receipt["approval_status"] == "REJECTED"
    assert receipt["scope"] == "STRUCTURAL"
    assert receipt["diff_sha256"]
    assert receipt["publication_allowed"] is False
    assert receipt["live_decision_allowed"] is False
    assert receipt["promotion_status"] == "NOT_EVALUATED"
    assert active.read_bytes() == b"version-1"
    stored = state / "change_approvals/approval-1.json"
    prior = stored.read_bytes()
    assert record_change_approval(packet_path, state_dir=state) == receipt
    assert stored.read_bytes() == prior


def test_changed_same_approval_id_conflicts(tmp_path):
    packet_path, packet, state = _approval_fixture(tmp_path)
    record_change_approval(packet_path, state_dir=state)
    packet["rationale"] = "A different human reason for rejecting this exact proposal"
    _write(packet_path, packet)
    with pytest.raises(ValueError, match="approval|existing"):
        record_change_approval(packet_path, state_dir=state)


def test_future_dated_decision_rejected(tmp_path):
    packet_path, packet, state = _approval_fixture(tmp_path)
    packet["decided_at"] = "2099-01-01T00:00:00+00:00"
    _write(packet_path, packet)
    with pytest.raises(ValueError, match="future"):
        record_change_approval(packet_path, state_dir=state)
    assert not (state / "change_approvals/approval-1.json").exists()


def test_synthetic_mechanics_and_forged_pass_cannot_be_approved(tmp_path):
    packet_path, packet, state = _approval_fixture(tmp_path, decision="APPROVED")
    with pytest.raises(ValueError, match="approval|regression|trusted"):
        record_change_approval(packet_path, state_dir=state)
    regression_path = state / "change_regressions/run-1.json"
    forged = json.loads(regression_path.read_text())
    forged["status"] = "REGRESSION_PASS_FOR_REVIEW"
    from src.kb_runtime.case_snapshot import _digest
    forged["regression_digest"] = _digest({key: value for key, value in forged.items()
                                            if key != "regression_digest"})
    _write(regression_path, forged)
    packet["regression_digest"] = forged["regression_digest"]
    _write(packet_path, packet)
    with pytest.raises(ValueError, match="approval|trusted|regression"):
        record_change_approval(packet_path, state_dir=state)
    assert not (state / "change_approvals/approval-1.json").exists()


@pytest.mark.parametrize("damage", ["missing_run", "stale_proposal", "swapped_candidate",
                                    "bad_decision_time", "self_review", "wrong_scope"])
def test_invalid_approval_link_or_scope_fails(tmp_path, damage):
    packet_path, packet, state = _approval_fixture(tmp_path)
    if damage == "missing_run":
        (state / "change_regressions/run-1.json").unlink()
    elif damage == "stale_proposal":
        packet["proposal_digest"] = "0" * 64
    elif damage == "swapped_candidate":
        packet["candidate_sha256"] = "0" * 64
    elif damage == "bad_decision_time":
        packet["decided_at"] = "2026-01-01T00:00:00+05:30"
    elif damage == "self_review":
        packet["decision"] = "APPROVED"
        packet["reviewer_id"] = "analyst-1"
    else:
        packet["scope"] = "NONSTRUCTURAL"
    _write(packet_path, packet)
    with pytest.raises(ValueError):
        record_change_approval(packet_path, state_dir=state)
    assert not (state / "change_approvals/approval-1.json").exists()


def test_unknown_or_dangerous_change_scope_is_structural(tmp_path):
    packet_path, packet, state = _approval_fixture(tmp_path)
    proposal_path = state / "change_proposals/proposal-1.json"
    proposal = json.loads(proposal_path.read_text())
    assert proposal["change_type"] == "PROMPT"
    assert "runtime_contracts" in proposal["changed_contract_paths"][0]
    assert record_change_approval(packet_path, state_dir=state)["scope"] == "STRUCTURAL"


@pytest.mark.parametrize("change_type,path,expected", [
    ("PROMPT", "config/prompts/display/research_summary.txt", "NONSTRUCTURAL"),
    ("PROMPT", "config/prompts/decision/ranking.txt", "STRUCTURAL"),
    ("WEIGHT", "config/prompts/display/research_summary.txt", "STRUCTURAL"),
    ("SCHEMA", "config/prompts/display/research_summary.txt", "STRUCTURAL"),
    ("RULE", "config/prompts/display/research_summary.txt", "STRUCTURAL"),
    ("PROMPT", "unknown/path.txt", "STRUCTURAL"),
])
def test_scope_comes_from_allowlisted_path_and_actual_diff(change_type, path, expected):
    assert classify_change_scope(change_type, [path], b"Old display", b"New display") == expected
    assert classify_change_scope(change_type, [path], b"same", b"same") == "STRUCTURAL"


def test_malformed_decision_rejected(tmp_path):
    packet_path, packet, state = _approval_fixture(tmp_path)
    packet["decision"] = []
    _write(packet_path, packet)
    with pytest.raises(ValueError):
        record_change_approval(packet_path, state_dir=state)
