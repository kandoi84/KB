"""Freeze data-only methodology proposals with replayed process-error links."""

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Mapping

from .case_snapshot import _digest, _id, _ids, _read
from .identity_store import _timestamp
from .outcome_postmortem import SAFETY, _check_existing, _link_once, _path, evaluate_due_case


PACKET_FIELDS = {"proposal_id", "change_type", "baseline_version", "candidate_version",
                 "author_id", "created_at", "changed_contract_paths", "rationale",
                 "eval_candidate_ids"}
CHANGE_TYPES = {"PROMPT", "WEIGHT", "SCHEMA", "RULE"}
FLOATING_VERSIONS = {"latest", "current", "head", "active", "production", "main"}
REPLAY_KEYS = {"case_packet_path", "project_dir", "catalog"}


def _contract_path(value):
    if (not isinstance(value, str) or "\\" in value or "\x00" in value
            or value.startswith("/") or not value.strip()):
        raise ValueError("changed contract path is invalid")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts) or ":" in parts[0]:
        raise ValueError("changed contract path escapes its root")
    return value


def _packet(value):
    if not isinstance(value, dict) or set(value) != PACKET_FIELDS:
        raise ValueError("proposal packet fields are invalid")
    for field in ("proposal_id", "baseline_version", "candidate_version", "author_id"):
        _id(value[field], field)
    if (value["baseline_version"] == value["candidate_version"]
            or any(value[field].lower() in FLOATING_VERSIONS
                   for field in ("baseline_version", "candidate_version"))):
        raise ValueError("proposal versions must be distinct and pinned")
    if not isinstance(value["change_type"], str) or value["change_type"] not in CHANGE_TYPES:
        raise ValueError("proposal change type is invalid")
    _timestamp(value["created_at"], "created_at")
    if not isinstance(value["rationale"], str) or len(value["rationale"].strip()) < 12:
        raise ValueError("proposal rationale must be substantive")
    paths = value["changed_contract_paths"]
    if not isinstance(paths, list) or not paths or len(paths) != len(set(map(str, paths))):
        raise ValueError("changed contract paths must be unique and nonempty")
    for path in paths:
        _contract_path(path)
    _ids(value["eval_candidate_ids"], "eval_candidate_ids")
    return value


def _artifact_bytes(path, state_dir, project_dir):
    path = Path(path)
    resolved = path.resolve()
    roots = [Path(state_dir).resolve()]
    if project_dir is not None:
        roots.append(Path(project_dir).resolve())
    if path.is_symlink() or not any(resolved.is_relative_to(root) for root in roots):
        raise ValueError("artifact path escapes project or state root")
    if not path.is_file():
        raise ValueError("artifact is missing")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ValueError("artifact cannot be read") from exc
    if not data:
        raise ValueError("artifact is empty")
    return data


def _store_artifact(state_dir, data):
    digest = hashlib.sha256(data).hexdigest()
    root = Path(state_dir).resolve()
    path = root / "change_artifacts" / "sha256" / digest
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        raise ValueError("artifact store path escapes state root")
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("stored artifact differs")
        return digest
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".incoming-", delete=False) as output:
        temporary = Path(output.name)
        try:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.link(temporary, path)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != data:
            raise ValueError("stored artifact differs")
    finally:
        temporary.unlink(missing_ok=True)
    return digest


def _candidate(candidate_id, state_dir, replay):
    due_path = replay.get(f"due_packet:{candidate_id}")
    if due_path is None and "due_packet_path" in replay:
        due_path = replay["due_packet_path"]
    if due_path is None or not REPLAY_KEYS <= set(replay):
        raise ValueError("candidate source replay inputs are missing")
    due_packet = _read(due_path, "postmortem packet")
    if due_packet.get("postmortem_id") != candidate_id:
        raise ValueError("candidate postmortem packet identity differs")
    candidate_path = _path(state_dir, "eval_candidates", candidate_id)
    postmortem_path = _path(state_dir, "postmortems", candidate_id)
    if not candidate_path.is_file() or not postmortem_path.is_file():
        raise ValueError("candidate or postmortem receipt is missing")
    case_replay = {key: value for key, value in replay.items()
                   if key not in REPLAY_KEYS and not key.startswith("due_packet:")
                   and key != "due_packet_path"}
    expected_postmortem = evaluate_due_case(
        due_path, case_packet_path=replay["case_packet_path"],
        project_dir=replay["project_dir"], catalog=replay["catalog"],
        state_dir=state_dir, case_replay_inputs=case_replay)
    candidate = _read(candidate_path, "eval candidate")
    if (expected_postmortem["postmortem_status"] != "COMPLETE"
            or expected_postmortem["eval_candidate_id"] != candidate_id
            or expected_postmortem["process_review"]["process_assessment"] != "BAD_PROCESS"
            or expected_postmortem["process_review"]["reproducible_process_failure"] is not True
            or candidate.get("candidate_id") != candidate_id
            or candidate.get("postmortem_digest") != expected_postmortem["postmortem_digest"]
            or candidate.get("candidate_status") != "UNREVIEWED"
            or any(candidate.get(key) != value for key, value in SAFETY.items())):
        raise ValueError("eval candidate is not a replayed reproducible process error")
    return {"candidate_id": candidate_id, "candidate_digest": candidate["candidate_digest"],
            "postmortem_digest": expected_postmortem["postmortem_digest"],
            "case_id": candidate["case_id"], "case_digest": candidate["case_digest"]}


def register_change_proposal(packet_path: Path, *, baseline_artifact: Path,
                             candidate_artifact: Path, state_dir: Path,
                             case_replay_inputs: Mapping[str, Path]) -> dict:
    """Register an immutable, source-linked proposal without changing active configuration."""
    packet = _packet(_read(packet_path, "proposal packet"))
    if not isinstance(case_replay_inputs, Mapping):
        raise ValueError("case replay inputs must be a mapping")
    project_dir = case_replay_inputs.get("project_dir")
    baseline = _artifact_bytes(baseline_artifact, state_dir, project_dir)
    candidate = _artifact_bytes(candidate_artifact, state_dir, project_dir)
    links = [_candidate(identifier, state_dir, case_replay_inputs)
             for identifier in packet["eval_candidate_ids"]]
    baseline_sha = hashlib.sha256(baseline).hexdigest()
    candidate_sha = hashlib.sha256(candidate).hexdigest()
    if baseline_sha == candidate_sha:
        raise ValueError("baseline and candidate artifact bytes are identical")
    body = {**packet, "baseline_sha256": baseline_sha,
            "candidate_sha256": candidate_sha, "eval_candidates": links, **SAFETY}
    body["proposal_digest"] = _digest(body)
    path = _path(state_dir, "change_proposals", packet["proposal_id"])
    _check_existing(path, body, "proposal")
    _store_artifact(state_dir, baseline)
    _store_artifact(state_dir, candidate)
    return _link_once(path, body, "proposal")
