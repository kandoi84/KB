"""Reveal synthetic market outcomes only after a frozen historical score.

The fixture declares its first eligible close. No trading-calendar service
exists to verify that selection, so every receipt labels it unverified.
"""

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping

from .case_snapshot import _digest, _id
from .historical_cohort import SAFETY, _sha, _strict
from .historical_score import RESULT_FIELDS, _case_view, _decimal, _read_bounded, _result
from .identity_store import _timestamp


REQUEST_FIELDS = {"run_id", "cohort_id", "cohort_digest", "score_run_id",
                  "score_digest", "rubric_version", "feed_id", "feed_version",
                  "feed_source_sha256", "reviewer_id", "calendar_version",
                  "execution_lag_days"}
ENTRY_FIELDS = {"at", "price", "currency", "exchange", "source_sha256",
                "source_json", "publication_at", "rights"}
HORIZON_FIELDS = {"at", "exit_price", "dividends", "split_factor",
                  "delisting_cashflow", "nifty_entry", "nifty_exit",
                  "sector_entry", "sector_exit", "publication_at",
                  "source_sha256", "source_json", "rights"}
MISSING_FIELDS = {"availability", "reason", "as_of", "publication_at",
                  "rights", "source_json", "source_sha256"}
MISSING_REASONS = {"NO_PRICE_OBSERVATION", "NO_ACTION_DATA",
                   "NO_DELISTING_DATA", "NO_BENCHMARK_OBSERVATION", "NO_DATA_RIGHTS"}
MONTHS = (6, 12, 24, 36)
REFERENCE_FIELDS = {"sector_membership", "benchmark_composition",
                    "benchmark_methodology", "sector_methodology"}
MEMBERSHIP_FIELDS = {"isin", "sector_id", "valid_from", "valid_to",
                     "observed_at", "publication_at", "source_sha256", "source_json", "rights"}
COMPOSITION_FIELDS = {"benchmark_id", "composition_id", "effective_from",
                      "effective_to", "observed_at", "publication_at",
                      "source_sha256", "source_json", "rights"}
METHODOLOGY_FIELDS = {"methodology_id", "return_kind", "currency",
                      "observed_at", "publication_at", "source_sha256", "source_json", "rights"}


@dataclass(frozen=True)
class MarketFeedAdapter:
    """Trusted fixture feed; no real feed is registered in this runtime."""

    feed_id: str
    version: str
    source_bytes: bytes
    dataset_kind: str
    provider_rights: str
    reviewer_id: str
    fetch: Callable[[Mapping], dict]


def _time(value, label):
    return datetime.fromisoformat(_timestamp(value, label))


def _months_later(stamp, months):
    year = stamp.year + (stamp.month - 1 + months) // 12
    month = (stamp.month - 1 + months) % 12 + 1
    # Trading-calendar convention: use the first eligible close on or after
    # this calendar date. A month-end date rolls to that target month's end.
    from calendar import monthrange
    day = min(stamp.day, monthrange(year, month)[1])
    return stamp.replace(year=year, month=month, day=day)


def _bound_source(value, label):
    source = value["source_json"]
    if not isinstance(source, str) or len(source.encode("utf-8")) > 64_000:
        raise ValueError(f"{label} source bytes are invalid")
    expected = {key: item for key, item in value.items()
                if key not in ("source_json", "source_sha256")}
    canonical = json.dumps(expected, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False)
    if source != canonical:
        raise ValueError(f"{label} source bytes differ from observation")
    _sha(value["source_sha256"], f"{label} source hash")
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != value["source_sha256"]:
        raise ValueError(f"{label} source hash differs from bytes")


def _known_reference(value, cutoff, label):
    observed = _time(value["observed_at"], f"{label} observed_at")
    published = _time(value["publication_at"], f"{label} publication_at")
    if observed > cutoff or published > cutoff or published < observed:
        raise ValueError(f"{label} was unavailable at decision cutoff")
    _bound_source(value, label)
    if value["rights"] != "REVIEWED_RESEARCH_USE":
        raise ValueError(f"{label} rights are unreviewed")


