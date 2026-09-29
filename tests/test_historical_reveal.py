"""Outcome reveal follows an immutable score and remains nonpromotional."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from threading import Barrier

import pytest

from test_case_snapshot import _write
from test_historical_score import _adapter, _fixture, _freeze


def _setup(tmp_path, dataset_kind="SYNTHETIC_FIXTURE"):
    setup, cohort, score_request = _fixture(tmp_path, dataset_kind)
    registry = {} if dataset_kind == "REVIEWED_REAL" else {"fixture-scorer": _adapter()}
    score = _freeze(tmp_path, setup, score_request, registry)
    request = {
        "run_id": "reveal-1", "cohort_id": cohort["cohort_id"],
        "cohort_digest": cohort["cohort_digest"],
        "score_run_id": score["run_id"], "score_digest": score["score_digest"],
        "rubric_version": cohort["rubric_version"],
        "feed_id": "fixture-feed", "feed_version": "v1",
        "feed_source_sha256": hashlib.sha256(b"feed-v1").hexdigest(),
        "reviewer_id": "reviewer-3", "calendar_version": "fixture-calendar-v1",
        "execution_lag_days": 1,
    }
    return setup, cohort, score, request


def _seal(record):
    clean = {key: value for key, value in record.items()
             if key not in ("source_json", "source_sha256")}
    source = json.dumps(clean, sort_keys=True, separators=(",", ":"))
    record["source_json"] = source
    record["source_sha256"] = hashlib.sha256(source.encode()).hexdigest()


def _row(view):

    entry = datetime.fromisoformat(view["score_frozen_at"]) + timedelta(days=2)
    at = entry.isoformat()
    entry_record = {"at": at, "price": "100", "currency": "INR",
                    "exchange": "NSE", "source_sha256": "a" * 64,
                    "publication_at": at, "rights": "REVIEWED_RESEARCH_USE"}
    horizons = {}
    for months, days in ((6, 184), (12, 365), (24, 731), (36, 1096)):
        end = (entry + timedelta(days=days)).isoformat()
        horizons[str(months)] = {
            "at": end, "exit_price": "108", "dividends": "2",
            "split_factor": "1", "delisting_cashflow": None,
            "nifty_entry": "100", "nifty_exit": "105",
            "sector_entry": "100", "sector_exit": "104",
            "publication_at": end, "source_sha256": "b" * 64,
            "rights": "REVIEWED_RESEARCH_USE",
        }
    cutoff = datetime.fromisoformat(view["cutoff_timestamp"])
    known = (cutoff - timedelta(days=1)).isoformat()
    reference = {
        "sector_membership": {"isin": view["isin"], "sector_id": "BANKS",
                              "valid_from": "2020-01-01T00:00:00+05:30",
                              "valid_to": None, "observed_at": known,
                              "publication_at": known, "source_sha256": "c" * 64,
                              "rights": "REVIEWED_RESEARCH_USE"},
        "benchmark_composition": {"benchmark_id": "NIFTY_50",
                                  "composition_id": "nifty-set-2026q3",
                                  "effective_from": "2026-07-01T00:00:00+05:30",
                                  "effective_to": None, "observed_at": known,
                                  "publication_at": known, "source_sha256": "d" * 64,
                                  "rights": "REVIEWED_RESEARCH_USE"},
        "benchmark_methodology": {"methodology_id": "nifty-total-return-v1",
                                  "benchmark_id": "NIFTY_50",
                                  "return_kind": "TOTAL_RETURN", "currency": "INR",
                                  "observed_at": known, "publication_at": known,
                                  "source_sha256": "e" * 64,
                                  "rights": "REVIEWED_RESEARCH_USE"},
        "sector_methodology": {"methodology_id": "bank-total-return-v1",
                               "sector_id": "BANKS",
                               "return_kind": "TOTAL_RETURN", "currency": "INR",
                               "observed_at": known, "publication_at": known,
                               "source_sha256": "f" * 64,
                               "rights": "REVIEWED_RESEARCH_USE"},
    }
    _seal(entry_record)
    for horizon in horizons.values():
        _seal(horizon)
    for record in reference.values():
        _seal(record)
    return {"case_id": view["case_id"], "isin": view["isin"],
            "entry": entry_record, "horizons": horizons,
            "reference": reference}


def _feed(mutate=None, *, reseal=True):
    from src.kb_runtime.historical_reveal import MarketFeedAdapter

    def fetch(view):
        row = _row(view)
        if mutate:
            mutate(row, view)
            if reseal:
                for record in [row["entry"], *row["reference"].values(),
                               *row["horizons"].values()]:
                    if isinstance(record, dict) and "source_json" in record:
                        _seal(record)
        return row

    return MarketFeedAdapter("fixture-feed", "v1", b"feed-v1",
                             "SYNTHETIC_FIXTURE", "REVIEWED_RESEARCH_USE",
                             "reviewer-3", fetch)


def _reveal(tmp_path, setup, request, registry):
    from src.kb_runtime.historical_reveal import reveal_historical_outcomes

    return reveal_historical_outcomes(_write(tmp_path / "reveal-request.json", request),
                                      state_dir=setup[0][1], feed_registry=registry)


def test_real_current_runtime_blocks_without_market_feed(tmp_path):
    setup, _, _, request = _setup(tmp_path, "REVIEWED_REAL")
    result = _reveal(tmp_path, setup, request, {})
    assert result["reveal_status"] == "BLOCKED_NO_MARKET_FEED"
    assert result["observations"] == []
    assert "NO_REVIEWED_MARKET_FEED" in result["blockers"]
    assert all(result[key] is False for key in
               ("publication_allowed", "live_decision_allowed", "promotion_allowed"))


def test_synthetic_postfreeze_returns_and_exact_retry(tmp_path):
    setup, _, score, request = _setup(tmp_path)
    result = _reveal(tmp_path, setup, request, {"fixture-feed": _feed()})
    assert result["reveal_status"] == "MECHANICS_ONLY"
    row = result["observations"][0]
    assert row["case_id"] == score["scores"][0]["case_id"]
    assert row["horizons"]["12"]["eligibility"] == "ELIGIBLE"
    assert Decimal(row["horizons"]["12"]["total_return"]) == Decimal("0.10")
    assert Decimal(row["horizons"]["12"]["nifty_excess_return"]) == Decimal("0.05")
    assert result["horizon_counts"]["12"] == {"eligible": 1, "missing": 0}
    assert row["entry_selection_status"] == "DECLARED_FIRST_CLOSE_UNVERIFIED"
    assert row["reference"]["benchmark_methodology"]["return_kind"] == "TOTAL_RETURN"
    assert all(result[key] is False for key in
               ("publication_allowed", "live_decision_allowed", "promotion_allowed"))
    assert not result["promotion_allowed"]
    assert _reveal(tmp_path, setup, request, {"fixture-feed": _feed()}) == result


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(outcome_path="future.json"),
    lambda r: r.update(feed_source_sha256="c" * 64),
    lambda r: r.update(score_digest="d" * 64),
    lambda r: r.update(execution_lag_days=-1),
    lambda r: r.update(command="fetch prices"),
])
def test_request_rejects_unknown_or_mismatched_inputs(tmp_path, mutation):
    setup, _, _, request = _setup(tmp_path)
    mutation(request)
    with pytest.raises(ValueError):
        _reveal(tmp_path, setup, request, {"fixture-feed": _feed()})


def test_fixture_feed_cannot_reveal_real_scores(tmp_path):
    setup, _, _, request = _setup(tmp_path, "REVIEWED_REAL")
    result = _reveal(tmp_path, setup, request, {"fixture-feed": _feed()})
    assert result["reveal_status"] == "BLOCKED_NO_MARKET_FEED"


@pytest.mark.parametrize("mutate", [
    lambda row, view: row["entry"].update(at=view["score_frozen_at"]),
    lambda row, view: row["entry"].update(rights="NO_RESEARCH_RIGHTS"),
    lambda row, view: row["horizons"]["12"].update(publication_at=view["score_frozen_at"]),
    lambda row, view: row.update(isin="INE030A01027"),
    lambda row, view: row["horizons"]["12"].update(nifty_exit=None),
])
def test_invalid_or_unreviewed_feed_does_not_write(tmp_path, mutate):
    setup, _, _, request = _setup(tmp_path)
    with pytest.raises(ValueError):
        _reveal(tmp_path, setup, request, {"fixture-feed": _feed(mutate)})
    assert not (setup[0][1] / "historical_evaluation/reveals/reveal-1.json").exists()


def test_missing_horizon_is_counted_not_a_win(tmp_path):
    setup, _, _, request = _setup(tmp_path)
    result = _reveal(tmp_path, setup, request,
                     {"fixture-feed": _feed(lambda row, view:
                                            row["horizons"].update({"36": None}))})
    assert result["observations"][0]["horizons"]["36"]["eligibility"] == "MISSING"
    assert result["observations"][0]["horizons"]["36"]["total_return"] is None
    assert result["horizon_counts"]["36"] == {"eligible": 0, "missing": 1}


def test_delisting_cashflow_includes_dividends_and_split(tmp_path):
    setup, _, _, request = _setup(tmp_path)

    def delist(row, view):
        row["horizons"]["12"].update(exit_price=None, split_factor="2",
                                      dividends="3", delisting_cashflow="120")

    result = _reveal(tmp_path, setup, request, {"fixture-feed": _feed(delist)})
    assert Decimal(result["observations"][0]["horizons"]["12"]["total_return"]) == Decimal("0.23")


def test_split_adjusted_exit_price_and_dividends(tmp_path):
    setup, _, _, request = _setup(tmp_path)

    def split(row, view):
        row["horizons"]["12"].update(exit_price="54", split_factor="2",
                                      dividends="2", delisting_cashflow=None)

    result = _reveal(tmp_path, setup, request, {"fixture-feed": _feed(split)})
    assert Decimal(result["observations"][0]["horizons"]["12"]["total_return"]) == Decimal("0.10")


def test_incomplete_calendar_horizon_is_rejected(tmp_path):
    setup, _, _, request = _setup(tmp_path)

    def early(row, view):
        row["horizons"]["24"].update(at=row["entry"]["at"],
                                      publication_at=row["entry"]["at"])

    with pytest.raises(ValueError, match="incomplete"):
        _reveal(tmp_path, setup, request, {"fixture-feed": _feed(early)})


def test_horizon_cannot_select_a_much_later_price(tmp_path):
    setup, _, _, request = _setup(tmp_path)

    def late(row, view):
        far_later = (datetime.fromisoformat(row["horizons"]["6"]["at"])
                     + timedelta(days=90)).isoformat()
        row["horizons"]["6"].update(at=far_later, publication_at=far_later)

    with pytest.raises(ValueError, match="window|horizon"):
        _reveal(tmp_path, setup, request, {"fixture-feed": _feed(late)})


def test_concurrent_identical_reveal_returns_one_receipt(tmp_path):
    from src.kb_runtime.historical_reveal import MarketFeedAdapter, reveal_historical_outcomes

    setup, _, _, request = _setup(tmp_path)
    barrier = Barrier(2)

    def fetch(view):
        barrier.wait(timeout=5)
        return _row(view)

    adapter = MarketFeedAdapter("fixture-feed", "v1", b"feed-v1",
                                "SYNTHETIC_FIXTURE", "REVIEWED_RESEARCH_USE",
                                "reviewer-3", fetch)
    request_path = _write(tmp_path / "reveal-request.json", request)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(reveal_historical_outcomes, request_path,
                               state_dir=setup[0][1],
                               feed_registry={"fixture-feed": adapter}) for _ in range(2)]
        first, second = [future.result(timeout=10) for future in futures]
    assert first == second


def test_changed_same_reveal_id_conflicts(tmp_path):
    setup, _, _, request = _setup(tmp_path)
    _reveal(tmp_path, setup, request, {"fixture-feed": _feed()})
    request["execution_lag_days"] = 2
    with pytest.raises(ValueError, match="existing|differs"):
        _reveal(tmp_path, setup, request, {"fixture-feed": _feed()})


def test_malformed_rehashed_score_rows_fail_closed(tmp_path):
    from src.kb_runtime.case_snapshot import _digest

    setup, _, _, request = _setup(tmp_path)
    path = setup[0][1] / "historical_evaluation/scores/score-1.json"
    score = json.loads(path.read_text())
    score["scores"] = [[]]
    score["score_digest"] = _digest({key: value for key, value in score.items()
                                      if key != "score_digest"})
    _write(path, score)
    request["score_digest"] = score["score_digest"]
    with pytest.raises(ValueError, match="score"):
        _reveal(tmp_path, setup, request, {"fixture-feed": _feed()})


@pytest.mark.parametrize("mutate", [
    lambda row, view: row["reference"]["sector_membership"].update(isin="INE030A01027"),
    lambda row, view: row["reference"]["sector_membership"].update(
        valid_to="2020-12-31T00:00:00+05:30"),
    lambda row, view: row["reference"]["benchmark_composition"].update(
        effective_from="2027-01-01T00:00:00+05:30"),
    lambda row, view: row["reference"]["benchmark_composition"].update(
        publication_at="2027-01-01T00:00:00+05:30"),
    lambda row, view: row["reference"]["benchmark_methodology"].update(
        observed_at="2027-01-01T00:00:00+05:30"),
    lambda row, view: row["reference"]["benchmark_methodology"].update(
        return_kind="PRICE_RETURN"),
    lambda row, view: row["reference"]["benchmark_methodology"].update(
        benchmark_id="NIFTY_NEXT_50"),
    lambda row, view: row["reference"]["sector_methodology"].update(
        sector_id="IT"),
    lambda row, view: row["reference"].pop("sector_methodology"),
])
def test_future_stale_wrong_or_missing_reference_blocks_reveal(tmp_path, mutate):
    setup, _, _, request = _setup(tmp_path)
    with pytest.raises(ValueError, match="reference|membership|composition|methodology"):
        _reveal(tmp_path, setup, request, {"fixture-feed": _feed(mutate)})
    assert not (setup[0][1] / "historical_evaluation/reveals/reveal-1.json").exists()


def test_source_hash_must_match_raw_canonical_observation(tmp_path):
    setup, _, _, request = _setup(tmp_path)
    with pytest.raises(ValueError, match="source"):
        _reveal(tmp_path, setup, request, {"fixture-feed": _feed(
            lambda row, view: row["horizons"]["12"].update(exit_price="999"),
            reseal=False)})


@pytest.mark.parametrize("reason", ["NO_PRICE_OBSERVATION", "NO_ACTION_DATA",
                                    "NO_DELISTING_DATA", "NO_BENCHMARK_OBSERVATION",
                                    "NO_DATA_RIGHTS"])
def test_explicit_unavailable_horizon_counts_missing(tmp_path, reason):
    setup, _, _, request = _setup(tmp_path)

    def unavailable(row, view):
        record = {"availability": "MISSING", "reason": reason,
                  "as_of": row["horizons"]["12"]["at"],
                  "publication_at": row["horizons"]["12"]["at"],
                  "rights": "REVIEWED_RESEARCH_USE"}
        source = json.dumps(record, sort_keys=True, separators=(",", ":"))
        record["source_json"] = source
        record["source_sha256"] = hashlib.sha256(source.encode()).hexdigest()
        row["horizons"]["12"] = record

    result = _reveal(tmp_path, setup, request, {"fixture-feed": _feed(unavailable)})
    assert result["observations"][0]["horizons"]["12"]["reason"] == reason
    assert result["horizon_counts"]["12"] == {"eligible": 0, "missing": 1}


def test_malformed_unavailable_claim_rejected(tmp_path):
    setup, _, _, request = _setup(tmp_path)
    with pytest.raises(ValueError):
        _reveal(tmp_path, setup, request, {"fixture-feed": _feed(
            lambda row, view: row["horizons"].update({"12": {
                "availability": "MISSING", "reason": "NO_PRICE_OBSERVATION"}}))})
