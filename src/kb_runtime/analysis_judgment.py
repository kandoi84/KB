"""Freeze an internal analyst worksheet; never promote it to investment research."""

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from contextlib import closing
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path

from .claim_lineage import _hash_json
from .claim_review import _evaluate, _packet, _read_existing, _upstream
from .identity_store import SAFE_ID, DIGEST, _date, _source, _timestamp, _valid_isin
from .metric_store import DECIMAL_TEXT, query_metrics


LAYERS = ("macro", "sector", "industry", "company")
BIAS_CHECKS = frozenset({"confirmation", "anchoring", "recency", "availability",
                         "overconfidence", "narrative", "authority", "loss_aversion", "sunk_cost"})
PACKET_FIELDS = frozenset({"issuer_id", "isin", "cutoff_timestamp", "claim_review_report_id",
                           "analyst_id", "prepared_at", "layers", "metric_refs", "most_likely_path",
                           "base_fair_value", "debates", "valuation_range", "quality_trajectory",
                           "valuation_fragility", "catalysts", "no_catalyst_reason", "judgment"})
METRIC_KEYS = frozenset({"isin", "metric_name", "period_end", "period_kind", "reporting_scope",
                         "unit", "value_kind", "metric_id", "filing_id", "value_decimal"})
GENERIC = {"looks good", "fine", "okay", "ok", "none", "n/a", "not applicable", "checked", "unknown"}


def _read(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _id(value, label):
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise ValueError(f"{label} is invalid")
    return value


def _text(value, label, *, prose=True):
    if (not isinstance(value, str) or len(value.strip()) < (12 if prose else 1)
            or value.strip().lower() in GENERIC):
        raise ValueError(f"{label} is empty or generic")
    if prose and re.search(r"\d", value):
        raise ValueError(f"{label} contains an untyped number")
    return value


def _decimal(value, label, *, positive=False, probability=False):
    if not isinstance(value, str) or len(value) > 40 or not DECIMAL_TEXT.fullmatch(value):
        raise ValueError(f"{label} must be a plain decimal string")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{label} is invalid") from exc
    if not number.is_finite() or abs(number) > Decimal("1e20"):
        raise ValueError(f"{label} is out of range")
    if positive and number <= 0 or probability and not (0 <= number <= 1):
        raise ValueError(f"{label} is out of range")
    return number


def _ids(values, label, known=None, *, required=False):
    if not isinstance(values, list) or (required and not values):
        raise ValueError(f"{label} must be a list")
    for value in values:
        _id(value, label)
        if known is not None and value not in known:
            raise ValueError(f"{label} names unavailable evidence")
    if len(values) != len(set(values)):
        raise ValueError(f"{label} has duplicates")
    return values


def _object(value, fields, label):
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} fields are invalid")
    return value


def _choice(value, choices, label):
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f"{label} is invalid")
    return value


def _reviewed_identity(packet, catalog_path, project_dir):
    """Bind the packet's security to its reviewed issuer at the packet cutoff."""
    if not Path(catalog_path).is_file():
        raise ValueError("issuer and ISIN are missing from the catalog")
    try:
        with closing(sqlite3.connect(catalog_path)) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("""SELECT s.*, c.source_id AS company_source_id,
                c.version_id AS company_version_id, c.first_seen_at AS company_first_seen_at,
                c.reviewed_at AS company_reviewed_at,
                c.review_decision AS company_review_decision
                FROM securities s JOIN companies c ON c.issuer_id=s.issuer_id
                WHERE s.isin=?""", (packet["isin"],)).fetchone()
    except sqlite3.DatabaseError as exc:
        raise ValueError("issuer and ISIN catalog is invalid") from exc
    cutoff = _timestamp(packet["cutoff_timestamp"], "cutoff_timestamp")
    if (row is None or row["issuer_id"] != packet["issuer_id"]
            or row["review_decision"] != "CONFIRMED"
            or row["company_review_decision"] != "CONFIRMED"):
        raise ValueError("issuer and ISIN do not match reviewed identity")
    for key in ("announced_at", "first_seen_at", "reviewed_at",
                "company_first_seen_at", "company_reviewed_at"):
        if _timestamp(row[key], key) > cutoff:
            raise ValueError("issuer and ISIN identity is after cutoff")
    cutoff_day = datetime.fromisoformat(packet["cutoff_timestamp"]).date()
    if _date(row["listed_from"], "listed_from") > cutoff_day.isoformat() or (
            row["listed_to"] is not None and _date(row["listed_to"], "listed_to") < cutoff_day.isoformat()):
        raise ValueError("ISIN was not listed at cutoff")
    for source_id, version_id, first_seen in (
            (row["source_id"], row["version_id"], row["first_seen_at"]),
            (row["company_source_id"], row["company_version_id"], row["company_first_seen_at"])):
        _source({"source_id": source_id, "version_id": version_id,
                 "first_seen_at": first_seen}, project_dir)


