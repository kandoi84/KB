"""Historical cohort receipts replay cases and never imply promotion."""

import hashlib
import json

import pytest

from test_case_snapshot import _fixture, _open, _write
from src.kb_runtime.identity_store import _valid_isin


def _setup(tmp_path, dataset_kind="REVIEWED_REAL"):
    data = _fixture(tmp_path)
    case = _open(data)
    project, state, catalog, paths, packet_path, _, _ = data
    manifest = {
        "cohort_id": "cohort-1", "dataset_kind": dataset_kind,
        "rubric_version": "rubric-v1", "quarter_cutoffs": [case["cutoff_timestamp"]],
        "universe_rule": "All eligible issuers fixed before scoring begins",
        "reviewer_id": "reviewer-1", "reviewed_at": "2026-09-29T10:00:00+05:30",
        "scorer_id": None, "scorer_source_sha256": None,
        "cases": [{"case_id": case["case_id"], "case_digest": case["case_digest"],
                   "isin": case["isin"], "cutoff_timestamp": case["cutoff_timestamp"],
                   "seal_proof": None}],
    }
    inputs = {case["case_id"]: {"case_packet_path": packet_path, **paths}}
    kwargs = dict(state_dir=state, project_dir=project, catalog=catalog,
                  case_replay_inputs=inputs)
    return data, case, manifest, kwargs


def _register(tmp_path, setup):
    from src.kb_runtime.historical_cohort import register_evaluation_cohort

    return register_evaluation_cohort(_write(tmp_path / "cohort.json", setup[2]), **setup[3])


def test_replayed_real_case_stays_blocked_and_exact_retry(tmp_path):
    setup = _setup(tmp_path)
    result = _register(tmp_path, setup)
    assert result["cases"][0]["case_class"] == "REPLAY_ONLY"
    assert "INDEPENDENT_SEAL_MISSING" in result["blockers"]
    assert "QUARTER_UNIVERSE_INCOMPLETE" in result["blockers"]
    assert result["quarter_coverage"][0]["issuer_count"] == 1
    assert result["publication_allowed"] is False
    assert result["live_decision_allowed"] is False
    assert result["promotion_allowed"] is False
    assert "outcome" not in json.dumps(result).lower()
    assert "price" not in json.dumps(result).lower()
    path = setup[0][1] / "historical_evaluation/cohorts/cohort-1.json"
    original = path.read_bytes()
    assert _register(tmp_path, setup) == result
    assert path.read_bytes() == original


def test_synthetic_case_is_mechanics_only_and_changed_id_conflicts(tmp_path):
    setup = _setup(tmp_path, "SYNTHETIC_FIXTURE")
    result = _register(tmp_path, setup)
    assert result["cases"][0]["case_class"] == "SYNTHETIC_FIXTURE"
    assert result["cohort_status"] == "BLOCKED"
    setup[2]["universe_rule"] = "A different later universe chosen after the result"
    with pytest.raises(ValueError, match="existing|cohort"):
        _register(tmp_path, setup)


def test_rehashed_forged_case_and_wrong_issuer_rejected(tmp_path):
    setup = _setup(tmp_path)
    setup[2]["cases"][0]["isin"] = "INE030A01027"
    with pytest.raises(ValueError, match="ISIN|issuer|case"):
        _register(tmp_path, setup)
    setup[2]["cases"][0]["isin"] = setup[1]["isin"]
    path = setup[0][1] / "cases/case-1.json"
    forged = json.loads(path.read_text())
    forged["hypothesis"] = "Later rewritten with different analyst judgment"
    forged["case_digest"] = hashlib.sha256(json.dumps(
        {key: value for key, value in forged.items() if key != "case_digest"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    _write(path, forged)
    with pytest.raises(ValueError, match="case"):
        _register(tmp_path, setup)


@pytest.mark.parametrize("mutation", [
    lambda m: m.update(outcome_path="future.json"),
    lambda m: m["cases"][0].update(seal_proof=[]),
    lambda m: m["cases"][0].update(case_digest=[]),
    lambda m: m["cases"].append(dict(m["cases"][0])),
    lambda m: m.update(quarter_cutoffs=["2026-09-28"]),
    lambda m: m.update(scorer_id="code.py"),
])
def test_manifest_rejects_unknown_malformed_or_duplicate_input(tmp_path, mutation):
    setup = _setup(tmp_path)
    mutation(setup[2])
    with pytest.raises(ValueError):
        _register(tmp_path, setup)


def test_claimed_seal_after_reveal_is_rejected(tmp_path):
    setup = _setup(tmp_path)
    setup[2]["cases"][0]["seal_proof"] = {
        "provider_id": "seal-provider", "seal_id": "seal-1",
        "case_digest": setup[1]["case_digest"],
        "sealed_at": "2027-07-16T10:00:00+05:30",
        "earliest_reveal_at": "2027-07-10T10:00:00+05:30",
        "reviewer_id": "reviewer-1", "reviewed_at": "2027-07-16T11:00:00+05:30",
        "evidence_sha256": "a" * 64,
    }
    with pytest.raises(ValueError, match="seal|reveal"):
        _register(tmp_path, setup)


def _isin(index):
    prefix = "INE" + f"{index:08d}"
    return next(prefix + str(digit) for digit in range(10)
                if _valid_isin(prefix + str(digit)))


@pytest.mark.parametrize("count,eligible", [(29, False), (30, True), (50, True), (51, False)])
def test_distinct_quarter_universe_counts_are_explicit(tmp_path, monkeypatch, count, eligible):
    setup = _setup(tmp_path, "SYNTHETIC_FIXTURE")
    base = setup[2]["cases"][0]
    rows = [{**base, "case_id": f"case-{index}", "isin": _isin(index)}
            for index in range(count)]
    setup[2]["cases"] = rows
    original_inputs = setup[3]["case_replay_inputs"]["case-1"]
    setup[3]["case_replay_inputs"] = {row["case_id"]: original_inputs for row in rows}
    by_id = {row["case_id"]: row for row in rows}

    def fake_replay(path, packet_path, **kwargs):
        row = by_id[path.stem]
        return {**row, "case_status": "SANDBOX_OPEN",
                "publication_allowed": False, "live_decision_allowed": False,
                "promotion_status": "NOT_EVALUATED",
                "timing_class": "HISTORICAL_RECONSTRUCTION",
                "input_sha256": {}}

    monkeypatch.setattr("src.kb_runtime.historical_cohort.verify_frozen_case", fake_replay)
    receipt = _register(tmp_path, setup)
    assert receipt["quarter_coverage"][0]["issuer_count"] == count
    assert receipt["quarter_coverage"][0]["eligible_for_ranking"] is eligible
    assert receipt["cohort_status"] == ("MECHANICS_ONLY" if eligible else "BLOCKED")
    assert receipt["promotion_allowed"] is False


def test_quarter_uses_indian_local_date_not_utc_date():
    from src.kb_runtime.historical_cohort import _quarter

    assert _quarter("2027-04-01T00:30:00+05:30") == "2027-Q2"


def test_cohort_symlink_escape_is_rejected(tmp_path):
    setup = _setup(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (setup[0][1] / "historical_evaluation").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="path|root"):
        _register(tmp_path, setup)
