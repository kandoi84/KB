"""Independent labels bind to exact frozen gap attempts."""

import json
import hashlib
from datetime import datetime, timezone

import pytest

from src.kb_runtime.claim_lineage import evaluate_claims, _hash_json
from src.kb_runtime.gap_attempt import attempt_gap
from src.kb_runtime.source_refresh import evaluate_sources
from src.kb_runtime.trust_observation import record_trust_observation


CUTOFF = "2026-09-28T18:00:00+05:30"
URL = "https://www.bseindia.com/filings/sbi.pdf"


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def fixture(tmp_path, classification="PUBLIC_PRIMARY_MISSING"):
    project, state = tmp_path / "project", tmp_path / "state"
    sources = write(tmp_path / "sources.json", {
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "required_sources": [{"source_id": "SBI_FILING", "max_age_days": 60}],
    })
    source = evaluate_sources(sources, project, state, "source-one")
    claims = write(tmp_path / "claims.json", {
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "claims": [{"claim_id": "deposit", "claim_type": "REPORTED_FACT",
                    "statement": "Deposit growth", "as_of": "2026-06-30",
                    "source_id": "SBI_FILING", "version_id": "0" * 64,
                    "passage_locator": "page 2"}],
    })
    claim = evaluate_claims(claims, state / "refresh_runs/source-one.json",
                            project, state, "claim-one")
    reviewed = "2026-09-28T23:00:00+05:30"
    packet = write(tmp_path / "packet.json", {
        "gap_id": claim["gaps"][0]["gap_id"], "claim_report_id": claim["report_id"],
        "source_report_id": source["report_id"], "entity": "SBI",
        "cutoff_timestamp": CUTOFF, "classification": classification,
        "operator_id": "researcher-1", "reviewer_id": "reviewer-1",
        "reviewed_at": reviewed, "classification_reason": "Primary filing missing",
        "adapter_id": "reviewed_local_primary_v1", "source_id": "SBI_FILING",
        "source_url": URL, "rights_use": "LOCAL_RESEARCH_COLLECTION_ALLOWED",
        "rights_evidence_ref": "agreement-2026-1", "rights_scope_actor": "researcher-1",
        "rights_scope_method": "manual local download",
        "rights_scope_storage": "local KB raw store",
        "rights_scope_purpose": "internal equity research",
        "rights_reviewed_by": "reviewer-1", "rights_reviewed_at": reviewed,
    })
    metadata = write(tmp_path / "metadata.json", {
        "source_id": "SBI_FILING", "entity": "SBI", "source_kind": "EXCHANGE_FILING",
        "url": URL, "source_date": "2026-09-27",
        "observed_at": reviewed, "retrieved_at": reviewed,
    })
    raw = tmp_path / "raw.pdf"
    raw.write_bytes(b"synthetic evidence")
    result = attempt_gap(packet, state / "claim_runs/claim-one.json",
                         state / "refresh_runs/source-one.json", sources, claims,
                         raw if classification == "PUBLIC_PRIMARY_MISSING" else None,
                         metadata if classification == "PUBLIC_PRIMARY_MISSING" else None,
                         project, state, "attempt-one")
    observation = {
        "observation_id": "obs-one", "attempt_id": "attempt-one",
        "declared_origin": "SYNTHETIC_FIXTURE", "adjudicator_id": "reviewer-2",
        "adjudicated_at": datetime.now(timezone.utc).isoformat(),
        "rubric_version": "trust-v1", "source_authority": "BSE",
        "document_type": "EXCHANGE_FILING", "reporting_period": "2026-Q2",
        "raw_sha256": result["raw_sha256"],
        "labels": {"source_identity": "PASS", "publication_cutoff": "PASS",
                   "raw_replay": "UNVERIFIED", "rights_workflow": "PASS",
                   "usable_document": "PASS"},
        "failure_class": "NONE",
    }
    return packet, state, write(tmp_path / "observation.json", observation), result


def call(data):
    packet, state, observation, _ = data
    base = state / "gap_attempts/attempt-one"
    return record_trust_observation(observation, packet, base / "intent.json",
                                    base / "result.json", state)


def mutate(data, field, value):
    item = json.loads(data[2].read_text())
    item[field] = value
    write(data[2], item)


def test_independent_observation_is_frozen_and_binds_attempt(tmp_path):
    data = fixture(tmp_path)
    receipt = call(data)
    assert receipt["attempt_id"] == "attempt-one"
    assert receipt["attempt_result_id"] == data[3]["result_id"]
    assert receipt["origin"] == "SYNTHETIC_FIXTURE"
    assert receipt["adapter_version"] == data[3]["adapter_version"]
    assert receipt["attempted_at"] == data[3]["attempted_at"]
    assert receipt["rights_reference_hash"] == hashlib.sha256(
        data[3]["rights_evidence_ref"].encode()).hexdigest()
    packet = json.loads(data[0].read_text())
    assert receipt["rights_policy_hash"] == _hash_json({
        key: packet[key] for key in (
            "rights_use", "rights_evidence_ref", "rights_scope_actor",
            "rights_scope_method", "rights_scope_storage", "rights_scope_purpose")})
    assert receipt["publication_allowed"] is False
    assert call(data) == receipt


