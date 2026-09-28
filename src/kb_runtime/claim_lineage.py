"""Check supplied claims against frozen sources without approving their meaning."""

import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path

from .source_refresh import load_refresh_report
from .source_store import _hash_file, _read_existing


CLAIM_TYPES = frozenset({
    "REPORTED_FACT", "MANAGEMENT_GUIDANCE", "CONSENSUS", "MARKET_DATA",
    "DERIVED", "ANALYST_ASSUMPTION", "INFERENCE", "SENTIMENT", "UNKNOWN",
})
DIRECT_TYPES = frozenset({
    "REPORTED_FACT", "MANAGEMENT_GUIDANCE", "CONSENSUS", "MARKET_DATA", "SENTIMENT",
})
CLAIM_FIELDS = frozenset({
    "claim_id", "claim_type", "statement", "as_of", "source_id",
    "version_id", "passage_locator",
})
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def _hash_json(value):
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_request(path):
    try:
        request = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("claim request must be valid JSON") from exc
    if not isinstance(request, dict) or set(request) != {"entity", "cutoff_timestamp", "claims"}:
        raise ValueError("claim request requires entity, cutoff_timestamp and claims")
    if not isinstance(request["entity"], str) or not request["entity"].strip():
        raise ValueError("entity must be a nonempty string")
    cutoff_text = request["cutoff_timestamp"]
    if not isinstance(cutoff_text, str):
        raise ValueError("cutoff_timestamp must be timezone-aware")
    try:
        cutoff = datetime.fromisoformat(cutoff_text)
    except ValueError as exc:
        raise ValueError("cutoff_timestamp must be timezone-aware") from exc
    if cutoff.utcoffset() is None:
        raise ValueError("cutoff_timestamp must be timezone-aware")
    claims = request["claims"]
    if not isinstance(claims, list) or not claims:
        raise ValueError("claims must be a nonempty list")
    seen = set()
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != CLAIM_FIELDS:
            raise ValueError("claim fields must be: " + ", ".join(sorted(CLAIM_FIELDS)))
        claim_id = claim["claim_id"]
        if not isinstance(claim_id, str) or not SAFE_ID.fullmatch(claim_id):
            raise ValueError("invalid claim_id")
        if claim_id in seen:
            raise ValueError("duplicate claim_id")
        seen.add(claim_id)
        if not isinstance(claim["claim_type"], str) or claim["claim_type"] not in CLAIM_TYPES:
            raise ValueError("invalid claim_type")
        for field in ("statement", "passage_locator"):
            if not isinstance(claim[field], str) or not claim[field].strip():
                raise ValueError(f"{field} must be a nonempty string")
        if not isinstance(claim["source_id"], str) or not SAFE_ID.fullmatch(claim["source_id"]):
            raise ValueError("invalid source_id")
        if not isinstance(claim["version_id"], str) or not DIGEST.fullmatch(claim["version_id"]):
            raise ValueError("invalid version_id")
        if not isinstance(claim["as_of"], str):
            raise ValueError("as_of must be an ISO date")
        try:
            if date.fromisoformat(claim["as_of"]).isoformat() != claim["as_of"]:
                raise ValueError("as_of must be an ISO date")
        except ValueError as exc:
            raise ValueError("as_of must be an ISO date") from exc
    return request, cutoff


def _validate_source_report(report, request):
    if report.get("entity") != request["entity"]:
        raise ValueError("source report entity differs from claim request")
    if report.get("cutoff_timestamp") != request["cutoff_timestamp"]:
        raise ValueError("source report cutoff differs from claim request")
    if report.get("status") not in {"SOURCE_READY", "SOURCE_BLOCKED"}:
        raise ValueError("source report status is invalid")
    sources = report.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("source report has no source results")
    if any(not isinstance(item, dict) or not isinstance(item.get("source_id"), str)
           for item in sources):
        raise ValueError("source report has invalid source results")
    if len({item["source_id"] for item in sources}) != len(sources):
        raise ValueError("source report has duplicate source IDs")


