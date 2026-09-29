"""Freeze exact quote-byte presence for pinned claims without approving meaning."""

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path

from .claim_lineage import load_claim_report
from .source_store import _hash_file, _read_existing


SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
MAX_TEXT_BYTES = 16 * 1024 * 1024
MAX_QUOTE_BYTES = 4096


def _hash_json(value):
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_packet(path, claim_report):
    try:
        packet = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("passage packet must be valid JSON") from exc
    if not isinstance(packet, dict) or set(packet) != {"entity", "cutoff_timestamp", "quotes"}:
        raise ValueError("passage packet requires entity, cutoff_timestamp, and quotes")
    if packet["entity"] != claim_report.get("entity"):
        raise ValueError("passage packet entity differs from claim report")
    cutoff = packet["cutoff_timestamp"]
    if not isinstance(cutoff, str) or cutoff != claim_report.get("cutoff_timestamp"):
        raise ValueError("passage packet cutoff differs from claim report")
    try:
        parsed = datetime.fromisoformat(cutoff)
    except ValueError as exc:
        raise ValueError("passage packet cutoff is invalid") from exc
    if parsed.utcoffset() is None:
        raise ValueError("passage packet cutoff must be timezone-aware")
    if not isinstance(packet["quotes"], list):
        raise ValueError("quotes must be a list")
    known = {claim["claim_id"] for claim in claim_report["claims"]}
    seen = set()
    for entry in packet["quotes"]:
        if not isinstance(entry, dict) or set(entry) != {"claim_id", "verbatim_quote"}:
            raise ValueError("quote needs claim_id and verbatim_quote")
        claim_id = entry["claim_id"]
        if not isinstance(claim_id, str) or claim_id not in known or claim_id in seen:
            raise ValueError("duplicate or unknown passage claim_id")
        seen.add(claim_id)
        quote = entry["verbatim_quote"]
        if not isinstance(quote, str) or not quote or "\x00" in quote:
            raise ValueError("verbatim_quote must be nonempty text without NUL")
        try:
            quote_size = len(quote.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise ValueError("verbatim_quote must be valid UTF-8") from exc
        if quote_size > MAX_QUOTE_BYTES:
            raise ValueError("verbatim_quote is too long")
    return packet


def _plain_text(raw):
    if b"%PDF-" in raw[:1024] or b"\x00" in raw:
        return False
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return all(
        character in "\t\n\r" or unicodedata.category(character) != "Cc"
        for character in decoded
    )


def _presence(claim, quote, project_dir):
    if claim.get("status") != "LINEAGE_LINKED":
        return "LINEAGE_BLOCKED", None
    if quote is None:
        return "MISSING_QUOTE", None
    source_id = claim.get("source_id")
    version_id = claim.get("version_id")
    raw_hash = claim.get("raw_sha256")
    if (not isinstance(source_id, str) or not SAFE_ID.fullmatch(source_id)
            or not isinstance(version_id, str) or not DIGEST.fullmatch(version_id)
            or not isinstance(raw_hash, str) or not DIGEST.fullmatch(raw_hash)):
        return "INVALID_SOURCE", None
    version_path = project_dir / "data/registry/sources" / source_id / f"{version_id}.json"
    blob = project_dir / "data/raw/sha256" / raw_hash
    try:
        version = _read_existing(version_path)
        if (version["source_id"] != source_id or version["version_id"] != version_id
                or version["raw_sha256"] != raw_hash or _hash_file(blob) != raw_hash):
            return "INVALID_SOURCE", None
        if blob.stat().st_size > MAX_TEXT_BYTES:
            return "UNSUPPORTED_FORMAT", None
        raw = blob.read_bytes()
    except (OSError, ValueError, KeyError, TypeError):
        return "INVALID_SOURCE", None
    if hashlib.sha256(raw).hexdigest() != raw_hash:
        return "INVALID_SOURCE", None
    if not _plain_text(raw):
        return "UNSUPPORTED_FORMAT", None
    offset = raw.find(quote.encode("utf-8"))
    return ("QUOTE_PRESENT", offset) if offset >= 0 else ("QUOTE_ABSENT", None)


def _read_frozen(path, run_id, packet_hash, claim_report_id):
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("existing passage report is invalid")
        report_id = report.pop("report_id")
    except (OSError, json.JSONDecodeError, UnicodeError, KeyError, TypeError) as exc:
        raise ValueError("existing passage report is invalid") from exc
    if report_id != _hash_json(report):
        raise ValueError("existing passage report differs from its digest")
    report["report_id"] = report_id
    if report.get("run_id") != run_id:
        raise ValueError("existing passage report run_id differs from path")
    if (report.get("status") != "PASSAGES_UNVERIFIED"
            or report.get("publication_allowed") is not False
            or not isinstance(report.get("results"), list)
            or any(not isinstance(result, dict) or result.get("semantic_status") != "UNVERIFIED"
                   for result in report["results"])):
        raise ValueError("existing passage report has invalid safety fields")
    if (report.get("packet_hash") != packet_hash
            or report.get("claim_report_id") != claim_report_id):
        raise ValueError("run_id cannot be reused with changed passage inputs")
    return report


def evaluate_passages(packet_path: Path, claim_report_path: Path, project_dir: Path,
                      state_dir: Path, run_id: str) -> dict:
    """Record quote-byte presence while keeping all claim meaning unverified."""
    if not isinstance(run_id, str) or not SAFE_ID.fullmatch(run_id):
        raise ValueError("run_id is invalid")
    claim_report = load_claim_report(claim_report_path)
    packet = _read_packet(packet_path, claim_report)
    packet_hash = _hash_json(packet)
    claim_report_id = claim_report["report_id"]
    state_dir = Path(state_dir)
    path = state_dir / "passage_runs" / f"{run_id}.json"
    if path.exists():
        return _read_frozen(path, run_id, packet_hash, claim_report_id)
    quotes = {item["claim_id"]: item["verbatim_quote"] for item in packet["quotes"]}
    project_dir = Path(project_dir)
    results = []
    for claim in claim_report["claims"]:
        quote = quotes.get(claim["claim_id"])
        status, offset = _presence(claim, quote, project_dir)
        results.append({
            "claim_id": claim["claim_id"], "source_id": claim["source_id"],
            "version_id": claim["version_id"], "raw_sha256": claim.get("raw_sha256"),
            "passage_locator": claim["passage_locator"], "verbatim_quote": quote,
            "byte_offset": offset, "status": status, "semantic_status": "UNVERIFIED",
        })
    report = {
        "run_id": run_id, "entity": packet["entity"],
        "cutoff_timestamp": packet["cutoff_timestamp"],
        "packet_hash": packet_hash, "claim_report_id": claim_report_id,
        "status": "PASSAGES_UNVERIFIED", "publication_allowed": False,
        "results": results,
    }
    report["report_id"] = _hash_json(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=".incoming-", delete=False
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
        os.link(temp_path, path)
    except FileExistsError:
        return _read_frozen(path, run_id, packet_hash, claim_report_id)
    finally:
        temp_path.unlink(missing_ok=True)
    return report
