"""Operating outcomes and process reviews remain source-bound and sandboxed."""

import hashlib
import json

import pytest

from test_case_snapshot import _fixture, _open, _write
from src.kb_runtime.metric_store import register_filing_metrics
from src.kb_runtime.source_store import record_source


def _setup(tmp_path, value="14", kind="REPORTED"):
    data = _fixture(tmp_path)
    case = _open(data)
    project, state, catalog, paths, packet_path, _, _ = data
    metadata = {
        "source_id": "OUTCOME1", "entity": "SBI", "source_kind": "EXCHANGE_FILING",
        "url": "https://example.org/outcome1", "source_date": "2027-07-10",
        "observed_at": "2027-07-10T09:00:00+05:30",
        "retrieved_at": "2027-07-10T09:01:00+05:30",
    }
    raw = tmp_path / "outcome.txt"
    raw.write_text(f"Revenue {value} crore", encoding="utf-8")
    source = record_source(_write(tmp_path / "outcome-source.json", metadata), raw, project)
    request = {
        "filing_id": "OUTF1", "issuer_id": "SBI", "isin": "INE062A01020",
        "source_id": "OUTCOME1", "version_id": source["version_id"],
        "document_type": "RESULTS", "period_end": "2027-06-30",
        "published_at": "2027-07-10T08:00:00+05:30",
        "first_seen_at": "2027-07-10T09:01:00+05:30",
        "rights_status": "REVIEWED", "reviewer_id": "analyst-1",
        "reviewed_at": "2027-07-10T09:02:00+05:30",
        "review_decision": "CONFIRMED", "evidence_locator": "results table",
        "supersedes_filing_id": None,
        "metrics": [{"metric_id": "OUTM1", "metric_name": "revenue",
                     "value_decimal": value, "unit": "INR_CRORE",
                     "period_end": "2027-06-30", "period_kind": "QUARTER",
                     "reporting_scope": "CONSOLIDATED", "value_kind": kind,
                     "evidence_locator": "page 1 table 2", "supersedes_metric_id": None}],
    }
    register_filing_metrics(_write(tmp_path / "outcome-filing.json", request), project, catalog)
    event_packet = {
        "event_id": "event-1", "case_id": "case-1", "case_digest": case["case_digest"],
        "event_type": "OUTCOME_OBSERVED", "metric_id": "OUTM1",
        "observed_at": "2027-07-10T10:00:00+05:30",
        "recorded_at": "2027-07-10T11:00:00+05:30",
        "supersedes_event_id": None,
    }
    kwargs = dict(project_dir=project, catalog=catalog, state_dir=state,
                  case_packet_path=packet_path, case_replay_inputs=paths)
    return data, case, request, event_packet, kwargs


def _append(tmp_path, setup):
    from src.kb_runtime.outcome_postmortem import append_outcome_observation
    return append_outcome_observation(_write(tmp_path / "event.json", setup[3]), **setup[4])


def _due_packet(case, event_id="event-1", process="GOOD_PROCESS", error="NONE",
                reproducible=False):
    return {
        "postmortem_id": "post-1", "case_id": "case-1",
        "case_digest": case["case_digest"],
        "evaluated_at": "2027-07-16T10:00:00+05:30",
        "observation_event_id": event_id,
        "process_review": {
            "reviewer_id": "reviewer-1", "reviewed_at": "2027-07-16T09:00:00+05:30",
            "process_assessment": process,
            "reasoning": "The original evidence and method were reviewed against the cutoff",
            "cited_case_ids": ["case-1"], "cited_claim_ids": ["growth"],
            "cited_metric_ids": ["M1"], "cited_gap_ids": [],
            "error_class": error,
            "error_explanation": "The process fault can be reproduced from the frozen evidence",
            "reproducible_process_failure": reproducible,
            "failure_invariant": ("Do not accept a stale evidence source" if reproducible else None),
        },
    }


