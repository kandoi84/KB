"""Read-only paired regression receipts for pinned methodology artifacts."""

import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Mapping, Protocol

from .case_snapshot import _digest, _id, _read
from .identity_store import _timestamp
from .outcome_postmortem import SAFETY, _link_once, _path
from .retrieval_eval import SHA256


class RegressionAdapter(Protocol):
    runner_id: str
    runner_version: str
    source_sha256: str
    supported_change_types: frozenset[str]

    def evaluate(self, artifact_bytes: bytes, frozen_case: dict) -> dict: ...


PACKET_FIELDS = {"run_id", "proposal_id", "proposal_digest", "manifest_path",
                 "manifest_sha256", "runner_id", "runner_version", "runner_source_sha256",
                 "baseline_sha256", "candidate_sha256"}
MANIFEST_FIELDS = {"regression_set_id", "dataset_version", "rubric_version", "dataset_kind",
                   "reviewer_id", "reviewed_at", "thresholds", "cases"}
CASE_FIELDS = {"case_id", "inception_cutoff", "input_path", "input_sha256",
               "expected_invariants", "hard"}
THRESHOLD_FIELDS = {"minimum_cases", "maximum_new_hard_failures", "minimum_score_delta"}
OUTPUT_FIELDS = {"artifact_sha256", "passed", "score", "invariants", "guardrail_violations"}
LEAK_KEYS = {"outcome", "actual", "observed_value_decimal", "result_status", "quadrant",
             "postmortem", "observation_event", "future_outcome"}


def _sha(value, label):
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise ValueError(f"{label} is invalid")
    return value


def _relative(path, root, label):
    if not isinstance(path, str) or not path or "\\" in path or Path(path).is_absolute():
        raise ValueError(f"{label} path is invalid")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts) or ":" in parts[0]:
        raise ValueError(f"{label} path escapes project root")
    root = Path(root).resolve()
    found = root / path
    if not found.resolve().is_relative_to(root) or found.is_symlink() or not found.is_file():
        raise ValueError(f"{label} path is missing or escapes project root")
    return found


def _bytes(path, expected, label):
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise ValueError(f"{label} is missing") from exc
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"{label} digest differs")
    return data


def _packet(value):
    if not isinstance(value, dict) or set(value) != PACKET_FIELDS:
        raise ValueError("regression packet fields are invalid")
    for field in ("run_id", "proposal_id", "runner_id", "runner_version"):
        _id(value[field], field)
    for field in ("proposal_digest", "manifest_sha256", "runner_source_sha256",
                  "baseline_sha256", "candidate_sha256"):
        _sha(value[field], field)
    if value["baseline_sha256"] == value["candidate_sha256"]:
        raise ValueError("regression artifacts must differ")
    return value


def _proposal(packet, state_dir):
    path = _path(state_dir, "change_proposals", packet["proposal_id"])
    if not path.is_file():
        raise ValueError("proposal receipt is missing")
    proposal = _read(path, "proposal receipt")
    if (proposal.get("proposal_id") != packet["proposal_id"]
            or proposal.get("proposal_digest") != packet["proposal_digest"]
            or _digest({k: v for k, v in proposal.items() if k != "proposal_digest"})
            != packet["proposal_digest"]
            or proposal.get("baseline_sha256") != packet["baseline_sha256"]
            or proposal.get("candidate_sha256") != packet["candidate_sha256"]
            or any(proposal.get(key) != value for key, value in SAFETY.items())):
        raise ValueError("proposal receipt or artifact identity differs")
    baseline = _stored_artifact(state_dir, packet["baseline_sha256"], "baseline artifact")
    candidate = _stored_artifact(state_dir, packet["candidate_sha256"], "candidate artifact")
    return proposal, baseline, candidate


def _stored_artifact(state_dir, digest, label):
    root = Path(state_dir).resolve()
    path = root / "change_artifacts/sha256" / digest
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError(f"{label} path escapes state root")
    return _bytes(path, digest, label)


def _has_leak(value):
    if isinstance(value, dict):
        return any(key in LEAK_KEYS or _has_leak(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_has_leak(item) for item in value)
    return False


def _has_future(value, cutoff):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"observed_at", "recorded_at", "published_at", "first_seen_at",
                       "reviewed_at", "retrieved_at"}:
                if _timestamp(item, key) > cutoff:
                    return True
            elif _has_future(item, cutoff):
                return True
    elif isinstance(value, list):
        return any(_has_future(item, cutoff) for item in value)
    return False


