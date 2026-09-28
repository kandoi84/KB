"""Diagnostic trust reporting from frozen observation receipts."""

import json
import inspect
from datetime import datetime, timedelta, timezone

import pytest

from src.kb_runtime.gap_attempt import _sealed
from src.kb_runtime.trust_report import build_trust_report
from src.kb_runtime import case_snapshot, historical_cohort, historical_score
from test_trust_observation import call, fixture


def observations(tmp_path, count=1):
    data = fixture(tmp_path)
    first = call(data)
    state = data[1]
    ids = []
    for index in range(count):
        row = {key: value for key, value in first.items() if key != "observation_digest"}
        row["observation_id"] = f"sample-{index}"
        row["attempt_id"] = f"attempt-{index}"
        row["attempt_intent_id"] = f"intent-{index}"
        row["attempt_result_id"] = f"result-{index}"
        row["entity"] = f"ISSUER-{index % 5}"
        row["reporting_period"] = "2026-Q2" if index % 2 else "2026-Q1"
        row["attempted_at"] = (datetime.fromisoformat(row["adjudicated_at"])
                               - timedelta(hours=index + 1)).isoformat()
        receipt = _sealed(row, "observation_digest")
        (state / "trust_observations" / f"sample-{index}.json").write_text(
            json.dumps(receipt), encoding="utf-8")
        ids.append(f"sample-{index}")
    return state, ids


def test_empty_cohort_has_no_estimate_and_no_score(tmp_path):
    report = build_trust_report([], {}, tmp_path, "empty")
    assert report["sample_status"] == "INSUFFICIENT_SAMPLE"
    assert report["included_count"] == 0
    assert report["metrics"] == {}
    assert report["probability_calibration"] == "NOT_CALIBRATABLE"
    assert report["acquisition_lag"]["status"] == "NO_ESTIMATE"
    assert not any(key in report for key in (
        "poker_score", "fair_value", "publication_allowed", "promotion_score"))


def test_subthreshold_synthetic_sample_is_diagnostic(tmp_path):
    state, ids = observations(tmp_path, 2)
    report = build_trust_report(ids, {}, state, "few")
    assert report["sample_status"] == "INSUFFICIENT_SAMPLE"
    assert report["included_count"] == 2
    metric = report["metrics"]["source_identity"]
    assert metric["pass"] == 2
    assert metric["denominator"] == 2
    assert metric["rate"] == 1.0
    assert metric["ci95"][0] == pytest.approx(0.34238, abs=1e-4)
    assert report["adjudication_lag_seconds"]["median"] > 0


def test_thirty_synthetic_attempts_do_not_pass_real_sample_gate(tmp_path):
    state, ids = observations(tmp_path, 30)
    report = build_trust_report(ids, {}, state, "thirty")
    assert report["sample_counts"] == {
        "attempts": 30, "issuers": 5, "reporting_periods": 2,
        "verified_real_attempts": 0,
    }
    assert report["volume_gate_met"] is True
    assert report["sample_status"] == "INSUFFICIENT_SAMPLE"
    assert "UNVERIFIED_REAL_ORIGIN" in report["sample_reasons"]
    assert report["strata"][0]["breakdowns"]["issuer"] == {
        f"ISSUER-{index}": 6 for index in range(5)}
    assert report["strata"][0]["breakdowns"]["reporting_period"] == {
        "2026-Q1": 15, "2026-Q2": 15}


def test_unresolved_labels_and_blocked_attempts_have_separate_counts(tmp_path):
    state, ids = observations(tmp_path, 2)
    path = state / "trust_observations/sample-1.json"
    row = json.loads(path.read_text())
    row["labels"]["source_identity"] = "UNRESOLVED"
    row["labels"]["usable_document"] = "NOT_APPLICABLE"
    row["labels"]["raw_replay"] = "NOT_APPLICABLE"
    row["attempt_status"] = "RIGHTS_BLOCKED"
    row["failure_class"] = "PERMISSION"
    row["raw_sha256"] = None
    path.write_text(json.dumps(_sealed({k: v for k, v in row.items()
                                        if k != "observation_digest"},
                                       "observation_digest")), encoding="utf-8")
    report = build_trust_report(ids, {}, state, "labels")
    assert report["metrics"]["source_identity"]["unresolved"] == 1
    assert report["metrics"]["source_identity"]["denominator"] == 1
    assert report["metrics"]["usable_document"]["not_applicable"] == 1
    assert report["failure_classes"]["PERMISSION"] == 1
    assert report["attempt_statuses"]["RIGHTS_BLOCKED"] == 1


