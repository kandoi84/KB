"""Synthetic sandbox-case contracts over real evidence and analysis artifacts."""

import hashlib
import json
from pathlib import Path

import pytest

from test_analysis_judgment import setup as analysis_setup
from src.kb_runtime.analysis_judgment import analyze_judgment
from src.kb_runtime.evidence_workflow import run_evidence_workflow


CONTRACT = (Path(__file__).resolve().parents[1] /
            "projects/indian-equities/config/runtime_contracts/evidence_review.v1.json")
INPUTS = ("source_request", "claim_request", "passage_packet", "review_packet",
          "workflow_contract", "claim_review_report", "analysis_packet", "analysis_report")


def _write(path, value):
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return path


def _fixture(tmp_path):
    project, state, catalog, _, analysis_packet, worksheet, model = analysis_setup(tmp_path)
    paths = {
        "source_request": tmp_path / "sources.json",
        "claim_request": tmp_path / "claims.json",
        "passage_packet": tmp_path / "passages.json",
        "review_packet": tmp_path / "review.json",
        "workflow_contract": CONTRACT,
        "claim_review_report": state / "claim_review_runs/flow-1.json",
        "analysis_packet": analysis_packet,
        "analysis_report": state / "analysis_runs/analysis-1.json",
    }
    args = (paths["source_request"], paths["claim_request"], paths["passage_packet"],
            None, CONTRACT, project, catalog, state, "flow-1")
    awaiting = run_evidence_workflow(*args)
    assert awaiting["status"] == "AWAITING_REVIEW"
    review = json.loads(paths["review_packet"].read_text())
    review["claim_report_id"] = awaiting["stages"][0]["child_ids"]["claim_report_id"]
    review["passage_report_id"] = awaiting["stages"][1]["output_id"]
    _write(paths["review_packet"], review)
    complete = run_evidence_workflow(*args[:3], paths["review_packet"], *args[4:])
    claim_review = json.loads(paths["claim_review_report"].read_text())
    worksheet["claim_review_report_id"] = claim_review["report_id"]
    _write(analysis_packet, worksheet)
    analysis = analyze_judgment(analysis_packet, paths["claim_review_report"],
                                project, catalog, state, "analysis-1")
    assert complete["status"] == "COMPLETE"
    assert analysis["analysis_status"] == "CALCULATED_MODEL_UNVERIFIED"
    packet = {
        "case_id": "case-1", "workflow_run_id": "flow-1", "analysis_run_id": "analysis-1",
        "issuer_id": "SBI", "isin": "INE062A01020",
        "cutoff_timestamp": "2026-09-28T18:00:00+05:30", "mode": "SANDBOX",
        "opened_at": "2026-09-29T09:00:00+05:30", "previous_case_id": None,
        "input_sha256": {key: hashlib.sha256(path.read_bytes()).hexdigest()
                         for key, path in paths.items()},
        "hypothesis": "Deposit growth sustains lending through the next review period",
        "rationale_claim_ids": ["growth"], "rationale_metric_ids": ["M1"],
        "outcome": {"metric_name": "revenue", "unit": "INR_CRORE",
                    "comparison": "AT_LEAST", "target_decimal": "13",
                    "target_kind": "ANALYST_HYPOTHESIS", "period_end": "2027-06-30",
                    "due_at": "2027-07-15T18:00:00+05:30"},
    }
    packet_path = _write(tmp_path / "case.json", packet)
    return project, state, catalog, paths, packet_path, packet, model


def _open(data):
    from src.kb_runtime.case_snapshot import open_sandbox_case

    project, state, catalog, paths, packet_path, _, _ = data
    return open_sandbox_case(packet_path, project_dir=project, catalog=catalog,
                             state_dir=state, **paths)


def test_case_opens_only_from_matching_completed_parents(tmp_path):
    data = _fixture(tmp_path)
    result = _open(data)
    assert result["case_status"] == "SANDBOX_OPEN"
    assert result["timing_class"] == "HISTORICAL_RECONSTRUCTION"
    assert result["publication_allowed"] is False
    assert result["live_decision_allowed"] is False
    assert result["promotion_status"] == "NOT_EVALUATED"
    workflow = json.loads((data[1] / "workflow_runs/flow-1/state.json").read_text())
    assert workflow["publication_allowed"] is False
    assert result["fair_value"]["value_decimal"] == "105.00"
    assert result["fair_value"]["value_kind"] == "ANALYST_ESTIMATE"
    assert result["fair_value"]["model_status"] == "MODEL_UNVERIFIED"
    case_path = data[1] / "cases/case-1.json"
    before = case_path.read_bytes()
    assert _open(data) == result
    assert case_path.read_bytes() == before