def test_adjudicator_must_be_independent_of_operator_and_first_reviewer(tmp_path):
    data = fixture(tmp_path)
    mutate(data, "adjudicator_id", "researcher-1")
    with pytest.raises(ValueError):
        call(data)
    mutate(data, "adjudicator_id", "reviewer-1")
    with pytest.raises(ValueError):
        call(data)


def test_wrong_raw_hash_or_changed_label_fails(tmp_path):
    data = fixture(tmp_path)
    mutate(data, "raw_sha256", "0" * 64)
    with pytest.raises(ValueError):
        call(data)
    mutate(data, "raw_sha256", data[3]["raw_sha256"])
    call(data)
    item = json.loads(data[2].read_text())
    item["labels"]["source_identity"] = "FAIL"
    write(data[2], item)
    with pytest.raises(ValueError):
        call(data)


def test_missing_or_tampered_attempt_fails(tmp_path):
    data = fixture(tmp_path)
    (data[1] / "gap_attempts/attempt-one/result.json").unlink()
    with pytest.raises(ValueError):
        call(data)


def test_blocked_attempt_can_be_labeled_and_real_origin_is_unverified(tmp_path):
    data = fixture(tmp_path, "INTERNAL_RESEARCH")
    item = json.loads(data[2].read_text())
    item["declared_origin"] = "REAL_OBSERVED"
    item["labels"] = {key: "NOT_APPLICABLE" for key in item["labels"]}
    item["failure_class"] = "HUMAN_WORK"
    write(data[2], item)
    receipt = call(data)
    assert receipt["origin"] == "UNVERIFIED"
    assert receipt["attempt_status"] == "HUMAN_WORK_REQUIRED"


def test_future_adjudication_and_duplicate_id_fail(tmp_path):
    data = fixture(tmp_path)
    mutate(data, "adjudicated_at", "2099-01-01T00:00:00+00:00")
    with pytest.raises(ValueError):
        call(data)
    mutate(data, "adjudicated_at", datetime.now(timezone.utc).isoformat())
    call(data)
    mutate(data, "reporting_period", "2026-Q3")
    with pytest.raises(ValueError):
        call(data)


def test_blocked_failure_class_must_match_attempt_status(tmp_path):
    data = fixture(tmp_path, "INTERNAL_RESEARCH")
    item = json.loads(data[2].read_text())
    item["labels"] = {key: "NOT_APPLICABLE" for key in item["labels"]}
    item["failure_class"] = "RATE_LIMIT"
    write(data[2], item)
    with pytest.raises(ValueError):
        call(data)


def test_rehashed_attempt_with_added_fields_is_not_a_valid_receipt(tmp_path):
    from src.kb_runtime.claim_lineage import _hash_json

    data = fixture(tmp_path)
    base = data[1] / "gap_attempts/attempt-one"
    intent_path, result_path = base / "intent.json", base / "result.json"
    intent = json.loads(intent_path.read_text())
    result = json.loads(result_path.read_text())
    intent["unreviewed_extra"] = result["unreviewed_extra"] = "spoof"
    intent["intent_id"] = _hash_json({k: v for k, v in intent.items() if k != "intent_id"})
    result["intent_id"] = intent["intent_id"]
    result["result_id"] = _hash_json({k: v for k, v in result.items() if k != "result_id"})
    write(intent_path, intent)
    write(result_path, result)
    with pytest.raises(ValueError):
        call(data)


def test_malformed_label_is_validation_error(tmp_path):
    data = fixture(tmp_path)
    item = json.loads(data[2].read_text())
    item["labels"]["source_identity"] = []
    write(data[2], item)
    with pytest.raises(ValueError):
        call(data)


def test_unproven_raw_replay_cannot_be_labeled_pass(tmp_path):
    data = fixture(tmp_path)
    item = json.loads(data[2].read_text())
    item["labels"]["raw_replay"] = "PASS"
    write(data[2], item)
    with pytest.raises(ValueError):
        call(data)


def test_rehashed_non_exchange_host_cannot_default_to_bse(tmp_path):
    from src.kb_runtime.claim_lineage import _hash_json

    data = fixture(tmp_path)
    packet = json.loads(data[0].read_text())
    packet["source_url"] = "https://not-an-exchange.example/filing.pdf"
    write(data[0], packet)
    base = data[1] / "gap_attempts/attempt-one"
    intent_path, result_path = base / "intent.json", base / "result.json"
    intent, result = json.loads(intent_path.read_text()), json.loads(result_path.read_text())
    intent["source_url"] = result["source_url"] = packet["source_url"]
    intent["packet_hash"] = result["packet_hash"] = _hash_json(packet)
    intent["intent_id"] = _hash_json({k: v for k, v in intent.items() if k != "intent_id"})
    result["intent_id"] = intent["intent_id"]
    result["result_id"] = _hash_json({k: v for k, v in result.items() if k != "result_id"})
    write(intent_path, intent)
    write(result_path, result)
    with pytest.raises(ValueError):
        call(data)
