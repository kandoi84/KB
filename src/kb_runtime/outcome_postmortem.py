"""Source-backed sandbox outcomes and immutable human postmortems."""

import json
import os
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .case_snapshot import _digest, _id, _ids, _read, verify_frozen_case
from .identity_store import DIGEST, _timestamp
from .metric_store import query_metrics
from .source_store import _read_existing


EVENT_REQUIRED = {"event_id", "case_id", "case_digest", "event_type", "metric_id",
                  "observed_at", "recorded_at"}
DUE_REQUIRED = {"postmortem_id", "case_id", "case_digest", "evaluated_at"}
REVIEW_FIELDS = {"reviewer_id", "reviewed_at", "process_assessment", "reasoning",
                 "cited_case_ids", "cited_claim_ids", "cited_metric_ids", "cited_gap_ids",
                 "error_class", "error_explanation", "reproducible_process_failure",
                 "failure_invariant"}
ERROR_CLASSES = {"THESIS_ERROR", "PROBABILITY_ERROR", "VALUATION_ERROR", "TIMING_ERROR",
                 "DATA_ERROR", "SOURCE_ERROR", "MACRO_REGIME_ERROR", "CATALYST_ERROR",
                 "MISSING_INFORMATION", "PROCESS_VIOLATION", "MODEL_ERROR",
                 "UNAVOIDABLE_SURPRISE", "NONE"}
SAFETY = {"publication_allowed": False, "live_decision_allowed": False,
          "promotion_status": "NOT_EVALUATED"}


def _time(value, label):
    return datetime.fromisoformat(_timestamp(value, label))


def _digest_field(value, label):
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        raise ValueError(f"{label} is invalid")
    return value


def _strict(value, required, optional, label):
    if not isinstance(value, dict) or not required <= set(value) or set(value) - required - optional:
        raise ValueError(f"{label} fields are invalid")
    return value


def _path(state_dir, folder, identifier):
    root = Path(state_dir).resolve()
    path = Path(state_dir) / folder / f"{_id(identifier, folder)}.json"
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"{folder} path escapes state root")
    return path


def _existing(path, label):
    if not path.is_file():
        return None
    return _read(path, label)


def _check_existing(path, expected, label):
    existing = _existing(path, label)
    if existing is not None and existing != expected:
        raise ValueError(f"existing {label} differs")
    return existing