def _claim_status(claim, source_report, project_dir, cutoff):
    base = {
        "claim_id": claim["claim_id"], "claim_type": claim["claim_type"],
        "statement": claim["statement"], "as_of": claim["as_of"],
        "source_id": claim["source_id"], "version_id": claim["version_id"],
        "passage_locator": claim["passage_locator"], "passage_status": "UNVERIFIED",
    }
    if date.fromisoformat(claim["as_of"]) > cutoff.date():
        return {**base, "status": "AFTER_CUTOFF", "reason": "claim date is after cutoff"}
    if claim["claim_type"] not in DIRECT_TYPES:
        return {**base, "status": "NEEDS_DERIVATION",
                "reason": "claim type needs a calculation or judgment contract"}
    if source_report["status"] != "SOURCE_READY":
        return {**base, "status": "SOURCE_NOT_READY", "reason": "source report is blocked"}
    selected = next((item for item in source_report["sources"]
                     if item["source_id"] == claim["source_id"]), None)
    if selected is None or selected.get("status") != "CURRENT":
        return {**base, "status": "SOURCE_NOT_READY", "reason": "source is not current in report"}
    if selected.get("version_id") != claim["version_id"]:
        return {**base, "status": "VERSION_MISMATCH", "reason": "claim does not use selected version"}
    version_path = (project_dir / "data/registry/sources" / claim["source_id"] /
                    f'{claim["version_id"]}.json')
    try:
        version = _read_existing(version_path)
        if version["source_id"] != claim["source_id"]:
            raise ValueError("version source ID differs")
        digest = version["raw_sha256"]
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            raise ValueError("raw digest is invalid")
        if digest != selected.get("raw_sha256"):
            raise ValueError("raw digest differs from source report")
        blob = project_dir / "data/raw/sha256" / digest
        if _hash_file(blob) != digest:
            raise ValueError("raw blob differs from source version")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {**base, "status": "INVALID_SOURCE", "reason": str(exc)}
    return {**base, "raw_sha256": digest, "status": "LINEAGE_LINKED",
            "reason": "exact raw source is present; passage meaning is unverified"}


def _gap(claim_result, run_id):
    linked = claim_result["status"] == "LINEAGE_LINKED"
    reason = ("passage and statement need review" if linked else claim_result["reason"])
    return {
        "gap_id": f'{run_id}-{claim_result["claim_id"]}',
        "claim_id": claim_result["claim_id"], "status": "OPEN",
        "resolution_type": "INTERNAL_RESEARCH" if linked else "UNCLASSIFIED",
        "web_resolvable": False,
        "preferred_source": claim_result["source_id"],
        "fallback_source": None, "last_attempt": None,
        "reason_unresolved": reason,
    }


def _read_frozen(path, request_hash, source_report_id):
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("existing claim report is invalid")
        report_id = report.pop("report_id")
    except (json.JSONDecodeError, UnicodeError, KeyError, TypeError) as exc:
        raise ValueError("existing claim report is invalid") from exc
    if report_id != _hash_json(report):
        raise ValueError("existing claim report differs from its digest")
    report["report_id"] = report_id
    if report.get("request_hash") != request_hash or report.get("source_report_id") != source_report_id:
        raise ValueError("run_id cannot be reused with changed inputs")
    return report


def evaluate_claims(claims_path: Path, source_report_path: Path, project_dir: Path,
                    state_dir: Path, run_id: str) -> dict:
    """Freeze claim lineage and unresolved gaps; never approve claims."""
    if not isinstance(run_id, str) or not SAFE_ID.fullmatch(run_id):
        raise ValueError("run_id must use letters, digits, underscores or hyphens")
    request, cutoff = _read_request(claims_path)
    source_report = load_refresh_report(source_report_path)
    _validate_source_report(source_report, request)
    request_hash = _hash_json(request)
    source_report_id = source_report["report_id"]
    report_path = Path(state_dir) / "claim_runs" / f"{run_id}.json"
    if report_path.exists():
        return _read_frozen(report_path, request_hash, source_report_id)
    project_dir = Path(project_dir)
    claim_results = [
        _claim_status(claim, source_report, project_dir, cutoff) for claim in request["claims"]
    ]
    report = {
        "run_id": run_id, "entity": request["entity"],
        "cutoff_timestamp": request["cutoff_timestamp"],
        "request_hash": request_hash, "source_report_id": source_report_id,
        "status": "CLAIMS_BLOCKED", "claims": claim_results,
        "gaps": [_gap(item, run_id) for item in claim_results],
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
        return _read_frozen(report_path, request_hash, source_report_id)
    finally:
        temp_path.unlink(missing_ok=True)
    return report