def _find_parent(state_dir, folder, report_id):
    if not isinstance(report_id, str) or not DIGEST.fullmatch(report_id):
        raise ValueError("parent report ID is invalid")
    found = []
    for path in (Path(state_dir) / folder).glob("*.json"):
        report = _read(path, "parent report")
        if report.get("report_id") == report_id:
            found.append(path)
    if len(found) != 1:
        raise ValueError("parent report missing or ambiguous")
    return found[0]


def _verified_review(path, project_dir, catalog_path, state_dir):
    report = _read(path, "claim review report")
    if (Path(path).resolve().parent != (Path(state_dir) / "claim_review_runs").resolve()
            or not isinstance(report.get("results"), list)
            or not isinstance(report.get("claim_report_id"), str)
            or not isinstance(report.get("passage_report_id"), str)):
        raise ValueError("claim review report safety fields are invalid")
    claim_path = _find_parent(state_dir, "claim_runs", report["claim_report_id"])
    passage_path = _find_parent(state_dir, "passage_runs", report["passage_report_id"])
    claim, passage = _upstream(claim_path, passage_path, state_dir)
    packet = {"entity": report.get("entity"), "cutoff_timestamp": report.get("cutoff_timestamp"),
              "claim_report_id": report["claim_report_id"],
              "passage_report_id": report["passage_report_id"],
              "decisions": [row["decision"] for row in report["results"]
                            if isinstance(row, dict) and row.get("decision") is not None]}
    # Reuse the exact 05 packet validator, including passage byte anchors,
    # review timing, rights and conflict fields. A digest alone is not a review.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json") as temp_packet:
        json.dump(packet, temp_packet)
        temp_packet.flush()
        packet, cutoff = _packet(Path(temp_packet.name), claim, passage)
    results, gaps = _evaluate(packet, claim, passage, project_dir, catalog_path, cutoff)
    return _read_existing(path, packet, claim, passage, Path(path).stem, results, gaps)


