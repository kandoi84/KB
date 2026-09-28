"""Evaluate registered sources at a fixed information cutoff."""

import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path

from .source_store import _hash_file, _read_existing


def _hash_json(value):
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_request(path):
    try:
        request = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("refresh request must be valid JSON") from exc
    if not isinstance(request, dict) or set(request) != {
        "entity", "cutoff_timestamp", "required_sources"
    }:
        raise ValueError("refresh request requires entity, cutoff_timestamp and required_sources")
    if not isinstance(request["entity"], str) or not request["entity"].strip():
        raise ValueError("entity must be a nonempty string")
    cutoff = request["cutoff_timestamp"]
    if not isinstance(cutoff, str):
        raise ValueError("cutoff_timestamp must be timezone-aware")
    try:
        parsed_cutoff = datetime.fromisoformat(cutoff)
    except ValueError as exc:
        raise ValueError("cutoff_timestamp must be timezone-aware") from exc
    if parsed_cutoff.utcoffset() is None:
        raise ValueError("cutoff_timestamp must be timezone-aware")
    targets = request["required_sources"]
    if not isinstance(targets, list) or not targets:
        raise ValueError("required_sources must be a nonempty list")
    seen = set()
    for target in targets:
        if not isinstance(target, dict) or set(target) != {"source_id", "max_age_days"}:
            raise ValueError("each required source needs source_id and max_age_days")
        source_id = target["source_id"]
        if not isinstance(source_id, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", source_id
        ):
            raise ValueError("invalid source_id")
        if source_id in seen:
            raise ValueError("duplicate source_id in refresh request")
        seen.add(source_id)
        age = target["max_age_days"]
        if isinstance(age, bool) or not isinstance(age, int) or age < 0:
            raise ValueError("max_age_days must be a nonnegative integer")
    return request, parsed_cutoff


def _source_status(target, project_dir, cutoff):
    source_id = target["source_id"]
    base = {"source_id": source_id}
    versions_dir = project_dir / "data/registry/sources" / source_id
    paths = sorted(versions_dir.glob("*.json")) if versions_dir.is_dir() else []
    if not paths:
        return {**base, "status": "MISSING", "reason": "no registered source version"}
    versions = []
    for path in paths:
        try:
            value = _read_existing(path)
            if value["source_id"] != source_id:
                raise ValueError("source ID does not match directory")
            retrieved = datetime.fromisoformat(value["retrieved_at"])
            observed = datetime.fromisoformat(value["observed_at"])
            source_date = date.fromisoformat(value["source_date"])
            if retrieved.utcoffset() is None or observed.utcoffset() is None:
                raise ValueError("source timestamps lack timezone")
            if not re.fullmatch(r"[0-9a-f]{64}", value["raw_sha256"]):
                raise ValueError("raw digest is invalid")
        except (ValueError, KeyError, TypeError) as exc:
            return {**base, "status": "INVALID_REGISTRY", "reason": str(exc)}
        versions.append((retrieved, observed, source_date, value))
    eligible = [entry for entry in versions if
                entry[0] <= cutoff and entry[1] <= cutoff and entry[2] <= cutoff.date()]
    if not eligible:
        return {**base, "status": "AFTER_CUTOFF", "reason": "all versions are after cutoff"}
    retrieved, observed, source_date, selected = max(
        eligible, key=lambda entry: (entry[0], entry[1], entry[3]["version_id"])
    )
    result = {
        **base, "version_id": selected["version_id"],
        "raw_sha256": selected["raw_sha256"],
        "source_date": selected["source_date"],
        "age_days": (cutoff.date() - source_date).days,
    }
    blob = project_dir / "data/raw/sha256" / selected["raw_sha256"]
    if not blob.is_file():
        return {**result, "status": "MISSING_RAW", "reason": "raw blob is unavailable"}
    try:
        actual_hash = _hash_file(blob)
    except OSError as exc:
        return {**result, "status": "MISSING_RAW", "reason": str(exc)}
    if actual_hash != selected["raw_sha256"]:
        return {**result, "status": "CORRUPT_RAW", "reason": "raw hash differs from version"}
    if result["age_days"] > target["max_age_days"]:
        return {**result, "status": "STALE", "reason": "source age exceeds max_age_days"}
    return {**result, "status": "CURRENT", "reason": "source is available at cutoff"}


def _read_report(path, request_hash):
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("existing refresh report is invalid")
        report_id = report.pop("report_id")
    except (json.JSONDecodeError, UnicodeError, KeyError, TypeError) as exc:
        raise ValueError("existing refresh report is invalid") from exc
    if report_id != _hash_json(report):
        raise ValueError("existing refresh report differs from its digest")
    report["report_id"] = report_id
    if report.get("request_hash") != request_hash:
        raise ValueError("run_id cannot be reused with a changed request")
    return report


def evaluate_sources(request_path: Path, project_dir: Path, state_dir: Path, run_id: str) -> dict:
    """Freeze one source-readiness evaluation; a new run ID rechecks sources."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", run_id):
        raise ValueError("run_id must use letters, digits, underscores or hyphens")
    request, cutoff = _read_request(request_path)
    request_hash = _hash_json(request)
    state_dir = Path(state_dir)
    report_path = state_dir / "refresh_runs" / f"{run_id}.json"
    if report_path.exists():
        return _read_report(report_path, request_hash)

    project_dir = Path(project_dir)
    sources = [_source_status(target, project_dir, cutoff) for target in request["required_sources"]]
    report = {
        "run_id": run_id, "entity": request["entity"],
        "cutoff_timestamp": request["cutoff_timestamp"],
        "request_hash": request_hash,
        "status": "SOURCE_READY" if all(item["status"] == "CURRENT" for item in sources)
                  else "SOURCE_BLOCKED",
        "sources": sources,
    }
    report["report_id"] = _hash_json(report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=report_path.parent, prefix=".incoming-", delete=False
    ) as output:
        temp_path = Path(output.name)
        try:
            json.dump(report, output, indent=2, sort_keys=True, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
    try:
        os.link(temp_path, report_path)
    except FileExistsError:
        return _read_report(report_path, request_hash)
    finally:
        temp_path.unlink(missing_ok=True)
    return report
