"""Small resumable workflow over supplied research; no investment analysis is generated."""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


STEPS = (
    "PLAN_READY", "INGESTING", "NORMALIZED", "ANALYZED",
    "JUDGMENT_REVIEWED", "VALIDATED", "SNAPSHOT_FROZEN",
    "PUBLISHED", "CASE_OPENED",
)
REQUIRED_RESEARCH = (
    "price", "benchmark", "business_quality", "quality_trajectory",
    "market_implied_expectations", "most_likely_path", "expectation_gap",
    "valuation", "valuation_fragility", "multiple_compression_risk",
    "catalysts", "probabilities", "timing", "downside_mechanism",
    "premortem", "score", "score_error_band", "evidence_grade",
    "poker_hand", "poker_draw", "critical_gaps", "falsifiers",
)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as output:
        json.dump(payload, output, indent=2, sort_keys=True, ensure_ascii=False)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temp, path)


def _canonical_hash(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validate(entity, data):
    if data.get("test_fixture") is not True:
        raise ValueError("real research publication is blocked until source and integrity validation exist")
    if data.get("entity") != entity:
        raise ValueError("input entity does not match requested entity")
    cutoff = data.get("cutoff_timestamp")
    if not isinstance(cutoff, str) or datetime.fromisoformat(cutoff).tzinfo is None:
        raise ValueError("a timezone-aware cutoff_timestamp is required")
    if not data.get("source_ids"):
        raise ValueError("at least one source ID is required")
    research = data.get("research")
    if not isinstance(research, dict):
        raise ValueError("research object is required")
    missing = [name for name in REQUIRED_RESEARCH if research.get(name) is None or research.get(name) == ""]
    if missing:
        raise ValueError("missing research fields: " + ", ".join(missing))
    if not 0 <= research["score"] <= 100 or research["score_error_band"] < 0:
        raise ValueError("score or score_error_band is invalid")


def _open_case(path, state, data, snapshot_id):
    inception = {
        "case_id": state["run_id"], "entity": state["entity"],
        "decision_date": data["cutoff_timestamp"][:10],
        "cutoff_timestamp": data["cutoff_timestamp"],
        "snapshot_id": snapshot_id,
        "source_ids": data["source_ids"],
        "test_fixture": bool(data.get("test_fixture", False)),
        **data["research"],
    }
    case = {"inception": inception, "observations": []}
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing["inception"] != inception:
            raise ValueError("existing Case Book inception differs; refusing overwrite")
        return
    _write_json(path, case)


def run_company_research(entity, input_path, state_dir, run_id, fail_once=None):
    """Resume a run with the same immutable input; terminal success is CASE_OPENED."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", run_id):
        raise ValueError("run_id must use letters, digits, underscores or hyphens")
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    input_hash = _canonical_hash(data)
    state_dir = Path(state_dir)
    run_dir = state_dir / "runs" / run_id
    state_path = run_dir / "state.json"
    manifest_path = run_dir / "manifest.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if state["entity"] != entity or state["input_hash"] != input_hash:
            raise ValueError("a run_id cannot be resumed with changed entity or input")
    else:
        state = {
            "run_id": run_id, "entity": entity, "input_hash": input_hash,
            "status": "CREATED", "completed_steps": [], "completed_at": {},
            "injected_failures": [],
        }
        manifest = {
            "run_id": run_id, "entity": entity, "started_at": _now(),
            "source_cutoff": data.get("cutoff_timestamp"),
            "source_ids": data.get("source_ids", []),
            "input_hash": input_hash, "snapshot_id": None,
            "steps": [], "publication_status": "NOT_PUBLISHED",
            "runtime_version": 1,
        }
        _write_json(state_path, state)
        _write_json(manifest_path, manifest)

    if state["status"] == "CASE_OPENED":
        case_path = state_dir / "cases" / f"{run_id}.json"
        if case_path.exists():
            _open_case(case_path, state, data, manifest["snapshot_id"])
            return state
        state["completed_steps"].remove("CASE_OPENED")
        state["completed_at"].pop("CASE_OPENED")
        state["status"] = "PUBLISHED"
        manifest["publication_status"] = "PENDING_CASE"
        manifest["steps"] = [item for item in manifest["steps"] if item["state"] != "CASE_OPENED"]
        _write_json(manifest_path, manifest)
        _write_json(state_path, state)
    for step in STEPS:
        if step in state["completed_steps"]:
            continue
        try:
            if step == "VALIDATED":
                _validate(entity, data)
            elif step == "SNAPSHOT_FROZEN":
                snapshot_id = _canonical_hash(data)
                snapshot_path = state_dir / "snapshots" / f"{snapshot_id}.json"
                if snapshot_path.exists():
                    if json.loads(snapshot_path.read_text(encoding="utf-8")) != data:
                        raise ValueError("snapshot hash collision or modified snapshot")
                else:
                    _write_json(snapshot_path, data)
                manifest["snapshot_id"] = snapshot_id
            elif step == "PUBLISHED":
                if not manifest["snapshot_id"] or "VALIDATED" not in state["completed_steps"]:
                    raise ValueError("publication requires validation and frozen snapshot")
                manifest["publication_status"] = "PENDING_CASE"
            elif step == "CASE_OPENED":
                if fail_once == step and step not in state["injected_failures"]:
                    state["injected_failures"].append(step)
                    raise RuntimeError("injected CASE_OPENED failure")
                _open_case(state_dir / "cases" / f"{run_id}.json", state, data, manifest["snapshot_id"])
                manifest["publication_status"] = "COMPLETE"
            state["completed_steps"].append(step)
            state["completed_at"][step] = _now()
            state["status"] = step
            manifest["steps"].append({"state": step, "completed_at": state["completed_at"][step]})
            _write_json(manifest_path, manifest)
            _write_json(state_path, state)
        except (OSError, ValueError, RuntimeError) as exc:
            state["status"] = "BLOCKED_VALIDATION" if step == "VALIDATED" else "FAILED_RUNTIME"
            state["last_error"] = str(exc)
            _write_json(manifest_path, manifest)
            _write_json(state_path, state)
            raise
    return state