def _check_packet(packet, report):
    if not PACKET_FIELDS <= set(packet) or set(packet) - PACKET_FIELDS != ({"previous_report_id"} if "previous_report_id" in packet else set()):
        raise ValueError("analysis packet fields are invalid")
    _id(packet["issuer_id"], "issuer_id")
    _id(packet["analyst_id"], "analyst_id")
    if not _valid_isin(packet["isin"]):
        raise ValueError("ISIN is invalid")
    cutoff = _timestamp(packet["cutoff_timestamp"], "cutoff_timestamp")
    if _timestamp(packet["prepared_at"], "prepared_at") > cutoff:
        raise ValueError("analysis prepared after cutoff")
    if (packet["claim_review_report_id"] != report.get("report_id")
            or packet["issuer_id"] != report.get("entity")
            or packet["cutoff_timestamp"] != report.get("cutoff_timestamp")):
        raise ValueError("analysis and review report binding differs")
    claims = {row["claim_id"] for row in report["results"] if row["status"] == "INTERNAL_REVIEWED"}
    if not isinstance(packet["metric_refs"], list) or not packet["metric_refs"] or any(not isinstance(row, dict) or "metric_id" not in row for row in packet["metric_refs"]):
        raise ValueError("metric_refs must be a nonempty list of records")
    metric_ids = {_id(row["metric_id"], "metric_id") for row in packet["metric_refs"]}
    if (not isinstance(packet["layers"], list)
            or len(packet["layers"]) != len(LAYERS)
            or any(not isinstance(row, dict) for row in packet["layers"])
            or [row.get("layer") for row in packet["layers"]] != list(LAYERS)):
        raise ValueError("macro sector industry company layers are required in order")
    for layer in packet["layers"]:
        if set(layer) != {"layer", "current_state", "transmission", "claim_ids", "metric_ids", "unknown_reason"}:
            raise ValueError("layer fields are invalid")
        _text(layer["current_state"], "current_state")
        _text(layer["transmission"], "transmission")
        _ids(layer["claim_ids"], "claim_ids", claims)
        _ids(layer["metric_ids"], "metric_ids", metric_ids)
        if not layer["claim_ids"] and not layer["metric_ids"]:
            _text(layer["unknown_reason"], "unknown_reason")
        elif layer["unknown_reason"] is not None:
            raise ValueError("known layer cannot have unknown reason")
    return claims, metric_ids


def _previous_report(packet, state_dir, project_dir, catalog_path, run_id=None,
                     _seen=frozenset()):
    if "previous_report_id" not in packet:
        return None
    previous_id = packet["previous_report_id"]
    if not isinstance(previous_id, str) or not DIGEST.fullmatch(previous_id):
        raise ValueError("previous report ID is invalid")
    if previous_id in _seen or len(_seen) >= 64:
        raise ValueError("previous report chain has a cycle or exceeds 64 revisions")
    try:
        path = _find_parent(state_dir, "analysis_runs", previous_id)
    except ValueError as exc:
        raise ValueError("previous report missing or ambiguous") from exc
    previous = _read(path, "previous report")
    body = {key: value for key, value in previous.items() if key != "report_id"}
    if (previous.get("report_id") != _hash_json(body)
            or previous.get("run_id") != path.stem
            or previous.get("run_id") == run_id
            or previous.get("issuer_id") != packet["issuer_id"]
            or previous.get("isin") != packet["isin"]
            or previous.get("publication_allowed") is not False
            or previous.get("analysis_status") not in {"CALCULATED_MODEL_UNVERIFIED", "BLOCKED_EVIDENCE"}
            or previous.get("judgment_status") != "HUMAN_REVIEW_REQUIRED"
            or _timestamp(previous.get("cutoff_timestamp"), "previous cutoff") > _timestamp(packet["cutoff_timestamp"], "cutoff_timestamp")):
        raise ValueError("previous report is damaged or belongs to another analysis")
    worksheet = previous.get("worksheet")
    if not isinstance(worksheet, dict) or previous.get("packet_hash") != _hash_json(worksheet):
        raise ValueError("previous report worksheet binding is invalid")
    try:
        claim_path = _find_parent(state_dir, "claim_review_runs", previous.get("claim_review_report_id"))
        review = _verified_review(claim_path, project_dir, catalog_path, state_dir)
        claims, metric_ids = _check_packet(worksheet, review)
        _reviewed_identity(worksheet, catalog_path, project_dir)
        leaves, gaps = _select_metrics(worksheet, project_dir, catalog_path)
        fair, model_hash = _validate_content(worksheet, claims, metric_ids, project_dir)
    except (OSError, ValueError) as exc:
        raise ValueError("previous report evidence no longer verifies") from exc
    expected_status = "BLOCKED_EVIDENCE" if gaps else "CALCULATED_MODEL_UNVERIFIED"
    if (review["report_id"] != previous["claim_review_report_id"]
            or leaves != previous.get("metric_leaves")
            or gaps != previous.get("gaps")
            or model_hash != previous.get("model_sha256")
            or previous.get("analysis_status") != expected_status
            or previous.get("probability_weighted_fair_value") != (None if gaps else f"{fair:.2f}")):
        raise ValueError("previous report differs from current evidence")
    ancestor_id = _previous_report(worksheet, state_dir, project_dir, catalog_path,
                                   previous["run_id"], _seen | {previous_id})
    if previous.get("previous_report_id") != ancestor_id:
        raise ValueError("previous report revision link differs from worksheet")
    return previous_id


