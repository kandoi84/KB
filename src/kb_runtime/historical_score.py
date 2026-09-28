"""Freeze synthetic score mechanics without exposing future market observations."""

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping

from .case_snapshot import _digest, _id, _read
from .historical_cohort import SAFETY, _sha, _strict
from .identity_store import _timestamp


REQUEST_FIELDS = {"run_id", "cohort_id", "cohort_digest", "rubric_version",
                  "scorer_id", "scorer_version", "scorer_source_sha256",
                  "independent_run_id", "reviewer_id"}
RESULT_FIELDS = {"score", "factors", "error_band", "catalyst_forecasts", "fair_value"}
FACTORS = {"market_structure", "economics", "management", "valuation", "catalysts"}
FORECAST_FIELDS = {"catalyst_id", "probability", "due_at"}


@dataclass(frozen=True)
class ScoreAdapter:
    """Trusted local fixture scorer; metadata never authorizes real research."""

    scorer_id: str
    version: str
    source_bytes: bytes
    dataset_kind: str
    score: Callable[[Mapping], dict]


def _read_bounded(path, label, maximum):
    try:
        if Path(path).stat().st_size > maximum:
            raise ValueError(f"{label} is too large")
    except OSError as exc:
        raise ValueError(f"{label} is unavailable") from exc
    return _read(path, label)


def _decimal(value, label, *, minimum=None, maximum=None):
    if not isinstance(value, str) or not value or len(value) > 40:
        raise ValueError(f"{label} must be a decimal string")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{label} must be a decimal string") from exc
    if not number.is_finite() or (minimum is not None and number < minimum) or (
            maximum is not None and number > maximum):
        raise ValueError(f"{label} is out of range")
    return number


def _result(value, cutoff):
    _strict(value, RESULT_FIELDS, "score result")
    score = _decimal(value["score"], "score", minimum=0, maximum=100)
    factors = _strict(value["factors"], FACTORS, "score factors")
    for key, number in factors.items():
        _decimal(number, key, minimum=0, maximum=100)
    band = _strict(value["error_band"], {"lower", "upper"}, "score error band")
    lower = _decimal(band["lower"], "error lower", minimum=0, maximum=100)
    upper = _decimal(band["upper"], "error upper", minimum=0, maximum=100)
    if lower > score or upper < score:
        raise ValueError("score error band must contain score")
    forecasts = value["catalyst_forecasts"]
    if not isinstance(forecasts, list) or len(forecasts) > 100:
        raise ValueError("catalyst forecasts must be a bounded list")
    seen = set()
    for forecast in forecasts:
        _strict(forecast, FORECAST_FIELDS, "catalyst forecast")
        cid = _id(forecast["catalyst_id"], "catalyst_id")
        if cid in seen:
            raise ValueError("catalyst ID repeats")
        seen.add(cid)
        _decimal(forecast["probability"], "probability", minimum=0, maximum=1)
        due = datetime.fromisoformat(_timestamp(forecast["due_at"], "due_at"))
        if due <= datetime.fromisoformat(cutoff):
            raise ValueError("forecast due date precedes decision cutoff")
    fair = _strict(value["fair_value"], {"value_decimal", "unit"}, "fair value")
    _decimal(fair["value_decimal"], "fair value", minimum=0)
    if fair["unit"] != "INR_PER_SHARE":
        raise ValueError("fair value unit is unsupported")
    return value


def _freeze_view(case):
    """Copy only original decision fields; the adapter receives no state path."""
    selected = {key: case[key] for key in
                ("case_id", "case_digest", "isin", "cutoff_timestamp", "hypothesis",
                 "rationale_claim_ids", "rationale_metric_ids")}
    selected["forecast"] = case["prediction"]

    def immutable(value):
        if isinstance(value, dict):
            return MappingProxyType({key: immutable(item) for key, item in value.items()})
        if isinstance(value, list):
            return tuple(immutable(item) for item in value)
        return value

    return immutable(selected)


def _case_view(state, row):
    case_id = _id(row["case_id"], "case_id")
    path = state / "cases" / f"{case_id}.json"
    if not path.resolve().is_relative_to(state.resolve()):
        raise ValueError("case path escapes state root")
    case = _read_bounded(path, "frozen case", 1_000_000)
    case_digest = case.get("case_digest")
    if not isinstance(case_digest, str) or _digest({key: value for key, value in case.items()
                                                     if key != "case_digest"}) != case_digest:
        raise ValueError("frozen case digest differs")
    for field in ("case_id", "case_digest", "isin", "cutoff_timestamp", "input_sha256"):
        if case.get(field) != row.get(field):
            raise ValueError("frozen case differs from cohort")
    if (case.get("publication_allowed") is not False
            or case.get("live_decision_allowed") is not False):
        raise ValueError("frozen case safety differs")
    if not isinstance(case.get("prediction"), dict):
        raise ValueError("frozen case forecast is invalid")
    return _freeze_view(case)


def _link_once(path, body):
    def equivalent(old):
        if (old.get("score_digest") != _digest({key: value for key, value in old.items()
                                                 if key != "score_digest"})
                or any(old.get(key) is not False for key in SAFETY)):
            return False
        return ({key: value for key, value in old.items()
                 if key not in ("frozen_at", "score_digest")}
                == {key: value for key, value in body.items()
                    if key not in ("frozen_at", "score_digest")})

    if path.is_file():
        old = _read(path, "existing score")
        if not equivalent(old):
            raise ValueError("existing score differs")
        return old
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
        old = _read(path, "existing score")
        if not equivalent(old):
            raise ValueError("existing score differs from concurrent replay")
        return old
    finally:
        temporary.unlink(missing_ok=True)
    return body


