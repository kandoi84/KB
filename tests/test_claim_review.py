import json
import hashlib
import subprocess
import sys

import pytest

from src.kb_runtime.claim_lineage import evaluate_claims
from src.kb_runtime.claim_review import review_claims
from src.kb_runtime.identity_store import register_identity
from src.kb_runtime.metric_store import register_filing
from src.kb_runtime.passage_evidence import evaluate_passages
from src.kb_runtime.source_refresh import evaluate_sources
from src.kb_runtime.source_store import record_source


CUTOFF = "2026-09-28T18:00:00+05:30"


def _json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _source(tmp, project, source_id, kind, raw, observed):
    metadata = _json(tmp / f"{source_id}-metadata.json", {
        "source_id": source_id, "entity": "SBI", "source_kind": kind,
        "url": f"https://example.org/{source_id}", "source_date": "2026-09-28",
        "observed_at": observed, "retrieved_at": "2026-09-28T10:05:00+05:30",
    })
    raw_path = tmp / f"{source_id}.txt"
    raw_path.write_bytes(raw)
    return record_source(metadata, raw_path, project)


def fixture(tmp, claim_type="REPORTED_FACT", quote="Deposits grew by 12 percent"):
    project, state, catalog = tmp / "project", tmp / "state", tmp / "catalog.sqlite"
    identity = _source(tmp, project, "IDENT", "EXCHANGE_SECURITY_FILE",
                       b"SBI INE062A01020", "2026-09-28T09:00:00+05:30")
    register_identity(_json(tmp / "identity.json", {
        "issuer_id": "SBI", "legal_name": "State Bank of India", "isin": "INE062A01020",
        "security_type": "EQUITY", "listed_from": "1995-01-01", "listed_to": None,
        "exchange": "NSE", "symbol": "SBIN", "valid_from": "1995-01-01", "valid_to": None,
        "announced_at": "2026-09-28T09:00:00+05:30",
        "first_seen_at": "2026-09-28T10:05:00+05:30", "source_id": "IDENT",
        "version_id": identity["version_id"], "reviewer_id": "analyst-1",
        "reviewed_at": "2026-09-28T10:06:00+05:30", "review_decision": "CONFIRMED",
        "evidence_locator": "exchange identity row",
    }), project, catalog)
    filing = _source(tmp, project, "FILING", "EXCHANGE_FILING",
                     (quote + ".\n").encode(), "2026-09-28T10:00:00+05:30")
    register_filing(_json(tmp / "filing.json", {
        "filing_id": "F1", "issuer_id": "SBI", "isin": "INE062A01020",
        "source_id": "FILING", "version_id": filing["version_id"],
        "document_type": "CONCALL_TRANSCRIPT", "period_end": "2026-06-30",
        "published_at": "2026-09-28T10:00:00+05:30",
        "first_seen_at": "2026-09-28T10:05:00+05:30", "rights_status": "REVIEWED",
        "reviewer_id": "analyst-1", "reviewed_at": "2026-09-28T10:06:00+05:30",
        "review_decision": "CONFIRMED", "evidence_locator": "exchange filing row",
        "supersedes_filing_id": None, "metrics": [],
    }), project, catalog)
    evaluate_sources(_json(tmp / "sources.json", {
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "required_sources": [{"source_id": "FILING", "max_age_days": 60}],
    }), project, state, "source-1")
    claim_report = evaluate_claims(_json(tmp / "claims.json", {
        "entity": "SBI", "cutoff_timestamp": CUTOFF, "claims": [{
            "claim_id": "growth", "claim_type": claim_type,
            "statement": "SBI deposits grew by 12 percent in June 2026.",
            "as_of": "2026-06-30", "source_id": "FILING",
            "version_id": filing["version_id"], "passage_locator": "sentence 1",
        }],
    }), state / "refresh_runs/source-1.json", project, state, "claim-1")
    passage_report = evaluate_passages(_json(tmp / "passages.json", {
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "quotes": [{"claim_id": "growth", "verbatim_quote": quote}],
    }), state / "claim_runs/claim-1.json", project, state, "passage-1")
    result = passage_report["results"][0]
    packet = {
        "entity": "SBI", "cutoff_timestamp": CUTOFF,
        "claim_report_id": claim_report["report_id"],
        "passage_report_id": passage_report["report_id"],
        "decisions": [{
            "claim_id": "growth", "reviewer_id": "analyst-2",
            "reviewed_at": "2026-09-28T11:00:00+05:30",
            "rights_evidence_ref": "license record 7 permits local analysis",
            "rights_use": "LOCAL_ANALYSIS_ALLOWED", "semantic_decision": "SUPPORTS",
            "review_note": "SBI deposits grew by 12 percent for June 2026; scope and unit match; no negation.",
            "contradiction_status": "NO_KNOWN_CONFLICT", "related_claim_ids": [],
            "conflict_explanation": None,
            "source_id": result["source_id"], "version_id": result["version_id"],
            "raw_sha256": result["raw_sha256"], "verbatim_quote": quote,
            "byte_offset": result["byte_offset"],
        }],
    }
    packet_path = _json(tmp / "review.json", packet)
    return project, state, catalog, packet_path, packet