def _manifest(packet, project_dir):
    path = _relative(packet["manifest_path"], project_dir, "manifest")
    raw = _bytes(path, packet["manifest_sha256"], "manifest")
    try:
        manifest = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("manifest must be JSON") from exc
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_FIELDS:
        raise ValueError("manifest fields are invalid")
    for field in ("regression_set_id", "dataset_version", "rubric_version"):
        _id(manifest[field], field)
    kind = manifest["dataset_kind"]
    if not isinstance(kind, str) or kind not in {"SYNTHETIC_FIXTURE", "REVIEWED_REAL"}:
        raise ValueError("manifest dataset kind is invalid")
    if kind == "REVIEWED_REAL":
        _id(manifest["reviewer_id"], "reviewer_id")
        if manifest["reviewer_id"] == "SYNTHETIC_TEST":
            raise ValueError("real regression needs a real reviewer")
        _timestamp(manifest["reviewed_at"], "reviewed_at")
    elif manifest["reviewer_id"] is not None or manifest["reviewed_at"] is not None:
        raise ValueError("synthetic regression cannot claim review")
    thresholds = manifest["thresholds"]
    if not isinstance(thresholds, dict) or set(thresholds) != THRESHOLD_FIELDS:
        raise ValueError("regression thresholds are invalid")
    if (type(thresholds["minimum_cases"]) is not int or thresholds["minimum_cases"] < 20
            or type(thresholds["maximum_new_hard_failures"]) is not int
            or thresholds["maximum_new_hard_failures"] != 0
            or type(thresholds["minimum_score_delta"]) not in {int, float}
            or not math.isfinite(thresholds["minimum_score_delta"])
            or thresholds["minimum_score_delta"] < 0):
        raise ValueError("regression thresholds weaken the minimum gate")
    cases = manifest["cases"]
    if not isinstance(cases, list) or len(cases) < thresholds["minimum_cases"]:
        raise ValueError("regression needs at least 20 complete cases")
    seen = set()
    frozen = []
    for entry in cases:
        if not isinstance(entry, dict) or set(entry) != CASE_FIELDS:
            raise ValueError("regression case fields are invalid")
        case_id = _id(entry["case_id"], "case_id")
        if case_id in seen:
            raise ValueError("duplicate regression case ID")
        seen.add(case_id)
        cutoff = _timestamp(entry["inception_cutoff"], "inception_cutoff")
        _sha(entry["input_sha256"], "input_sha256")
        if (type(entry["hard"]) is not bool or not isinstance(entry["expected_invariants"], list)
                or not entry["expected_invariants"]
                or len(entry["expected_invariants"]) != len(set(map(str, entry["expected_invariants"])))):
            raise ValueError("regression case invariants are invalid")
        for invariant in entry["expected_invariants"]:
            _id(invariant, "expected invariant")
        input_path = _relative(entry["input_path"], project_dir, "case input")
        raw_case = _bytes(input_path, entry["input_sha256"], "case input")
        try:
            content = json.loads(raw_case)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("frozen case must be JSON") from exc
        if (not isinstance(content, dict) or content.get("case_id") != case_id
                or _has_leak(content) or "decision_inputs" not in content
                or _has_future(content["decision_inputs"], cutoff)
                or _timestamp(content.get("cutoff_timestamp"), "case cutoff") != cutoff):
            raise ValueError("frozen case identity, cutoff, or future outcome differs")
        frozen.append((entry, content))
    if _bytes(path, packet["manifest_sha256"], "manifest") != raw:
        raise ValueError("manifest changed during validation")
    return manifest, frozen


def _adapter_result(adapter, artifact, frozen_case, expected_invariants):
    result = deepcopy(adapter.evaluate(artifact, deepcopy(frozen_case)))
    if not isinstance(result, dict) or set(result) != OUTPUT_FIELDS:
        raise ValueError("runner result fields are invalid")
    digest = hashlib.sha256(artifact).hexdigest()
    if (result["artifact_sha256"] != digest or type(result["passed"]) is not bool
            or type(result["score"]) not in {int, float}
            or not math.isfinite(result["score"])
            or not isinstance(result["invariants"], dict)
            or any(type(item) is not bool for item in result["invariants"].values())
            or not set(expected_invariants) <= set(result["invariants"])
            or not isinstance(result["guardrail_violations"], list)
            or any(not isinstance(item, str) or not item for item in result["guardrail_violations"])):
        raise ValueError("runner did not return valid artifact-aware evidence")
    return result


