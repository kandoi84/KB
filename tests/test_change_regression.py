"""Paired regression checks against frozen data-only proposals."""

import hashlib
import json

import pytest

from test_change_proposal import _ready
from test_case_snapshot import _write
from src.kb_runtime.change_proposal import register_change_proposal
from src.kb_runtime.change_regression import run_change_regression


class DeterministicAdapter:
    runner_id = "test-runner"
    runner_version = "runner-v1"
    source_sha256 = "a" * 64
    supported_change_types = frozenset({"PROMPT"})
    test_only = True

    def evaluate(self, artifact_bytes, frozen_case):
        digest = hashlib.sha256(artifact_bytes).hexdigest()
        return {"artifact_sha256": digest, "passed": True,
                "score": 2 if artifact_bytes == b"candidate version" else 1,
                "invariants": {"no_future_data": True},
                "guardrail_violations": []}


def _run_fixture(tmp_path, *, dataset_kind="SYNTHETIC_FIXTURE", cases=20):
    proposal_path, _, proposal_kwargs, state = _ready(tmp_path, linked=False)
    proposal = register_change_proposal(proposal_path, **proposal_kwargs)
    project = proposal_kwargs["case_replay_inputs"]["project_dir"]
    entries = []
    for index in range(cases):
        case_id = f"reg-{index:02d}"
        payload = {"case_id": case_id, "cutoff_timestamp": "2026-09-28T18:00:00+05:30",
                   "decision_inputs": {"claim": f"claim-{index}"}}
        path = _write(project / f"{case_id}.json", payload)
        entries.append({"case_id": case_id, "inception_cutoff": payload["cutoff_timestamp"],
                        "input_path": path.name,
                        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "expected_invariants": ["no_future_data"], "hard": True})
    manifest = {"regression_set_id": "regression-set-1", "dataset_version": "dataset-v1",
                "rubric_version": "rubric-v1", "dataset_kind": dataset_kind,
                "reviewer_id": "reviewer-1" if dataset_kind == "REVIEWED_REAL" else None,
                "reviewed_at": ("2027-07-16T12:00:00+05:30"
                                if dataset_kind == "REVIEWED_REAL" else None),
                "thresholds": {"minimum_cases": 20, "maximum_new_hard_failures": 0,
                               "minimum_score_delta": 0}, "cases": entries}
    manifest_path = _write(project / "regression-manifest.json", manifest)
    packet = {"run_id": "run-1", "proposal_id": proposal["proposal_id"],
              "proposal_digest": proposal["proposal_digest"],
              "manifest_path": manifest_path.name,
              "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
              "runner_id": "test-runner", "runner_version": "runner-v1",
              "runner_source_sha256": "a" * 64,
              "baseline_sha256": proposal["baseline_sha256"],
              "candidate_sha256": proposal["candidate_sha256"]}
    packet_path = _write(tmp_path / "regression-run.json", packet)
    kwargs = dict(state_dir=state, project_dir=project,
                  adapter_registry={"test-runner": DeterministicAdapter()})
    return packet_path, packet, manifest_path, manifest, kwargs, state


def test_synthetic_paired_regression_is_mechanics_only_and_immutable(tmp_path):
    packet_path, _, _, _, kwargs, state = _run_fixture(tmp_path)
    result = run_change_regression(packet_path, **kwargs)
    assert result["status"] == "MECHANICS_PASS"
    assert result["case_count"] == 20
    assert result["baseline_passed"] == 20
    assert result["candidate_passed"] == 20
    assert result["new_hard_failures"] == 0
    assert result["cases"][0]["baseline"]["score"] == 1
    assert result["cases"][0]["candidate"]["score"] == 2
    assert result["publication_allowed"] is False
    assert result["live_decision_allowed"] is False
    assert result["promotion_status"] == "NOT_EVALUATED"
    receipt = state / "change_regressions/run-1.json"
    prior = receipt.read_bytes()
    assert run_change_regression(packet_path, **kwargs) == result
    assert receipt.read_bytes() == prior


def test_missing_executor_is_explicitly_blocked(tmp_path):
    packet_path, _, _, _, kwargs, _ = _run_fixture(tmp_path)
    kwargs["adapter_registry"] = {}
    result = run_change_regression(packet_path, **kwargs)
    assert result["status"] == "BLOCKED_NO_EXECUTOR"
    assert result["cases"] == []


@pytest.mark.parametrize("mutation", ["duplicate", "too_few", "mixed_kind", "future_outcome",
                                       "changed_input", "changed_manifest"])
