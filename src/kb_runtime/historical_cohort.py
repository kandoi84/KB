"""Replay-verified historical cohorts with explicit nonpromotion readiness."""

import hashlib
import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .case_snapshot import INPUT_NAMES, _digest, _id, _read, verify_frozen_case
from .identity_store import DIGEST, _timestamp, _valid_isin


MANIFEST_FIELDS = {"cohort_id", "dataset_kind", "rubric_version", "quarter_cutoffs",
                   "universe_rule", "reviewer_id", "reviewed_at", "scorer_id",
                   "scorer_source_sha256", "cases"}
CASE_FIELDS = {"case_id", "case_digest", "isin", "cutoff_timestamp", "seal_proof"}
PROOF_FIELDS = {"provider_id", "seal_id", "case_digest", "sealed_at",
                "earliest_reveal_at", "reviewer_id", "reviewed_at", "evidence_sha256"}
SAFETY = {"publication_allowed": False, "live_decision_allowed": False,
          "promotion_allowed": False}


def _time(value, label):
    return datetime.fromisoformat(_timestamp(value, label))


def _sha(value, label):
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        raise ValueError(f"{label} must be a SHA-256 digest")
    return value


def _strict(value, fields, label):
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} fields are invalid")
    return value


def _read_manifest(path):
    try:
        if Path(path).stat().st_size > 1_000_000:
            raise ValueError("cohort manifest is too large")
    except OSError as exc:
        raise ValueError("cohort manifest is unavailable") from exc
    return _read(path, "cohort manifest")


def _quarter(value):
    stamp = _time(value, "quarter cutoff").astimezone(ZoneInfo("Asia/Kolkata"))
    return f"{stamp.year}-Q{(stamp.month - 1) // 3 + 1}"


def _manifest(value):
    _strict(value, MANIFEST_FIELDS, "cohort manifest")
    for key in ("cohort_id", "rubric_version", "reviewer_id"):
        _id(value[key], key)
    if value["dataset_kind"] not in ("SYNTHETIC_FIXTURE", "REVIEWED_REAL"):
        raise ValueError("cohort dataset kind is invalid")
    if (not isinstance(value["universe_rule"], str)
            or len(value["universe_rule"].strip()) < 12
            or len(value["universe_rule"]) > 1000):
        raise ValueError("cohort universe rule is invalid")
    reviewed_at = _time(value["reviewed_at"], "reviewed_at")
    now = datetime.now(timezone.utc)
    if value["dataset_kind"] == "REVIEWED_REAL" and reviewed_at > now:
        raise ValueError("cohort review attestation is in the future")
    scorer_id, scorer_sha = value["scorer_id"], value["scorer_source_sha256"]
    if (scorer_id is None) != (scorer_sha is None):
        raise ValueError("cohort scorer identity and hash must both be present")
    if scorer_id is not None:
        _id(scorer_id, "scorer_id")
        _sha(scorer_sha, "scorer_source_sha256")
    cutoffs = value["quarter_cutoffs"]
    if not isinstance(cutoffs, list) or not cutoffs or len(cutoffs) > 100:
        raise ValueError("cohort quarter cutoffs are invalid")
    normalized = [_timestamp(cutoff, "quarter cutoff") for cutoff in cutoffs]
    quarters = [_quarter(cutoff) for cutoff in cutoffs]
    if len(set(normalized)) != len(normalized) or len(set(quarters)) != len(quarters):
        raise ValueError("cohort quarter cutoffs repeat")
    cases = value["cases"]
    if not isinstance(cases, list) or not cases or len(cases) > 5000:
        raise ValueError("cohort cases must be a bounded nonempty list")
    seen_ids, seen_pairs = set(), set()
    for row in cases:
        _strict(row, CASE_FIELDS, "cohort case")
        _id(row["case_id"], "case_id")
        _sha(row["case_digest"], "case_digest")
        if not _valid_isin(row["isin"]):
            raise ValueError("cohort case ISIN is invalid")
        cutoff = _timestamp(row["cutoff_timestamp"], "case cutoff")
        if cutoff not in normalized:
            raise ValueError("cohort case cutoff is not declared")
        pair = (row["isin"], cutoff)
        if row["case_id"] in seen_ids or pair in seen_pairs:
            raise ValueError("duplicate cohort case or ISIN/cutoff observation")
        seen_ids.add(row["case_id"])
        seen_pairs.add(pair)
        proof = row["seal_proof"]
        if proof is not None:
            _strict(proof, PROOF_FIELDS, "seal proof")
            for key in ("provider_id", "seal_id", "reviewer_id"):
                _id(proof[key], key)
            _sha(proof["case_digest"], "seal case_digest")
            _sha(proof["evidence_sha256"], "seal evidence_sha256")
            if proof["case_digest"] != row["case_digest"]:
                raise ValueError("seal case digest differs")
            sealed = _time(proof["sealed_at"], "sealed_at")
            reveal = _time(proof["earliest_reveal_at"], "earliest_reveal_at")
            reviewed = _time(proof["reviewed_at"], "seal reviewed_at")
            if sealed >= reveal or reviewed < sealed:
                raise ValueError("seal must precede reveal and review")
            if value["dataset_kind"] == "REVIEWED_REAL" and (sealed > now or reviewed > now):
                raise ValueError("seal attestation is in the future")
    return value