def _reference(value, view):
    _strict(value, REFERENCE_FIELDS, "market reference")
    cutoff = _time(view["cutoff_timestamp"], "case cutoff")
    membership = _strict(value["sector_membership"], MEMBERSHIP_FIELDS,
                         "sector membership")
    if membership["isin"] != view["isin"]:
        raise ValueError("sector membership ISIN differs")
    _id(membership["sector_id"], "sector_id")
    _known_reference(membership, cutoff, "sector membership")
    start = _time(membership["valid_from"], "sector membership valid_from")
    end = (None if membership["valid_to"] is None else
           _time(membership["valid_to"], "sector membership valid_to"))
    if start > cutoff or (end is not None and end < cutoff):
        raise ValueError("sector membership is stale or future")
    composition = _strict(value["benchmark_composition"], COMPOSITION_FIELDS,
                          "benchmark composition")
    for key in ("benchmark_id", "composition_id"):
        _id(composition[key], key)
    _known_reference(composition, cutoff, "benchmark composition")
    start = _time(composition["effective_from"], "composition effective_from")
    end = (None if composition["effective_to"] is None else
           _time(composition["effective_to"], "composition effective_to"))
    if start > cutoff or (end is not None and end < cutoff):
        raise ValueError("benchmark composition is stale or future")
    for name in ("benchmark_methodology", "sector_methodology"):
        parent_key = "benchmark_id" if name == "benchmark_methodology" else "sector_id"
        expected = composition["benchmark_id"] if parent_key == "benchmark_id" else membership["sector_id"]
        method = _strict(value[name], METHODOLOGY_FIELDS | {parent_key}, name)
        _id(method["methodology_id"], "methodology_id")
        if method[parent_key] != expected:
            raise ValueError(f"{name} differs from {parent_key}")
        _known_reference(method, cutoff, name)
        if method["return_kind"] != "TOTAL_RETURN" or method["currency"] != "INR":
            raise ValueError(f"{name} must use INR total returns")
    return value


def _replay(state, request):
    root = state.resolve()
    cohort_path = state / "historical_evaluation/cohorts" / f"{request['cohort_id']}.json"
    score_path = state / "historical_evaluation/scores" / f"{request['score_run_id']}.json"
    output_path = state / "historical_evaluation/reveals" / f"{request['run_id']}.json"
    if any(not path.resolve().is_relative_to(root)
           for path in (cohort_path, score_path, output_path)):
        raise ValueError("historical evaluation path escapes state root")
    cohort = _read_bounded(cohort_path, "cohort receipt", 20_000_000)
    score = _read_bounded(score_path, "score receipt", 20_000_000)
    if (cohort.get("cohort_id") != request["cohort_id"]
            or cohort.get("cohort_digest") != request["cohort_digest"]
            or _digest({key: value for key, value in cohort.items() if key != "cohort_digest"})
            != request["cohort_digest"]
            or score.get("run_id") != request["score_run_id"]
            or score.get("score_digest") != request["score_digest"]
            or _digest({key: value for key, value in score.items() if key != "score_digest"})
            != request["score_digest"]
            or score.get("cohort_digest") != request["cohort_digest"]
            or score.get("rubric_version") != request["rubric_version"]
            or cohort.get("rubric_version") != request["rubric_version"]):
        raise ValueError("cohort or score identity differs")
    if any(cohort.get(key) is not False or score.get(key) is not False for key in SAFETY):
        raise ValueError("cohort or score safety differs")
    if (score.get("dataset_kind") != cohort.get("dataset_kind")
            or not isinstance(score.get("scores"), list)
            or not isinstance(cohort.get("cases"), list)):
        raise ValueError("score and cohort dataset or rows differ")
    for row in score["scores"]:
        _strict(row, RESULT_FIELDS | {"case_id", "case_digest", "isin",
                                      "cutoff_timestamp"}, "score row")
        _result({key: row[key] for key in RESULT_FIELDS},
                _timestamp(row["cutoff_timestamp"], "score cutoff"))
    for row in cohort["cases"]:
        _strict(row, {"case_id", "case_digest", "isin", "cutoff_timestamp",
                      "case_packet_sha256", "input_sha256", "timing_class",
                      "case_class", "seal_proof", "blockers"}, "cohort row")
    score_rows = {row["case_id"]: row for row in score["scores"]}
    if len(score_rows) != len(score["scores"]):
        raise ValueError("score case IDs repeat")
    cohort_rows = {row["case_id"]: row for row in cohort["cases"]}
    if len(cohort_rows) != len(cohort["cases"]):
        raise ValueError("cohort case IDs repeat")
    if score["score_status"] == "MECHANICS_ONLY":
        if set(score_rows) != set(cohort_rows):
            raise ValueError("score sample differs from cohort")
        for case_id, row in score_rows.items():
            parent = cohort_rows[case_id]
            if any(row.get(field) != parent.get(field) for field in
                   ("case_digest", "isin", "cutoff_timestamp")):
                raise ValueError("score row differs from cohort")
    elif score["score_status"] != "BLOCKED_NO_SCORER" or score["scores"]:
        raise ValueError("score status is invalid")
    for row in cohort["cases"]:
        _case_view(state, row)
    _time(score["frozen_at"], "score frozen_at")
    return cohort, score, output_path


