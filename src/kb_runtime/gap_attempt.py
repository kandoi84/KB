"""Freeze a reviewed local attempt to obtain one missing primary source."""

import hashlib
import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .claim_lineage import (SAFE_ID, _claim_status, _gap, _hash_json,
                            _read_request as _read_claim_request, load_claim_report)
from .source_refresh import (_read_request as _read_source_request, _source_status,
                             load_refresh_report)
from .source_store import _hash_file, _metadata, _read_existing, record_source


ADAPTER_ID = "reviewed_local_primary_v1"
MAX_RAW_BYTES = 25 * 1024 * 1024
PACKET_FIELDS = {
    "gap_id", "claim_report_id", "source_report_id", "entity", "cutoff_timestamp",
    "classification", "operator_id", "reviewer_id", "reviewed_at",
    "classification_reason", "adapter_id", "source_id", "source_url", "rights_use",
    "rights_evidence_ref", "rights_scope_actor", "rights_scope_method",
    "rights_scope_storage", "rights_scope_purpose", "rights_reviewed_by",
    "rights_reviewed_at",
}
CLASSES = {
    "PUBLIC_PRIMARY_MISSING", "PUBLIC_PRIMARY_STALE", "INTERNAL_RESEARCH",
    "PROPRIETARY_OR_RESTRICTED", "UNCLASSIFIED",
}