def test_append_source_backed_actual_and_exact_retry(tmp_path):
    setup = _setup(tmp_path)
    event = _append(tmp_path, setup)
    assert event["value_decimal"] == "14"
    assert event["metric_id"] == "OUTM1"
    assert event["citation"]["filing_id"] == "OUTF1"
    assert event["citation"]["raw_sha256"] == hashlib.sha256(b"Revenue 14 crore").hexdigest()
    assert event["observation_timing"] == "ON_TIME"
    assert event["case_timing_class"] == "HISTORICAL_RECONSTRUCTION"
    assert event["publication_allowed"] is False
    assert event["live_decision_allowed"] is False
    assert event["promotion_status"] == "NOT_EVALUATED"
    path = setup[0][1] / "case_events/case-1/event-1.json"
    before = path.read_bytes()
    assert _append(tmp_path, setup) == event
    assert path.read_bytes() == before


def test_rehashed_case_and_changed_event_replay_fail(tmp_path):
    setup = _setup(tmp_path)
    _append(tmp_path, setup)
    setup[3]["recorded_at"] = "2027-07-10T12:00:00+05:30"
    with pytest.raises(ValueError, match="event|existing"):
        _append(tmp_path, setup)
    case_path = setup[0][1] / "cases/case-1.json"
    forged = json.loads(case_path.read_text())
    forged["hypothesis"] = "Later rewritten and falsely sealed research judgment"
    forged["case_digest"] = hashlib.sha256(json.dumps(
        {key: value for key, value in forged.items() if key != "case_digest"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    _write(case_path, forged)
    with pytest.raises(ValueError, match="case"):
        _append(tmp_path, setup)


@pytest.mark.parametrize("value,process,error,expected", [
    ("14", "GOOD_PROCESS", "NONE", "GOOD_PROCESS_GOOD_RESULT"),
    ("12", "GOOD_PROCESS", "NONE", "GOOD_PROCESS_BAD_RESULT"),
    ("14", "BAD_PROCESS", "DATA_ERROR", "BAD_PROCESS_GOOD_RESULT"),
    ("12", "BAD_PROCESS", "DATA_ERROR", "BAD_PROCESS_BAD_RESULT"),
])
def test_due_quadrant_is_metric_comparison_plus_human_review(tmp_path, value, process, error, expected):
    from src.kb_runtime.outcome_postmortem import evaluate_due_case

    setup = _setup(tmp_path, value=value)
    _append(tmp_path, setup)
    packet = _due_packet(setup[1], process=process, error=error)
    result = evaluate_due_case(_write(tmp_path / "due.json", packet), **setup[4])
    assert result["quadrant"] == expected
    assert result["result_status"] == ("RESULT_MET" if value == "14" else "RESULT_MISSED")
    assert result["publication_allowed"] is False
    assert result["live_decision_allowed"] is False
    assert result["promotion_status"] == "NOT_EVALUATED"


def test_due_pending_and_candidate_first(tmp_path):
    from src.kb_runtime.outcome_postmortem import evaluate_due_case

    setup = _setup(tmp_path, value="12")
    packet = _due_packet(setup[1], event_id=None)
    packet["process_review"] = None
    pending = evaluate_due_case(_write(tmp_path / "due.json", packet), **setup[4])
    assert pending["postmortem_status"] == "AWAITING_OBSERVATION"
    assert pending["quadrant"] is None
    packet["postmortem_id"] = "post-2"
    packet["observation_event_id"] = "event-1"
    _append(tmp_path, setup)
    awaiting = evaluate_due_case(_write(tmp_path / "due.json", packet), **setup[4])
    assert awaiting["postmortem_status"] == "AWAITING_PROCESS_REVIEW"
    packet = _due_packet(setup[1], process="BAD_PROCESS", error="DATA_ERROR", reproducible=True)
    packet["postmortem_id"] = "post-3"
    complete = evaluate_due_case(_write(tmp_path / "due.json", packet), **setup[4])
    candidate_path = setup[0][1] / "eval_candidates/post-3.json"
    assert complete["postmortem_status"] == "COMPLETE"
    assert candidate_path.is_file()
    candidate = json.loads(candidate_path.read_text())
    assert candidate["candidate_status"] == "UNREVIEWED"
    assert candidate["publication_allowed"] is False
    assert "value_decimal" not in json.dumps(candidate["decision_inputs"])
    assert evaluate_due_case(_write(tmp_path / "due.json", packet), **setup[4]) == complete


def test_due_before_deadline_rejected(tmp_path):
    from src.kb_runtime.outcome_postmortem import evaluate_due_case

    setup = _setup(tmp_path)
    packet = _due_packet(setup[1], event_id=None)
    packet["evaluated_at"] = "2027-07-14T10:00:00+05:30"
    with pytest.raises(ValueError, match="due"):
        evaluate_due_case(_write(tmp_path / "due.json", packet), **setup[4])


def test_guidance_cannot_be_outcome_and_raw_damage_blocks_retry(tmp_path):
    from src.kb_runtime.outcome_postmortem import append_outcome_observation

    guidance = _setup(tmp_path / "guidance", kind="GUIDANCE")
    with pytest.raises(ValueError, match="reported"):
        _append(tmp_path / "guidance", guidance)
    assert not (guidance[0][1] / "case_events/case-1/event-1.json").exists()

    actual = _setup(tmp_path / "actual")
    _append(tmp_path / "actual", actual)
    raw_sha = hashlib.sha256(b"Revenue 14 crore").hexdigest()
    (actual[0][0] / "data/raw/sha256" / raw_sha).write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="source|raw|digest"):
        _append(tmp_path / "actual", actual)


def test_late_observation_retains_historical_label(tmp_path):
    setup = _setup(tmp_path)
    setup[3]["observed_at"] = "2027-07-16T10:00:00+05:30"
    setup[3]["recorded_at"] = "2027-07-16T11:00:00+05:30"
    event = _append(tmp_path, setup)
    assert event["observation_timing"] == "LATE_OBSERVATION"
    assert event["case_timing_class"] == "HISTORICAL_RECONSTRUCTION"


@pytest.mark.parametrize("bad_review", [
    {"error_class": "UNAVOIDABLE_SURPRISE"},
    {"process_assessment": "BAD_PROCESS", "error_class": "NONE"},
    {"reproducible_process_failure": True},
    {"reviewed_at": "2027-07-17T10:00:00+05:30"},
    {"cited_claim_ids": ["unreviewed"]},
    {"cited_gap_ids": ["invented"]},
    {"error_class": "MADE_UP"},
])
def test_due_rejects_false_or_malformed_process_label(tmp_path, bad_review):
    from src.kb_runtime.outcome_postmortem import evaluate_due_case

    setup = _setup(tmp_path)
    _append(tmp_path, setup)
    packet = _due_packet(setup[1])
    packet["process_review"].update(bad_review)
    with pytest.raises(ValueError):
        evaluate_due_case(_write(tmp_path / "due.json", packet), **setup[4])
    assert not (setup[0][1] / "postmortems/post-1.json").exists()


def test_candidate_missing_after_completion_and_changed_review_fail(tmp_path):
    from src.kb_runtime.outcome_postmortem import evaluate_due_case

    setup = _setup(tmp_path, value="12")
    _append(tmp_path, setup)
    packet = _due_packet(setup[1], process="BAD_PROCESS", error="DATA_ERROR",
                         reproducible=True)
    evaluate_due_case(_write(tmp_path / "due.json", packet), **setup[4])
    packet["process_review"]["reasoning"] = "A different later explanation of the original evidence"
    with pytest.raises(ValueError, match="existing postmortem"):
        evaluate_due_case(_write(tmp_path / "due.json", packet), **setup[4])
    packet = _due_packet(setup[1], process="BAD_PROCESS", error="DATA_ERROR",
                         reproducible=True)
    (setup[0][1] / "eval_candidates/post-1.json").unlink()
    with pytest.raises(ValueError, match="missing its eval candidate"):
        evaluate_due_case(_write(tmp_path / "due.json", packet), **setup[4])


@pytest.mark.parametrize("packet_change", [
    {"metric_id": None}, {"case_id": []}, {"observed_at": {}},
    {"supersedes_event_id": []}, {"unknown": "field"},
])
def test_malformed_event_packet_fails_closed(tmp_path, packet_change):
    setup = _setup(tmp_path)
    setup[3].update(packet_change)
    with pytest.raises(ValueError):
        _append(tmp_path, setup)
    assert not (setup[0][1] / "case_events/case-1/event-1.json").exists()


@pytest.mark.parametrize("bad_review", [
    {"process_assessment": []}, {"error_class": {}},
    {"cited_claim_ids": "growth"}, {"reproducible_process_failure": "true"},
    {"failure_invariant": ["rule"]}, {"reasoning": {}},
])
def test_malformed_nested_review_returns_value_error(tmp_path, bad_review):
    from src.kb_runtime.outcome_postmortem import evaluate_due_case

    setup = _setup(tmp_path)
    _append(tmp_path, setup)
    packet = _due_packet(setup[1])
    packet["process_review"].update(bad_review)
    with pytest.raises(ValueError):
        evaluate_due_case(_write(tmp_path / "due.json", packet), **setup[4])


def test_candidate_only_retry_completes_pair(tmp_path):
    from src.kb_runtime.outcome_postmortem import evaluate_due_case

    setup = _setup(tmp_path, value="12")
    _append(tmp_path, setup)
    packet = _due_packet(setup[1], process="BAD_PROCESS", error="DATA_ERROR",
                         reproducible=True)
    original = evaluate_due_case(_write(tmp_path / "due.json", packet), **setup[4])
    post_path = setup[0][1] / "postmortems/post-1.json"
    candidate_path = setup[0][1] / "eval_candidates/post-1.json"
    candidate_bytes = candidate_path.read_bytes()
    post_path.unlink()
    assert evaluate_due_case(_write(tmp_path / "due.json", packet), **setup[4]) == original
    assert candidate_path.read_bytes() == candidate_bytes
    assert post_path.is_file()


def test_revision_replays_prior_source_and_requires_same_metric_series(tmp_path):
    setup = _setup(tmp_path)
    first = _append(tmp_path, setup)
    next_packet = {**setup[3], "event_id": "event-2",
                   "observed_at": "2027-07-10T12:00:00+05:30",
                   "recorded_at": "2027-07-10T13:00:00+05:30",
                   "supersedes_event_id": "event-1"}
    setup[3].clear()
    setup[3].update(next_packet)
    revision = _append(tmp_path, setup)
    assert revision["previous_event_digest"] == first["event_digest"]

    setup[3]["event_id"] = "event-3"
    setup[3]["observed_at"] = "2027-07-10T09:30:00+05:30"
    setup[3]["recorded_at"] = "2027-07-10T14:00:00+05:30"
    with pytest.raises(ValueError, match="order|prior|previous"):
        _append(tmp_path, setup)

    setup[3]["observed_at"] = "2027-07-10T14:00:00+05:30"
    setup[3]["recorded_at"] = "2027-07-10T15:00:00+05:30"
    other_series = json.loads(json.dumps(setup[2]))
    other_series["filing_id"] = "OUTF2"
    other_series["metrics"][0]["metric_id"] = "OUTM2"
    other_series["metrics"][0]["reporting_scope"] = "STANDALONE"
    metadata = {
        "source_id": "OUTCOME1", "entity": "SBI", "source_kind": "EXCHANGE_FILING",
        "url": "https://example.org/outcome1", "source_date": "2027-07-10",
        "observed_at": "2027-07-10T11:30:00+05:30",
        "retrieved_at": "2027-07-10T11:31:00+05:30",
    }
    other_raw = tmp_path / "other-outcome.txt"
    other_raw.write_text("Standalone revenue 14 crore", encoding="utf-8")
    other_source = record_source(_write(tmp_path / "other-source.json", metadata),
                                 other_raw, setup[0][0])
    other_series["version_id"] = other_source["version_id"]
    other_series["published_at"] = "2027-07-10T11:20:00+05:30"
    other_series["first_seen_at"] = "2027-07-10T11:31:00+05:30"
    other_series["reviewed_at"] = "2027-07-10T11:32:00+05:30"
    register_filing_metrics(_write(tmp_path / "other-series.json", other_series),
                            setup[0][0], setup[0][2])
    setup[3]["metric_id"] = "OUTM2"
    with pytest.raises(ValueError, match="series|prior|previous"):
        _append(tmp_path, setup)

    setup[3]["metric_id"] = "OUTM1"
    prior_path = setup[0][1] / "case_events/case-1/event-1.json"
    forged = json.loads(prior_path.read_text())
    forged["value_decimal"] = "99"
    forged["event_digest"] = hashlib.sha256(json.dumps(
        {key: value for key, value in forged.items() if key != "event_digest"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    _write(prior_path, forged)
    with pytest.raises(ValueError, match="prior|previous|source"):
        _append(tmp_path, setup)