def review(data, run_id="review-1"):
    project, state, catalog, packet_path, _ = data
    return review_claims(packet_path, state / "claim_runs/claim-1.json",
                         state / "passage_runs/passage-1.json", project, catalog,
                         state, run_id)


def test_supported_direct_claim_closes_only_review_receipt(tmp_path):
    data = fixture(tmp_path)
    report = review(data)
    assert report["publication_allowed"] is False
    assert report["results"][0]["status"] == "INTERNAL_REVIEWED"
    assert report["gaps"][0]["status"] == "CLOSED_BY_REVIEW"
    assert report["gaps"][0]["gap_id"] == "claim-1-growth"
    assert report["gaps"][0]["review_report_id"] == report["report_id"]
    assert json.loads((data[1] / "claim_runs/claim-1.json").read_text())["gaps"][0]["status"] == "OPEN"
    assert review(data) == report


@pytest.mark.parametrize("field,value,error", [
    ("claim_report_id", "0" * 64, "binding"),
    ("passage_report_id", "0" * 64, "binding"),
    ("entity", "HDFC", "binding"),
    ("cutoff_timestamp", "2026-09-29T18:00:00+05:30", "binding"),
])
def test_packet_must_bind_exact_reports_and_entity(tmp_path, field, value, error):
    data = fixture(tmp_path)
    data[4][field] = value
    _json(data[3], data[4])
    with pytest.raises(ValueError, match=error):
        review(data)


@pytest.mark.parametrize("field,value,error", [
    ("reviewer_id", "../bad", "reviewer_id"),
    ("reviewed_at", "2026-09-28T11:00:00", "timezone"),
    ("rights_evidence_ref", "", "rights_evidence_ref"),
    ("rights_use", "PUBLISH_ALLOWED", "rights_use"),
    ("semantic_decision", "APPROVED", "semantic_decision"),
    ("review_note", "", "review_note"),
    ("contradiction_status", "NONE", "contradiction_status"),
    ("raw_sha256", "0" * 64, "exact passage"),
    ("verbatim_quote", "different", "exact passage"),
    ("byte_offset", 1, "exact passage"),
    ("source_id", "OTHER", "exact passage"),
    ("version_id", "0" * 64, "exact passage"),
])
def test_review_decision_rejects_invalid_or_unpinned_fields(tmp_path, field, value, error):
    data = fixture(tmp_path)
    data[4]["decisions"][0][field] = value
    _json(data[3], data[4])
    with pytest.raises(ValueError, match=error):
        review(data)


def test_unknown_duplicate_and_extra_decisions_fail(tmp_path):
    data = fixture(tmp_path)
    decision = data[4]["decisions"][0]
    data[4]["decisions"] = [decision, dict(decision)]
    _json(data[3], data[4])
    with pytest.raises(ValueError, match="duplicate"):
        review(data)
    data[4]["decisions"] = [{**decision, "claim_id": "unknown"}]
    _json(data[3], data[4])
    with pytest.raises(ValueError, match="unknown"):
        review(data)
    data[4]["decisions"] = [{**decision, "surprise": True}]
    _json(data[3], data[4])
    with pytest.raises(ValueError, match="fields"):
        review(data)