def _read_json(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _time(value, field):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a timezone-aware timestamp")
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be a timezone-aware timestamp") from exc
    if timestamp.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware timestamp")
    return timestamp


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    return value


def _url(value):
    _text(value, "source_url")
    parsed = urlsplit(value)
    host = parsed.hostname
    if (parsed.scheme != "https" or not host or parsed.username or parsed.password
            or parsed.port is not None or parsed.query or parsed.fragment
            or not parsed.path or parsed.path == "/"
            or host.lower() != host or parsed.netloc != host
            or not any(host == root or host.endswith("." + root)
                       for root in ("nseindia.com", "bseindia.com"))):
        raise ValueError("source_url must be an exact reviewed HTTPS exchange URL")


def _packet(path, claim, source, now):
    packet = _read_json(path, "classification packet")
    if set(packet) != PACKET_FIELDS:
        raise ValueError("classification packet fields are invalid")
    for field in PACKET_FIELDS:
        _text(packet[field], field)
    if packet["classification"] not in CLASSES or packet["adapter_id"] != ADAPTER_ID:
        raise ValueError("classification or adapter_id is invalid")
    for field in ("gap_id", "operator_id", "reviewer_id", "source_id"):
        if not SAFE_ID.fullmatch(packet[field]):
            raise ValueError(f"{field} is unsafe")
    if (packet["claim_report_id"] != claim.get("report_id")
            or packet["source_report_id"] != source.get("report_id")
            or packet["entity"] != claim.get("entity") or packet["entity"] != source.get("entity")
            or packet["cutoff_timestamp"] != claim.get("cutoff_timestamp")
            or packet["cutoff_timestamp"] != source.get("cutoff_timestamp")
            or claim.get("source_report_id") != source.get("report_id")):
        raise ValueError("classification packet parent binding differs")
    _time(packet["cutoff_timestamp"], "cutoff_timestamp")
    if (_time(packet["reviewed_at"], "reviewed_at") > now
            or _time(packet["rights_reviewed_at"], "rights_reviewed_at") > now):
        raise ValueError("review timestamp is after attempt time")
    _url(packet["source_url"])
    return packet


def _parents(claim, source, packet):
    if (claim.get("status") != "CLAIMS_BLOCKED" or source.get("status") not in
            {"SOURCE_READY", "SOURCE_BLOCKED"}):
        raise ValueError("parent report status is invalid")
    claims, gaps, sources = claim.get("claims"), claim.get("gaps"), source.get("sources")
    if (not isinstance(claims, list) or not isinstance(gaps, list) or not isinstance(sources, list)
            or not claims or len(claims) != len(gaps) or not sources):
        raise ValueError("parent report entries are invalid")
    if len({item.get("claim_id") for item in claims if isinstance(item, dict)}) != len(claims):
        raise ValueError("duplicate claim in parent report")
    if len({item.get("source_id") for item in sources if isinstance(item, dict)}) != len(sources):
        raise ValueError("duplicate source in parent report")
    matches = [gap for gap in gaps if isinstance(gap, dict)
               and gap.get("gap_id") == packet["gap_id"]]
    if len(matches) != 1:
        raise ValueError("gap_id is absent or duplicate")
    gap = matches[0]
    claims_found = [item for item in claims if isinstance(item, dict)
                    and item.get("claim_id") == gap.get("claim_id")]
    if (len(claims_found) != 1 or gap.get("status") != "OPEN"
            or gap.get("gap_id") != f'{claim.get("run_id")}-{gap.get("claim_id")}'
            or gap.get("preferred_source") != packet["source_id"]
            or gap.get("web_resolvable") is not False
            or claims_found[0].get("source_id") != packet["source_id"]):
        raise ValueError("gap does not bind to the claimed source")
    item = claims_found[0]
    selected = [entry for entry in sources if isinstance(entry, dict)
                and entry.get("source_id") == packet["source_id"]]
    if len(selected) != 1:
        raise ValueError("source_id is absent or duplicate")
    return gap, item, selected[0]


def _eligibility(packet, source_entry, claim_entry, gap, source_report):
    if (claim_entry.get("status") != "SOURCE_NOT_READY"
            or claim_entry.get("passage_status") != "UNVERIFIED"
            or gap.get("resolution_type") != "UNCLASSIFIED"
            or source_report.get("status") != "SOURCE_BLOCKED"
            or source_entry.get("status") in {"AFTER_CUTOFF", "MISSING_RAW",
                                              "CORRUPT_RAW", "INVALID_REGISTRY"}):
        return "INELIGIBLE", "gap is not an unresolved missing or stale primary source"
    classification = packet["classification"]
    if classification == "INTERNAL_RESEARCH":
        return "HUMAN_WORK_REQUIRED", "gap requires analyst work"
    if classification == "PROPRIETARY_OR_RESTRICTED":
        return "RIGHTS_BLOCKED", "source is restricted"
    if classification == "UNCLASSIFIED":
        return "CLASSIFICATION_REQUIRED", "gap has no actionable classification"
    expected = "MISSING" if classification == "PUBLIC_PRIMARY_MISSING" else "STALE"
    if source_entry.get("status") != expected:
        return "INELIGIBLE", f"source readiness is not {expected}"
    return "RECORDED", "reviewed local primary source recorded for a later refresh"


def _historical_source(target, project, cutoff, frozen):
    current = _source_status(target, project, cutoff)
    if current == frozen:
        return current
    # A later import is deliberately invisible to the old missing-source run.
    if frozen == {"source_id": target["source_id"], "status": "MISSING",
                  "reason": "no registered source version"} and current.get("status") == "AFTER_CUTOFF":
        versions_dir = project / "data/registry/sources" / target["source_id"]
        versions = [_read_existing(path) for path in sorted(versions_dir.glob("*.json"))]
        if versions and all(_time(value["retrieved_at"], "retrieved_at") > cutoff
                            for value in versions):
            return frozen
    raise ValueError("source report differs from historical source state")


def _verify_parents(source_request_path, claim_request_path, source, claim, project):
    source_request, cutoff = _read_source_request(source_request_path)
    claim_request, claim_cutoff = _read_claim_request(claim_request_path)
    if (source.get("request_hash") != _hash_json(source_request)
            or claim.get("request_hash") != _hash_json(claim_request)):
        raise ValueError("parent request hash differs")
    if (source.get("entity") != source_request["entity"]
            or source.get("cutoff_timestamp") != source_request["cutoff_timestamp"]
            or claim.get("entity") != claim_request["entity"]
            or claim.get("cutoff_timestamp") != claim_request["cutoff_timestamp"]
            or source_request["entity"] != claim_request["entity"]
            or source_request["cutoff_timestamp"] != claim_request["cutoff_timestamp"]
            or cutoff != claim_cutoff):
        raise ValueError("parent request scope differs")
    frozen_sources = source.get("sources")
    if not isinstance(frozen_sources, list) or len(frozen_sources) != len(source_request["required_sources"]):
        raise ValueError("source report differs from historical source state")
    for target, frozen in zip(source_request["required_sources"], frozen_sources):
        _historical_source(target, project, cutoff, frozen)
    expected_source_status = ("SOURCE_READY" if all(item["status"] == "CURRENT"
                                                  for item in frozen_sources)
                              else "SOURCE_BLOCKED")
    if source.get("status") != expected_source_status:
        raise ValueError("source report differs from historical source state")
    expected_claims = [_claim_status(item, source, project, cutoff)
                       for item in claim_request["claims"]]
    expected_gaps = [_gap(item, claim["run_id"]) for item in expected_claims]
    if (claim.get("claims") != expected_claims or claim.get("gaps") != expected_gaps
            or claim.get("status") != "CLAIMS_BLOCKED"
            or claim.get("source_report_id") != source.get("report_id")):
        raise ValueError("claim report differs from historical claim state")


def _rights(packet):
    if packet["rights_use"] != "LOCAL_RESEARCH_COLLECTION_ALLOWED":
        raise ValueError("rights_use does not permit local research collection")
    ref = packet["rights_evidence_ref"].strip().lower()
    if ref in {"public", "n/a", "na", "none"} or ref.startswith(("http://", "https://")):
        raise ValueError("rights_evidence_ref must identify concrete permission")
    if packet["rights_scope_actor"] != packet["operator_id"]:
        raise ValueError("rights scope actor differs from operator")
    if (packet["rights_scope_method"] != "manual local download"
            or packet["rights_scope_storage"] != "local KB raw store"
            or packet["rights_scope_purpose"] != "internal equity research"):
        raise ValueError("rights scope does not cover local research collection")


def _inputs(packet, metadata_path, raw_path, now):
    _rights(packet)
    if metadata_path is None or raw_path is None:
        raise ValueError("eligible attempt requires metadata and raw file")
    metadata = _metadata(metadata_path)
    if (metadata["source_id"] != packet["source_id"] or metadata["entity"] != packet["entity"]
            or metadata["url"] != packet["source_url"]
            or metadata["source_kind"] != "EXCHANGE_FILING"):
        raise ValueError("metadata differs from reviewed primary source")
    if (_time(metadata["retrieved_at"], "retrieved_at") > now
            or _time(metadata["observed_at"], "observed_at") > now):
        raise ValueError("source metadata timestamp is after attempt time")
    path = Path(raw_path)
    try:
        mode = path.lstat().st_mode
        size = path.stat().st_size
    except OSError as exc:
        raise ValueError("raw file is unavailable") from exc
    if not stat.S_ISREG(mode) or size <= 0 or size > MAX_RAW_BYTES:
        raise ValueError("raw file must be a nonempty regular file within 25 MiB")
    raw_hash = _hash_file(path)
    return metadata, raw_hash, size


def _copy_verified_raw(raw_path, expected_hash, expected_size, target_dir):
    """Pin exact bytes before the source store reads a caller-owned path."""
    with tempfile.NamedTemporaryFile(dir=target_dir, prefix=".gap-raw-", delete=False) as output:
        snapshot = Path(output.name)
        digest = hashlib.sha256()
        size = 0
        try:
            with Path(raw_path).open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    size += len(chunk)
                    if size > MAX_RAW_BYTES:
                        raise ValueError("raw file grew beyond 25 MiB")
                    digest.update(chunk)
                    output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            snapshot.unlink(missing_ok=True)
            raise
    if size != expected_size or digest.hexdigest() != expected_hash:
        snapshot.unlink(missing_ok=True)
        raise ValueError("raw file changed before source registration")
    return snapshot


def _sealed(value, id_field):
    return {**value, id_field: _hash_json(value)}


def _read_sealed(path, id_field):
    value = _read_json(path, path.name)
    digest = value.get(id_field)
    if not isinstance(digest, str) or digest != _hash_json({k: v for k, v in value.items()
                                                           if k != id_field}):
        raise ValueError(f"{path.name} differs from its digest")
    return value


def _write_once(path, value, id_field):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".incoming-", delete=False) as output:
        temp = Path(output.name)
        try:
            json.dump(value, output, indent=2, sort_keys=True, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    try:
        os.link(temp, path)
    except FileExistsError:
        if _read_sealed(path, id_field) != value:
            raise ValueError(f"{path.name} collision")
    finally:
        temp.unlink(missing_ok=True)


def _verify_version(result, project):
    if result["version_id"] is None:
        return
    path = project / "data/registry/sources" / result["source_id"] / f'{result["version_id"]}.json'
    try:
        version = _read_existing(path)
    except OSError as exc:
        raise ValueError("recorded source version is unavailable") from exc
    if (version.get("raw_sha256") != result["raw_sha256"]
            or version.get("version_id") != result["version_id"]
            or version.get("retrieved_at") != result["attempted_at"]
            or version.get("url") != result["source_url"]):
        raise ValueError("recorded source version differs from attempt")
    blob = project / "data/raw/sha256" / result["raw_sha256"]
    try:
        actual_hash = _hash_file(blob)
    except OSError as exc:
        raise ValueError("recorded raw blob is unavailable") from exc
    if actual_hash != result["raw_sha256"]:
        raise ValueError("recorded raw blob differs from attempt")


def attempt_gap(packet_path: Path, claim_report_path: Path, source_report_path: Path,
                source_request_path: Path, claim_request_path: Path,
                raw_path: Path | None, metadata_path: Path | None, project_dir: Path,
                state_dir: Path, attempt_id: str) -> dict:
    """Record one rights-reviewed local source candidate; leave the gap open."""
    if not isinstance(attempt_id, str) or not SAFE_ID.fullmatch(attempt_id):
        raise ValueError("attempt_id is unsafe")
    project, state = Path(project_dir), Path(state_dir)
    claim = load_claim_report(Path(claim_report_path))
    source = load_refresh_report(Path(source_report_path))
    if (Path(claim_report_path).resolve() != (state / "claim_runs" /
            f'{claim.get("run_id")}.json').resolve() or
            Path(source_report_path).resolve() != (state / "refresh_runs" /
            f'{source.get("run_id")}.json').resolve()):
        raise ValueError("parent report path differs from state run")
    _verify_parents(source_request_path, claim_request_path, source, claim, project)
    base = state / "gap_attempts" / attempt_id
    intent_path, result_path = base / "intent.json", base / "result.json"
    existing_intent = _read_sealed(intent_path, "intent_id") if intent_path.exists() else None
    now = (_time(existing_intent["attempted_at"], "attempted_at") if existing_intent
           else datetime.now(timezone.utc))
    packet = _packet(packet_path, claim, source, now)
    gap, claim_entry, source_entry = _parents(claim, source, packet)
    status, reason = _eligibility(packet, source_entry, claim_entry, gap, source)
    metadata = raw_hash = size = None
    if status == "RECORDED":
        metadata, raw_hash, size = _inputs(packet, metadata_path, raw_path, now)
    input_binding = {
        "attempt_id": attempt_id, "claim_report_id": claim["report_id"],
        "source_report_id": source["report_id"], "gap_id": gap["gap_id"],
        "claim_id": claim_entry["claim_id"], "gap_reason": gap["reason_unresolved"],
        "packet_hash": _hash_json(packet), "classification": packet["classification"],
        "adapter_id": ADAPTER_ID, "adapter_version": 1, "source_id": packet["source_id"],
        "source_url": packet["source_url"], "reviewer_id": packet["reviewer_id"],
        "rights_use": packet["rights_use"], "rights_evidence_ref": packet["rights_evidence_ref"],
        "metadata_hash": _hash_json(metadata) if metadata is not None else None,
        "raw_sha256": raw_hash, "raw_byte_count": size, "status": status, "reason": reason,
    }
    if existing_intent:
        if {key: existing_intent.get(key) for key in input_binding} != input_binding:
            raise ValueError("attempt_id cannot be reused with changed inputs")
        intent = existing_intent
    else:
        intent = _sealed({**input_binding, "attempted_at": now.isoformat()}, "intent_id")
        _write_once(intent_path, intent, "intent_id")
    expected_version = (_hash_json({**metadata, "retrieved_at": intent["attempted_at"],
                                    "raw_sha256": raw_hash}) if metadata else None)
    expected_result = {
        **input_binding, "intent_id": intent["intent_id"],
        "attempted_at": intent["attempted_at"], "version_id": expected_version,
        "gap_status": "OPEN", "publication_allowed": False,
    }
    if result_path.exists():
        result = _read_sealed(result_path, "result_id")
        if result != _sealed(expected_result, "result_id"):
            raise ValueError("result differs from frozen intent")
        _verify_version(result, project)
        return result
    version = None
    if status == "RECORDED":
        registration = {**metadata, "retrieved_at": intent["attempted_at"]}
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json",
                                         delete=False) as output:
            temp = Path(output.name)
            json.dump(registration, output)
        try:
            snapshot = _copy_verified_raw(raw_path, raw_hash, size, base)
            try:
                version = record_source(temp, snapshot, project)
            finally:
                snapshot.unlink(missing_ok=True)
        finally:
            temp.unlink(missing_ok=True)
        if version["raw_sha256"] != raw_hash:
            raise ValueError("raw file changed during source registration")
        if version["version_id"] != expected_version:
            raise ValueError("recorded source version differs from frozen inputs")
    result = _sealed(expected_result, "result_id")
    _write_once(result_path, result, "result_id")
    _verify_version(result, project)
    return result
