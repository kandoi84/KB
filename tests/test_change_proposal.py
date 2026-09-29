"""Immutable methodology proposals stay tied to replayed process failures."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from test_outcome_postmortem import _append, _due_packet, _setup
from test_case_snapshot import _write
from src.kb_runtime.outcome_postmortem import evaluate_due_case
from src.kb_runtime.change_proposal import register_change_proposal


def _ready(tmp_path, *, linked=True, change_type="PROMPT"):
    setup = _setup(tmp_path, value="12")
    project, state, catalog, case_paths, case_packet, _, _ = setup[0]
    due_path = tmp_path / "due.json"
    candidate_ids = []
    if linked:
        _append(tmp_path, setup)
        due = _due_packet(setup[1], process="BAD_PROCESS", error="DATA_ERROR",
                          reproducible=True)
        _write(due_path, due)
        evaluate_due_case(due_path, **setup[4])
        candidate_ids = ["post-1"]
    baseline = project / "baseline.txt"
    candidate = project / "candidate.txt"
    baseline.write_bytes(b"baseline version")
    candidate.write_bytes(b"candidate version")
    packet = {"proposal_id": "proposal-1", "change_type": change_type,
              "baseline_version": "version-1", "candidate_version": "version-2",
              "author_id": "analyst-1", "created_at": "2026-09-28T10:00:00+05:30",
              "changed_contract_paths": ["config/runtime_contracts/evidence_review.v1.json"],
              "rationale": "Correct a reproducible stale evidence process failure",
              "eval_candidate_ids": candidate_ids}
    packet_path = _write(tmp_path / "proposal.json", packet)
    replay = {**case_paths, "case_packet_path": case_packet, "project_dir": project,
              "catalog": catalog, "due_packet:post-1": due_path}
    kwargs = dict(baseline_artifact=baseline, candidate_artifact=candidate,
                  state_dir=state, case_replay_inputs=replay)
    return packet_path, packet, kwargs, state


@pytest.mark.parametrize("change_type", ["PROMPT", "WEIGHT", "SCHEMA", "RULE"])
def test_linked_proposal_is_immutable_and_artifacts_are_content_addressed(tmp_path, change_type):
    packet_path, packet, kwargs, state = _ready(tmp_path, change_type=change_type)
    receipt = register_change_proposal(packet_path, **kwargs)
    assert receipt["change_type"] == change_type
    assert receipt["eval_candidate_ids"] == ["post-1"]
    assert receipt["eval_candidates"][0]["candidate_digest"]
    assert receipt["baseline_sha256"] == hashlib.sha256(b"baseline version").hexdigest()
    assert receipt["candidate_sha256"] == hashlib.sha256(b"candidate version").hexdigest()
    assert receipt["publication_allowed"] is False
    assert receipt["live_decision_allowed"] is False
    assert receipt["promotion_status"] == "NOT_EVALUATED"
    stored = state / "change_artifacts/sha256" / receipt["candidate_sha256"]
    assert stored.read_bytes() == b"candidate version"
    path = state / "change_proposals/proposal-1.json"
    before = path.read_bytes()
    assert register_change_proposal(packet_path, **kwargs) == receipt
    assert path.read_bytes() == before
    packet["rationale"] = "A new interpretation of the same process failure"
    _write(packet_path, packet)
    with pytest.raises(ValueError, match="proposal|existing"):
        register_change_proposal(packet_path, **kwargs)


def test_unlinked_proposal_is_allowed_but_cannot_claim_an_eval_trigger(tmp_path):
    packet_path, _, kwargs, _ = _ready(tmp_path, linked=False)
    receipt = register_change_proposal(packet_path, **kwargs)
    assert receipt["eval_candidate_ids"] == []
    assert receipt["eval_candidates"] == []


def test_future_dated_proposal_is_rejected_before_receipt_or_artifact_store(tmp_path):
    packet_path, packet, kwargs, state = _ready(tmp_path, linked=False)
    packet["created_at"] = "2099-01-01T00:00:00+00:00"
    _write(packet_path, packet)
    with pytest.raises(ValueError, match="future"):
        register_change_proposal(packet_path, **kwargs)
    assert not (state / "change_proposals/proposal-1.json").exists()
    assert not (state / "change_artifacts").exists()


def test_forged_or_damaged_eval_candidate_fails_source_replay(tmp_path):
    packet_path, _, kwargs, state = _ready(tmp_path)
    candidate_path = state / "eval_candidates/post-1.json"
    candidate = json.loads(candidate_path.read_text())
    candidate["failure_invariant"] = "Invented rule from a rewritten candidate"
    candidate["candidate_digest"] = hashlib.sha256(json.dumps(
        {key: value for key, value in candidate.items() if key != "candidate_digest"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    _write(candidate_path, candidate)
    with pytest.raises(ValueError, match="candidate|postmortem"):
        register_change_proposal(packet_path, **kwargs)
    assert not (state / "change_proposals/proposal-1.json").exists()


def test_luck_or_surprise_cannot_be_a_change_trigger(tmp_path):
    packet_path, _, kwargs, state = _ready(tmp_path)
    due_path = kwargs["case_replay_inputs"]["due_packet:post-1"]
    due = json.loads(due_path.read_text())
    due["process_review"]["process_assessment"] = "GOOD_PROCESS"
    due["process_review"]["error_class"] = "UNAVOIDABLE_SURPRISE"
    due["process_review"]["reproducible_process_failure"] = False
    due["process_review"]["failure_invariant"] = None
    _write(due_path, due)
    with pytest.raises(ValueError, match="postmortem|candidate|process"):
        register_change_proposal(packet_path, **kwargs)
    assert not (state / "change_proposals/proposal-1.json").exists()


def test_artifact_swap_and_same_version_fail(tmp_path):
    packet_path, packet, kwargs, _ = _ready(tmp_path, linked=False)
    register_change_proposal(packet_path, **kwargs)
    kwargs["candidate_artifact"].write_bytes(b"changed later")
    with pytest.raises(ValueError, match="existing|proposal|artifact"):
        register_change_proposal(packet_path, **kwargs)
    packet["candidate_version"] = packet["baseline_version"]
    _write(packet_path, packet)
    with pytest.raises(ValueError, match="version"):
        register_change_proposal(packet_path, **kwargs)


def test_distinct_version_labels_cannot_hide_identical_bytes(tmp_path):
    packet_path, _, kwargs, state = _ready(tmp_path, linked=False)
    kwargs["candidate_artifact"].write_bytes(kwargs["baseline_artifact"].read_bytes())
    with pytest.raises(ValueError, match="artifact|identical"):
        register_change_proposal(packet_path, **kwargs)
    assert not (state / "change_proposals/proposal-1.json").exists()


@pytest.mark.parametrize("field,value", [
    ("proposal_id", "../escape"), ("baseline_version", "latest"),
    ("changed_contract_paths", ["../active.json"]),
    ("changed_contract_paths", ["/tmp/active.json"]),
    ("changed_contract_paths", ["config\\active.json"]),
    ("change_type", "COMMAND"),
    ("change_type", []),
])
def test_unsafe_packet_rejected(tmp_path, field, value):
    packet_path, packet, kwargs, state = _ready(tmp_path, linked=False)
    packet[field] = value
    _write(packet_path, packet)
    with pytest.raises(ValueError):
        register_change_proposal(packet_path, **kwargs)
    assert not (state / "change_proposals/proposal-1.json").exists()


def test_artifact_path_must_stay_in_project_or_state(tmp_path):
    packet_path, _, kwargs, _ = _ready(tmp_path, linked=False)
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside")
    kwargs["candidate_artifact"] = outside
    with pytest.raises(ValueError, match="artifact|root"):
        register_change_proposal(packet_path, **kwargs)


def test_concurrent_exact_same_id_registration_returns_one_receipt(tmp_path):
    packet_path, _, kwargs, state = _ready(tmp_path, linked=False)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: register_change_proposal(packet_path, **kwargs), range(2)))
    assert results[0] == results[1]
    assert json.loads((state / "change_proposals/proposal-1.json").read_text()) == results[0]