def _select_metrics(packet, project_dir, catalog_path):
    refs = packet["metric_refs"]
    if not isinstance(refs, list) or len(refs) != len({row.get("metric_id") for row in refs if isinstance(row, dict)}):
        raise ValueError("metric_refs are invalid or duplicated")
    selected, gaps = [], []
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != METRIC_KEYS or ref["isin"] != packet["isin"]:
            raise ValueError("metric reference fields or ISIN are invalid")
        for key in ("metric_name", "metric_id", "filing_id"):
            _id(ref[key], key)
        _date(ref["period_end"], "metric period_end")
        _decimal(ref["value_decimal"], "metric value_decimal")
        try:
            leaves = query_metrics(catalog_path, project_dir, ref["isin"], ref["metric_name"],
                                   ref["period_end"], packet["cutoff_timestamp"])
        except ValueError as exc:
            gaps.append({"metric_id": ref["metric_id"], "reason": f"METRIC_DAMAGED: {exc}"})
            continue
        matches = [leaf for leaf in leaves if all(leaf.get(key) == ref[key] for key in METRIC_KEYS)]
        if len(matches) != 1:
            gaps.append({"metric_id": ref["metric_id"], "reason": "METRIC_NOT_EXACT_CUTOFF_LEAF"})
        else:
            selected.append(matches[0])
    return selected, gaps


def load_analysis_inputs(packet_path: Path, claim_review_path: Path, project_dir: Path,
                         catalog_path: Path, state_dir: Path) -> tuple[dict, dict, list[dict]]:
    """Validate the worksheet binding and return currently selected typed leaves."""
    report = _verified_review(claim_review_path, project_dir, catalog_path, state_dir)
    packet = _read(packet_path, "analysis packet")
    _check_packet(packet, report)
    _reviewed_identity(packet, catalog_path, project_dir)
    _previous_report(packet, state_dir, project_dir, catalog_path)
    leaves, gaps = _select_metrics(packet, project_dir, catalog_path)
    if gaps:
        raise ValueError(f"metric evidence unavailable: {gaps}")
    return packet, report, leaves