@pytest.mark.parametrize("change,expected", [
    ({"semantic_decision": "DOES_NOT_SUPPORT"}, "SEMANTIC_REJECTED"),
    ({"semantic_decision": "UNCERTAIN"}, "SEMANTIC_UNCERTAIN"),
    ({"rights_use": "BLOCKED"}, "RIGHTS_BLOCKED"),
    ({"reviewed_at": "2026-09-29T11:00:00+05:30"}, "REVIEW_AFTER_CUTOFF"),
])
def test_distinct_review_gates_leave_gap_open(tmp_path, change, expected):
    data = fixture(tmp_path)
    data[4]["decisions"][0].update(change)
    _json(data[3], data[4])
    result = review(data)
    assert result["results"][0]["status"] == expected
    assert result["gaps"][0]["status"] == "OPEN"
    assert result["publication_allowed"] is False


def test_missing_review_and_absent_quote_remain_open(tmp_path):
    data = fixture(tmp_path)
    data[4]["decisions"] = []
    _json(data[3], data[4])
    assert review(data)["results"][0]["status"] == "MISSING_REVIEW"
    data = fixture(tmp_path / "absent", quote="Deposits grew by 12 percent")
    # The frozen passage result is changed only in this synthetic test to
    # model an upstream quote-absent run, then correctly rehashed.
    passage_path = data[1] / "passage_runs/passage-1.json"
    passage = json.loads(passage_path.read_text())
    passage["results"][0]["status"] = "QUOTE_ABSENT"
    passage["results"][0]["byte_offset"] = None
    passage.pop("report_id")
    from src.kb_runtime.claim_lineage import _hash_json
    passage["report_id"] = _hash_json(passage)
    _json(passage_path, passage)
    data[4]["passage_report_id"] = passage["report_id"]
    data[4]["decisions"] = []
    _json(data[3], data[4])
    assert review(data)["results"][0]["status"] == "QUOTE_NOT_PRESENT"


@pytest.mark.parametrize("claim_type,expected", [
    ("MANAGEMENT_GUIDANCE", "INTERNAL_REVIEWED"),
    ("DERIVED", "TYPE_CONTRACT_MISSING"),
    ("ANALYST_ASSUMPTION", "TYPE_CONTRACT_MISSING"),
    ("CONSENSUS", "ORIGIN_CONTRACT_MISSING"),
    ("MARKET_DATA", "ORIGIN_CONTRACT_MISSING"),
    ("SENTIMENT", "ORIGIN_CONTRACT_MISSING"),
])
def test_type_contracts(tmp_path, claim_type, expected):
    data = fixture(tmp_path, claim_type=claim_type)
    assert review(data)["results"][0]["status"] == expected


def test_replay_rejects_changed_packet_and_rechecks_raw_for_new_run(tmp_path):
    data = fixture(tmp_path)
    report = review(data)
    data[4]["decisions"][0]["semantic_decision"] = "UNCERTAIN"
    _json(data[3], data[4])
    with pytest.raises(ValueError, match="inputs"):
        review(data)
    data[4]["decisions"][0]["semantic_decision"] = "SUPPORTS"
    _json(data[3], data[4])
    blob = data[0] / "data/raw/sha256" / data[4]["decisions"][0]["raw_sha256"]
    blob.write_text("Deposits grew by 99 percent")
    with pytest.raises(ValueError, match="current evidence|safety"):
        review(data)
    assert review(data, "review-2")["results"][0]["status"] == "SOURCE_DAMAGED"


def test_self_consistent_upstream_safety_edits_fail(tmp_path):
    data = fixture(tmp_path)
    passage_path = data[1] / "passage_runs/passage-1.json"
    passage = json.loads(passage_path.read_text())
    passage["publication_allowed"] = True
    passage["results"][0]["semantic_status"] = "APPROVED"
    passage.pop("report_id")
    from src.kb_runtime.claim_lineage import _hash_json
    passage["report_id"] = _hash_json(passage)
    _json(passage_path, passage)
    data[4]["passage_report_id"] = passage["report_id"]
    _json(data[3], data[4])
    with pytest.raises(ValueError, match="safety"):
        review(data)