def test_bad_manifest_or_frozen_input_fails_closed(tmp_path, mutation):
    packet_path, packet, manifest_path, manifest, kwargs, state = _run_fixture(tmp_path)
    if mutation == "duplicate":
        manifest["cases"][1]["case_id"] = manifest["cases"][0]["case_id"]
    elif mutation == "too_few":
        manifest["cases"] = manifest["cases"][:-1]
    elif mutation == "mixed_kind":
        manifest["cases"][0]["dataset_kind"] = "REVIEWED_REAL"
    elif mutation == "future_outcome":
        path = kwargs["project_dir"] / manifest["cases"][0]["input_path"]
        payload = json.loads(path.read_text())
        payload["observed_value_decimal"] = "12"
        _write(path, payload)
        manifest["cases"][0]["input_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    elif mutation == "changed_input":
        path = kwargs["project_dir"] / manifest["cases"][0]["input_path"]
        _write(path, {"case_id": "reg-00"})
    else:
        manifest["rubric_version"] = "rubric-v2"
    if mutation != "changed_input":
        _write(manifest_path, manifest)
        if mutation != "changed_manifest":
            packet["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            _write(packet_path, packet)
    with pytest.raises(ValueError):
        run_change_regression(packet_path, **kwargs)
    assert not (state / "change_regressions/run-1.json").exists()


def test_changed_runner_and_swapped_artifact_fail(tmp_path):
    packet_path, packet, _, _, kwargs, state = _run_fixture(tmp_path)
    kwargs["adapter_registry"]["test-runner"].source_sha256 = "b" * 64
    with pytest.raises(ValueError, match="runner"):
        run_change_regression(packet_path, **kwargs)
    kwargs["adapter_registry"]["test-runner"].source_sha256 = "a" * 64
    (state / "change_artifacts/sha256" / packet["candidate_sha256"]).write_bytes(b"swapped")
    with pytest.raises(ValueError, match="artifact"):
        run_change_regression(packet_path, **kwargs)


def test_stored_artifact_symlink_is_rejected_even_when_bytes_match(tmp_path):
    packet_path, packet, _, _, kwargs, state = _run_fixture(tmp_path)
    outside = tmp_path / "external-artifact.txt"
    outside.write_bytes(b"candidate version")
    stored = state / "change_artifacts/sha256" / packet["candidate_sha256"]
    stored.unlink()
    stored.symlink_to(outside)
    with pytest.raises(ValueError, match="artifact"):
        run_change_regression(packet_path, **kwargs)


def test_runner_ignoring_candidate_bytes_cannot_pass(tmp_path):
    packet_path, _, _, _, kwargs, _ = _run_fixture(tmp_path)
    class IgnoringAdapter(DeterministicAdapter):
        def evaluate(self, artifact_bytes, frozen_case):
            return {"artifact_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
                    "passed": True, "score": 1,
                    "invariants": {"no_future_data": True}, "guardrail_violations": []}
    kwargs["adapter_registry"]["test-runner"] = IgnoringAdapter()
    result = run_change_regression(packet_path, **kwargs)
    assert result["status"] == "BLOCKED_NO_ARTIFACT_EFFECT"


def test_baseline_failure_and_real_gold_test_adapter_cannot_pass(tmp_path):
    packet_path, _, _, _, kwargs, _ = _run_fixture(tmp_path)
    class FailingBaseline(DeterministicAdapter):
        def evaluate(self, artifact_bytes, frozen_case):
            result = super().evaluate(artifact_bytes, frozen_case)
            if artifact_bytes == b"baseline version":
                result["passed"] = False
            return result
    kwargs["adapter_registry"]["test-runner"] = FailingBaseline()
    result = run_change_regression(packet_path, **kwargs)
    assert result["status"] == "FAILED_BASELINE"

    other = tmp_path / "real"
    other.mkdir()
    packet_path, _, _, _, kwargs, _ = _run_fixture(other, dataset_kind="REVIEWED_REAL")
    kwargs["adapter_registry"]["test-runner"].test_only = False
    kwargs["adapter_registry"]["test-runner"].production_ready = True
    result = run_change_regression(packet_path, **kwargs)
    assert result["status"] == "BLOCKED_NO_PRODUCTION_ADAPTER"


def test_adapter_cannot_mutate_frozen_case_between_paired_calls(tmp_path):
    packet_path, _, _, _, kwargs, _ = _run_fixture(tmp_path)
    class MutatingAdapter(DeterministicAdapter):
        def evaluate(self, artifact_bytes, frozen_case):
            assert "tampered" not in frozen_case["decision_inputs"]
            frozen_case["decision_inputs"]["tampered"] = True
            return super().evaluate(artifact_bytes, frozen_case)
    kwargs["adapter_registry"]["test-runner"] = MutatingAdapter()
    result = run_change_regression(packet_path, **kwargs)
    assert result["status"] == "MECHANICS_PASS"


def test_hard_case_score_regression_is_not_hidden_by_aggregate_gain(tmp_path):
    packet_path, _, _, _, kwargs, _ = _run_fixture(tmp_path)
    class MixedScoreAdapter(DeterministicAdapter):
        def evaluate(self, artifact_bytes, frozen_case):
            result = super().evaluate(artifact_bytes, frozen_case)
            if artifact_bytes == b"candidate version":
                result["score"] = 0 if frozen_case["case_id"] == "reg-00" else 3
            return result
    kwargs["adapter_registry"]["test-runner"] = MixedScoreAdapter()
    result = run_change_regression(packet_path, **kwargs)
    assert result["status"] == "FAILED"


def test_future_dated_decision_input_rejected_even_with_matching_hash(tmp_path):
    packet_path, packet, manifest_path, manifest, kwargs, state = _run_fixture(tmp_path)
    entry = manifest["cases"][0]
    path = kwargs["project_dir"] / entry["input_path"]
    payload = json.loads(path.read_text())
    payload["decision_inputs"]["source"] = {"observed_at": "2027-07-10T09:00:00+05:30"}
    _write(path, payload)
    entry["input_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    _write(manifest_path, manifest)
    packet["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    _write(packet_path, packet)
    with pytest.raises(ValueError, match="future|cutoff"):
        run_change_regression(packet_path, **kwargs)
    assert not (state / "change_regressions/run-1.json").exists()


def test_changed_same_run_id_conflicts_and_active_file_is_untouched(tmp_path):
    packet_path, packet, _, _, kwargs, state = _run_fixture(tmp_path)
    active = kwargs["project_dir"] / "active-version.txt"
    active.write_bytes(b"version-1")
    run_change_regression(packet_path, **kwargs)
    assert active.read_bytes() == b"version-1"
    packet["run_id"] = "run-1"
    packet["runner_source_sha256"] = "b" * 64
    _write(packet_path, packet)
    with pytest.raises(ValueError):
        run_change_regression(packet_path, **kwargs)
    assert active.read_bytes() == b"version-1"