def _row(value, view, lag):
    _strict(value, {"case_id", "isin", "entry", "horizons", "reference"}, "market row")
    if value["case_id"] != view["case_id"] or value["isin"] != view["isin"]:
        raise ValueError("market row case or ISIN differs")
    reference = _reference(value["reference"], view)
    entry = _strict(value["entry"], ENTRY_FIELDS, "market entry")
    at = _time(entry["at"], "entry at")
    frozen = _time(view["score_frozen_at"], "score frozen_at")
    cutoff = _time(view["cutoff_timestamp"], "case cutoff")
    if at <= frozen + timedelta(days=lag) or at <= cutoff:
        raise ValueError("market entry must follow frozen decision and execution lag")
    if _time(entry["publication_at"], "entry publication") < at:
        raise ValueError("market entry publication precedes observation")
    if entry["currency"] != "INR" or entry["exchange"] not in ("NSE", "BSE"):
        raise ValueError("market currency or exchange is unsupported")
    if entry["rights"] != "REVIEWED_RESEARCH_USE":
        raise ValueError("market entry rights are unreviewed")
    _bound_source(entry, "entry")
    entry_price = _decimal(entry["price"], "entry price", minimum=Decimal("0.000000001"))
    horizons = _strict(value["horizons"], {str(month) for month in MONTHS}, "market horizons")
    result = {}
    for month in MONTHS:
        key = str(month)
        horizon = horizons[key]
        if horizon is None:
            result[key] = {"eligibility": "MISSING", "reason": "NO_REVIEWED_HORIZON_OBSERVATION",
                           "total_return": None, "nifty_excess_return": None,
                           "sector_excess_return": None}
            continue
        if isinstance(horizon, dict) and horizon.get("availability") == "MISSING":
            _strict(horizon, MISSING_FIELDS, "missing market horizon")
            if horizon["reason"] not in MISSING_REASONS:
                raise ValueError("missing horizon reason is invalid")
            as_of = _time(horizon["as_of"], "missing horizon as_of")
            published = _time(horizon["publication_at"], "missing horizon publication")
            target = _months_later(at, month)
            if as_of < target or as_of > target + timedelta(days=10) or published < as_of:
                raise ValueError("missing horizon is outside calendar or publication window")
            if horizon["rights"] != "REVIEWED_RESEARCH_USE":
                raise ValueError("missing horizon claim rights are unreviewed")
            _bound_source(horizon, "missing horizon")
            result[key] = {"eligibility": "MISSING", "reason": horizon["reason"],
                           "as_of": horizon["as_of"], "publication_at": horizon["publication_at"],
                           "source_sha256": horizon["source_sha256"],
                           "source_json": horizon["source_json"],
                           "total_return": None, "nifty_excess_return": None,
                           "sector_excess_return": None}
            continue
        _strict(horizon, HORIZON_FIELDS, "market horizon")
        end = _time(horizon["at"], "horizon at")
        target = _months_later(at, month)
        if end < target:
            raise ValueError("market horizon is incomplete")
        if end > target + timedelta(days=10):
            raise ValueError("market horizon is outside the calendar window")
        if _time(horizon["publication_at"], "horizon publication") < end:
            raise ValueError("market horizon publication precedes observation")
        if horizon["rights"] != "REVIEWED_RESEARCH_USE":
            raise ValueError("market horizon rights are unreviewed")
        _bound_source(horizon, "horizon")
        dividends = _decimal(horizon["dividends"], "dividends", minimum=0)
        split = _decimal(horizon["split_factor"], "split factor",
                         minimum=Decimal("0.000000001"))
        exit_value = horizon["exit_price"]
        delisting = horizon["delisting_cashflow"]
        if (exit_value is None) == (delisting is None):
            raise ValueError("exactly one exit price or delisting cashflow is required")
        if delisting is None:
            proceeds = _decimal(exit_value, "exit price", minimum=0) * split + dividends
        else:
            proceeds = _decimal(delisting, "delisting cashflow", minimum=0) + dividends
        nifty_entry = _decimal(horizon["nifty_entry"], "Nifty entry",
                               minimum=Decimal("0.000000001"))
        nifty_exit = _decimal(horizon["nifty_exit"], "Nifty exit", minimum=0)
        sector_entry = _decimal(horizon["sector_entry"], "sector entry",
                                minimum=Decimal("0.000000001"))
        sector_exit = _decimal(horizon["sector_exit"], "sector exit", minimum=0)
        total = proceeds / entry_price - 1
        nifty = nifty_exit / nifty_entry - 1
        sector = sector_exit / sector_entry - 1
        result[key] = {"eligibility": "ELIGIBLE", "reason": None,
                       "at": horizon["at"], "source_sha256": horizon["source_sha256"],
                       "source_json": horizon["source_json"],
                       "publication_at": horizon["publication_at"],
                       "delisted": delisting is not None,
                       "total_return": format(total, "f"),
                       "nifty_excess_return": format(total - nifty, "f"),
                       "sector_excess_return": format(total - sector, "f")}
    return {"case_id": view["case_id"], "isin": view["isin"],
            "entry": entry, "reference": reference, "horizons": result,
            "entry_selection_status": "DECLARED_FIRST_CLOSE_UNVERIFIED"}