def test_invalid_run_id_and_tampered_frozen_review_fail(tmp_path):
    data = fixture(tmp_path)
    with pytest.raises(ValueError, match="run_id"):
        review(data, "../outside")
    review(data)
    report_path = data[1] / "claim_review_runs/review-1.json"
    report = json.loads(report_path.read_text())
    report["publication_allowed"] = True
    _json(report_path, report)
    with pytest.raises(ValueError, match="digest"):
        review(data)


def test_self_consistent_future_claim_date_cannot_pass(tmp_path):
    data = fixture(tmp_path)
    claim_path = data[1] / "claim_runs/claim-1.json"
    passage_path = data[1] / "passage_runs/passage-1.json"
    from src.kb_runtime.claim_lineage import _hash_json
    claim = json.loads(claim_path.read_text())
    claim["claims"][0]["as_of"] = "2026-10-01"
    claim.pop("report_id")
    claim["report_id"] = _hash_json(claim)
    _json(claim_path, claim)
    passage = json.loads(passage_path.read_text())
    passage["claim_report_id"] = claim["report_id"]
    passage.pop("report_id")
    passage["report_id"] = _hash_json(passage)
    _json(passage_path, passage)
    data[4]["claim_report_id"] = claim["report_id"]
    data[4]["passage_report_id"] = passage["report_id"]
    _json(data[3], data[4])
    assert review(data)["results"][0]["status"] == "AFTER_CUTOFF"


def two_claims(tmp_path):
    data = fixture(tmp_path)
    project, state, catalog, packet_path, packet = data
    claims_path = tmp_path / "claims.json"
    claims = json.loads(claims_path.read_text())
    second = dict(claims["claims"][0], claim_id="growth-2",
                  statement="SBI deposits grew by 12 percent in June 2026, revised view.")
    claims["claims"].append(second)
    _json(claims_path, claims)
    claim_report = evaluate_claims(claims_path, state / "refresh_runs/source-1.json",
                                   project, state, "claim-2")
    passage_path = tmp_path / "passages.json"
    passages = json.loads(passage_path.read_text())
    passages["quotes"].append({"claim_id": "growth-2",
                                "verbatim_quote": passages["quotes"][0]["verbatim_quote"]})
    _json(passage_path, passages)
    passage_report = evaluate_passages(passage_path, state / "claim_runs/claim-2.json",
                                      project, state, "passage-2")
    packet["claim_report_id"] = claim_report["report_id"]
    packet["passage_report_id"] = passage_report["report_id"]
    packet["decisions"].append(dict(packet["decisions"][0], claim_id="growth-2"))
    _json(packet_path, packet)
    return data


def review_two(data, run_id="review-2"):
    project, state, catalog, packet_path, _ = data
    return review_claims(packet_path, state / "claim_runs/claim-2.json",
                         state / "passage_runs/passage-2.json", project, catalog,
                         state, run_id)


def test_open_conflict_blocks_related_claim_too(tmp_path):
    data = two_claims(tmp_path)
    first = data[4]["decisions"][0]
    first.update(contradiction_status="CONFLICT_OPEN", related_claim_ids=["growth-2"],
                 conflict_explanation="This claim conflicts with the revised view.")
    _json(data[3], data[4])
    result = review_two(data)
    assert [item["status"] for item in result["results"]] == ["CONFLICT_OPEN", "CONFLICT_OPEN"]
    assert [item["status"] for item in result["gaps"]] == ["OPEN", "OPEN"]


def test_resolved_conflict_requires_named_claim_and_reason(tmp_path):
    data = two_claims(tmp_path)
    first = data[4]["decisions"][0]
    first["contradiction_status"] = "CONFLICT_RESOLVED"
    _json(data[3], data[4])
    with pytest.raises(ValueError, match="related claims"):
        review_two(data)
    first["related_claim_ids"] = ["growth-2"]
    first["conflict_explanation"] = "Claims describe the same June 2026 period; first filing controls."
    _json(data[3], data[4])
    result = review_two(data)
    assert [item["status"] for item in result["results"]] == ["INTERNAL_REVIEWED", "INTERNAL_REVIEWED"]