def run_change_regression(packet_path: Path, *, state_dir: Path, project_dir: Path,
                          adapter_registry: Mapping[str, RegressionAdapter]) -> dict:
    """Run paired frozen cases through a registered adapter; never activate a version."""
    packet = _packet(_read(packet_path, "regression packet"))
    proposal, baseline, candidate = _proposal(packet, state_dir)
    manifest, cases = _manifest(packet, project_dir)
    adapter = adapter_registry.get(packet["runner_id"])
    rows = []
    status = "BLOCKED_NO_EXECUTOR"
    runner_version = packet["runner_version"]
    source_sha = packet["runner_source_sha256"]
    if adapter is not None:
        if (adapter.runner_id != packet["runner_id"]
                or adapter.runner_version != runner_version
                or adapter.source_sha256 != source_sha):
            raise ValueError("runner identity, version, or source hash differs")
        if proposal["change_type"] not in adapter.supported_change_types:
            status = "BLOCKED_NO_EXECUTOR"
        else:
            for entry, frozen_case in cases:
                baseline_result = _adapter_result(adapter, baseline, frozen_case,
                                                  entry["expected_invariants"])
                candidate_result = _adapter_result(adapter, candidate, frozen_case,
                                                   entry["expected_invariants"])
                rows.append({"case_id": entry["case_id"], "hard": entry["hard"],
                             "input_sha256": entry["input_sha256"],
                             "baseline": baseline_result, "candidate": candidate_result})
            baseline_failed = any(not row["baseline"]["passed"] or
                                  row["baseline"]["guardrail_violations"] or
                                  not all(row["baseline"]["invariants"].values()) for row in rows)
            new_hard_failures = sum(row["hard"] and row["baseline"]["passed"] and
                                    not row["candidate"]["passed"] for row in rows)
            candidate_failed = any(not row["candidate"]["passed"] or
                                   row["candidate"]["guardrail_violations"] or
                                   not all(row["candidate"]["invariants"].values()) for row in rows)
            hard_score_loss = any(row["hard"] and
                                  row["candidate"]["score"] < row["baseline"]["score"]
                                  for row in rows)
            score_delta = sum(row["candidate"]["score"] - row["baseline"]["score"]
                              for row in rows)
            effect = any(row["baseline"]["score"] != row["candidate"]["score"] or
                         row["baseline"]["passed"] != row["candidate"]["passed"] or
                         row["baseline"]["invariants"] != row["candidate"]["invariants"]
                         for row in rows)
            if baseline_failed:
                status = "FAILED_BASELINE"
            elif (candidate_failed or new_hard_failures or hard_score_loss
                  or score_delta < manifest["thresholds"]["minimum_score_delta"]):
                status = "FAILED"
            elif not effect:
                status = "BLOCKED_NO_ARTIFACT_EFFECT"
            elif manifest["dataset_kind"] == "SYNTHETIC_FIXTURE":
                status = "MECHANICS_PASS"
            else:
                # No production adapter or independently attested real gold is
                # registered in this mini-spec. Caller-supplied flags cannot lift it.
                status = "BLOCKED_NO_PRODUCTION_ADAPTER"
    body = {**packet, "regression_set_id": manifest["regression_set_id"],
            "dataset_version": manifest["dataset_version"],
            "dataset_kind": manifest["dataset_kind"], "rubric_version": manifest["rubric_version"],
            "reviewer_id": manifest["reviewer_id"], "reviewed_at": manifest["reviewed_at"],
            "thresholds": manifest["thresholds"], "case_count": len(cases),
            "baseline_passed": sum(row["baseline"]["passed"] for row in rows),
            "candidate_passed": sum(row["candidate"]["passed"] for row in rows),
            "new_hard_failures": sum(row["hard"] and row["baseline"]["passed"] and
                                     not row["candidate"]["passed"] for row in rows),
            "cases": rows, "status": status, "case_order": [entry["case_id"] for entry, _ in cases],
            **SAFETY}
    body["regression_digest"] = _digest(body)
    return _link_once(_path(state_dir, "change_regressions", packet["run_id"]), body,
                      "change regression")