def test_local_calendar_day_marks_historical_reconstruction(tmp_path):
    data = _fixture(tmp_path)
    packet = data[5]
    packet["opened_at"] = "2026-09-29T00:30:00+05:30"
    _write(data[4], packet)
    assert _open(data)["timing_class"] == "HISTORICAL_RECONSTRUCTION"


def test_parent_symlink_outside_state_root_is_rejected(tmp_path):
    data = _fixture(tmp_path)
    target = tmp_path / "outside-analysis.json"
    report = data[3]["analysis_report"]
    target.write_bytes(report.read_bytes())
    report.unlink()
    report.symlink_to(target)
    with pytest.raises(ValueError, match="path|root"):
        _open(data)
    assert not (data[1] / "cases/case-1.json").exists()


def test_previous_case_id_may_be_omitted(tmp_path):
    data = _fixture(tmp_path)
    data[5].pop("previous_case_id")
    _write(data[4], data[5])
    assert _open(data)["previous_case_id"] is None


def test_case_directory_symlink_outside_state_root_is_rejected(tmp_path):
    data = _fixture(tmp_path)
    outside = tmp_path / "outside-cases"
    outside.mkdir()
    (data[1] / "cases").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="path|root"):
        _open(data)
    assert not list(outside.iterdir())


def test_compact_date_is_not_an_iso_period_end(tmp_path):
    data = _fixture(tmp_path)
    data[5]["outcome"]["period_end"] = "20270630"
    _write(data[4], data[5])
    with pytest.raises(ValueError, match="period"):
        _open(data)
    assert not (data[1] / "cases/case-1.json").exists()


@pytest.mark.parametrize("path,value", [
    (("outcome",), []),
    (("outcome", "comparison"), []),
    (("outcome", "period_end"), []),
    (("outcome", "due_at"), {}),
    (("outcome", "target_decimal"), {}),
    (("rationale_claim_ids",), ["growth", {}]),
    (("input_sha256",), []),
    (("opened_at",), []),
    (("previous_case_id",), []),
])
def test_malformed_nested_packet_is_value_error_without_case(tmp_path, path, value):
    data = _fixture(tmp_path)
    target = data[5]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    _write(data[4], data[5])
    with pytest.raises(ValueError):
        _open(data)
    assert not (data[1] / "cases/case-1.json").exists()


