"""Freeze human review of exact direct filing claims for internal use only."""

import json
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

from .claim_lineage import CLAIM_TYPES, DIGEST, SAFE_ID, _hash_json, load_claim_report
from .identity_store import _source, _timestamp
from .metric_store import _filing_source
from .passage_evidence import _presence
from .source_refresh import load_refresh_report


PACKET_FIELDS = {"entity", "cutoff_timestamp", "claim_report_id", "passage_report_id", "decisions"}
DECISION_FIELDS = {
    "claim_id", "reviewer_id", "reviewed_at", "rights_evidence_ref", "rights_use",
    "semantic_decision", "review_note", "contradiction_status", "related_claim_ids",
    "conflict_explanation", "source_id", "version_id", "raw_sha256",
    "verbatim_quote", "byte_offset",
}
DIRECT_TYPES = {"REPORTED_FACT", "MANAGEMENT_GUIDANCE"}
OTHER_ORIGIN_TYPES = {"CONSENSUS", "MARKET_DATA", "SENTIMENT"}
LINEAGE_STATUSES = {
    "LINEAGE_LINKED", "AFTER_CUTOFF", "NEEDS_DERIVATION", "SOURCE_NOT_READY",
    "VERSION_MISMATCH", "INVALID_SOURCE",
}
PASSAGE_STATUSES = {
    "QUOTE_PRESENT", "QUOTE_ABSENT", "MISSING_QUOTE", "LINEAGE_BLOCKED",
    "INVALID_SOURCE", "UNSUPPORTED_FORMAT",
}


