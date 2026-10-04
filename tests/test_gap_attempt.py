import json
from pathlib import Path

import pytest

from src.kb_runtime.claim_lineage import _hash_json
from src.kb_runtime.claim_lineage import evaluate_claims
from src.kb_runtime.gap_attempt import attempt_gap
from src.kb_runtime.source_refresh import evaluate_sources


CUTOFF = "2026-09-28T18:00:00+05:30"
URL = "https://www.bseindia.com/filings/sbi.pdf"


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def setup(tmp_path, classification="PUBLIC_PRIMARY_MISSING"):
    project, state = tmp_path / "project", tmp_path / "state"
    source_request = write(tmp_path / "source-request.json", {
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
    packet = {
        "gap_id": claim["gaps"][0]["gap_id"], "claim_report_id": claim["report_id"],
        "source_report_id": source["report_id"], "entity": "SBI",
        "cutoff_timestamp": CUTOFF, "classification": classification,
        "operator_id": "researcher-1", "reviewer_id": "reviewer-1",
        "reviewed_at": "2026-09-28T23:00:00+05:30",
        "classification_reason": "Primary exchange filing is missing",
        "adapter_id": "reviewed_local_primary_v1", "source_id": "SBI_FILING",
        "source_url": URL, "rights_use": "LOCAL_RESEARCH_COLLECTION_ALLOWED",
        "rights_evidence_ref": "agreement-2026-1", "rights_scope_actor": "researcher-1",
        "rights_scope_method": "manual local download", "rights_scope_storage": "local KB raw store",
        "rights_scope_purpose": "internal equity research", "rights_reviewed_by": "reviewer-1",
        "rights_reviewed_at": "2026-09-28T23:00:00+05:30",
    }
    packet_path = write(tmp_path / "packet.json", packet)
    metadata = write(tmp_path / "metadata.json", {
        "source_id": "SBI_FILING", "entity": "SBI", "source_kind": "EXCHANGE_FILING",
        "url": URL, "source_date": "2026-09-27",
        "observed_at": "2026-09-28T23:00:00+05:30",
        "retrieved_at": "2026-09-28T23:00:00+05:30",
    })
    raw = tmp_path / "filing.pdf"
    raw.write_bytes(b"synthetic fixture only")
    return project, state, packet_path, metadata, raw, claim, source


def call(fixture, attempt_id="attempt-one", raw=True):
    project, state, packet, metadata, raw_file, *_ = fixture
    return attempt_gap(packet, state / "claim_runs/claim-one.json",
                       state / "refresh_runs/source-one.json", packet.parent / "source-request.json",
                       packet.parent / "claims.json", raw_file if raw else None,
                       metadata if raw else None, project, state, attempt_id)


def test_missing_primary_records_once_and_replay_is_stable(tmp_path):
    fixture = setup(tmp_path)
    result = call(fixture)
    assert result["status"] == "RECORDED"
    assert result["gap_status"] == "OPEN"
    assert result["publication_allowed"] is False
    assert result["version_id"]
    assert call(fixture) == result
    assert len(list((fixture[0] / "data/registry/sources/SBI_FILING").glob("*.json"))) == 1


def test_same_reviewed_decision_cannot_use_a_second_attempt_id(tmp_path):
    fixture = setup(tmp_path)
    call(fixture)
    with pytest.raises(ValueError, match="duplicate decision"):
        call(fixture, attempt_id="attempt-two")
    assert len(list((fixture[0] / "data/registry/sources/SBI_FILING").glob("*.json"))) == 1


def test_rejected_attempt_id_reuse_does_not_reserve_new_decision(tmp_path):
    fixture = setup(tmp_path)
    call(fixture)
    packet = json.loads(fixture[2].read_text())
    packet["rights_evidence_ref"] = "agreement-2026-2"
    write(fixture[2], packet)
    with pytest.raises(ValueError, match="changed inputs"):
        call(fixture)
    result = call(fixture, attempt_id="attempt-two")
    assert result["status"] == "RECORDED"
    assert len(list((fixture[0] / "data/registry/sources/SBI_FILING").glob("*.json"))) == 2


@pytest.mark.parametrize("classification,status", [
    ("INTERNAL_RESEARCH", "HUMAN_WORK_REQUIRED"),
    ("PROPRIETARY_OR_RESTRICTED", "RIGHTS_BLOCKED"),
    ("UNCLASSIFIED", "CLASSIFICATION_REQUIRED"),
])
def test_blocked_classification_never_imports(tmp_path, classification, status):
    fixture = setup(tmp_path, classification)
    result = call(fixture, raw=False)
    assert result["status"] == status
    assert result["version_id"] is None
    assert not (fixture[0] / "data/registry/sources/SBI_FILING").exists()


@pytest.mark.parametrize("field,value", [
    ("gap_id", "fake"), ("entity", "HDFC"), ("source_id", "OTHER"),
    ("rights_evidence_ref", "PUBLIC"), ("rights_scope_actor", "other"),
    ("source_url", "https://www.bseindia.com.evil.test/file.pdf"),
])
def test_invalid_packet_fails_before_import(tmp_path, field, value):
    fixture = setup(tmp_path)
    packet = json.loads(fixture[2].read_text())
    packet[field] = value
    write(fixture[2], packet)
    with pytest.raises(ValueError):
        call(fixture)
    assert not (fixture[0] / "data/registry/sources/SBI_FILING").exists()


def test_changed_bytes_or_tampered_receipt_fail_replay(tmp_path):
    fixture = setup(tmp_path)
    call(fixture)
    fixture[4].write_bytes(b"different")
    with pytest.raises(ValueError):
        call(fixture)
    fixture[4].write_bytes(b"synthetic fixture only")
    receipt = fixture[1] / "gap_attempts/attempt-one/result.json"
    receipt.write_text(receipt.read_text().replace("RECORDED", "BLOCKED"))
    with pytest.raises(ValueError):
        call(fixture)


def test_crash_after_registration_resumes_without_new_version(tmp_path):
    fixture = setup(tmp_path)
    result = call(fixture)
    (fixture[1] / "gap_attempts/attempt-one/result.json").unlink()
    resumed = call(fixture)
    assert resumed == result
    assert len(list((fixture[0] / "data/registry/sources/SBI_FILING").glob("*.json"))) == 1


def test_rehashed_result_cannot_erase_recorded_version(tmp_path):
    fixture = setup(tmp_path)
    call(fixture)
    path = fixture[1] / "gap_attempts/attempt-one/result.json"
    result = json.loads(path.read_text())
    result["version_id"] = None
    result["result_id"] = _hash_json({k: v for k, v in result.items() if k != "result_id"})
    write(path, result)
    with pytest.raises(ValueError):
        call(fixture)


@pytest.mark.parametrize("damage", ["metadata", "rights", "intent", "version", "blob", "missing_version"])
def test_replay_rejects_changed_inputs_or_damaged_storage(tmp_path, damage):
    fixture = setup(tmp_path)
    result = call(fixture)
    project, state, packet, metadata, *_ = fixture
    if damage == "metadata":
        value = json.loads(metadata.read_text())
        value["source_date"] = "2026-09-26"
        write(metadata, value)
    elif damage == "rights":
        value = json.loads(packet.read_text())
        value["rights_evidence_ref"] = "different-agreement"
        write(packet, value)
    elif damage == "intent":
        path = state / "gap_attempts/attempt-one/intent.json"
        path.write_text(path.read_text().replace("agreement-2026-1", "agreement-2026-2"))
    elif damage == "version":
        path = project / "data/registry/sources/SBI_FILING" / f'{result["version_id"]}.json'
        path.write_text(path.read_text().replace(URL, "https://www.bseindia.com/other.pdf"))
    elif damage == "missing_version":
        (project / "data/registry/sources/SBI_FILING" / f'{result["version_id"]}.json').unlink()
    else:
        (project / "data/raw/sha256" / result["raw_sha256"]).write_bytes(b"damaged")
    with pytest.raises(ValueError):
        call(fixture)


@pytest.mark.parametrize("value", [
    "http://www.bseindia.com/file.pdf", "https://user@www.bseindia.com/file.pdf",
    "https://www.bseindia.com/file.pdf?x=1",
    "https://www.bseindia.com/file.pdf#page=1",
    "https://www.bseindia.com.evil.test/file.pdf",
    "https://127.0.0.1/file.pdf", "https://localhost/file.pdf",
])
def test_unsafe_url_fails(tmp_path, value):
    fixture = setup(tmp_path)
    packet = json.loads(fixture[2].read_text())
    metadata = json.loads(fixture[3].read_text())
    packet["source_url"] = metadata["url"] = value
    write(fixture[2], packet)
    write(fixture[3], metadata)
    with pytest.raises(ValueError):
        call(fixture)


@pytest.mark.parametrize("damage", ["symlink", "empty", "oversize"])
def test_bad_raw_file_fails(tmp_path, damage):
    fixture = setup(tmp_path)
    raw = fixture[4]
    if damage == "symlink":
        raw.unlink()
        raw.symlink_to(tmp_path / "target.pdf")
        (tmp_path / "target.pdf").write_bytes(b"bytes")
    elif damage == "empty":
        raw.write_bytes(b"")
    else:
        with raw.open("wb") as output:
            output.truncate(25 * 1024 * 1024 + 1)
    with pytest.raises(ValueError):
        call(fixture)


def test_tampered_parent_report_fails(tmp_path):
    fixture = setup(tmp_path)
    path = fixture[1] / "claim_runs/claim-one.json"
    path.write_text(path.read_text().replace("SOURCE_NOT_READY", "LINEAGE_LINKED"))
    with pytest.raises(ValueError):
        call(fixture)


def test_stale_source_records_later_version_but_old_report_stays_stale(tmp_path):
    fixture = setup(tmp_path, "PUBLIC_PRIMARY_STALE")
    project, state, packet_path, metadata, raw, _, _ = fixture
    from src.kb_runtime.source_store import record_source
    prior_meta = json.loads(metadata.read_text())
    prior_meta.update(source_date="2026-01-01", observed_at="2026-09-28T10:00:00+05:30",
                      retrieved_at="2026-09-28T10:00:00+05:30")
    write(metadata, prior_meta)
    record_source(metadata, raw, project)
    request = write(tmp_path / "stale-request.json", {
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "required_sources": [{"source_id": "SBI_FILING", "max_age_days": 60}],
    })
    stale_source = evaluate_sources(request, project, state, "stale-source")
    claims = write(tmp_path / "stale-claims.json", {
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "claims": [{"claim_id": "deposit", "claim_type": "REPORTED_FACT",
                    "statement": "Deposit growth", "as_of": "2026-06-30",
                    "source_id": "SBI_FILING", "version_id": "0" * 64,
                    "passage_locator": "page 2"}],
    })
    stale_claim = evaluate_claims(claims, state / "refresh_runs/stale-source.json",
                                  project, state, "stale-claim")
    packet = json.loads(packet_path.read_text())
    packet.update(gap_id=stale_claim["gaps"][0]["gap_id"],
                  claim_report_id=stale_claim["report_id"],
                  source_report_id=stale_source["report_id"])
    write(packet_path, packet)
    prior_meta.update(source_date="2026-09-28", observed_at="2026-09-28T23:00:00+05:30",
                      retrieved_at="2026-09-28T23:00:00+05:30")
    write(metadata, prior_meta)
    result = attempt_gap(packet_path, state / "claim_runs/stale-claim.json",
                         state / "refresh_runs/stale-source.json", request, claims, raw, metadata,
                         project, state, "stale-attempt")
    assert result["status"] == "RECORDED"
    assert json.loads((state / "refresh_runs/stale-source.json").read_text())["sources"][0]["status"] == "STALE"


@pytest.mark.parametrize("target", ["source_request", "claim_request"])
def test_changed_parent_request_fails_before_import(tmp_path, target):
    fixture = setup(tmp_path)
    path = tmp_path / ("source-request.json" if target == "source_request" else "claims.json")
    value = json.loads(path.read_text())
    if target == "source_request":
        value["required_sources"][0]["max_age_days"] = 61
    else:
        value["claims"][0]["statement"] = "Altered claim"
    write(path, value)
    with pytest.raises(ValueError, match="request"):
        call(fixture)
    assert not (fixture[0] / "data/registry/sources/SBI_FILING").exists()


def test_self_hashed_forged_source_parent_fails_before_import(tmp_path):
    fixture = setup(tmp_path)
    source_path = fixture[1] / "refresh_runs/source-one.json"
    claim_path = fixture[1] / "claim_runs/claim-one.json"
    source = json.loads(source_path.read_text())
    source["sources"][0]["status"] = "STALE"
    source["sources"][0]["reason"] = "source age exceeds max_age_days"
    source["report_id"] = _hash_json({k: v for k, v in source.items() if k != "report_id"})
    write(source_path, source)
    claim = json.loads(claim_path.read_text())
    claim["source_report_id"] = source["report_id"]
    claim["report_id"] = _hash_json({k: v for k, v in claim.items() if k != "report_id"})
    write(claim_path, claim)
    packet = json.loads(fixture[2].read_text())
    packet["source_report_id"] = source["report_id"]
    packet["claim_report_id"] = claim["report_id"]
    write(fixture[2], packet)
    with pytest.raises(ValueError, match="historical"):
        call(fixture)
    assert not (fixture[0] / "data/registry/sources/SBI_FILING").exists()


def test_missing_parent_remains_valid_after_later_import(tmp_path):
    fixture = setup(tmp_path)
    result = call(fixture)
    assert call(fixture) == result


def test_self_hashed_forged_claim_parent_fails_before_import(tmp_path):
    fixture = setup(tmp_path)
    claim_path = fixture[1] / "claim_runs/claim-one.json"
    claim = json.loads(claim_path.read_text())
    claim["claims"][0]["status"] = "AFTER_CUTOFF"
    claim["claims"][0]["reason"] = "claim date is after cutoff"
    claim["gaps"][0]["reason_unresolved"] = "claim date is after cutoff"
    claim["report_id"] = _hash_json({k: v for k, v in claim.items() if k != "report_id"})
    write(claim_path, claim)
    packet = json.loads(fixture[2].read_text())
    packet["claim_report_id"] = claim["report_id"]
    write(fixture[2], packet)
    with pytest.raises(ValueError, match="historical"):
        call(fixture)


def test_late_claim_has_frozen_ineligible_receipt(tmp_path):
    fixture = setup(tmp_path)
    project, state, packet_path, *_ = fixture
    request = json.loads((tmp_path / "claims.json").read_text())
    request["claims"][0]["as_of"] = "2026-09-29"
    claim_request = write(tmp_path / "late-claims.json", request)
    late = evaluate_claims(claim_request, state / "refresh_runs/source-one.json",
                           project, state, "late-claim")
    packet = json.loads(packet_path.read_text())
    packet.update(gap_id=late["gaps"][0]["gap_id"], claim_report_id=late["report_id"])
    write(packet_path, packet)
    result = attempt_gap(packet_path, state / "claim_runs/late-claim.json",
                         state / "refresh_runs/source-one.json", tmp_path / "source-request.json",
                         claim_request, None, None, project, state, "late-attempt")
    assert result["status"] == "INELIGIBLE"
    assert result["version_id"] is None
    assert result["publication_allowed"] is False
    assert not (project / "data/registry/sources/SBI_FILING").exists()


@pytest.mark.parametrize("damage", ["linked", "missing_raw"])
def test_non_acquisition_gap_has_frozen_ineligible_receipt(tmp_path, damage):
    fixture = setup(tmp_path)
    project, state, packet_path, metadata_path, raw, *_ = fixture
    from src.kb_runtime.source_store import record_source
    metadata = json.loads(metadata_path.read_text())
    metadata.update(source_date="2026-09-27", observed_at="2026-09-28T10:00:00+05:30",
                    retrieved_at="2026-09-28T10:00:00+05:30")
    write(metadata_path, metadata)
    version = record_source(metadata_path, raw, project)
    if damage == "missing_raw":
        (project / "data/raw/sha256" / version["raw_sha256"]).unlink()
    source = evaluate_sources(tmp_path / "source-request.json", project, state,
                              f"{damage}-source")
    request = json.loads((tmp_path / "claims.json").read_text())
    request["claims"][0]["version_id"] = version["version_id"]
    claim_request = write(tmp_path / f"{damage}-claims.json", request)
    claim = evaluate_claims(claim_request, state / f"refresh_runs/{damage}-source.json",
                            project, state, f"{damage}-claim")
    packet = json.loads(packet_path.read_text())
    packet.update(gap_id=claim["gaps"][0]["gap_id"], claim_report_id=claim["report_id"],
                  source_report_id=source["report_id"])
    write(packet_path, packet)
    result = attempt_gap(packet_path, state / f"claim_runs/{damage}-claim.json",
                         state / f"refresh_runs/{damage}-source.json",
                         tmp_path / "source-request.json", claim_request, None, None,
                         project, state, f"{damage}-attempt")
    assert result["status"] == "INELIGIBLE"
    assert result["version_id"] is None
    assert result["publication_allowed"] is False
    assert len(list((project / "data/registry/sources/SBI_FILING").glob("*.json"))) == 1