def test_actual_blocked_attempt_is_reportable_without_raw_hash(tmp_path):
    data = fixture(tmp_path, "INTERNAL_RESEARCH")
    row = json.loads(data[2].read_text())
    row["labels"] = {name: "NOT_APPLICABLE" for name in row["labels"]}
    row["failure_class"] = "HUMAN_WORK"
    data[2].write_text(json.dumps(row), encoding="utf-8")
    observation = call(data)
    assert observation["raw_sha256"] is None
    report = build_trust_report(["obs-one"], {}, data[1], "blocked")
    assert report["attempt_statuses"] == {"HUMAN_WORK_REQUIRED": 1}
    assert report["metrics"]["raw_replay"]["status"] == "NO_ESTIMATE"


def test_duplicate_attempt_and_tampered_observation_fail(tmp_path):
    state, ids = observations(tmp_path, 2)
    path = state / "trust_observations/sample-1.json"
    row = json.loads(path.read_text())
    row["attempt_id"] = "attempt-0"
    path.write_text(json.dumps(_sealed({k: v for k, v in row.items()
                                        if k != "observation_digest"},
                                       "observation_digest")), encoding="utf-8")
    with pytest.raises(ValueError):
        build_trust_report(ids, {}, state, "duplicate")
    row["attempt_id"] = "attempt-1"
    row["labels"]["source_identity"] = "FAIL"
    path.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError):
        build_trust_report(ids, {}, state, "tampered")


def test_adapter_version_and_rights_policy_are_separate_strata(tmp_path):
    state, ids = observations(tmp_path, 3)
    for suffix, field, value in ((1, "adapter_version", 2),
                                 (2, "rights_policy_hash", "f" * 64)):
        path = state / f"trust_observations/sample-{suffix}.json"
        row = json.loads(path.read_text())
        row[field] = value
        path.write_text(json.dumps(_sealed({k: v for k, v in row.items()
                                            if k != "observation_digest"},
                                           "observation_digest")), encoding="utf-8")
    report = build_trust_report(ids, {}, state, "split")
    assert report["sample_status"] == "INSUFFICIENT_SAMPLE"
    assert len(report["strata"]) == 3
    assert sorted(part["count"] for part in report["strata"]) == [1, 1, 1]
    assert report["metrics"] == {}


def test_attempt_date_range_uses_instants_across_offsets(tmp_path):
    state, ids = observations(tmp_path, 2)
    now = datetime.now(timezone.utc)
    earlier, later = now - timedelta(hours=4), now - timedelta(hours=3)
    for suffix, instant, offset in ((0, earlier, 14), (1, later, -10)):
        path = state / f"trust_observations/sample-{suffix}.json"
        row = json.loads(path.read_text())
        row["attempted_at"] = instant.astimezone(timezone(timedelta(hours=offset))).isoformat()
        path.write_text(json.dumps(_sealed({k: v for k, v in row.items()
                                            if k != "observation_digest"},
                                           "observation_digest")), encoding="utf-8")
    report = build_trust_report(ids, {}, state, "offsets")
    assert report["strata"][0]["attempt_date_range"] == [
        earlier.isoformat(), later.isoformat()]


def test_filter_counts_exclusions_and_write_once(tmp_path):
    state, ids = observations(tmp_path, 2)
    report = build_trust_report(ids, {"reporting_period": "2026-Q1"}, state, "filtered")
    assert report["included_count"] == 1
    assert report["excluded_count"] == 1
    assert report["selection"] == {"method": "EXPLICIT_IDS", "seed": None,
                                   "population_count": 2,
                                   "population_scope": "PROVIDED_IDS_ONLY",
                                   "excluded_ids": ["sample-1"]}
    assert build_trust_report(ids, {"reporting_period": "2026-Q1"}, state, "filtered") == report
    with pytest.raises(ValueError):
        build_trust_report(ids, {}, state, "filtered")


def test_rehashed_fake_real_origin_is_rejected(tmp_path):
    state, ids = observations(tmp_path)
    path = state / "trust_observations/sample-0.json"
    row = json.loads(path.read_text())
    row["origin"] = "REAL_OBSERVED"
    path.write_text(json.dumps(_sealed({k: v for k, v in row.items()
                                        if k != "observation_digest"},
                                       "observation_digest")), encoding="utf-8")
    with pytest.raises(ValueError):
        build_trust_report(ids, {}, state, "fake-real")


def test_investment_entry_points_have_no_trust_report_dependency():
    for module in (case_snapshot, historical_cohort, historical_score):
        code = inspect.getsource(module)
        assert "trust_report" not in code
        assert "trust_observations" not in code
