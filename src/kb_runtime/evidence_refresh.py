"""Run source and claim checks together and freeze their change manifest."""

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from .claim_lineage import _read_request as _read_claim_request
from .claim_lineage import evaluate_claims, load_claim_report
from .source_refresh import _read_request as _read_source_request
from .source_refresh import evaluate_sources, load_refresh_report


SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}\Z")
CLAIM_INPUT_FIELDS = (
    "claim_type", "statement", "as_of", "source_id", "version_id", "passage_locator",
)


def _hash_json(value):
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_manifest(path):
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("evidence run manifest is invalid")
        manifest_id = manifest.pop("manifest_id")
    except (OSError, json.JSONDecodeError, UnicodeError, KeyError, TypeError) as exc:
        raise ValueError("evidence run manifest is invalid") from exc
    if manifest_id != _hash_json(manifest):
        raise ValueError("evidence run manifest differs from its digest")
    manifest["manifest_id"] = manifest_id
    return manifest


def _previous_run(state_dir, previous_run_id, entity, cutoff):
    path = state_dir / "evidence_runs" / f"{previous_run_id}.json"
    if not path.is_file():
        raise ValueError("previous evidence run is missing")
    manifest = _read_manifest(path)
    if manifest.get("run_id") != previous_run_id or manifest.get("entity") != entity:
        raise ValueError("previous evidence run entity or ID differs")
    try:
        previous_cutoff = datetime.fromisoformat(manifest["cutoff_timestamp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("previous evidence run cutoff is invalid") from exc
    if previous_cutoff.utcoffset() is None or previous_cutoff > cutoff:
        raise ValueError("previous evidence run cutoff is after current cutoff")
    source = load_refresh_report(state_dir / "refresh_runs" / f"{previous_run_id}.json")
    claim = load_claim_report(state_dir / "claim_runs" / f"{previous_run_id}.json")
    if (manifest.get("source_report_id") != source.get("report_id")
            or manifest.get("claim_report_id") != claim.get("report_id")
            or claim.get("source_report_id") != source.get("report_id")
            or source.get("run_id") != previous_run_id
            or claim.get("run_id") != previous_run_id
            or source.get("entity") != entity or claim.get("entity") != entity
            or source.get("cutoff_timestamp") != manifest["cutoff_timestamp"]
            or claim.get("cutoff_timestamp") != manifest["cutoff_timestamp"]):
        raise ValueError("previous evidence run reports do not match manifest")
    return manifest, source, claim


def _source_changes(previous, current):
    earlier = {item["source_id"]: item for item in previous["sources"]} if previous else {}
    latest = {item["source_id"]: item for item in current["sources"]}
    changes = []
    for source_id in sorted(earlier.keys() | latest.keys()):
        before = earlier.get(source_id)
        after = latest.get(source_id)
        if previous is None:
            status = "INITIAL" if after["status"] == "CURRENT" else "BLOCKED"
        elif after is None:
            status = "REMOVED"
        elif after["status"] != "CURRENT":
            status = "BLOCKED"
        elif before is None:
            status = "NEW"
        elif before.get("status") == after["status"] and before.get("version_id") == after.get("version_id"):
            status = "UNCHANGED"
        else:
            status = "UPDATED"
        changes.append({
            "source_id": source_id, "status": status,
            "previous_status": before.get("status") if before else None,
            "current_status": after.get("status") if after else None,
            "previous_version_id": before.get("version_id") if before else None,
            "current_version_id": after.get("version_id") if after else None,
        })
    return changes


def _claim_impacts(previous, current, source_changes):
    earlier = {item["claim_id"]: item for item in previous["claims"]} if previous else {}
    changed = {item["source_id"]: item["status"] for item in source_changes}
    impacts = []
    for claim in current["claims"]:
        prior = earlier.get(claim["claim_id"])
        if previous is None:
            status = "INITIAL"
        elif claim["status"] != "LINEAGE_LINKED" or (prior and prior["status"] != "LINEAGE_LINKED"):
            status = "BLOCKED_GAP"
        elif prior is None or changed.get(claim["source_id"]) != "UNCHANGED":
            status = "RECHECK_SOURCE"
        elif any(prior.get(field) != claim.get(field) for field in CLAIM_INPUT_FIELDS):
            status = "RECHECK_SOURCE"
        else:
            status = "UNCHANGED"
        impacts.append({
            "claim_id": claim["claim_id"], "source_id": claim["source_id"],
            "lineage_status": claim["status"], "status": status,
        })
    for claim_id in sorted(earlier.keys() - {item["claim_id"] for item in current["claims"]}):
        impacts.append({
            "claim_id": claim_id, "source_id": earlier[claim_id]["source_id"],
            "lineage_status": None, "status": "REMOVED",
        })
    return impacts


def refresh_evidence(source_request_path: Path, claim_request_path: Path,
                     project_dir: Path, state_dir: Path, run_id: str,
                     previous_run_id: str | None = None) -> dict:
    """Resume source and claim evaluations, then freeze an evidence manifest."""
    if not isinstance(run_id, str) or not SAFE_ID.fullmatch(run_id):
        raise ValueError("run_id is invalid")
    if previous_run_id is not None and (
        not isinstance(previous_run_id, str) or not SAFE_ID.fullmatch(previous_run_id)
        or previous_run_id == run_id
    ):
        raise ValueError("previous_run_id is invalid")
    source_request, source_cutoff = _read_source_request(source_request_path)
    claim_request, _ = _read_claim_request(claim_request_path)
    if source_request["entity"] != claim_request["entity"]:
        raise ValueError("source and claim request entity differs")
    if source_request["cutoff_timestamp"] != claim_request["cutoff_timestamp"]:
        raise ValueError("source and claim request cutoff differs")
    state_dir = Path(state_dir)
    prior = _previous_run(state_dir, previous_run_id, source_request["entity"], source_cutoff) if previous_run_id else None
    previous_source = prior[1] if prior else None
    previous_claim = prior[2] if prior else None
    source = evaluate_sources(source_request_path, project_dir, state_dir, run_id)
    claim = evaluate_claims(
        claim_request_path, state_dir / "refresh_runs" / f"{run_id}.json",
        project_dir, state_dir, run_id,
    )
    changes = _source_changes(previous_source, source)
    impacts = _claim_impacts(previous_claim, claim, changes)
    manifest = {
        "run_id": run_id, "previous_run_id": previous_run_id,
        "entity": source_request["entity"],
        "cutoff_timestamp": source_request["cutoff_timestamp"],
        "source_request_hash": source["request_hash"],
        "claim_request_hash": claim["request_hash"],
        "source_report_id": source["report_id"],
        "claim_report_id": claim["report_id"],
        "source_status": source["status"], "claim_status": claim["status"],
        "source_changes": changes, "claim_impacts": impacts,
        "open_gap_ids": [gap["gap_id"] for gap in claim["gaps"] if gap["status"] == "OPEN"],
        "publication_allowed": False,
    }
    manifest["manifest_id"] = _hash_json(manifest)
    path = state_dir / "evidence_runs" / f"{run_id}.json"
    if path.exists():
        existing = _read_manifest(path)
        if existing != manifest:
            raise ValueError("run_id cannot be reused with changed evidence inputs")
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=".incoming-", delete=False
    ) as output:
        temp_path = Path(output.name)
        try:
            json.dump(manifest, output, indent=2, sort_keys=True, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
    try:
        os.link(temp_path, path)
    except FileExistsError:
        existing = _read_manifest(path)
        if existing != manifest:
            raise ValueError("run_id cannot be reused with changed evidence inputs")
        return existing
    finally:
        temp_path.unlink(missing_ok=True)
    return manifest
