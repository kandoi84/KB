"""Open replay-verified, immutable sandbox cases; never authorize publication."""

import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .analysis_judgment import analyze_judgment
from .evidence_workflow import run_evidence_workflow
from .identity_store import DIGEST, SAFE_ID, _date, _timestamp, _valid_isin
from .metric_store import DECIMAL_TEXT


INPUT_NAMES = ("source_request", "claim_request", "passage_packet", "review_packet",
               "workflow_contract", "claim_review_report", "analysis_packet", "analysis_report")
PACKET_FIELDS = {"case_id", "workflow_run_id", "analysis_run_id", "issuer_id", "isin",
                 "cutoff_timestamp", "mode", "opened_at",
                 "input_sha256", "hypothesis", "rationale_claim_ids",
                 "rationale_metric_ids", "outcome"}
OUTCOME_FIELDS = {"metric_name", "unit", "comparison", "target_decimal",
                  "target_kind", "period_end", "due_at"}
CASE_FIELDS = (PACKET_FIELDS - {"outcome"} |
               {"previous_case_id", "previous_case_digest", "prediction", "poker",
                "claim_review_report_id", "analysis_report_id", "fair_value",
                "case_status", "timing_class", "publication_allowed",
                "live_decision_allowed", "promotion_status", "case_digest"})