def _validate_content(packet, claims, metric_ids, project_dir):
    path = _object(packet["most_likely_path"],
                   {"horizon_end", "hypothesis", "driver_ids", "claim_ids", "metric_ids", "falsifiers"},
                   "most likely path")
    if not date.fromisoformat(_date(path["horizon_end"], "path horizon_end")) > datetime.fromisoformat(packet["cutoff_timestamp"]).date():
        raise ValueError("most likely path horizon is invalid")
    _text(path["hypothesis"], "path hypothesis")
    _ids(path["driver_ids"], "path driver_ids", required=True)
    _ids(path["claim_ids"], "path claim_ids", claims)
    _ids(path["metric_ids"], "path metric_ids", metric_ids)
    if not isinstance(path["falsifiers"], list) or not path["falsifiers"]:
        raise ValueError("path needs a list of falsifiers")
    for reason in path["falsifiers"]:
        _text(reason, "path falsifier")
    base = _object(packet["base_fair_value"],
                   {"value_decimal", "unit", "value_kind", "method", "model_snapshot_id",
                    "model_path", "model_sha256", "as_of", "rationale"}, "base fair value")
    if base["unit"] != "INR_PER_SHARE" or base["value_kind"] != "ANALYST_ESTIMATE":
        raise ValueError("base fair value labels are invalid")
    _choice(base["method"], {"DCF", "SOTP", "RESIDUAL_INCOME", "OTHER"}, "base fair value method")
    value = _decimal(base["value_decimal"], "base fair value", positive=True)
    _id(base["model_snapshot_id"], "model_snapshot_id")
    if not isinstance(base["model_sha256"], str) or not DIGEST.fullmatch(base["model_sha256"]):
        raise ValueError("model sha256 is invalid")
    if not isinstance(base["model_path"], str) or not base["model_path"].strip():
        raise ValueError("model path must be nonempty text")
    model_path = (Path(project_dir) / base["model_path"]).resolve()
    if not model_path.is_relative_to(Path(project_dir).resolve()) or not model_path.is_file():
        raise ValueError("model path must be an existing project file")
    try:
        actual_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError("model file is unavailable") from exc
    if actual_hash != base["model_sha256"]:
        raise ValueError("model bytes differ from pinned hash")
    if _timestamp(base["as_of"], "model as_of") > _timestamp(packet["cutoff_timestamp"], "cutoff_timestamp"):
        raise ValueError("model is after cutoff")
    _text(base["rationale"], "base rationale")
    if not isinstance(packet["debates"], list) or len(packet["debates"]) > 100:
        raise ValueError("debates must be a bounded list")
    seen_drivers, seen_debates = set(), set()
    for debate in packet["debates"]:
        _object(debate, {"debate_id", "driver_id", "occurrence", "probability", "incremental_impact",
                         "claim_ids", "metric_ids", "rationale", "falsifier", "incremental_attestation",
                         "correlation"}, "debate")
        did, driver = _id(debate["debate_id"], "debate_id"), _id(debate["driver_id"], "driver_id")
        if did in seen_debates or driver in seen_drivers or debate["correlation"] != "NONE_KNOWN" or debate["incremental_attestation"] is not True:
            raise ValueError("debates are duplicated, correlated or not incremental")
        seen_debates.add(did); seen_drivers.add(driver)
        for key in ("occurrence", "rationale", "falsifier"):
            _text(debate[key], key)
        _ids(debate["claim_ids"], "debate claim_ids", claims)
        _ids(debate["metric_ids"], "debate metric_ids", metric_ids)
        _decimal(debate["probability"], "debate probability", probability=True)
        _decimal(debate["incremental_impact"], "debate incremental_impact")
    fair = value + sum((_decimal(d["probability"], "probability") * _decimal(d["incremental_impact"], "impact") for d in packet["debates"]), Decimal(0))
    if fair <= 0:
        raise ValueError("fair value must be positive")
    try:
        rounded = fair.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    except InvalidOperation as exc:
        raise ValueError("fair value cannot be rounded safely") from exc
    value_range = _object(packet["valuation_range"],
                          {"low", "high", "method", "rationale", "fragility_drivers"},
                          "valuation range")
    low = _decimal(value_range["low"], "range low", positive=True)
    high = _decimal(value_range["high"], "range high", positive=True)
    if not low < high or not low <= rounded <= high:
        raise ValueError("valuation range must contain calculated fair value")
    _text(value_range["method"], "range method", prose=False)
    _text(value_range["rationale"], "range rationale")
    if not isinstance(value_range["fragility_drivers"], list) or not value_range["fragility_drivers"]:
        raise ValueError("fragility drivers are required")
    for driver in value_range["fragility_drivers"]:
        _text(driver, "fragility driver", prose=False)
    for key, choices in (("quality_trajectory", {"IMPROVING", "STABLE", "DETERIORATING", "UNKNOWN"}), ("valuation_fragility", {"LOW", "MEDIUM", "HIGH", "UNKNOWN"})):
        diagnostic = packet[key]
        if not isinstance(diagnostic, dict) or set(diagnostic) != {"status", "explanation", "evidence_ids"}:
            raise ValueError(f"{key} is invalid")
        _choice(diagnostic["status"], choices, f"{key} status")
        _text(diagnostic["explanation"], key)
        _ids(diagnostic["evidence_ids"], key, claims | metric_ids, required=True)
    catalysts = packet["catalysts"]
    if not isinstance(catalysts, list):
        raise ValueError("catalysts must be a list")
    if not catalysts:
        _text(packet["no_catalyst_reason"], "no_catalyst_reason")
    elif packet["no_catalyst_reason"] is not None:
        raise ValueError("no_catalyst_reason conflicts with catalysts")
    catalyst_ids = set()
    for catalyst in catalysts:
        _object(catalyst, {"catalyst_id", "event", "window_start", "window_end", "probability",
                           "affected_kpi", "earnings_link", "valuation_link", "debate_id",
                           "claim_ids", "metric_ids", "double_count_disposition"}, "catalyst")
        cid = _id(catalyst["catalyst_id"], "catalyst_id")
        if cid in catalyst_ids:
            raise ValueError("catalyst ID duplicated")
        catalyst_ids.add(cid)
        start = date.fromisoformat(_date(catalyst["window_start"], "catalyst window_start"))
        end = date.fromisoformat(_date(catalyst["window_end"], "catalyst window_end"))
        cutoff_day = datetime.fromisoformat(packet["cutoff_timestamp"]).date()
        if start <= cutoff_day or end < start or (end - cutoff_day).days > 731 or (start - cutoff_day).days < 90:
            raise ValueError("catalyst window must be within three to twenty-four months")
        for key in ("event", "affected_kpi", "earnings_link", "valuation_link"):
            _text(catalyst[key], key)
        _decimal(catalyst["probability"], "catalyst probability", probability=True)
        _ids(catalyst["claim_ids"], "catalyst claim_ids", claims)
        _ids(catalyst["metric_ids"], "catalyst metric_ids", metric_ids)
        debate_id = _id(catalyst["debate_id"], "catalyst debate_id")
        if debate_id in seen_debates:
            if catalyst["double_count_disposition"] != "VALUE_ALREADY_IN_DEBATE":
                raise ValueError("catalyst double count disposition is invalid")
        elif debate_id == "NO_VALUATION_DELTA":
            if catalyst["double_count_disposition"] != "WATCH_ONLY":
                raise ValueError("catalyst without debate must be watch only")
        else:
            raise ValueError("catalyst debate link is invalid")
    _validate_judgment(packet["judgment"], catalyst_ids,
                       datetime.fromisoformat(packet["cutoff_timestamp"]).date())
    return rounded, actual_hash