def _link_once(path, body):
    def equivalent(old):
        return (old.get("reveal_digest") == _digest({key: value for key, value in old.items()
                                                     if key != "reveal_digest"})
                and all(old.get(key) is False for key in SAFETY)
                and {key: value for key, value in old.items()
                     if key not in ("revealed_at", "reveal_digest")}
                == {key: value for key, value in body.items()
                    if key not in ("revealed_at", "reveal_digest")})

    if path.is_file():
        old = _read_bounded(path, "existing reveal", 20_000_000)
        if not equivalent(old):
            raise ValueError("existing reveal differs from request")
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
        old = _read_bounded(path, "existing reveal", 20_000_000)
        if not equivalent(old):
            raise ValueError("existing reveal differs from concurrent replay")
        return old
    finally:
        temporary.unlink(missing_ok=True)
    return body


def reveal_historical_outcomes(request_path: Path, *, state_dir: Path,
                               feed_registry: Mapping[str, MarketFeedAdapter]) -> dict:
    """Read outcomes only after a score receipt; real returns remain blocked."""
    request = _strict(_read_bounded(request_path, "reveal request", 64_000),
                      REQUEST_FIELDS, "reveal request")
    for key in ("run_id", "cohort_id", "score_run_id", "rubric_version", "feed_id",
                "feed_version", "reviewer_id", "calendar_version"):
        _id(request[key], key)
    for key in ("cohort_digest", "score_digest", "feed_source_sha256"):
        _sha(request[key], key)
    lag = request["execution_lag_days"]
    if type(lag) is not int or not 0 <= lag <= 10:
        raise ValueError("execution lag days must be an integer from zero to ten")
    state = Path(state_dir)
    cohort, score, output_path = _replay(state, request)
    if not isinstance(feed_registry, Mapping):
        raise ValueError("feed registry must be a mapping")
    adapter = feed_registry.get(request["feed_id"])
    if adapter is not None and not isinstance(adapter, MarketFeedAdapter):
        raise ValueError("market feed registry entry is invalid")
    if adapter is not None:
        if (adapter.feed_id != request["feed_id"] or adapter.version != request["feed_version"]
                or not isinstance(adapter.source_bytes, bytes)
                or hashlib.sha256(adapter.source_bytes).hexdigest()
                != request["feed_source_sha256"]
                or adapter.provider_rights != "REVIEWED_RESEARCH_USE"
                or adapter.reviewer_id != request["reviewer_id"]):
            raise ValueError("market feed source, rights, or reviewer differs")
    available = (cohort["dataset_kind"] == "SYNTHETIC_FIXTURE"
                 and score["score_status"] == "MECHANICS_ONLY"
                 and adapter is not None and adapter.dataset_kind == "SYNTHETIC_FIXTURE")
    request_sha = _digest(request)
    if output_path.is_file():
        old = _read_bounded(output_path, "existing reveal", 20_000_000)
        if (old.get("reveal_digest") != _digest({key: value for key, value in old.items()
                                                 if key != "reveal_digest"})
                or old.get("request_sha256") != request_sha
                or old.get("reveal_status") != ("MECHANICS_ONLY" if available else
                                                "BLOCKED_NO_MARKET_FEED")
                or any(old.get(key) is not False for key in SAFETY)):
            raise ValueError("existing reveal differs from replay")
        return old
    observations = []
    if available:
        for scored in score["scores"]:
            view = MappingProxyType({"case_id": scored["case_id"], "isin": scored["isin"],
                                     "cutoff_timestamp": scored["cutoff_timestamp"],
                                     "score_frozen_at": score["frozen_at"]})
            observations.append(_row(adapter.fetch(view), view, lag))
        # Detect case/receipt changes made while the fixture feed ran.
        _replay(state, request)
    counts = {str(month): {"eligible": sum(row["horizons"][str(month)]["eligibility"] ==
                                           "ELIGIBLE" for row in observations),
                           "missing": sum(row["horizons"][str(month)]["eligibility"] ==
                                          "MISSING" for row in observations)}
              for month in MONTHS}
    status = "MECHANICS_ONLY" if available else "BLOCKED_NO_MARKET_FEED"
    body = {"run_id": request["run_id"], "cohort_id": request["cohort_id"],
            "cohort_digest": request["cohort_digest"],
            "score_run_id": request["score_run_id"], "score_digest": request["score_digest"],
            "rubric_version": request["rubric_version"],
            "feed_id": request["feed_id"], "feed_version": request["feed_version"],
            "feed_source_sha256": request["feed_source_sha256"],
            "reviewer_id": request["reviewer_id"], "calendar_version": request["calendar_version"],
            "execution_lag_days": lag, "dataset_kind": cohort["dataset_kind"],
            "observations": observations, "horizon_counts": counts,
            "reveal_status": status,
            "blockers": [] if available else ["NO_REVIEWED_MARKET_FEED"],
            "request_sha256": request_sha,
            "revealed_at": datetime.now(timezone.utc).isoformat(), **SAFETY}
    body["reveal_digest"] = _digest(body)
    return _link_once(output_path, body)
