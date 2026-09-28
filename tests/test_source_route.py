"""A route is a frozen decision, never a document acquisition."""

import json
from pathlib import Path

import pytest

from src.kb_runtime.claim_lineage import _hash_json, evaluate_claims
from src.kb_runtime.source_refresh import evaluate_sources
from src.kb_runtime.source_route import select_gap_route


CUTOFF = "2026-09-28T18:00:00+05:30"
URL = "https://www.bseindia.com/filings/sbi.pdf"


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def fixture(tmp_path, classification="PUBLIC_PRIMARY_MISSING"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    project, state = tmp_path / "project", tmp_path / "state"
    if classification == "PUBLIC_PRIMARY_STALE":
        from src.kb_runtime.source_store import record_source
        metadata = write(tmp_path / "old-metadata.json", {
            "source_id": "SBI_FILING", "entity": "SBI",
            "source_kind": "EXCHANGE_FILING", "url": URL,
            "source_date": "2026-01-01",
            "observed_at": "2026-09-28T10:00:00+05:30",
            "retrieved_at": "2026-09-28T10:00:00+05:30",
        })
        raw = tmp_path / "old.pdf"
        raw.write_bytes(b"synthetic stale source")
        record_source(metadata, raw, project)
    source_request = write(tmp_path / "sources.json", {
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "required_sources": [{"source_id": "SBI_FILING", "max_age_days": 60}],
    })
    source = evaluate_sources(source_request, project, state, "source-one")
    claim_request = write(tmp_path / "claims.json", {
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "claims": [{"claim_id": "deposit", "claim_type": "REPORTED_FACT",
                    "statement": "Deposit growth", "as_of": "2026-06-30",
                    "source_id": "SBI_FILING", "version_id": "0" * 64,
                    "passage_locator": "page 2"}],
    })
    claim = evaluate_claims(claim_request, state / "refresh_runs/source-one.json",
                            project, state, "claim-one")
    reviewed = "2026-09-28T23:00:00+05:30"
    classification_packet = {
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
    }
    activation = {
        "origin": "SYNTHETIC_FIXTURE", "observed_gap_reason": "No filing registered",
        "local_attempt_id": None,
        "classification_packet": classification_packet,
        "rights_extension": {
            "endpoint": URL, "frequency": "one reviewed document",
            "retention": "local KB raw store", "limits": "no redistribution",
            "expires_at": "2027-09-28T23:00:00+05:30",
        },
    }
    return project, state, write(tmp_path / "activation.json", activation), source_request, claim_request


def call(data, route_id="route-one"):
    project, state, packet, source_request, claim_request = data
    return select_gap_route(packet, state / "claim_runs/claim-one.json",
                            state / "refresh_runs/source-one.json", source_request,
                            claim_request, project, state, route_id)


def mutate(data, field, value, nested="classification_packet"):
    payload = json.loads(data[2].read_text())
    payload[nested][field] = value
    write(data[2], payload)


def test_valid_missing_primary_plan_is_frozen_and_has_no_acquisition(tmp_path):
    data = fixture(tmp_path)
    result = call(data)
    assert result["status"] == "REVIEWED_LOCAL"
    assert result["origin"] == "SYNTHETIC_FIXTURE"
    assert result["gap_status"] == "OPEN"
    assert result["publication_allowed"] is False
    assert call(data) == result
    assert (data[1] / "source_routes/route-one.json").exists()
    assert not (data[0] / "data").exists()
    assert not (data[1] / "gap_attempts").exists()


def test_stale_primary_plan_keeps_old_source_version_untouched(tmp_path):
    data = fixture(tmp_path, "PUBLIC_PRIMARY_STALE")
    versions_before = sorted((data[0] / "data/registry/sources/SBI_FILING").glob("*.json"))
    assert call(data)["status"] == "REVIEWED_LOCAL"
    assert sorted((data[0] / "data/registry/sources/SBI_FILING").glob("*.json")) == versions_before


def test_narrow_or_missing_rights_are_not_routed(tmp_path):
    data = fixture(tmp_path)
    mutate(data, "rights_scope_method", "automated scrape")
    assert call(data)["status"] == "RIGHTS_REVIEW_REQUIRED"
    data = fixture(tmp_path / "other")
    payload = json.loads(data[2].read_text())
    payload["rights_extension"] = None
    write(data[2], payload)
    assert call(data)["status"] == "RIGHTS_REVIEW_REQUIRED"


@pytest.mark.parametrize("classification,status", [
    ("INTERNAL_RESEARCH", "HUMAN_WORK_REQUIRED"),
    ("PROPRIETARY_OR_RESTRICTED", "NO_APPROVED_ROUTE"),
    ("UNCLASSIFIED", "HUMAN_WORK_REQUIRED"),
])
def test_nonpublic_classification_has_no_route(tmp_path, classification, status):
    data = fixture(tmp_path, classification)
    assert call(data)["status"] == status


def test_cross_entity_and_changed_request_fail_closed(tmp_path):
    data = fixture(tmp_path)
    mutate(data, "entity", "HDFC")
    with pytest.raises(ValueError):
        call(data)
    data = fixture(tmp_path / "other")
    request = json.loads(data[3].read_text())
    request["required_sources"][0]["max_age_days"] = 61
    write(data[3], request)
    with pytest.raises(ValueError):
        call(data)


def test_rehashed_fake_parent_and_route_collision_fail_closed(tmp_path):
    data = fixture(tmp_path)
    path = data[1] / "claim_runs/claim-one.json"
    parent = json.loads(path.read_text())
    parent["claims"][0]["status"] = "SUPPORTED"
    parent["report_id"] = _hash_json({k: v for k, v in parent.items() if k != "report_id"})
    write(path, parent)
    payload = json.loads(data[2].read_text())
    payload["classification_packet"]["claim_report_id"] = parent["report_id"]
    write(data[2], payload)
    with pytest.raises(ValueError):
        call(data)
    data = fixture(tmp_path / "other")
    call(data)
    mutate(data, "classification_reason", "Different rationale")
    with pytest.raises(ValueError):
        call(data)


def test_expired_rights_and_tampered_receipt_fail_closed(tmp_path):
    data = fixture(tmp_path)
    mutate(data, "expires_at", "2020-01-01T00:00:00+00:00", "rights_extension")
    assert call(data)["status"] == "RIGHTS_REVIEW_REQUIRED"
    receipt = data[1] / "source_routes/route-one.json"
    receipt.write_text(receipt.read_text().replace("RIGHTS_REVIEW_REQUIRED", "REVIEWED_LOCAL"))
    with pytest.raises(ValueError):
        call(data)


def test_claimed_local_attempt_must_be_intact_and_match_gap(tmp_path):
    data = fixture(tmp_path)
    payload = json.loads(data[2].read_text())
    payload["local_attempt_id"] = "missing-attempt"
    write(data[2], payload)
    with pytest.raises(ValueError):
        call(data)


def test_caller_declared_real_origin_is_not_verified_or_activated(tmp_path):
    data = fixture(tmp_path)
    payload = json.loads(data[2].read_text())
    payload["origin"] = "REAL_OBSERVED"
    write(data[2], payload)
    route = call(data)
    assert route["origin"] == "UNVERIFIED"
    assert route["adapter_activation_allowed"] is False


def test_rehashed_receipt_with_spoofed_time_fails_replay(tmp_path):
    data = fixture(tmp_path)
    call(data)
    path = data[1] / "source_routes/route-one.json"
    route = json.loads(path.read_text())
    route["planned_at"] = "2020-01-01T00:00:00+00:00"
    route["route_digest"] = _hash_json({k: v for k, v in route.items()
                                         if k != "route_digest"})
    write(path, route)
    with pytest.raises(ValueError):
        call(data)