def _link_once(path, body, label):
    existing = _check_existing(path, body, label)
    if existing is not None:
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".incoming-", delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(body, output, sort_keys=True, indent=2, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.link(temporary, path)
    except FileExistsError:
        _check_existing(path, body, label)
    finally:
        temporary.unlink(missing_ok=True)
    return body


def _case(case_id, case_digest, *, case_packet_path, project_dir, catalog, state_dir,
          case_replay_inputs):
    _id(case_id, "case_id")
    _digest_field(case_digest, "case_digest")
    case = verify_frozen_case(_path(state_dir, "cases", case_id), case_packet_path,
                              project_dir=project_dir, catalog=catalog, state_dir=state_dir,
                              case_replay_inputs=case_replay_inputs)
    if (case["case_id"] != case_id or case["case_digest"] != case_digest
            or case["case_status"] != "SANDBOX_OPEN"
            or any(case.get(key) != value for key, value in SAFETY.items())):
        raise ValueError("case is invalid or publication gate differs")
    return case


def _event_packet(packet):
    _strict(packet, EVENT_REQUIRED, {"supersedes_event_id"}, "event")
    for key in ("event_id", "case_id", "metric_id"):
        _id(packet[key], key)
    _digest_field(packet["case_digest"], "case_digest")
    if packet["event_type"] != "OUTCOME_OBSERVED":
        raise ValueError("event type is invalid")
    observed = _time(packet["observed_at"], "observed_at")
    if _time(packet["recorded_at"], "recorded_at") < observed:
        raise ValueError("event recorded before observation")
    prior = packet.get("supersedes_event_id")
    if prior is not None:
        _id(prior, "supersedes_event_id")
        if prior == packet["event_id"]:
            raise ValueError("event cannot supersede itself")
    return observed


def _expected_event(packet, case, *, project_dir, catalog, state_dir, _seen=frozenset()):
    observed = _event_packet(packet)
    if packet["event_id"] in _seen or len(_seen) >= 128:
        raise ValueError("event revision chain has a cycle or exceeds its limit")
    seen = _seen | {packet["event_id"]}
    if (packet["case_id"] != case["case_id"] or packet["case_digest"] != case["case_digest"]
            or observed <= _time(case["cutoff_timestamp"], "case cutoff")):
        raise ValueError("event case or observation cutoff differs")
    prediction = case["prediction"]
    rows = query_metrics(catalog, project_dir, case["isin"], prediction["metric_name"],
                         prediction["period_end"], packet["observed_at"])
    selected = [row for row in rows if row["metric_id"] == packet["metric_id"]]
    if len(selected) != 1:
        raise ValueError("event metric is missing or ambiguous at observation cutoff")
    metric = selected[0]
    if (metric["isin"] != case["isin"] or metric["metric_name"] != prediction["metric_name"]
            or metric["period_end"] != prediction["period_end"]
            or metric["unit"] != prediction["unit"] or metric["value_kind"] != "REPORTED"
            or metric["availability_mode"] != "LIVE_STRICT"
            or metric["publication_allowed"] is not False):
        raise ValueError("event metric identity, unit, or reported status differs")
    for key in ("published_at", "first_seen_at", "reviewed_at"):
        if _time(metric[key], key) > observed:
            raise ValueError("event metric has future availability")
    version_path = (Path(project_dir) / "data/registry/sources" / metric["source_id"]
                    / f"{metric['version_id']}.json")
    try:
        version = _read_existing(version_path)
        if (version["source_id"] != metric["source_id"]
                or version["version_id"] != metric["version_id"]
                or _time(version["observed_at"], "source observed_at") > observed
                or _time(version["retrieved_at"], "source retrieved_at") > observed):
            raise ValueError("event source version or availability differs")
        raw_sha = _digest_field(version["raw_sha256"], "raw_sha256")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("event source version is invalid") from exc
    previous_id = packet.get("supersedes_event_id")
    previous_digest = None
    if previous_id is not None:
        previous = _existing(_path(state_dir, f"case_events/{case['case_id']}", previous_id),
                             "previous event")
        if previous is None or previous.get("event_id") != previous_id:
            raise ValueError("previous event is invalid or out of order")
        try:
            expected_previous = _expected_event(_event_from_receipt(previous), case,
                                                project_dir=project_dir, catalog=catalog,
                                                state_dir=state_dir, _seen=seen)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("previous event source replay is invalid") from exc
        series = ("isin", "metric_name", "unit", "period_end", "period_kind",
                  "reporting_scope", "value_kind")
        if (previous != expected_previous
                or any(previous[key] != metric[key] for key in series)
                or _time(previous["observed_at"], "previous observed_at") >= observed
                or _time(previous["recorded_at"], "previous recorded_at")
                >= _time(packet["recorded_at"], "recorded_at")):
            raise ValueError("previous event differs from source, series, or revision order")
        previous_digest = previous["event_digest"]
    citation = {key: metric[key] for key in (
        "filing_id", "source_id", "version_id", "document_type", "evidence_locator",
        "published_at", "first_seen_at", "reviewed_at")}
    citation["raw_sha256"] = raw_sha
    body = {key: packet[key] for key in EVENT_REQUIRED}
    body.update({"supersedes_event_id": previous_id, "previous_event_digest": previous_digest,
                 "isin": case["isin"], "metric_name": metric["metric_name"],
                 "unit": metric["unit"], "period_end": metric["period_end"],
                 "period_kind": metric["period_kind"],
                 "reporting_scope": metric["reporting_scope"],
                 "value_kind": metric["value_kind"], "value_decimal": metric["value_decimal"],
                 "citation": citation, "availability_mode": "LIVE_STRICT",
                 "observation_timing": ("ON_TIME" if observed <= _time(prediction["due_at"], "due_at")
                                        else "LATE_OBSERVATION"),
                 "case_timing_class": case["timing_class"], **SAFETY})
    body["event_digest"] = _digest(body)
    return body


def append_outcome_observation(packet_path: Path, *, case_packet_path: Path,
                               project_dir: Path, catalog: Path, state_dir: Path,
                               case_replay_inputs: dict[str, Path]) -> dict:
    """Append one source-backed actual; changed same-ID replays fail."""
    packet = _read(packet_path, "event packet")
    _event_packet(packet)
    case = _case(packet["case_id"], packet["case_digest"],
                 case_packet_path=case_packet_path, project_dir=project_dir, catalog=catalog,
                 state_dir=state_dir, case_replay_inputs=case_replay_inputs)
    body = _expected_event(packet, case, project_dir=project_dir, catalog=catalog,
                           state_dir=state_dir)
    return _link_once(_path(state_dir, f"case_events/{case['case_id']}", packet["event_id"]),
                      body, "event")


def _review(packet, case, result_status, evaluated_at):
    _strict(packet, REVIEW_FIELDS, set(), "process review")
    _id(packet["reviewer_id"], "reviewer_id")
    reviewed = _time(packet["reviewed_at"], "reviewed_at")
    if reviewed > evaluated_at or reviewed <= _time(case["cutoff_timestamp"], "case cutoff"):
        raise ValueError("process review time is outside case evaluation")
    if (not isinstance(packet["process_assessment"], str)
            or packet["process_assessment"] not in {"GOOD_PROCESS", "BAD_PROCESS"}):
        raise ValueError("process assessment is invalid")
    for key in ("reasoning", "error_explanation"):
        if not isinstance(packet[key], str) or len(packet[key].strip()) < 12:
            raise ValueError(f"process {key} must be substantive")
    if not isinstance(packet["error_class"], str) or packet["error_class"] not in ERROR_CLASSES:
        raise ValueError("process error class is invalid")
    for key in ("cited_case_ids", "cited_claim_ids", "cited_metric_ids", "cited_gap_ids"):
        _ids(packet[key], key)
    if (packet["cited_case_ids"] != [case["case_id"]]
            or not set(packet["cited_claim_ids"]) <= set(case["rationale_claim_ids"])
            or not set(packet["cited_metric_ids"]) <= set(case["rationale_metric_ids"])
            or packet["cited_gap_ids"]):
        raise ValueError("process review cites unavailable frozen inputs")
    reproducible = packet["reproducible_process_failure"]
    invariant = packet["failure_invariant"]
    if not isinstance(reproducible, bool):
        raise ValueError("process reproducibility must be boolean")
    if reproducible:
        if not isinstance(invariant, str) or len(invariant.strip()) < 12:
            raise ValueError("process failure invariant is required")
    elif invariant is not None:
        raise ValueError("process failure invariant requires reproducibility")
    if packet["process_assessment"] == "GOOD_PROCESS":
        if packet["error_class"] not in {"NONE", "UNAVOIDABLE_SURPRISE"} or reproducible:
            raise ValueError("good process error taxonomy differs")
    elif packet["error_class"] in {"NONE", "UNAVOIDABLE_SURPRISE"}:
        raise ValueError("bad process requires a named process error")
    if packet["error_class"] == "UNAVOIDABLE_SURPRISE" and result_status != "RESULT_MISSED":
        raise ValueError("unavoidable surprise requires a missed target")
    return packet


def _event_from_receipt(receipt):
    return {key: receipt[key] for key in EVENT_REQUIRED} | {
        "supersedes_event_id": receipt["supersedes_event_id"]}


def evaluate_due_case(packet_path: Path, *, case_packet_path: Path,
                      project_dir: Path, catalog: Path, state_dir: Path,
                      case_replay_inputs: dict[str, Path]) -> dict:
    """Freeze a due result and human review; candidate writes precede completion."""
    packet = _read(packet_path, "postmortem packet")
    _strict(packet, DUE_REQUIRED, {"observation_event_id", "process_review"}, "postmortem")
    _id(packet["postmortem_id"], "postmortem_id")
    evaluated = _time(packet["evaluated_at"], "evaluated_at")
    case = _case(packet["case_id"], packet["case_digest"],
                 case_packet_path=case_packet_path, project_dir=project_dir, catalog=catalog,
                 state_dir=state_dir, case_replay_inputs=case_replay_inputs)
    prediction = case["prediction"]
    if evaluated < _time(prediction["due_at"], "due_at"):
        raise ValueError("case is not due")
    event_id = packet.get("observation_event_id")
    review = packet.get("process_review")
    if event_id is not None:
        _id(event_id, "observation_event_id")
    if event_id is None and review is not None:
        raise ValueError("process review requires an observation")
    event = None
    result_status = None
    quadrant = None
    if event_id is not None:
        event_path = _path(state_dir, f"case_events/{case['case_id']}", event_id)
        event = _existing(event_path, "observation event")
        if event is None:
            raise ValueError("observation event is missing")
        try:
            expected_event = _expected_event(_event_from_receipt(event), case,
                                             project_dir=project_dir, catalog=catalog,
                                             state_dir=state_dir)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("observation event replay is invalid") from exc
        if event != expected_event or event["event_id"] != event_id:
            raise ValueError("observation event differs from source replay")
        if (_time(event["observed_at"], "observed_at") > evaluated
                or _time(event["recorded_at"], "recorded_at") > evaluated):
            raise ValueError("observation event is later than evaluation")
        actual, target = Decimal(event["value_decimal"]), Decimal(prediction["target_decimal"])
        met = actual >= target if prediction["comparison"] == "AT_LEAST" else actual <= target
        result_status = "RESULT_MET" if met else "RESULT_MISSED"
    if review is not None:
        _review(review, case, result_status, evaluated)
        quadrant = (review["process_assessment"] +
                    ("_GOOD_RESULT" if result_status == "RESULT_MET" else "_BAD_RESULT"))
    status = ("AWAITING_OBSERVATION" if event is None else
              "AWAITING_PROCESS_REVIEW" if review is None else "COMPLETE")
    candidate_needed = (status == "COMPLETE" and review["process_assessment"] == "BAD_PROCESS"
                        and review["reproducible_process_failure"])
    body = {"postmortem_id": packet["postmortem_id"], "case_id": case["case_id"],
            "case_digest": case["case_digest"], "evaluated_at": packet["evaluated_at"],
            "observation_event_id": event_id,
            "observation_event_digest": event["event_digest"] if event else None,
            "observed_value_decimal": event["value_decimal"] if event else None,
            "target_decimal": prediction["target_decimal"],
            "comparison": prediction["comparison"], "result_status": result_status,
            "process_review": review, "quadrant": quadrant,
            "postmortem_status": status,
            "eval_candidate_id": packet["postmortem_id"] if candidate_needed else None,
            "case_timing_class": case["timing_class"], **SAFETY}
    body["postmortem_digest"] = _digest(body)
    post_path = _path(state_dir, "postmortems", packet["postmortem_id"])
    candidate_path = _path(state_dir, "eval_candidates", packet["postmortem_id"])
    if candidate_needed:
        candidate = {"candidate_id": packet["postmortem_id"],
                     "case_id": case["case_id"], "case_digest": case["case_digest"],
                     "postmortem_id": packet["postmortem_id"],
                     "postmortem_digest": body["postmortem_digest"],
                     "inception_cutoff": case["cutoff_timestamp"],
                     "decision_inputs": {"case_id": case["case_id"],
                                         "case_digest": case["case_digest"],
                                         "cutoff_timestamp": case["cutoff_timestamp"],
                                         "cited_claim_ids": review["cited_claim_ids"],
                                         "cited_metric_ids": review["cited_metric_ids"],
                                         "cited_gap_ids": review["cited_gap_ids"]},
                     "error_class": review["error_class"],
                     "failure_invariant": review["failure_invariant"],
                     "candidate_status": "UNREVIEWED", **SAFETY}
        candidate["candidate_digest"] = _digest(candidate)
        previous_post = _check_existing(post_path, body, "postmortem")
        _check_existing(candidate_path, candidate, "eval candidate")
        if previous_post is not None and not candidate_path.is_file():
            raise ValueError("completed postmortem is missing its eval candidate")
        _link_once(candidate_path, candidate, "eval candidate")
        _link_once(post_path, body, "postmortem")
        if (_check_existing(candidate_path, candidate, "eval candidate") is None
                or _check_existing(post_path, body, "postmortem") is None):
            raise ValueError("postmortem pair is incomplete")
    else:
        if candidate_path.exists():
            raise ValueError("postmortem has an unexpected eval candidate")
        _link_once(post_path, body, "postmortem")
    return body
