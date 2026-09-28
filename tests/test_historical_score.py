"""Score freezing never gives an adapter future observations or authority."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from test_historical_cohort import _register, _setup
from test_case_snapshot import _write


def _fixture(tmp_path, dataset_kind="SYNTHETIC_FIXTURE"):
    setup = _setup(tmp_path, dataset_kind)
    cohort = _register(tmp_path, setup)
    request = {
        "run_id": "score-1", "cohort_id": cohort["cohort_id"],
        "cohort_digest": cohort["cohort_digest"],
        "rubric_version": cohort["rubric_version"],
        "scorer_id": "fixture-scorer", "scorer_version": "v1",
        "scorer_source_sha256": hashlib.sha256(b"fixture-v1").hexdigest(),
        "independent_run_id": "repeat-1", "reviewer_id": "reviewer-2",
    }
    return setup, cohort, request


def _result():
    return {
        "score": "64.00", "factors": {
            "market_structure": "60.00", "economics": "65.00",
            "management": "70.00", "valuation": "55.00",
            "catalysts": "70.00"},
        "error_band": {"lower": "60.00", "upper": "68.00"},
        "catalyst_forecasts": [{"catalyst_id": "cat-1", "probability": "0.60",
                                 "due_at": "2027-07-15T18:00:00+05:30"}],
        "fair_value": {"value_decimal": "105.00", "unit": "INR_PER_SHARE"},
    }


def _adapter(seen=None):
    from src.kb_runtime.historical_score import ScoreAdapter

    def score(view):
        if seen is not None:
            seen.append(view)
        return _result()

    return ScoreAdapter("fixture-scorer", "v1", b"fixture-v1", "SYNTHETIC_FIXTURE", score)


def _freeze(tmp_path, setup, request, registry):
    from src.kb_runtime.historical_score import freeze_historical_scores

    return freeze_historical_scores(_write(tmp_path / "score-request.json", request),
                                    state_dir=setup[0][1], scorer_registry=registry)


def test_real_current_runtime_blocks_without_scorer(tmp_path):
    setup, cohort, request = _fixture(tmp_path, "REVIEWED_REAL")
    result = _freeze(tmp_path, setup, request, {})
    assert result["score_status"] == "BLOCKED_NO_SCORER"
    assert result["scores"] == []
    assert "NO_REVIEWED_SCORER" in result["blockers"]
    assert result["publication_allowed"] is False
    assert result["live_decision_allowed"] is False
    assert result["promotion_allowed"] is False
    assert _freeze(tmp_path, setup, request, {}) == result


def test_synthetic_adapter_gets_only_isolated_cutoff_view_and_freezes(tmp_path):
    setup, cohort, request = _fixture(tmp_path)
    seen = []
    result = _freeze(tmp_path, setup, request, {"fixture-scorer": _adapter(seen)})
    assert result["score_status"] == "MECHANICS_ONLY"
    assert result["scores"][0]["score"] == "64.00"
    assert result["scores"][0]["case_digest"] == cohort["cases"][0]["case_digest"]
    assert all(result[key] is False for key in
               ("publication_allowed", "live_decision_allowed", "promotion_allowed"))
    assert len(seen) == 1
    view = seen[0]
    assert set(view) == {"case_id", "case_digest", "isin", "cutoff_timestamp",
                         "hypothesis", "rationale_claim_ids", "rationale_metric_ids",
                         "forecast"}
    assert not any(word in str(view).lower() for word in
                   ("outcome_path", "market_price", "state_dir", "benchmark"))
    with pytest.raises(TypeError):
        view["isin"] = "INE030A01027"
    assert _freeze(tmp_path, setup, request,
                   {"fixture-scorer": _adapter()}) == result


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(code="print('unsafe')"),
    lambda r: r.update(command="python scorer.py"),
    lambda r: r.update(outcome_path="future.json"),
    lambda r: r.update(scorer_source_sha256="b" * 64),
    lambda r: r.update(independent_run_id=r["run_id"]),
    lambda r: r.update(cohort_digest="c" * 64),
    lambda r: r.update(scorer_id=[]),
])
def test_request_rejects_code_future_input_bad_identity_or_repeat(tmp_path, mutation):
    setup, _, request = _fixture(tmp_path)
    mutation(request)
    with pytest.raises(ValueError):
        _freeze(tmp_path, setup, request, {"fixture-scorer": _adapter()})


def test_test_adapter_cannot_score_real_reviewed_cohort(tmp_path):
    setup, _, request = _fixture(tmp_path, "REVIEWED_REAL")
    result = _freeze(tmp_path, setup, request, {"fixture-scorer": _adapter()})
    assert result["score_status"] == "BLOCKED_NO_SCORER"
    assert result["scores"] == []
    assert result["promotion_allowed"] is False


def test_changed_same_run_id_conflicts(tmp_path):
    setup, _, request = _fixture(tmp_path)
    _freeze(tmp_path, setup, request, {"fixture-scorer": _adapter()})
    request["independent_run_id"] = "repeat-2"
    with pytest.raises(ValueError, match="existing|differs"):
        _freeze(tmp_path, setup, request, {"fixture-scorer": _adapter()})


def test_two_declared_repeats_are_separate_receipts_with_same_fixture_score(tmp_path):
    setup, _, request = _fixture(tmp_path)
    first = _freeze(tmp_path, setup, request, {"fixture-scorer": _adapter()})
    request["run_id"] = "score-2"
    request["independent_run_id"] = "repeat-2"
    second = _freeze(tmp_path, setup, request, {"fixture-scorer": _adapter()})
    assert first["scores"] == second["scores"]
    assert first["score_digest"] != second["score_digest"]
    assert first["repeat_status"] == second["repeat_status"] == "NOT_VERIFIED"


def test_case_changed_after_cohort_cannot_be_scored(tmp_path):
    setup, _, request = _fixture(tmp_path)
    case_path = setup[0][1] / "cases/case-1.json"
    case = json.loads(case_path.read_text())
    case["hypothesis"] = "A later rewritten hypothesis using future facts"
    case["case_digest"] = hashlib.sha256(json.dumps(
        {key: value for key, value in case.items() if key != "case_digest"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    _write(case_path, case)
    with pytest.raises(ValueError, match="case"):
        _freeze(tmp_path, setup, request, {"fixture-scorer": _adapter()})


def test_existing_score_retry_rechecks_frozen_case(tmp_path):
    setup, _, request = _fixture(tmp_path)
    _freeze(tmp_path, setup, request, {"fixture-scorer": _adapter()})
    case_path = setup[0][1] / "cases/case-1.json"
    case = json.loads(case_path.read_text())
    case["hypothesis"] = "A later rewritten hypothesis using future facts"
    case["case_digest"] = hashlib.sha256(json.dumps(
        {key: value for key, value in case.items() if key != "case_digest"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    _write(case_path, case)
    with pytest.raises(ValueError, match="case"):
        _freeze(tmp_path, setup, request, {"fixture-scorer": _adapter()})


def test_case_mutated_during_adapter_execution_blocks_freeze(tmp_path):
    from src.kb_runtime.historical_score import ScoreAdapter

    setup, _, request = _fixture(tmp_path)
    case_path = setup[0][1] / "cases/case-1.json"

    def score(_):
        case = json.loads(case_path.read_text())
        case["hypothesis"] = "A later rewritten hypothesis using future facts"
        case["case_digest"] = hashlib.sha256(json.dumps(
            {key: value for key, value in case.items() if key != "case_digest"},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        _write(case_path, case)
        return _result()

    adapter = ScoreAdapter("fixture-scorer", "v1", b"fixture-v1",
                           "SYNTHETIC_FIXTURE", score)
    with pytest.raises(ValueError, match="case"):
        _freeze(tmp_path, setup, request, {"fixture-scorer": adapter})
    assert not (setup[0][1] / "historical_evaluation/scores/score-1.json").exists()


def test_concurrent_identical_score_freeze_returns_one_receipt(tmp_path):
    from src.kb_runtime.historical_score import ScoreAdapter, freeze_historical_scores

    setup, _, request = _fixture(tmp_path)
    barrier = Barrier(2)

    def score(_):
        barrier.wait(timeout=5)
        return _result()

    adapter = ScoreAdapter("fixture-scorer", "v1", b"fixture-v1",
                           "SYNTHETIC_FIXTURE", score)
    request_path = _write(tmp_path / "score-request.json", request)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(freeze_historical_scores, request_path,
                               state_dir=setup[0][1],
                               scorer_registry={"fixture-scorer": adapter}) for _ in range(2)]
        first, second = [future.result(timeout=10) for future in futures]
    assert first == second


@pytest.mark.parametrize("bad", [
    {**_result(), "factors": []},
    {**_result(), "score": "101.00"},
    {**_result(), "error_band": {"lower": "70.00", "upper": "68.00"}},
    {**_result(), "market_price": "123"},
])
def test_malformed_score_is_not_written(tmp_path, bad):
    from src.kb_runtime.historical_score import ScoreAdapter

    setup, _, request = _fixture(tmp_path)
    adapter = ScoreAdapter("fixture-scorer", "v1", b"fixture-v1",
                           "SYNTHETIC_FIXTURE", lambda _: bad)
    with pytest.raises(ValueError):
        _freeze(tmp_path, setup, request, {"fixture-scorer": adapter})
    assert not (setup[0][1] / "historical_evaluation/scores/score-1.json").exists()