def test_changed_same_id_and_tampered_old_case_cannot_replay(tmp_path):
    data = _fixture(tmp_path)
    original = _open(data)
    path = data[1] / "cases/case-1.json"
    original_bytes = path.read_bytes()
    data[5]["hypothesis"] = "Deposit growth weakens lending through the next review period"
    _write(data[4], data[5])
    with pytest.raises(ValueError, match="existing case"):
        _open(data)
    assert path.read_bytes() == original_bytes
    _write(data[4], {**data[5], "hypothesis": original["hypothesis"]})
    forged = json.loads(path.read_text())
    forged["publication_allowed"] = True
    forged["case_digest"] = hashlib.sha256(json.dumps(
        {key: value for key, value in forged.items() if key != "case_digest"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    _write(path, forged)
    with pytest.raises(ValueError, match="existing case"):
        _open(data)


def test_changed_model_bytes_block_case_opening(tmp_path):
    data = _fixture(tmp_path)
    data[6].write_text("changed model assumptions")
    with pytest.raises(ValueError, match="model"):
        _open(data)
    assert not (data[1] / "cases/case-1.json").exists()


def test_changed_workflow_input_blocks_case_opening(tmp_path):
    data = _fixture(tmp_path)
    source = data[3]["source_request"]
    request = json.loads(source.read_text())
    request["required_sources"][0]["max_age_days"] = 61
    _write(source, request)
    with pytest.raises(ValueError, match="bytes differ"):
        _open(data)
    assert not (data[1] / "cases/case-1.json").exists()


def test_workflow_publication_flag_blocks_case_opening(tmp_path):
    data = _fixture(tmp_path)
    state_path = data[1] / "workflow_runs/flow-1/state.json"
    state = json.loads(state_path.read_text())
    state["publication_allowed"] = True
    _write(state_path, state)
    with pytest.raises(ValueError, match="workflow"):
        _open(data)
    assert not (data[1] / "cases/case-1.json").exists()


def test_unsupported_claim_and_poker_label_block_case(tmp_path):
    data = _fixture(tmp_path)
    data[5]["rationale_claim_ids"] = ["unreviewed"]
    _write(data[4], data[5])
    with pytest.raises(ValueError, match="unavailable"):
        _open(data)
    data[5]["rationale_claim_ids"] = ["growth"]
    data[5]["poker"] = {"status": "ASSESSED", "hand": "PAIR", "draw": None}
    _write(data[4], data[5])
    with pytest.raises(ValueError, match="poker"):
        _open(data)
    assert not (data[1] / "cases/case-1.json").exists()


def test_mixed_cutoff_blocks_case_before_write(tmp_path):
    data = _fixture(tmp_path)
    data[5]["cutoff_timestamp"] = "2026-09-28T17:00:00+05:30"
    _write(data[4], data[5])
    with pytest.raises(ValueError, match="workflow|cross-bound"):
        _open(data)
    assert not (data[1] / "cases/case-1.json").exists()


def test_new_case_links_intact_prior_case_without_editing_it(tmp_path):
    data = _fixture(tmp_path)
    first = _open(data)
    first_path = data[1] / "cases/case-1.json"
    first_bytes = first_path.read_bytes()
    data[5]["case_id"] = "case-2"
    data[5]["previous_case_id"] = "case-1"
    data[5]["opened_at"] = "2026-09-30T09:00:00+05:30"
    _write(data[4], data[5])
    second = _open(data)
    assert second["previous_case_digest"] == first["case_digest"]
    assert first_path.read_bytes() == first_bytes
    first_path.write_text("{}")
    with pytest.raises(ValueError, match="previous case"):
        _open(data)


def test_rehashed_minimal_fake_prior_case_cannot_enter_chain(tmp_path):
    data = _fixture(tmp_path)
    fake = {"case_id": "case-fake", "issuer_id": "SBI", "isin": "INE062A01020",
            "cutoff_timestamp": "2026-09-27T18:00:00+05:30",
            "opened_at": "2026-09-28T09:00:00+05:30",
            "publication_allowed": False, "live_decision_allowed": False,
            "promotion_status": "NOT_EVALUATED"}
    fake["case_digest"] = hashlib.sha256(json.dumps(fake, sort_keys=True,
        separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    folder = data[1] / "cases"
    folder.mkdir()
    _write(folder / "case-fake.json", fake)
    data[5]["case_id"] = "case-2"
    data[5]["previous_case_id"] = "case-fake"
    _write(data[4], data[5])
    with pytest.raises(ValueError, match="previous case"):
        _open(data)
    assert not (folder / "case-2.json").exists()


@pytest.mark.parametrize("field,value", [
    ("case_status", "PUBLISHED"),
    ("claim_review_report_id", "missing-parent"),
    ("input_sha256", {}),
    ("prediction", {}),
    ("publication_allowed", True),
    ("fair_value", {}),
])
def test_rehashed_malformed_prior_case_cannot_enter_chain(tmp_path, field, value):
    data = _fixture(tmp_path)
    _open(data)
    previous_path = data[1] / "cases/case-1.json"
    previous = json.loads(previous_path.read_text())
    previous[field] = value
    previous.pop("case_digest")
    previous["case_digest"] = hashlib.sha256(json.dumps(previous, sort_keys=True,
        separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    _write(previous_path, previous)
    data[5]["case_id"] = "case-2"
    data[5]["previous_case_id"] = "case-1"
    data[5]["opened_at"] = "2026-09-30T09:00:00+05:30"
    _write(data[4], data[5])
    with pytest.raises(ValueError, match="previous case"):
        _open(data)
    assert not (data[1] / "cases/case-2.json").exists()


def test_rehashed_promoted_analysis_parent_cannot_open_case(tmp_path):
    data = _fixture(tmp_path)
    report_path = data[3]["analysis_report"]
    report = json.loads(report_path.read_text())
    report["publication_allowed"] = True
    report["report_id"] = hashlib.sha256(json.dumps(
        {key: value for key, value in report.items() if key != "report_id"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    _write(report_path, report)
    data[5]["input_sha256"]["analysis_report"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
    _write(data[4], data[5])
    with pytest.raises(ValueError, match="blocked|cross-bound"):
        _open(data)
    assert not (data[1] / "cases/case-1.json").exists()


def test_changed_raw_blob_blocks_case_opening(tmp_path):
    data = _fixture(tmp_path)
    registry = data[0] / "data/registry/sources/FILING"
    source_version = json.loads(next(registry.glob("*.json")).read_text())
    blob = data[0] / "data/raw/sha256" / source_version["raw_sha256"]
    blob.write_bytes(b"changed raw filing")
    with pytest.raises(ValueError):
        _open(data)
    assert not (data[1] / "cases/case-1.json").exists()