def _validate_judgment(judgment, catalyst_ids, cutoff_day):
    keys = {"premortem", "premortem_horizon_end", "falsifiers", "earnings_engine", "value_drivers", "mechanism_chain", "bias_checks", "incentives", "second_order", "circle_of_competence", "opportunity_cost", "hammer_check", "price_assessment", "alternatives_assessment", "optionality_assessment"}
    if not isinstance(judgment, dict) or set(judgment) != keys:
        raise ValueError("judgment fields are invalid")
    for key in ("premortem", "earnings_engine", "incentives", "second_order", "circle_of_competence", "opportunity_cost", "hammer_check"):
        _text(judgment[key], key)
    if not isinstance(judgment["falsifiers"], list) or not judgment["falsifiers"]:
        raise ValueError("judgment falsifiers are required")
    for item in judgment["falsifiers"]:
        _text(item, "judgment falsifier")
    horizon = date.fromisoformat(_date(judgment["premortem_horizon_end"], "premortem horizon_end"))
    if not 1095 <= (horizon - cutoff_day).days <= 1827:
        raise ValueError("premortem horizon must be three to five years")
    if not isinstance(judgment["value_drivers"], list) or len(judgment["value_drivers"]) not in {2, 3}:
        raise ValueError("two or three value drivers are required")
    for item in judgment["value_drivers"]:
        _text(item, "value driver", prose=False)
    chain = judgment["mechanism_chain"]
    allowed_chain_ids = catalyst_ids if catalyst_ids else {"NO_EVIDENCED_CATALYST"}
    if not isinstance(chain, dict) or set(chain) != {"catalyst", "kpi", "earnings", "valuation"}:
        raise ValueError("catalyst to KPI to earnings to valuation chain is invalid")
    _choice(chain["catalyst"], allowed_chain_ids, "mechanism chain catalyst")
    for key in ("kpi", "earnings", "valuation"):
        _text(chain[key], "mechanism chain")
    checks = judgment["bias_checks"]
    if not isinstance(checks, dict) or set(checks) != BIAS_CHECKS:
        raise ValueError("all nine bias checks are required")
    reasons = []
    for item in checks.values():
        if not isinstance(item, dict) or set(item) != {"status", "reason"}:
            raise ValueError("bias check is invalid")
        _choice(item["status"], {"FLAGGED", "CHECKED"}, "bias status")
        _text(item["reason"], "bias reason")
        reasons.append(item["reason"].strip().casefold())
    if len(set(reasons)) != len(reasons):
        raise ValueError("bias checks need distinct concrete reasons")
    for key in ("price_assessment", "alternatives_assessment", "optionality_assessment"):
        if judgment[key] != "NOT_ASSESSED":
            raise ValueError(f"{key} must remain NOT_ASSESSED")