def _read_json(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    return value


def _report(path, label):
    report = _read_json(path, label)
    report_id = report.get("report_id")
    if not isinstance(report_id, str) or report_id != _hash_json({k: v for k, v in report.items() if k != "report_id"}):
        raise ValueError(f"{label} differs from its digest")
    return report


def _source_report(claim, state_dir):
    report_id = claim.get("source_report_id")
    if not isinstance(report_id, str) or not DIGEST.fullmatch(report_id):
        raise ValueError("claim source report ID is invalid")
    found = []
    for path in (Path(state_dir) / "refresh_runs").glob("*.json"):
        candidate = _read_json(path, "source report")
        if candidate.get("report_id") == report_id:
            found.append(path)
    if len(found) != 1:
        raise ValueError("claim source report is missing or ambiguous")
    source = load_refresh_report(found[0])
    entries = source.get("sources")
    if (source.get("run_id") != found[0].stem
            or source.get("entity") != claim.get("entity")
            or source.get("cutoff_timestamp") != claim.get("cutoff_timestamp")
            or source.get("status") not in {"SOURCE_READY", "SOURCE_BLOCKED"}
            or not isinstance(entries, list) or not entries
            or any(not isinstance(item, dict) or not isinstance(item.get("source_id"), str)
                   for item in entries)
            or len({item["source_id"] for item in entries}) != len(entries)):
        raise ValueError("claim source report safety fields are invalid")
    ready = all(item.get("status") == "CURRENT" for item in entries)
    if (ready and source["status"] != "SOURCE_READY") or (
            not ready and source["status"] != "SOURCE_BLOCKED"):
        raise ValueError("claim source report readiness is inconsistent")
    by_source = {item["source_id"]: item for item in entries}
    for item in claim["claims"]:
        if item.get("status") == "LINEAGE_LINKED":
            selected = by_source.get(item.get("source_id"))
            if (source["status"] != "SOURCE_READY" or selected is None
                    or selected.get("status") != "CURRENT"
                    or selected.get("version_id") != item.get("version_id")
                    or selected.get("raw_sha256") != item.get("raw_sha256")):
                raise ValueError("claim source report does not support linked lineage")


def _upstream(claim_path, passage_path, state_dir):
    claim = load_claim_report(Path(claim_path))
    passage = _report(passage_path, "passage report")
    claims = claim.get("claims")
    gaps = claim.get("gaps")
    results = passage.get("results")
    if (claim.get("status") != "CLAIMS_BLOCKED"
            or not isinstance(claims, list) or not claims
            or not isinstance(gaps, list) or len(gaps) != len(claims)
            or passage.get("status") != "PASSAGES_UNVERIFIED"
            or passage.get("publication_allowed") is not False
            or passage.get("claim_report_id") != claim["report_id"]
            or passage.get("entity") != claim.get("entity")
            or passage.get("cutoff_timestamp") != claim.get("cutoff_timestamp")
            or not isinstance(results, list) or len(results) != len(claims)):
        raise ValueError("input report safety fields or binding are invalid")
    claim_ids = set()
    gap_ids = set()
    result_ids = set()
    for item in claims:
        if (not isinstance(item, dict) or not isinstance(item.get("claim_id"), str)
                or not SAFE_ID.fullmatch(item["claim_id"])
                or item["claim_id"] in claim_ids
                or item.get("claim_type") not in CLAIM_TYPES
                or item.get("status") not in LINEAGE_STATUSES
                or item.get("passage_status") != "UNVERIFIED"):
            raise ValueError("claim report safety fields are invalid")
        claim_ids.add(item["claim_id"])
    for item in gaps:
        if (not isinstance(item, dict) or item.get("claim_id") not in claim_ids
                or item.get("claim_id") in gap_ids or item.get("status") != "OPEN"
                or item.get("gap_id") != f'{claim.get("run_id")}-{item.get("claim_id")}'
                or item.get("web_resolvable") is not False):
            raise ValueError("claim gap safety fields are invalid")
        gap_ids.add(item["claim_id"])
    for item in results:
        if (not isinstance(item, dict) or item.get("claim_id") not in claim_ids
                or item.get("claim_id") in result_ids
                or item.get("status") not in PASSAGE_STATUSES
                or item.get("semantic_status") != "UNVERIFIED"):
            raise ValueError("passage result safety fields are invalid")
        result_ids.add(item["claim_id"])
    if gap_ids != claim_ids or result_ids != claim_ids:
        raise ValueError("input report claim IDs differ")
    by_claim = {item["claim_id"]: item for item in claims}
    for result in results:
        item = by_claim[result["claim_id"]]
        for key in ("source_id", "version_id", "passage_locator"):
            if result.get(key) != item.get(key):
                raise ValueError("passage result differs from claim lineage")
        if result.get("raw_sha256") != item.get("raw_sha256"):
            raise ValueError("passage raw hash differs from claim lineage")
        if result["status"] == "QUOTE_PRESENT" and (
                not isinstance(result.get("verbatim_quote"), str)
                or not isinstance(result.get("byte_offset"), int)
                or isinstance(result.get("byte_offset"), bool)
                or result["byte_offset"] < 0):
            raise ValueError("passage result has invalid quote anchor")
    _source_report(claim, state_dir)
    return claim, passage


def _packet(path, claim, passage):
    packet = _read_json(path, "review packet")
    if set(packet) != PACKET_FIELDS:
        raise ValueError("review packet fields are invalid")
    if (packet["entity"] != claim.get("entity")
            or packet["cutoff_timestamp"] != claim.get("cutoff_timestamp")
            or packet["claim_report_id"] != claim["report_id"]
            or packet["passage_report_id"] != passage["report_id"]):
        raise ValueError("review packet input report binding differs")
    cutoff = _timestamp(packet["cutoff_timestamp"], "cutoff_timestamp")
    if not isinstance(packet["decisions"], list):
        raise ValueError("decisions must be a list")
    known = {item["claim_id"] for item in claim["claims"]}
    passages = {item["claim_id"]: item for item in passage["results"]}
    seen = set()
    for decision in packet["decisions"]:
        if not isinstance(decision, dict) or set(decision) != DECISION_FIELDS:
            raise ValueError("review decision fields are invalid")
        claim_id = decision["claim_id"]
        if not isinstance(claim_id, str) or claim_id not in known or claim_id in seen:
            raise ValueError("duplicate or unknown review claim_id")
        seen.add(claim_id)
        for key in ("reviewer_id", "rights_evidence_ref", "review_note"):
            _text(decision[key], key)
        if not SAFE_ID.fullmatch(decision["reviewer_id"]):
            raise ValueError("reviewer_id is invalid")
        _timestamp(decision["reviewed_at"], "reviewed_at")
        if decision["rights_use"] not in {"LOCAL_ANALYSIS_ALLOWED", "BLOCKED"}:
            raise ValueError("rights_use is invalid")
        if decision["semantic_decision"] not in {"SUPPORTS", "DOES_NOT_SUPPORT", "UNCERTAIN"}:
            raise ValueError("semantic_decision is invalid")
        if decision["contradiction_status"] not in {"NO_KNOWN_CONFLICT", "CONFLICT_OPEN", "CONFLICT_RESOLVED"}:
            raise ValueError("contradiction_status is invalid")
        related = decision["related_claim_ids"]
        if (not isinstance(related, list)
                or any(not isinstance(item, str) or item not in known or item == claim_id for item in related)
                or len(related) != len(set(related))):
            raise ValueError("related_claim_ids are invalid")
        if decision["contradiction_status"] == "NO_KNOWN_CONFLICT":
            if related or decision["conflict_explanation"] is not None:
                raise ValueError("no-known-conflict cannot name a resolution")
        elif not related or not isinstance(decision["conflict_explanation"], str) or not decision["conflict_explanation"].strip():
            raise ValueError("conflict disposition needs related claims and explanation")
        passage_result = passages[claim_id]
        for key in ("source_id", "version_id", "raw_sha256", "verbatim_quote", "byte_offset"):
            if decision[key] != passage_result.get(key) or type(decision[key]) is not type(passage_result.get(key)):
                raise ValueError("review receipt differs from exact passage")
    return packet, cutoff


def _filing_status(catalog_path, project_dir, claim, cutoff, decision_reviewed_at):
    if not Path(catalog_path).is_file():
        return "FILING_NOT_REVIEWED"
    with closing(sqlite3.connect(catalog_path)) as db:
        db.row_factory = sqlite3.Row
        try:
            rows = db.execute("""SELECT f.*, s.issuer_id AS security_issuer,
                s.announced_at AS security_announced, s.first_seen_at AS security_seen,
                s.reviewed_at AS security_reviewed, s.review_decision AS security_decision,
                s.source_id AS security_source, s.version_id AS security_version,
                c.first_seen_at AS company_seen, c.reviewed_at AS company_reviewed,
                c.review_decision AS company_decision, c.source_id AS company_source,
                c.version_id AS company_version
                FROM filings f JOIN securities s ON s.isin=f.isin
                JOIN companies c ON c.issuer_id=s.issuer_id
                WHERE f.source_id=? AND f.version_id=?""",
                (claim["source_id"], claim["version_id"])).fetchall()
        except sqlite3.DatabaseError:
            return "FILING_NOT_REVIEWED"
    if len(rows) != 1:
        return "FILING_NOT_REVIEWED"
    row = rows[0]
    if (row["issuer_id"] != claim["entity"] or row["security_issuer"] != claim["entity"]
            or row["raw_sha256"] != claim["raw_sha256"]
            or row["rights_status"] != "REVIEWED" or row["review_decision"] != "CONFIRMED"
            or row["security_decision"] != "CONFIRMED" or row["company_decision"] != "CONFIRMED"):
        return "FILING_NOT_REVIEWED"
    for key in ("published_at", "first_seen_at", "reviewed_at", "security_announced",
                "security_seen", "security_reviewed", "company_seen", "company_reviewed"):
        try:
            known_at = _timestamp(row[key], key)
            if known_at > cutoff:
                return "AFTER_CUTOFF"
            if known_at > decision_reviewed_at:
                return "REVIEW_BEFORE_EVIDENCE"
        except ValueError:
            return "FILING_NOT_REVIEWED"
    try:
        if _filing_source(row, project_dir) != row["raw_sha256"]:
            return "SOURCE_DAMAGED"
        for source, version, seen in ((row["security_source"], row["security_version"], row["security_seen"]),
                                      (row["company_source"], row["company_version"], row["company_seen"])):
            _source({"source_id": source, "version_id": version, "first_seen_at": seen}, project_dir)
    except (OSError, ValueError, KeyError, TypeError):
        return "SOURCE_DAMAGED"
    return None


def _result(claim, passage, decision, project_dir, catalog_path, cutoff, cutoff_day):
    claim_id = claim["claim_id"]
    base = {"claim_id": claim_id, "claim_type": claim["claim_type"],
            "source_id": claim["source_id"], "version_id": claim["version_id"],
            "raw_sha256": passage.get("raw_sha256"), "decision": decision}
    if claim["claim_type"] in OTHER_ORIGIN_TYPES:
        status = "ORIGIN_CONTRACT_MISSING"
    elif claim["claim_type"] not in DIRECT_TYPES:
        status = "TYPE_CONTRACT_MISSING"
    elif not isinstance(claim.get("as_of"), str):
        status = "AFTER_CUTOFF"
    elif date.fromisoformat(claim["as_of"]) > cutoff_day:
        status = "AFTER_CUTOFF"
    elif claim["status"] != "LINEAGE_LINKED":
        status = "LINEAGE_BLOCKED"
    elif passage["status"] != "QUOTE_PRESENT":
        status = "QUOTE_NOT_PRESENT"
    elif decision is None:
        status = "MISSING_REVIEW"
    elif _timestamp(decision["reviewed_at"], "reviewed_at") > cutoff:
        status = "REVIEW_AFTER_CUTOFF"
    else:
        quote = passage["verbatim_quote"]
        anchored_status, offset = _presence(claim, quote, Path(project_dir))
        if anchored_status == "INVALID_SOURCE":
            status = "SOURCE_DAMAGED"
        elif anchored_status != "QUOTE_PRESENT" or offset != passage["byte_offset"]:
            status = "QUOTE_NOT_PRESENT"
        else:
            status = _filing_status(catalog_path, project_dir, claim, cutoff,
                                    _timestamp(decision["reviewed_at"], "reviewed_at"))
            if status is None:
                if decision["rights_use"] != "LOCAL_ANALYSIS_ALLOWED":
                    status = "RIGHTS_BLOCKED"
                elif decision["semantic_decision"] == "DOES_NOT_SUPPORT":
                    status = "SEMANTIC_REJECTED"
                elif decision["semantic_decision"] == "UNCERTAIN":
                    status = "SEMANTIC_UNCERTAIN"
                elif decision["contradiction_status"] == "CONFLICT_OPEN":
                    status = "CONFLICT_OPEN"
                else:
                    status = "INTERNAL_REVIEWED"
    return {**base, "status": status}


def _read_existing(path, packet, claim, passage, run_id, expected_results, expected_gaps):
    report = _read_json(path, "review report")
    report_id = report.get("report_id")
    if not isinstance(report_id, str):
        raise ValueError("existing review report differs from its digest")
    if not isinstance(report.get("gaps"), list):
        raise ValueError("existing review report safety fields are invalid")
    body = {key: value for key, value in report.items() if key != "report_id"}
    body["gaps"] = [{key: value for key, value in gap.items() if key != "review_report_id"}
                    for gap in report.get("gaps", [])]
    if _hash_json(body) != report_id:
        raise ValueError("existing review report differs from its digest")
    if any((gap.get("review_report_id") != report_id if gap.get("status") == "CLOSED_BY_REVIEW"
            else "review_report_id" in gap) for gap in report["gaps"]):
        raise ValueError("existing review gap receipt is invalid")
    if (report.get("run_id") != run_id or report.get("status") != "CLAIMS_REVIEWED_INTERNAL"
            or report.get("entity") != packet["entity"]
            or report.get("cutoff_timestamp") != packet["cutoff_timestamp"]
            or report.get("publication_allowed") is not False
            or report.get("packet_hash") != _hash_json(packet)
            or report.get("claim_report_id") != claim["report_id"]
            or report.get("passage_report_id") != passage["report_id"]
            or not isinstance(report.get("results"), list)
            or not isinstance(report.get("gaps"), list)
            or any(item.get("status") not in {"INTERNAL_REVIEWED", "ORIGIN_CONTRACT_MISSING",
                                               "TYPE_CONTRACT_MISSING", "LINEAGE_BLOCKED",
                                               "QUOTE_NOT_PRESENT", "MISSING_REVIEW", "REVIEW_AFTER_CUTOFF",
                                               "SOURCE_DAMAGED", "FILING_NOT_REVIEWED", "AFTER_CUTOFF",
                                               "REVIEW_BEFORE_EVIDENCE",
                                               "RIGHTS_BLOCKED", "SEMANTIC_REJECTED", "SEMANTIC_UNCERTAIN",
                                               "CONFLICT_OPEN"} for item in report["results"])):
        raise ValueError("existing review report safety fields or inputs are invalid")
    results = report["results"]
    gaps = report["gaps"]
    claims_by_id = {item["claim_id"]: item for item in claim["claims"]}
    passages_by_id = {item["claim_id"]: item for item in passage["results"]}
    decisions_by_id = {item["claim_id"]: item for item in packet["decisions"]}
    gaps_by_id = {item["claim_id"]: item for item in claim["gaps"]}
    if (len(results) != len(gaps)
            or len({item.get("claim_id") for item in results}) != len(results)
            or {item.get("claim_id") for item in results} != set(claims_by_id)
            or {item.get("claim_id") for item in results} != {gap.get("claim_id") for gap in gaps}):
        raise ValueError("existing review report safety fields are invalid")
    by_id = {item["claim_id"]: item for item in results}
    for item in results:
        decision = item.get("decision")
        upstream_claim = claims_by_id[item["claim_id"]]
        upstream_passage = passages_by_id[item["claim_id"]]
        if (decision != decisions_by_id.get(item["claim_id"])
                or item.get("claim_type") != upstream_claim["claim_type"]
                or item.get("source_id") != upstream_claim["source_id"]
                or item.get("version_id") != upstream_claim["version_id"]
                or item.get("raw_sha256") != upstream_passage.get("raw_sha256")):
            raise ValueError("existing review report safety fields are invalid")
        if (item["status"] == "INTERNAL_REVIEWED" and (
                item.get("claim_type") not in DIRECT_TYPES or not isinstance(decision, dict)
                or decision.get("rights_use") != "LOCAL_ANALYSIS_ALLOWED"
                or decision.get("semantic_decision") != "SUPPORTS"
                or decision.get("contradiction_status") == "CONFLICT_OPEN")):
            raise ValueError("existing review report safety fields are invalid")
    for gap in gaps:
        expected = "CLOSED_BY_REVIEW" if by_id[gap["claim_id"]]["status"] == "INTERNAL_REVIEWED" else "OPEN"
        if (gap.get("status") != expected or gap.get("reason") != by_id[gap["claim_id"]]["status"]
                or gap.get("gap_id") != gaps_by_id[gap["claim_id"]]["gap_id"]):
            raise ValueError("existing review gap safety fields are invalid")
    normalized_gaps = [{key: value for key, value in gap.items() if key != "review_report_id"}
                       for gap in gaps]
    if results != expected_results or normalized_gaps != expected_gaps:
        raise ValueError("existing review report differs from current evidence")
    return report


def _evaluate(packet, claim, passage, project_dir, catalog_path, cutoff):
    decisions = {item["claim_id"]: item for item in packet["decisions"]}
    passages = {item["claim_id"]: item for item in passage["results"]}
    cutoff_day = datetime.fromisoformat(packet["cutoff_timestamp"]).date()
    results = [
        _result({**item, "entity": claim["entity"]}, passages[item["claim_id"]],
                decisions.get(item["claim_id"]), project_dir, catalog_path, cutoff, cutoff_day)
        for item in claim["claims"]
    ]
    open_conflicts = {related for result in results if result["decision"] is not None
                      and result["decision"]["contradiction_status"] == "CONFLICT_OPEN"
                      for related in result["decision"]["related_claim_ids"]}
    for result in results:
        if result["claim_id"] in open_conflicts and result["status"] == "INTERNAL_REVIEWED":
            result["status"] = "CONFLICT_OPEN"
    by_id = {result["claim_id"]: result for result in results}
    gaps = [{"gap_id": gap["gap_id"], "claim_id": gap["claim_id"],
             "status": "CLOSED_BY_REVIEW" if by_id[gap["claim_id"]]["status"] == "INTERNAL_REVIEWED" else "OPEN",
             "reason": by_id[gap["claim_id"]]["status"]}
            for gap in claim["gaps"]]
    return results, gaps


def review_claims(packet_path: Path, claim_report_path: Path, passage_report_path: Path,
                  project_dir: Path, catalog_path: Path, state_dir: Path, run_id: str) -> dict:
    """Freeze bounded human decisions without changing source reports or allowing publication."""
    if not isinstance(run_id, str) or not SAFE_ID.fullmatch(run_id):
        raise ValueError("run_id is invalid")
    claim, passage = _upstream(claim_report_path, passage_report_path, state_dir)
    packet, cutoff = _packet(packet_path, claim, passage)
    packet_hash = _hash_json(packet)
    path = Path(state_dir) / "claim_review_runs" / f"{run_id}.json"
    results, gaps = _evaluate(packet, claim, passage, project_dir, catalog_path, cutoff)
    if path.exists():
        return _read_existing(path, packet, claim, passage, run_id, results, gaps)
    report = {
        "run_id": run_id, "entity": packet["entity"], "cutoff_timestamp": packet["cutoff_timestamp"],
        "claim_report_id": claim["report_id"], "passage_report_id": passage["report_id"],
        "packet_hash": packet_hash, "status": "CLAIMS_REVIEWED_INTERNAL",
        "publication_allowed": False, "results": results, "gaps": gaps,
    }
    report["report_id"] = _hash_json(report)
    for gap in report["gaps"]:
        if gap["status"] == "CLOSED_BY_REVIEW":
            gap["review_report_id"] = report["report_id"]
    # A receipt references the report ID; the ID hashes the independent body.
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".incoming-", delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(report, output, indent=2, sort_keys=True, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.link(temporary, path)
    except FileExistsError:
        return _read_existing(path, packet, claim, passage, run_id, results, gaps)
    finally:
        temporary.unlink(missing_ok=True)
    return report