def _replay_inputs(value, case_ids):
    if not isinstance(value, dict) or set(value) != set(case_ids):
        raise ValueError("cohort case replay inputs must match case IDs")
    expected = set(INPUT_NAMES) | {"case_packet_path"}
    for case_id, paths in value.items():
        if not isinstance(paths, dict) or set(paths) != expected:
            raise ValueError(f"case replay paths are invalid for {case_id}")
        if any(not isinstance(path, (Path, str)) for path in paths.values()):
            raise ValueError(f"case replay path type is invalid for {case_id}")


def _link_once(path, body):
    if path.is_file():
        old = _read(path, "existing cohort")
        if old != body:
            raise ValueError("existing cohort differs from replayed manifest")
        return old
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".incoming-", delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(body, output, sort_keys=True, indent=2, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.link(temporary, path)
    except FileExistsError:
        old = _read(path, "existing cohort")
        if old != body:
            raise ValueError("existing cohort differs from concurrent replay")
    finally:
        temporary.unlink(missing_ok=True)
    return body


def register_evaluation_cohort(manifest_path: Path, *, state_dir: Path,
                               project_dir: Path, catalog: Path,
                               case_replay_inputs: dict[str, dict[str, Path]]) -> dict:
    """Freeze a replayed cohort; local seals never count as independent proof."""
    manifest = _manifest(_read_manifest(manifest_path))
    _replay_inputs(case_replay_inputs, [row["case_id"] for row in manifest["cases"]])
    root = Path(state_dir).resolve()
    path = Path(state_dir) / "historical_evaluation/cohorts" / f"{manifest['cohort_id']}.json"
    if not path.resolve().is_relative_to(root):
        raise ValueError("cohort path escapes state root")
    rows = []
    blockers = set()
    for selected in manifest["cases"]:
        case_id = selected["case_id"]
        inputs = case_replay_inputs[case_id]
        case = verify_frozen_case(Path(state_dir) / "cases" / f"{case_id}.json",
                                  Path(inputs["case_packet_path"]), project_dir=project_dir,
                                  catalog=catalog, state_dir=state_dir,
                                  case_replay_inputs={key: Path(inputs[key]) for key in INPUT_NAMES})
        if (case["case_id"] != case_id or case["case_digest"] != selected["case_digest"]
                or case["isin"] != selected["isin"]
                or _timestamp(case["cutoff_timestamp"], "case cutoff")
                != _timestamp(selected["cutoff_timestamp"], "manifest cutoff")
                or case["case_status"] != "SANDBOX_OPEN"
                or case["publication_allowed"] is not False
                or case["live_decision_allowed"] is not False
                or case["promotion_status"] != "NOT_EVALUATED"):
            raise ValueError("cohort case digest, ISIN, cutoff, or safety differs")
        if manifest["dataset_kind"] == "REVIEWED_REAL":
            opened_at = _time(case["opened_at"], "case opened_at")
            if opened_at > datetime.now(timezone.utc):
                raise ValueError("real cohort case opening is in the future")
            if _time(manifest["reviewed_at"], "reviewed_at") < opened_at:
                raise ValueError("real cohort review precedes case opening")
        try:
            case_packet_sha = hashlib.sha256(Path(inputs["case_packet_path"]).read_bytes()).hexdigest()
        except OSError as exc:
            raise ValueError("case packet bytes are unavailable") from exc
        case_class = ("SYNTHETIC_FIXTURE" if manifest["dataset_kind"] == "SYNTHETIC_FIXTURE"
                      else "REPLAY_ONLY")
        row_blockers = [] if case_class == "SYNTHETIC_FIXTURE" else ["INDEPENDENT_SEAL_MISSING"
            if selected["seal_proof"] is None else "INDEPENDENT_SEAL_UNVERIFIED"]
        blockers.update(row_blockers)
        rows.append({"case_id": case_id, "case_digest": case["case_digest"],
                     "isin": case["isin"], "cutoff_timestamp": case["cutoff_timestamp"],
                     "case_packet_sha256": case_packet_sha,
                     "input_sha256": case["input_sha256"],
                     "timing_class": case["timing_class"], "case_class": case_class,
                     "seal_proof": selected["seal_proof"], "blockers": row_blockers})
    counts = Counter(_timestamp(row["cutoff_timestamp"], "case cutoff") for row in rows)
    coverage = []
    for cutoff in manifest["quarter_cutoffs"]:
        count = counts[_timestamp(cutoff, "quarter cutoff")]
        eligible = 30 <= count <= 50
        if not eligible:
            blockers.add("QUARTER_UNIVERSE_INCOMPLETE")
        coverage.append({"quarter_cutoff": cutoff, "quarter": _quarter(cutoff),
                         "issuer_count": count, "eligible_for_ranking": eligible,
                         "blockers": [] if eligible else ["QUARTER_UNIVERSE_INCOMPLETE"]})
    if manifest["dataset_kind"] == "REVIEWED_REAL":
        blockers.add("INDEPENDENT_SEAL_VERIFIER_UNAVAILABLE")
    body = {"cohort_id": manifest["cohort_id"], "dataset_kind": manifest["dataset_kind"],
            "rubric_version": manifest["rubric_version"],
            "quarter_cutoffs": manifest["quarter_cutoffs"],
            "universe_rule": manifest["universe_rule"],
            "reviewer_id": manifest["reviewer_id"], "reviewed_at": manifest["reviewed_at"],
            "scorer_id": manifest["scorer_id"],
            "scorer_source_sha256": manifest["scorer_source_sha256"],
            "cases": rows, "quarter_coverage": coverage,
            "blockers": sorted(blockers),
            "cohort_status": "BLOCKED" if blockers else "MECHANICS_ONLY", **SAFETY}
    body["cohort_digest"] = _digest(body)
    return _link_once(path, body)