def analyze_judgment(packet_path: Path, claim_review_path: Path, project_dir: Path,
                     catalog_path: Path, state_dir: Path, run_id: str) -> dict:
    """Validate and freeze one internal worksheet; exact replay rechecks evidence."""
    _id(run_id, "run_id")
    report = _verified_review(claim_review_path, project_dir, catalog_path, state_dir)
    packet = _read(packet_path, "analysis packet")
    claims, metric_ids = _check_packet(packet, report)
    _reviewed_identity(packet, catalog_path, project_dir)
    previous_id = _previous_report(packet, state_dir, project_dir, catalog_path, run_id)
    leaves, gaps = _select_metrics(packet, project_dir, catalog_path)
    fair, model_hash = _validate_content(packet, claims, metric_ids, project_dir)
    body = {"run_id": run_id, "issuer_id": packet["issuer_id"], "isin": packet["isin"],
            "cutoff_timestamp": packet["cutoff_timestamp"], "packet_hash": _hash_json(packet),
            "claim_review_report_id": report["report_id"], "metric_leaves": leaves,
            "previous_report_id": previous_id,
            "worksheet": packet,
            "model_sha256": model_hash, "calculation_version": "decimal-half-even-2-v1",
            "analysis_status": "BLOCKED_EVIDENCE" if gaps else "CALCULATED_MODEL_UNVERIFIED",
            "probability_weighted_fair_value": None if gaps else f"{fair:.2f}",
            "fair_value_unit": "INR_PER_SHARE", "fair_value_kind": "ANALYST_ESTIMATE",
            "model_status": "MODEL_UNVERIFIED", "market_price_status": "NOT_ASSESSED",
            "consensus_status": "NOT_ASSESSED", "score_status": "NOT_ASSESSED",
            "judgment_status": "HUMAN_REVIEW_REQUIRED", "gaps": gaps,
            "publication_allowed": False}
    body["report_id"] = _hash_json(body)
    path = Path(state_dir) / "analysis_runs" / f"{run_id}.json"
    if path.exists():
        old = _read(path, "existing analysis report")
        if old != body:
            raise ValueError("existing analysis report differs from current inputs or evidence")
        return old
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".incoming-", delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(body, output, sort_keys=True, indent=2)
            output.write("\n")
            output.flush(); os.fsync(output.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.link(temporary, path)
    except FileExistsError:
        old = _read(path, "existing analysis report")
        if old != body:
            raise ValueError("existing analysis report differs from concurrent inputs")
        return old
    finally:
        temporary.unlink(missing_ok=True)
    return body