def freeze_historical_scores(request_path: Path, *, state_dir: Path,
                             scorer_registry: Mapping[str, ScoreAdapter]) -> dict:
    """Freeze fixture scores; no registered adapter may score real cases yet."""
    request = _strict(_read_bounded(request_path, "score request", 64_000),
                      REQUEST_FIELDS, "score request")
    for key in ("run_id", "cohort_id", "rubric_version", "scorer_id",
                "scorer_version", "independent_run_id", "reviewer_id"):
        _id(request[key], key)
    _sha(request["cohort_digest"], "cohort digest")
    _sha(request["scorer_source_sha256"], "scorer source hash")
    if request["independent_run_id"] == request["run_id"]:
        raise ValueError("repeat run ID must differ from score run ID")
    state = Path(state_dir)
    root = state.resolve()
    cohort_path = state / "historical_evaluation/cohorts" / f"{request['cohort_id']}.json"
    output_path = state / "historical_evaluation/scores" / f"{request['run_id']}.json"
    if (not cohort_path.resolve().is_relative_to(root)
            or not output_path.resolve().is_relative_to(root)):
        raise ValueError("historical evaluation path escapes state root")
    cohort = _read_bounded(cohort_path, "cohort receipt", 20_000_000)
    if (_digest({key: value for key, value in cohort.items() if key != "cohort_digest"})
            != request["cohort_digest"] or cohort.get("cohort_digest") != request["cohort_digest"]
            or cohort.get("cohort_id") != request["cohort_id"]
            or cohort.get("rubric_version") != request["rubric_version"]):
        raise ValueError("cohort digest, ID, or rubric differs")
    if (cohort.get("scorer_id") is not None and
            (cohort["scorer_id"] != request["scorer_id"] or
             cohort.get("scorer_source_sha256") != request["scorer_source_sha256"])):
        raise ValueError("cohort scorer differs from score request")
    if any(cohort.get(key) is not False for key in SAFETY):
        raise ValueError("cohort safety differs")
    if not isinstance(scorer_registry, Mapping):
        raise ValueError("scorer registry must be a mapping")
    adapter = scorer_registry.get(request["scorer_id"])
    available = (cohort.get("dataset_kind") == "SYNTHETIC_FIXTURE"
                 and isinstance(adapter, ScoreAdapter)
                 and adapter.dataset_kind == "SYNTHETIC_FIXTURE")
    if adapter is not None and isinstance(adapter, ScoreAdapter):
        if (adapter.scorer_id != request["scorer_id"]
                or adapter.version != request["scorer_version"]
                or not isinstance(adapter.source_bytes, bytes)
                or hashlib.sha256(adapter.source_bytes).hexdigest()
                != request["scorer_source_sha256"]):
            raise ValueError("scorer adapter source identity differs")
    if not available and adapter is not None and not isinstance(adapter, ScoreAdapter):
        raise ValueError("scorer registry entry is invalid")
    request_sha = _digest(request)
    if output_path.is_file():
        old = _read_bounded(output_path, "existing score", 20_000_000)
        if (old.get("score_digest") != _digest({key: value for key, value in old.items()
                                                 if key != "score_digest"})
                or old.get("request_sha256") != request_sha
                or old.get("cohort_digest") != request["cohort_digest"]):
            raise ValueError("existing score differs from request or digest")
        for cohort_case in cohort["cases"]:
            _case_view(state, cohort_case)
        if old.get("score_status") != ("MECHANICS_ONLY" if available else "BLOCKED_NO_SCORER"):
            raise ValueError("existing score differs from scorer availability")
        return old
    rows = []
    if available:
        for cohort_case in cohort["cases"]:
            view = _case_view(state, cohort_case)
            scored = _result(adapter.score(view), view["cutoff_timestamp"])
            rows.append({"case_id": view["case_id"], "case_digest": view["case_digest"],
                         "isin": view["isin"], "cutoff_timestamp": view["cutoff_timestamp"],
                         **scored})
        if _read_bounded(cohort_path, "cohort receipt", 20_000_000) != cohort:
            raise ValueError("cohort changed during scoring")
        for cohort_case in cohort["cases"]:
            _case_view(state, cohort_case)
    status = "MECHANICS_ONLY" if available else "BLOCKED_NO_SCORER"
    body = {"run_id": request["run_id"], "cohort_id": request["cohort_id"],
            "cohort_digest": request["cohort_digest"],
            "rubric_version": request["rubric_version"],
            "scorer_id": request["scorer_id"], "scorer_version": request["scorer_version"],
            "scorer_source_sha256": request["scorer_source_sha256"],
            "independent_run_id": request["independent_run_id"],
            "repeat_status": "NOT_VERIFIED", "reviewer_id": request["reviewer_id"],
            "dataset_kind": cohort["dataset_kind"], "scores": rows,
            "score_status": status,
            "blockers": [] if available else ["NO_REVIEWED_SCORER"],
            "request_sha256": request_sha,
            "frozen_at": datetime.now(timezone.utc).isoformat(), **SAFETY}
    body["score_digest"] = _digest(body)
    return _link_once(output_path, body)
