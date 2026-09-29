"""Human review receipts for methodology changes; activation is unavailable."""

import difflib
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .case_snapshot import _digest, _id, _read
from .change_regression import _sha, _stored_artifact
from .identity_store import _timestamp
from .outcome_postmortem import SAFETY, _link_once, _path


PACKET_FIELDS = {"approval_id", "proposal_id", "proposal_digest", "regression_run_id",
                 "regression_digest", "baseline_sha256", "candidate_sha256",
                 "reviewer_id", "decided_at", "decision", "scope", "rationale"}


def classify_change_scope(change_type, changed_contract_paths, baseline_bytes, candidate_bytes):
    """Treat any decision, scoring, source, safety, or unknown change as structural."""
    if (change_type != "PROMPT" or not isinstance(changed_contract_paths, list)
            or not changed_contract_paths or baseline_bytes == candidate_bytes):
        return "STRUCTURAL"
    if any(not isinstance(path, str) or
           not path.startswith("config/prompts/display/") or
           not path.endswith(".txt") for path in changed_contract_paths):
        return "STRUCTURAL"
    try:
        before = baseline_bytes.decode("utf-8")
        after = candidate_bytes.decode("utf-8")
    except UnicodeError:
        return "STRUCTURAL"
    risky = {"rank", "score", "source", "cutoff", "publish", "publication", "safety",
             "decision", "trade", "weight", "valuation", "probability", "rights"}
    if any(word in (before + " " + after).casefold() for word in risky):
        return "STRUCTURAL"
    return "NONSTRUCTURAL"


def _diff_sha(baseline, candidate):
    try:
        before = baseline.decode("utf-8").splitlines(keepends=True)
        after = candidate.decode("utf-8").splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(before, after, fromfile="baseline", tofile="candidate"))
        data = diff.encode("utf-8")
    except UnicodeError:
        data = baseline + b"\x00" + candidate
    return hashlib.sha256(data).hexdigest()


def _packet(value):
    if not isinstance(value, dict) or set(value) != PACKET_FIELDS:
        raise ValueError("change approval packet fields are invalid")
    for field in ("approval_id", "proposal_id", "regression_run_id", "reviewer_id"):
        _id(value[field], field)
    for field in ("proposal_digest", "regression_digest", "baseline_sha256",
                  "candidate_sha256"):
        _sha(value[field], field)
    if not isinstance(value["decision"], str) or value["decision"] not in {"APPROVED", "REJECTED"}:
        raise ValueError("change approval decision is invalid")
    if not isinstance(value["scope"], str) or value["scope"] not in {"STRUCTURAL", "NONSTRUCTURAL"}:
        raise ValueError("change approval scope is invalid")
    _timestamp(value["decided_at"], "decided_at")
    if not isinstance(value["rationale"], str) or len(value["rationale"].strip()) < 12:
        raise ValueError("change approval rationale must be substantive")
    return value


def _receipt(state_dir, folder, identifier, digest_field, expected_digest):
    path = _path(state_dir, folder, identifier)
    if not path.is_file():
        raise ValueError(f"{folder} receipt is missing")
    value = _read(path, f"{folder} receipt")
    if (value.get(digest_field) != expected_digest
            or _digest({key: item for key, item in value.items() if key != digest_field})
            != expected_digest
            or any(value.get(key) != expected for key, expected in SAFETY.items())):
        raise ValueError(f"{folder} receipt digest or safety gate differs")
    return value


def record_change_approval(packet_path: Path, *, state_dir: Path) -> dict:
    """Record rejection or a verified human decision; no activation occurs."""
    packet = _packet(_read(packet_path, "change approval packet"))
    proposal = _receipt(state_dir, "change_proposals", packet["proposal_id"],
                        "proposal_digest", packet["proposal_digest"])
    regression = _receipt(state_dir, "change_regressions", packet["regression_run_id"],
                          "regression_digest", packet["regression_digest"])
    if (proposal.get("proposal_id") != packet["proposal_id"]
            or regression.get("run_id") != packet["regression_run_id"]
            or regression.get("proposal_id") != packet["proposal_id"]
            or regression.get("proposal_digest") != packet["proposal_digest"]
            or any(proposal.get(key) != packet[key] or regression.get(key) != packet[key]
                   for key in ("baseline_sha256", "candidate_sha256"))):
        raise ValueError("change approval references a stale proposal or regression")
    decided = datetime.fromisoformat(_timestamp(packet["decided_at"], "decided_at"))
    created = datetime.fromisoformat(_timestamp(proposal["created_at"], "proposal created_at"))
    if decided < created:
        raise ValueError("approval decision predates proposal")
    if decided > datetime.now(timezone.utc):
        raise ValueError("approval decision is in the future")
    baseline = _stored_artifact(state_dir, packet["baseline_sha256"], "baseline artifact")
    candidate = _stored_artifact(state_dir, packet["candidate_sha256"], "candidate artifact")
    scope = classify_change_scope(proposal["change_type"], proposal["changed_contract_paths"],
                                  baseline, candidate)
    if packet["scope"] != scope:
        raise ValueError("change approval scope differs from contract paths and diff")
    if packet["decision"] == "APPROVED":
        if scope == "STRUCTURAL" and packet["reviewer_id"] == proposal["author_id"]:
            raise ValueError("structural change requires an independent reviewer")
        # Task 2 has no independently attested real gold, production runner, or
        # trusted timestamp. Its receipt is self-hashed local data. A caller
        # cannot turn that into authorization by editing status or flags.
        raise ValueError("approval requires a trusted real regression gate")
    body = {**packet, "diff_sha256": _diff_sha(baseline, candidate),
            "regression_status": regression["status"], "approval_status": "REJECTED",
            **SAFETY}
    body["approval_digest"] = _digest(body)
    return _link_once(_path(state_dir, "change_approvals", packet["approval_id"]), body,
                      "change approval")