def test_self_consistent_forged_gap_id_fails(tmp_path):
    data = fixture(tmp_path)
    claim_path = data[1] / "claim_runs/claim-1.json"
    passage_path = data[1] / "passage_runs/passage-1.json"
    from src.kb_runtime.claim_lineage import _hash_json
    claim = json.loads(claim_path.read_text())
    claim["gaps"][0]["gap_id"] = "someone-elses-gap"
    claim.pop("report_id")
    claim["report_id"] = _hash_json(claim)
    _json(claim_path, claim)
    passage = json.loads(passage_path.read_text())
    passage["claim_report_id"] = claim["report_id"]
    passage.pop("report_id")
    passage["report_id"] = _hash_json(passage)
    _json(passage_path, passage)
    data[4]["claim_report_id"] = claim["report_id"]
    data[4]["passage_report_id"] = passage["report_id"]
    _json(data[3], data[4])
    with pytest.raises(ValueError, match="gap safety"):
        review(data)


def test_self_consistent_review_status_and_gap_edit_fails(tmp_path):
    data = fixture(tmp_path, claim_type="DERIVED")
    review(data)
    report_path = data[1] / "claim_review_runs/review-1.json"
    report = json.loads(report_path.read_text())
    report["results"][0]["status"] = "INTERNAL_REVIEWED"
    report["gaps"][0]["status"] = "CLOSED_BY_REVIEW"
    report["gaps"][0]["reason"] = "INTERNAL_REVIEWED"
    report.pop("report_id")
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    report["report_id"] = digest
    report["gaps"][0]["review_report_id"] = digest
    _json(report_path, report)
    with pytest.raises(ValueError, match="safety"):
        review(data)


def test_self_consistent_replay_cannot_rewrite_reviewer_decision(tmp_path):
    data = fixture(tmp_path)
    data[4]["decisions"][0]["semantic_decision"] = "DOES_NOT_SUPPORT"
    _json(data[3], data[4])
    assert review(data)["results"][0]["status"] == "SEMANTIC_REJECTED"
    report_path = data[1] / "claim_review_runs/review-1.json"
    report = json.loads(report_path.read_text())
    report["results"][0]["decision"]["semantic_decision"] = "SUPPORTS"
    report["results"][0]["status"] = "INTERNAL_REVIEWED"
    report["gaps"][0]["status"] = "CLOSED_BY_REVIEW"
    report["gaps"][0]["reason"] = "INTERNAL_REVIEWED"
    report.pop("report_id")
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    report["report_id"] = digest
    report["gaps"][0]["review_report_id"] = digest
    _json(report_path, report)
    with pytest.raises(ValueError, match="safety"):
        review(data)


def _forge_internal_status(report_path):
    report = json.loads(report_path.read_text())
    report["results"][0]["status"] = "INTERNAL_REVIEWED"
    report["gaps"][0]["status"] = "CLOSED_BY_REVIEW"
    report["gaps"][0]["reason"] = "INTERNAL_REVIEWED"
    report.pop("report_id")
    for gap in report["gaps"]:
        gap.pop("review_report_id", None)
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    report["report_id"] = digest
    report["gaps"][0]["review_report_id"] = digest
    _json(report_path, report)


@pytest.mark.parametrize("change,blocked", [
    ({"reviewed_at": "2026-09-29T11:00:00+05:30"}, "REVIEW_AFTER_CUTOFF"),
    ({"rights_use": "BLOCKED"}, "RIGHTS_BLOCKED"),
])
def test_replay_recomputes_blocked_gate_before_returning(tmp_path, change, blocked):
    data = fixture(tmp_path)
    data[4]["decisions"][0].update(change)
    _json(data[3], data[4])
    assert review(data)["results"][0]["status"] == blocked
    _forge_internal_status(data[1] / "claim_review_runs/review-1.json")
    with pytest.raises(ValueError, match="current evidence|safety"):
        review(data)


