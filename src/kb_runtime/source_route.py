"""Freeze a rights-gated route decision for one observed source gap.

This module plans a reviewed local attempt. It does not acquire documents.
"""

from datetime import datetime, timezone
from pathlib import Path

from .claim_lineage import SAFE_ID, _hash_json, load_claim_report
from .gap_attempt import (ADAPTER_ID, CLASSES, PACKET_FIELDS, _eligibility,
                          _parents, _read_json, _read_sealed, _rights, _sealed,
                          _text, _time, _url, _verify_parents, _write_once)
from .source_refresh import load_refresh_report


ACTIVATION_FIELDS = {"origin", "observed_gap_reason", "local_attempt_id",
                     "classification_packet", "rights_extension"}
RIGHTS_FIELDS = {"endpoint", "frequency", "retention", "limits", "expires_at"}


def _classification(value, claim, source, now):
    if not isinstance(value, dict) or set(value) != PACKET_FIELDS:
        raise ValueError("classification packet fields are invalid")
    for field in PACKET_FIELDS:
        _text(value[field], field)
    if value["classification"] not in CLASSES or value["adapter_id"] != ADAPTER_ID:
        raise ValueError("classification or adapter_id is invalid")
    for field in ("gap_id", "operator_id", "reviewer_id", "source_id"):
        if not SAFE_ID.fullmatch(value[field]):
            raise ValueError(f"{field} is unsafe")
    if (value["claim_report_id"] != claim.get("report_id")
            or value["source_report_id"] != source.get("report_id")
            or value["entity"] != claim.get("entity")
            or value["entity"] != source.get("entity")
            or value["cutoff_timestamp"] != claim.get("cutoff_timestamp")
            or value["cutoff_timestamp"] != source.get("cutoff_timestamp")
            or claim.get("source_report_id") != source.get("report_id")):
        raise ValueError("classification packet parent binding differs")
    _time(value["cutoff_timestamp"], "cutoff_timestamp")
    if (_time(value["reviewed_at"], "reviewed_at") > now
            or _time(value["rights_reviewed_at"], "rights_reviewed_at") > now):
        raise ValueError("review timestamp is after route time")
    _url(value["source_url"])
    return value


def _rights_sufficient(packet, extension, now):
    try:
        _rights(packet)
        if not isinstance(extension, dict) or set(extension) != RIGHTS_FIELDS:
            return False
        for field in RIGHTS_FIELDS:
            _text(extension[field], field)
        if extension["endpoint"] != packet["source_url"]:
            return False
        if _time(extension["expires_at"], "expires_at") <= now:
            return False
        if extension["frequency"] != "one reviewed document":
            return False
        if extension["retention"] != "local KB raw store":
            return False
        if extension["limits"] != "no redistribution":
            return False
    except ValueError:
        return False
    return True


def _check_local_attempt(state, attempt_id, claim, source, gap, packet):
    base = state / "gap_attempts" / attempt_id
    try:
        intent = _read_sealed(base / "intent.json", "intent_id")
        result = _read_sealed(base / "result.json", "result_id")
    except OSError as exc:
        raise ValueError("local attempt is unavailable") from exc
    expected = {
        "claim_report_id": claim["report_id"],
        "source_report_id": source["report_id"],
        "gap_id": gap["gap_id"],
        "source_id": packet["source_id"],
        "source_url": packet["source_url"],
    }
    if (result.get("intent_id") != intent["intent_id"]
            or result.get("gap_status") != "OPEN"
            or result.get("publication_allowed") is not False
            or any(intent.get(key) != value or result.get(key) != value
                   for key, value in expected.items())
            or any(result.get(key) != intent.get(key)
                   for key in ("packet_hash", "classification", "adapter_id",
                               "attempted_at", "status", "rights_use", "rights_evidence_ref"))):
        raise ValueError("local attempt differs from route gap")


