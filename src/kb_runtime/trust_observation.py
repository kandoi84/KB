"""Bind an independent trust label to one frozen gap attempt."""

import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .claim_lineage import SAFE_ID, _hash_json
from .gap_attempt import (PACKET_FIELDS, _read_json, _read_sealed, _sealed, _text,
                          _time, _url, _write_once)


FIELDS = {"observation_id", "attempt_id", "declared_origin", "adjudicator_id",
          "adjudicated_at", "rubric_version", "source_authority", "document_type",
          "reporting_period", "raw_sha256", "labels", "failure_class"}
LABEL_FIELDS = {"source_identity", "publication_cutoff", "raw_replay",
                "rights_workflow", "usable_document"}
LABEL_VALUES = {"PASS", "FAIL", "UNRESOLVED", "NOT_APPLICABLE", "UNVERIFIED"}
FAILURE_CLASSES = {"NONE", "HUMAN_WORK", "PERMISSION", "RATE_LIMIT", "TRANSPORT",
                   "PARSE", "IDENTITY", "STALE", "MISSING", "OTHER"}
PERIOD = re.compile(r"[0-9]{4}-Q[1-4]\Z")
ATTEMPT_CORE_FIELDS = {"attempt_id", "claim_report_id", "source_report_id", "gap_id",
                       "claim_id", "gap_reason", "packet_hash", "classification",
                       "adapter_id", "adapter_version", "source_id", "source_url",
                       "reviewer_id", "rights_use", "rights_evidence_ref",
                       "metadata_hash", "raw_sha256", "raw_byte_count", "status", "reason",
                       "attempted_at"}
ATTEMPT_INTENT_FIELDS = ATTEMPT_CORE_FIELDS | {"intent_id"}
ATTEMPT_RESULT_FIELDS = ATTEMPT_CORE_FIELDS | {"intent_id", "result_id", "version_id",
                                                "gap_status", "publication_allowed"}
STATUS_FAILURE = {"RECORDED": "NONE", "HUMAN_WORK_REQUIRED": "HUMAN_WORK",
                  "RIGHTS_BLOCKED": "PERMISSION", "CLASSIFICATION_REQUIRED": "OTHER",
                  "INELIGIBLE": "OTHER"}


def _attempt(packet_path, intent_path, result_path, state, attempt_id):
    expected_base = state / "gap_attempts" / attempt_id
    if (Path(intent_path).resolve() != (expected_base / "intent.json").resolve()
            or Path(result_path).resolve() != (expected_base / "result.json").resolve()):
        raise ValueError("attempt paths differ from state")
    try:
        intent = _read_sealed(intent_path, "intent_id")
        result = _read_sealed(result_path, "result_id")
    except OSError as exc:
        raise ValueError("attempt receipt is unavailable") from exc
    if set(intent) != ATTEMPT_INTENT_FIELDS or set(result) != ATTEMPT_RESULT_FIELDS:
        raise ValueError("attempt receipt schema is invalid")
    packet = _read_json(packet_path, "classification packet")
    if set(packet) != PACKET_FIELDS or _hash_json(packet) != result.get("packet_hash"):
        raise ValueError("classification packet differs from attempt")
    _url(packet["source_url"])
    if (intent.get("attempt_id") != attempt_id or result.get("attempt_id") != attempt_id
            or result.get("intent_id") != intent.get("intent_id")
            or result.get("gap_status") != "OPEN"
            or result.get("publication_allowed") is not False
            or result.get("reviewer_id") != packet.get("reviewer_id")
            or result.get("source_id") != packet.get("source_id")
            or result.get("source_url") != packet.get("source_url")
            or result.get("claim_report_id") != packet.get("claim_report_id")
            or result.get("source_report_id") != packet.get("source_report_id")
            or result.get("gap_id") != packet.get("gap_id")
            or any(result.get(key) != intent.get(key) for key in intent
                   if key != "intent_id")):
        raise ValueError("attempt receipts disagree")
    return packet, intent, result