def test_review_cannot_precede_filing_and_identity_review(tmp_path):
    data = fixture(tmp_path)
    data[4]["decisions"][0]["reviewed_at"] = "2026-09-28T10:05:30+05:30"
    _json(data[3], data[4])
    result = review(data)
    assert result["results"][0]["status"] == "REVIEW_BEFORE_EVIDENCE"
    assert result["gaps"][0]["status"] == "OPEN"


def test_claim_lineage_cannot_promote_blocked_source_report(tmp_path):
    data = fixture(tmp_path)
    state = data[1]
    from src.kb_runtime.claim_lineage import _hash_json
    source_path = state / "refresh_runs/source-1.json"
    source = json.loads(source_path.read_text())
    source["status"] = "SOURCE_BLOCKED"
    source["sources"][0]["status"] = "STALE"
    source.pop("report_id")
    source["report_id"] = _hash_json(source)
    _json(source_path, source)
    claim_path = state / "claim_runs/claim-1.json"
    claim = json.loads(claim_path.read_text())
    claim["source_report_id"] = source["report_id"]
    claim.pop("report_id")
    claim["report_id"] = _hash_json(claim)
    _json(claim_path, claim)
    passage_path = state / "passage_runs/passage-1.json"
    passage = json.loads(passage_path.read_text())
    passage["claim_report_id"] = claim["report_id"]
    passage.pop("report_id")
    passage["report_id"] = _hash_json(passage)
    _json(passage_path, passage)
    data[4]["claim_report_id"] = claim["report_id"]
    data[4]["passage_report_id"] = passage["report_id"]
    _json(data[3], data[4])
    with pytest.raises(ValueError, match="source report"):
        review(data)


def test_replay_rejects_rehashed_entity_and_cutoff_edit(tmp_path):
    data = fixture(tmp_path)
    review(data)
    report_path = data[1] / "claim_review_runs/review-1.json"
    report = json.loads(report_path.read_text())
    report["entity"] = "HDFC"
    report["cutoff_timestamp"] = "2026-09-29T18:00:00+05:30"
    report.pop("report_id")
    report["gaps"][0].pop("review_report_id")
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    report["report_id"] = digest
    report["gaps"][0]["review_report_id"] = digest
    _json(report_path, report)
    with pytest.raises(ValueError, match="safety"):
        review(data)


def test_replay_recomputes_related_open_conflict(tmp_path):
    data = two_claims(tmp_path)
    data[4]["decisions"][0].update(
        contradiction_status="CONFLICT_OPEN", related_claim_ids=["growth-2"],
        conflict_explanation="The two statements conflict.")
    _json(data[3], data[4])
    assert [item["status"] for item in review_two(data)["results"]] == ["CONFLICT_OPEN", "CONFLICT_OPEN"]
    report_path = data[1] / "claim_review_runs/review-2.json"
    report = json.loads(report_path.read_text())
    report["results"][1]["status"] = "INTERNAL_REVIEWED"
    report["gaps"][1]["status"] = "CLOSED_BY_REVIEW"
    report["gaps"][1]["reason"] = "INTERNAL_REVIEWED"
    report.pop("report_id")
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    report["report_id"] = digest
    report["gaps"][1]["review_report_id"] = digest
    _json(report_path, report)
    with pytest.raises(ValueError, match="current evidence"):
        review_two(data)


def test_review_claims_cli_writes_internal_report(tmp_path):
    project, state, catalog, packet_path, _ = fixture(tmp_path)
    result = subprocess.run([
        sys.executable, "-m", "src.kb_runtime", "review-claims",
        "--packet", str(packet_path),
        "--claim-report", str(state / "claim_runs/claim-1.json"),
        "--passage-report", str(state / "passage_runs/passage-1.json"),
        "--project-dir", str(project), "--catalog", str(catalog),
        "--state-dir", str(state), "--run-id", "review-cli",
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["results"][0]["status"] == "INTERNAL_REVIEWED"
    assert report["publication_allowed"] is False