def _read(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def _file_digest(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError("case input is unavailable") from exc


def _id(value, label):
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise ValueError(f"{label} is invalid")
    return value


def _prose(value, label):
    if (not isinstance(value, str) or len(value.strip()) < 12
            or re.search(r"\d", value)):
        raise ValueError(f"{label} must be substantive prose without untyped numbers")
    return value


def _ids(value, label):
    if not isinstance(value, list) or any(not isinstance(item, str) or
                                          not SAFE_ID.fullmatch(item) for item in value):
        raise ValueError(f"{label} must be a list of safe IDs")
    if len(value) != len(set(value)):
        raise ValueError(f"{label} has duplicate IDs")
    return value


def _packet(packet):
    if (not isinstance(packet, dict) or not PACKET_FIELDS <= set(packet)
            or set(packet) - PACKET_FIELDS - {"poker", "previous_case_id"}):
        raise ValueError("case packet fields are invalid")
    for key in ("case_id", "workflow_run_id", "analysis_run_id", "issuer_id"):
        _id(packet[key], key)
    if not _valid_isin(packet["isin"]):
        raise ValueError("case ISIN is invalid")
    if packet["mode"] != "SANDBOX":
        raise ValueError("case mode must be SANDBOX")
    cutoff = datetime.fromisoformat(_timestamp(packet["cutoff_timestamp"], "cutoff_timestamp"))
    opened = datetime.fromisoformat(_timestamp(packet["opened_at"], "opened_at"))
    if opened < cutoff:
        raise ValueError("case opening precedes cutoff")
    previous = packet.get("previous_case_id")
    if previous is not None:
        _id(previous, "previous_case_id")
        if previous == packet["case_id"]:
            raise ValueError("case cannot follow itself")
    hashes = packet["input_sha256"]
    if (not isinstance(hashes, dict) or set(hashes) != set(INPUT_NAMES)
            or any(not isinstance(value, str) or not DIGEST.fullmatch(value)
                   for value in hashes.values())):
        raise ValueError("case input hashes are invalid")
    _prose(packet["hypothesis"], "hypothesis")
    _ids(packet["rationale_claim_ids"], "rationale_claim_ids")
    _ids(packet["rationale_metric_ids"], "rationale_metric_ids")
    if not packet["rationale_claim_ids"] and not packet["rationale_metric_ids"]:
        raise ValueError("case needs an existing evidence citation")
    if "poker" in packet and packet["poker"] != {"status": "NOT_ASSESSED",
                                                  "hand": None, "draw": None}:
        raise ValueError("poker labels are unavailable")
    outcome = packet["outcome"]
    if not isinstance(outcome, dict) or set(outcome) != OUTCOME_FIELDS:
        raise ValueError("outcome fields are invalid")
    for key in ("metric_name", "unit"):
        if not isinstance(outcome[key], str) or not outcome[key].strip() or re.search(r"\d", outcome[key]):
            raise ValueError(f"outcome {key} is invalid")
    if (outcome["comparison"] not in ("AT_LEAST", "AT_MOST")
            or outcome["target_kind"] != "ANALYST_HYPOTHESIS"):
        raise ValueError("outcome comparison or target kind is invalid")
    target = outcome["target_decimal"]
    if not isinstance(target, str) or len(target) > 40 or not DECIMAL_TEXT.fullmatch(target):
        raise ValueError("outcome target must be a plain decimal")
    try:
        number = Decimal(target)
    except InvalidOperation as exc:
        raise ValueError("outcome target is invalid") from exc
    if not number.is_finite() or abs(number) > Decimal("1e20"):
        raise ValueError("outcome target is out of range")
    try:
        period = date.fromisoformat(_date(outcome["period_end"], "outcome period_end"))
    except ValueError as exc:
        raise ValueError("outcome period end is invalid") from exc
    due = datetime.fromisoformat(_timestamp(outcome["due_at"], "outcome due_at"))
    if period <= cutoff.date() or due <= cutoff or due.date() < period:
        raise ValueError("outcome must be future and due after its period")
    return cutoff, opened


def _expected_report(path, state_dir, folder, run_id):
    expected = Path(state_dir) / folder / f"{run_id}.json"
    root = Path(state_dir).resolve()
    if (Path(path).resolve() != expected.resolve()
            or not expected.resolve().is_relative_to(root)
            or not expected.is_file()):
        raise ValueError("parent report path or root is invalid")
    return _read(expected, "parent report")


def verify_case_parents(packet: dict, *, source_request: Path, claim_request: Path,
                        passage_packet: Path, review_packet: Path, workflow_contract: Path,
                        claim_review_report: Path, analysis_packet: Path, analysis_report: Path,
                        project_dir: Path, catalog: Path, state_dir: Path) -> tuple[dict, dict, dict]:
    """Replay an existing completed workflow and analysis at one pinned cutoff."""
    _packet(packet)
    paths = dict(zip(INPUT_NAMES, (source_request, claim_request, passage_packet, review_packet,
                                   workflow_contract, claim_review_report, analysis_packet,
                                   analysis_report)))
    for name, path in paths.items():
        if _file_digest(path) != packet["input_sha256"][name]:
            raise ValueError(f"case input {name} bytes differ")
    workflow_id, analysis_id = packet["workflow_run_id"], packet["analysis_run_id"]
    old_state = _expected_report(Path(state_dir) / "workflow_runs" / workflow_id / "state.json",
                                 state_dir, f"workflow_runs/{workflow_id}", "state")
    old_review = _expected_report(claim_review_report, state_dir, "claim_review_runs", workflow_id)
    old_analysis = _expected_report(analysis_report, state_dir, "analysis_runs", analysis_id)
    worksheet = _read(analysis_packet, "analysis packet")
    if worksheet != old_analysis.get("worksheet"):
        raise ValueError("analysis packet differs from frozen worksheet")
    cutoff, issuer, isin = packet["cutoff_timestamp"], packet["issuer_id"], packet["isin"]
    stages = old_state.get("stages")
    if (old_state.get("status") != "COMPLETE" or old_state.get("publication_allowed") is not False
            or old_state.get("entity") != issuer or old_state.get("cutoff_timestamp") != cutoff
            or not isinstance(stages, list) or len(stages) != 3
            or [row.get("stage_id") if isinstance(row, dict) else None for row in stages]
            != ["refresh", "passages", "review"]
            or any(row.get("status") != "COMPLETE" for row in stages)
            or stages[2].get("output_id") != old_review.get("report_id")):
        raise ValueError("workflow parent is incomplete or cross-bound")
    if (old_review.get("entity") != issuer or old_review.get("cutoff_timestamp") != cutoff
            or old_review.get("publication_allowed") is not False
            or old_analysis.get("issuer_id") != issuer or old_analysis.get("isin") != isin
            or old_analysis.get("cutoff_timestamp") != cutoff
            or old_analysis.get("claim_review_report_id") != old_review.get("report_id")
            or old_analysis.get("analysis_status") != "CALCULATED_MODEL_UNVERIFIED"
            or old_analysis.get("gaps") != []
            or old_analysis.get("model_status") != "MODEL_UNVERIFIED"
            or old_analysis.get("judgment_status") != "HUMAN_REVIEW_REQUIRED"
            or old_analysis.get("publication_allowed") is not False):
        raise ValueError("review and analysis parents are blocked or cross-bound")
    replayed_state = run_evidence_workflow(source_request, claim_request, passage_packet,
                                           review_packet, workflow_contract, project_dir,
                                           catalog, state_dir, workflow_id)
    replayed_analysis = analyze_judgment(analysis_packet, claim_review_report, project_dir,
                                         catalog, state_dir, analysis_id)
    if (replayed_state != old_state or replayed_analysis != old_analysis
            or _read(claim_review_report, "claim review report") != old_review):
        raise ValueError("parent replay differs from frozen report")
    claims = {row["claim_id"] for row in old_review["results"]
              if row["status"] == "INTERNAL_REVIEWED"}
    metrics = {row["metric_id"] for row in old_analysis["metric_leaves"]}
    if (not set(packet["rationale_claim_ids"]) <= claims
            or not set(packet["rationale_metric_ids"]) <= metrics):
        raise ValueError("case cites unavailable reviewed evidence")
    return old_state, old_review, old_analysis


def _previous_case(packet, state_dir):
    """Check local receipt structure and digest, not source or timestamp authorship."""
    previous_id = packet.get("previous_case_id")
    if previous_id is None:
        return None
    path = Path(state_dir) / "cases" / f"{previous_id}.json"
    if not path.resolve().is_relative_to(Path(state_dir).resolve()):
        raise ValueError("previous case path escapes state root")
    previous = _read(path, "previous case")
    if set(previous) != CASE_FIELDS:
        raise ValueError("previous case has invalid fields")
    try:
        _packet({key: previous[key] for key in PACKET_FIELDS if key != "outcome"} |
                {"outcome": previous["prediction"],
                 "previous_case_id": previous["previous_case_id"],
                 "poker": previous["poker"]})
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("previous case packet is invalid") from exc
    digest = previous.get("case_digest")
    fair = previous["fair_value"]
    prior_id, prior_digest = previous["previous_case_id"], previous["previous_case_digest"]
    if (not isinstance(digest, str) or not DIGEST.fullmatch(digest)
            or _digest({key: value for key, value in previous.items() if key != "case_digest"}) != digest
            or previous.get("case_id") != previous_id
            or previous.get("issuer_id") != packet["issuer_id"]
            or previous.get("isin") != packet["isin"]
            or any(not isinstance(previous[key], str) or not DIGEST.fullmatch(previous[key])
                   for key in ("claim_review_report_id", "analysis_report_id"))
            or (prior_id is None) != (prior_digest is None)
            or (prior_digest is not None and
                (not isinstance(prior_digest, str) or not DIGEST.fullmatch(prior_digest)))
            or not isinstance(fair, dict)
            or set(fair) != {"value_decimal", "unit", "value_kind", "model_status",
                             "valuation_range"}
            or not isinstance(fair["value_decimal"], str)
            or not DECIMAL_TEXT.fullmatch(fair["value_decimal"])
            or fair["unit"] != "INR_PER_SHARE"
            or fair["value_kind"] != "ANALYST_ESTIMATE"
            or fair["model_status"] != "MODEL_UNVERIFIED"
            or not isinstance(fair["valuation_range"], dict)
            or previous.get("case_status") != "SANDBOX_OPEN"
            or previous.get("timing_class") != ("HISTORICAL_RECONSTRUCTION" if
                datetime.fromisoformat(previous["cutoff_timestamp"]).date() !=
                datetime.fromisoformat(previous["opened_at"]).date() else
                "ANALYST_DECLARED_PROSPECTIVE")
            or previous.get("publication_allowed") is not False
            or previous.get("live_decision_allowed") is not False
            or previous.get("promotion_status") != "NOT_EVALUATED"):
        raise ValueError("previous case is invalid or from another issuer")
    earlier_cutoff = datetime.fromisoformat(_timestamp(previous.get("cutoff_timestamp"), "previous cutoff"))
    earlier_opened = datetime.fromisoformat(_timestamp(previous.get("opened_at"), "previous opening"))
    current_cutoff = datetime.fromisoformat(_timestamp(packet["cutoff_timestamp"], "cutoff"))
    current_opened = datetime.fromisoformat(_timestamp(packet["opened_at"], "opening"))
    if earlier_cutoff > current_cutoff or earlier_opened >= current_opened:
        raise ValueError("previous case does not precede current case")
    return digest


def _expected_case(packet, *, source_request, claim_request, passage_packet,
                   review_packet, workflow_contract, claim_review_report,
                   analysis_packet, analysis_report, project_dir, catalog, state_dir):
    _packet(packet)
    _, review, analysis = verify_case_parents(packet, source_request=source_request,
        claim_request=claim_request, passage_packet=passage_packet,
        review_packet=review_packet, workflow_contract=workflow_contract,
        claim_review_report=claim_review_report, analysis_packet=analysis_packet,
        analysis_report=analysis_report, project_dir=project_dir, catalog=catalog,
        state_dir=state_dir)
    previous_digest = _previous_case(packet, state_dir)
    body = {"case_id": packet["case_id"], "issuer_id": packet["issuer_id"],
            "isin": packet["isin"], "cutoff_timestamp": packet["cutoff_timestamp"],
            "opened_at": packet["opened_at"], "mode": "SANDBOX",
            "workflow_run_id": packet["workflow_run_id"],
            "analysis_run_id": packet["analysis_run_id"],
            "claim_review_report_id": review["report_id"],
            "analysis_report_id": analysis["report_id"],
            "input_sha256": packet["input_sha256"],
            "previous_case_id": packet.get("previous_case_id"),
            "previous_case_digest": previous_digest,
            "hypothesis": packet["hypothesis"],
            "rationale_claim_ids": packet["rationale_claim_ids"],
            "rationale_metric_ids": packet["rationale_metric_ids"],
            "prediction": packet["outcome"],
            "poker": packet.get("poker", {"status": "NOT_ASSESSED", "hand": None, "draw": None}),
            "fair_value": {"value_decimal": analysis["probability_weighted_fair_value"],
                           "unit": analysis["fair_value_unit"],
                           "value_kind": analysis["fair_value_kind"],
                           "model_status": "MODEL_UNVERIFIED",
                           "valuation_range": analysis["worksheet"]["valuation_range"]},
            "case_status": "SANDBOX_OPEN",
            "timing_class": ("HISTORICAL_RECONSTRUCTION" if
                             datetime.fromisoformat(packet["cutoff_timestamp"]).date() !=
                             datetime.fromisoformat(packet["opened_at"]).date()
                             else "ANALYST_DECLARED_PROSPECTIVE"),
            "publication_allowed": False, "live_decision_allowed": False,
            "promotion_status": "NOT_EVALUATED"}
    body["case_digest"] = _digest(body)
    return body


def verify_frozen_case(case_path: Path, case_packet_path: Path, *,
                       project_dir: Path, catalog: Path, state_dir: Path,
                       case_replay_inputs: dict[str, Path]) -> dict:
    """Rebuild a stored case from original inputs without creating a case."""
    packet = _read(case_packet_path, "case packet")
    case_id = _id(packet.get("case_id"), "case_id")
    expected_path = Path(state_dir) / "cases" / f"{case_id}.json"
    if (Path(case_path).resolve() != expected_path.resolve()
            or not expected_path.resolve().is_relative_to(Path(state_dir).resolve())
            or not expected_path.is_file()):
        raise ValueError("case path or stored case is invalid")
    old = _read(expected_path, "frozen case")
    if set(old) != CASE_FIELDS:
        raise ValueError("frozen case fields are invalid")
    if not isinstance(case_replay_inputs, dict) or set(case_replay_inputs) != set(INPUT_NAMES):
        raise ValueError("case replay inputs are invalid")
    body = _expected_case(packet, project_dir=project_dir, catalog=catalog,
                          state_dir=state_dir, **case_replay_inputs)
    if old != body:
        raise ValueError("frozen case differs from original packet or parents")
    return old


def open_sandbox_case(packet_path: Path, *, source_request: Path, claim_request: Path,
                      passage_packet: Path, review_packet: Path, workflow_contract: Path,
                      claim_review_report: Path, analysis_packet: Path, analysis_report: Path,
                      project_dir: Path, catalog: Path, state_dir: Path) -> dict:
    """Freeze one internal hypothesis only after exact parent replay."""
    packet = _read(packet_path, "case packet")
    body = _expected_case(packet, source_request=source_request,
                          claim_request=claim_request, passage_packet=passage_packet,
                          review_packet=review_packet, workflow_contract=workflow_contract,
                          claim_review_report=claim_review_report, analysis_packet=analysis_packet,
                          analysis_report=analysis_report, project_dir=project_dir,
                          catalog=catalog, state_dir=state_dir)
    path = Path(state_dir) / "cases" / f"{packet['case_id']}.json"
    if not path.resolve().is_relative_to(Path(state_dir).resolve()):
        raise ValueError("case path escapes state root")
    if path.exists():
        old = _read(path, "existing case")
        if old != body:
            raise ValueError("existing case differs from current parents or packet")
        return old
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".incoming-", delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(body, output, sort_keys=True, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.link(temporary, path)
    except FileExistsError:
        old = _read(path, "existing case")
        if old != body:
            raise ValueError("existing case differs from concurrent inputs")
        return old
    finally:
        temporary.unlink(missing_ok=True)
    return body