def select_gap_route(activation_packet_path: Path, claim_report_path: Path,
                     source_report_path: Path, source_request_path: Path,
                     claim_request_path: Path, project_dir: Path,
                     state_dir: Path, route_id: str) -> dict:
    """Plan one source route without fetching, registering, or closing a gap."""
    if not isinstance(route_id, str) or not SAFE_ID.fullmatch(route_id):
        raise ValueError("route_id is unsafe")
    project, state = Path(project_dir), Path(state_dir)
    claim = load_claim_report(Path(claim_report_path))
    source = load_refresh_report(Path(source_report_path))
    if (Path(claim_report_path).resolve() !=
            (state / "claim_runs" / f'{claim.get("run_id")}.json').resolve()
            or Path(source_report_path).resolve() !=
            (state / "refresh_runs" / f'{source.get("run_id")}.json').resolve()):
        raise ValueError("parent report path differs from state run")
    _verify_parents(source_request_path, claim_request_path, source, claim, project)
    path = state / "source_routes" / f"{route_id}.json"
    prior = _read_sealed(path, "route_digest") if path.exists() else None
    now = _time(prior["planned_at"], "planned_at") if prior else datetime.now(timezone.utc)
    activation = _read_json(activation_packet_path, "activation packet")
    if set(activation) != ACTIVATION_FIELDS:
        raise ValueError("activation packet fields are invalid")
    if activation["origin"] not in {"SYNTHETIC_FIXTURE", "REAL_OBSERVED"}:
        raise ValueError("activation origin is invalid")
    _text(activation["observed_gap_reason"], "observed_gap_reason")
    local_attempt_id = activation["local_attempt_id"]
    if local_attempt_id is not None and (not isinstance(local_attempt_id, str)
                                         or not SAFE_ID.fullmatch(local_attempt_id)):
        raise ValueError("local_attempt_id is unsafe")
    packet = _classification(activation["classification_packet"], claim, source, now)
    gap, claim_entry, source_entry = _parents(claim, source, packet)
    if local_attempt_id is not None:
        _check_local_attempt(state, local_attempt_id, claim, source, gap, packet)
    eligibility, _ = _eligibility(packet, source_entry, claim_entry, gap, source)
    if eligibility == "RECORDED":
        status = ("REVIEWED_LOCAL" if _rights_sufficient(packet, activation["rights_extension"], now)
                  else "RIGHTS_REVIEW_REQUIRED")
    elif eligibility in {"HUMAN_WORK_REQUIRED", "CLASSIFICATION_REQUIRED"}:
        status = "HUMAN_WORK_REQUIRED"
    else:
        status = "NO_APPROVED_ROUTE"
    value = {
        "route_id": route_id, "planned_at": now.isoformat(),
        "origin": ("SYNTHETIC_FIXTURE" if activation["origin"] == "SYNTHETIC_FIXTURE"
                   else "UNVERIFIED"),
        "asserted_origin": activation["origin"],
        "adapter_activation_allowed": False,
        "activation_hash": _hash_json(activation),
        "rights_hash": _hash_json(activation["rights_extension"]),
        "claim_report_id": claim["report_id"], "source_report_id": source["report_id"],
        "claim_request_hash": claim["request_hash"],
        "source_request_hash": source["request_hash"],
        "gap_id": gap["gap_id"], "entity": packet["entity"],
        "cutoff_timestamp": packet["cutoff_timestamp"],
        "classification": packet["classification"],
        "adapter_id": ADAPTER_ID if status == "REVIEWED_LOCAL" else None,
        "source_id": packet["source_id"], "source_url": packet["source_url"],
        "local_attempt_id": local_attempt_id, "status": status,
        "gap_status": "OPEN", "publication_allowed": False,
    }
    result = _sealed(value, "route_digest")
    if prior is not None and prior != result:
        raise ValueError("route_id cannot be reused with changed inputs")
    _write_once(path, result, "route_digest")
    return result
