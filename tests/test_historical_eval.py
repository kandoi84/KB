"""Historical investment evaluation reports never authorize promotion."""

import json

import pytest

from test_case_snapshot import _write
from test_historical_reveal import _feed, _reveal, _setup
from src.kb_runtime.historical_eval import evaluate_historical_cohort


def _report_fixture(tmp_path, dataset_kind="SYNTHETIC_FIXTURE", missing_36=False):
    setup, cohort, score, reveal_request = _setup(tmp_path, dataset_kind)
    registry = {} if dataset_kind == "REVIEWED_REAL" else {
        "fixture-feed": _feed(lambda row, view: row["horizons"].update({"36": None})
                              if missing_36 else None)}
    reveal = _reveal(tmp_path, setup, reveal_request, registry)
    request = {
        "report_id": "evaluation-1", "cohort_id": cohort["cohort_id"],
        "cohort_digest": cohort["cohort_digest"],
        "score_run_id": score["run_id"], "score_digest": score["score_digest"],
        "repeat_score_run_id": None, "repeat_score_digest": None,
        "reveal_run_id": reveal["run_id"], "reveal_digest": reveal["reveal_digest"],
        "rubric_version": cohort["rubric_version"],
        "thresholds": {"minimum_snapshots": 100, "repeatability_median_max": "3",
                       "factor_agreement_min": "0.80", "maximum_lookahead_violations": 0,
                       "minimum_quintile_spread": "0", "minimum_top_five_beat_rate": "0",
                       "maximum_brier_score": "0.25"},
        "baseline_receipts": [],
    }
    state = setup[0][1]
    return state, cohort, score, reveal, request


def _run(tmp_path, state, request):
    return evaluate_historical_cohort(_write(tmp_path / "report-request.json", request),
                                      state_dir=state)


def test_current_real_runtime_is_blocked_with_no_fabricated_performance(tmp_path):
    state, cohort, score, reveal, request = _report_fixture(tmp_path, "REVIEWED_REAL")
    result = _run(tmp_path, state, request)
    assert result["report_status"] == "BLOCKED"
    assert result["dataset_kind"] == "REVIEWED_REAL"
    assert "NO_REVIEWED_SCORER" in result["blockers"]
    assert "NO_REVIEWED_MARKET_FEED" in result["blockers"]
    assert "INDEPENDENT_SEAL_MISSING" in result["blockers"]
    assert result["measures"]["ranking_12m"]["status"] == "NOT_EVALUABLE"
    assert all(result[key] is False for key in
               ("publication_allowed", "live_decision_allowed", "promotion_allowed"))


def test_synthetic_mechanics_reports_all_horizon_denominators_and_missing(tmp_path):
    state, _, _, _, request = _report_fixture(tmp_path, missing_36=True)
    result = _run(tmp_path, state, request)
    assert result["report_status"] == "MECHANICS_ONLY"
    assert result["snapshot_count"] == 1
    assert result["measures"]["horizon_12m"]["denominator"] == 1
    assert result["measures"]["horizon_12m"]["missing"] == 0
    assert result["measures"]["horizon_36m"]["denominator"] == 0
    assert result["measures"]["horizon_36m"]["missing"] == 1
    assert result["measures"]["horizon_36m"]["status"] == "NOT_EVALUABLE"
    assert result["measures"]["repeatability"]["status"] == "NOT_EVALUABLE"
    assert result["measures"]["calibration_brier"]["status"] == "NOT_EVALUABLE"
    assert set(result["baselines"]) == {
        "EQUAL_WEIGHT_NIFTY_50", "SECTOR_ADJUSTED_EQUAL_WEIGHT",
        "LOWEST_PE_OR_HIGHEST_FCF", "EARNINGS_REVISION_ONLY",
        "QUALITY_PLUS_VALUATION"}
    assert all(value["status"] == "BASELINE_NOT_EVALUABLE"
               for value in result["baselines"].values())
    assert _run(tmp_path, state, request) == result


def test_swapped_reveal_digest_and_changed_same_report_id_fail(tmp_path):
    state, _, _, _, request = _report_fixture(tmp_path)
    request["reveal_digest"] = "0" * 64
    with pytest.raises(ValueError, match="reveal|digest"):
        _run(tmp_path, state, request)
    request["reveal_digest"] = json.loads(
        (state / "historical_evaluation/reveals/reveal-1.json").read_text())["reveal_digest"]
    _run(tmp_path, state, request)
    request["thresholds"]["minimum_snapshots"] = 101
    with pytest.raises(ValueError, match="existing|report"):
        _run(tmp_path, state, request)


def test_weak_thresholds_and_unknown_code_field_fail(tmp_path):
    state, _, _, _, request = _report_fixture(tmp_path)
    request["thresholds"]["maximum_lookahead_violations"] = 1
    with pytest.raises(ValueError, match="threshold|lookahead"):
        _run(tmp_path, state, request)
    request["thresholds"]["maximum_lookahead_violations"] = 0
    request["command"] = "activate model"
    with pytest.raises(ValueError, match="fields"):
        _run(tmp_path, state, request)


def test_damaged_rehashed_reveal_counts_fail_closed(tmp_path):
    from src.kb_runtime.case_snapshot import _digest

    state, _, _, _, request = _report_fixture(tmp_path)
    path = state / "historical_evaluation/reveals/reveal-1.json"
    receipt = json.loads(path.read_text())
    receipt["horizon_counts"]["12"]["eligible"] = 99
    receipt["reveal_digest"] = _digest({key: value for key, value in receipt.items()
                                         if key != "reveal_digest"})
    _write(path, receipt)
    request["reveal_digest"] = receipt["reveal_digest"]
    with pytest.raises(ValueError, match="reveal|count"):
        _run(tmp_path, state, request)