def record_trust_observation(observation_path: Path, classification_packet_path: Path,
                             attempt_intent_path: Path, attempt_result_path: Path,
                             state_dir: Path) -> dict:
    """Store one write-once human label; no acquisition or investment scoring."""
    state = Path(state_dir)
    observation = _read_json(observation_path, "trust observation")
    if set(observation) != FIELDS:
        raise ValueError("trust observation fields are invalid")
    for field in ("observation_id", "attempt_id", "adjudicator_id", "rubric_version",
                  "source_authority", "document_type", "reporting_period", "failure_class"):
        _text(observation[field], field)
    for field in ("observation_id", "attempt_id", "adjudicator_id"):
        if not SAFE_ID.fullmatch(observation[field]):
            raise ValueError(f"{field} is unsafe")
    if (not isinstance(observation["declared_origin"], str)
            or observation["declared_origin"] not in {"SYNTHETIC_FIXTURE", "REAL_OBSERVED"}
            or observation["rubric_version"] != "trust-v1"
            or observation["document_type"] != "EXCHANGE_FILING"
            or not PERIOD.fullmatch(observation["reporting_period"])
            or observation["failure_class"] not in FAILURE_CLASSES):
        raise ValueError("observation classification is invalid")
    labels = observation["labels"]
    if (not isinstance(labels, dict) or set(labels) != LABEL_FIELDS
            or any(not isinstance(value, str) or value not in LABEL_VALUES
                   for value in labels.values())
            or labels["raw_replay"] not in {"UNVERIFIED", "NOT_APPLICABLE"}):
        raise ValueError("trust labels are invalid")
    packet, intent, result = _attempt(classification_packet_path, attempt_intent_path,
                                      attempt_result_path, state, observation["attempt_id"])
    if labels["raw_replay"] != ("UNVERIFIED" if result["status"] == "RECORDED"
                                else "NOT_APPLICABLE"):
        raise ValueError("raw replay label is unsupported by attempt evidence")
    if observation["adjudicator_id"] in {packet["operator_id"], packet["reviewer_id"]}:
        raise ValueError("trust adjudicator must be independent")
    adjudicated = _time(observation["adjudicated_at"], "adjudicated_at")
    if adjudicated < _time(intent["attempted_at"], "attempted_at") or adjudicated > datetime.now(timezone.utc):
        raise ValueError("adjudication time is outside attempt interval")
    authority = "NSE" if urlsplit(packet["source_url"]).hostname.endswith("nseindia.com") else "BSE"
    if observation["source_authority"] != authority:
        raise ValueError("source authority differs from attempt")
    if observation["raw_sha256"] != result["raw_sha256"]:
        raise ValueError("raw hash differs from attempt")
    if observation["failure_class"] != STATUS_FAILURE.get(result["status"]):
        raise ValueError("failure class differs from attempt status")
    value = {
        "observation_id": observation["observation_id"],
        "attempt_id": observation["attempt_id"],
        "attempt_intent_id": intent["intent_id"],
        "attempt_result_id": result["result_id"],
        "attempt_status": result["status"],
        "classification_packet_hash": _hash_json(packet),
        "observation_hash": _hash_json(observation),
        "origin": ("SYNTHETIC_FIXTURE" if observation["declared_origin"] == "SYNTHETIC_FIXTURE"
                   else "UNVERIFIED"),
        "declared_origin": observation["declared_origin"],
        "adjudicator_id": observation["adjudicator_id"],
        "adjudicated_at": observation["adjudicated_at"],
        "rubric_version": observation["rubric_version"],
        "entity": packet["entity"], "source_id": result["source_id"],
        "adapter_id": result["adapter_id"],
        "source_authority": observation["source_authority"],
        "document_type": observation["document_type"],
        "reporting_period": observation["reporting_period"],
        "raw_sha256": observation["raw_sha256"],
        "labels": labels, "failure_class": observation["failure_class"],
        "publication_allowed": False,
    }
    receipt = _sealed(value, "observation_digest")
    _write_once(state / "trust_observations" / f'{observation["observation_id"]}.json',
                receipt, "observation_digest")
    return receipt
