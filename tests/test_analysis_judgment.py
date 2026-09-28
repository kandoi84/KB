"""Synthetic, internal-only analysis worksheet contract."""

import hashlib
import json

import pytest

from test_claim_review import fixture as review_fixture, review, _json, _source
from src.kb_runtime.metric_store import register_filing_metrics
from src.kb_runtime.identity_store import register_identity
from src.kb_runtime.source_store import record_source
from src.kb_runtime.analysis_judgment import analyze_judgment, load_analysis_inputs, _previous_report
from src.kb_runtime.claim_lineage import _hash_json


def setup(tmp_path):
    data = review_fixture(tmp_path)
    reviewed = review(data)
    project, state, catalog, _, _ = data
    metric_source = _source(tmp_path, project, "NUMERIC", "EXCHANGE_FILING", b"Revenue statement", "2026-09-28T10:00:00+05:30")
    register_filing_metrics(_json(tmp_path / "metric.json", {
        "filing_id": "F2", "issuer_id": "SBI", "isin": "INE062A01020",
        "source_id": "NUMERIC", "version_id": metric_source["version_id"],
        "document_type": "RESULTS", "period_end": "2026-06-30",
        "published_at": "2026-09-28T10:00:00+05:30",
        "first_seen_at": "2026-09-28T10:05:00+05:30",
        "rights_status": "REVIEWED", "reviewer_id": "analyst-1",
        "reviewed_at": "2026-09-28T10:06:00+05:30",
        "review_decision": "CONFIRMED", "evidence_locator": "reported revenue row",
        "supersedes_filing_id": None,
        "metrics": [{"metric_id": "M1", "metric_name": "revenue",
                     "value_decimal": "12.5", "unit": "INR_CRORE",
                     "period_end": "2026-06-30", "period_kind": "QUARTER",
                     "reporting_scope": "CONSOLIDATED", "value_kind": "REPORTED",
                     "evidence_locator": "reported revenue row", "supersedes_metric_id": None}],
    }), project, catalog)
    model = project / "Model" / "model.txt"
    model.parent.mkdir(parents=True)
    model.write_text("synthetic analyst model assumptions")
    packet = {
        "issuer_id": "SBI", "isin": "INE062A01020",
        "cutoff_timestamp": "2026-09-28T18:00:00+05:30",
        "claim_review_report_id": reviewed["report_id"],
        "analyst_id": "analyst-1", "prepared_at": "2026-09-28T12:00:00+05:30",
        "layers": [{"layer": layer, "current_state": f"{layer} demand is stable",
                    "transmission": "Demand supports the next operating layer",
                    "claim_ids": ["growth"], "metric_ids": [], "unknown_reason": None}
                   for layer in ("macro", "sector", "industry", "company")],
        "metric_refs": [{"isin": "INE062A01020", "metric_name": "revenue",
                         "period_end": "2026-06-30", "period_kind": "QUARTER",
                         "reporting_scope": "CONSOLIDATED", "unit": "INR_CRORE",
                         "value_kind": "REPORTED", "metric_id": "M1",
                         "filing_id": "F2", "value_decimal": "12.5"}],
        "most_likely_path": {"horizon_end": "2029-09-28", "hypothesis": "Deposits fund stable lending growth",
                             "driver_ids": ["deposit-growth", "loan-demand"],
                             "claim_ids": ["growth"], "metric_ids": ["M1"],
                             "falsifiers": ["Funding growth fails to support loan demand"]},
        "base_fair_value": {"value_decimal": "100", "unit": "INR_PER_SHARE",
                            "value_kind": "ANALYST_ESTIMATE", "method": "DCF",
                            "model_snapshot_id": "model-v1", "model_path": "Model/model.txt",
                            "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
                            "as_of": "2026-09-28T12:00:00+05:30",
                            "rationale": "Lending returns and reinvestment support the explicit base estimate"},
        "debates": [{"debate_id": "D1", "driver_id": "deposit-cost",
                     "occurrence": "Deposit costs remain lower than assumed",
                     "probability": "0.25", "incremental_impact": "20",
                     "claim_ids": ["growth"], "metric_ids": ["M1"],
                     "rationale": "Funding costs change earnings beyond the base path",
                     "falsifier": "Deposit repricing is faster than expected",
                     "incremental_attestation": True, "correlation": "NONE_KNOWN"}],
        "valuation_range": {"low": "80", "high": "130", "method": "SENSITIVITY",
                            "rationale": "Funding cost and long-run margins move the value range",
                            "fragility_drivers": ["Deposit pricing", "Long-run margin"]},
        "quality_trajectory": {"status": "STABLE", "explanation": "The deposit franchise remains durable under base assumptions", "evidence_ids": ["growth"]},
        "valuation_fragility": {"status": "HIGH", "explanation": "Discounted value is sensitive to funding costs", "evidence_ids": ["M1"]},
        "catalysts": [{"catalyst_id": "C1", "event": "Next funding update",
                       "window_start": "2027-01-01", "window_end": "2027-06-30",
                       "probability": "0.3", "affected_kpi": "Deposit cost",
                       "earnings_link": "Lower funding cost increases net interest income",
                       "valuation_link": "Higher earnings raise intrinsic value",
                       "debate_id": "D1", "claim_ids": ["growth"], "metric_ids": ["M1"],
                       "double_count_disposition": "VALUE_ALREADY_IN_DEBATE"}],
        "no_catalyst_reason": None,
        "judgment": {"premortem": "Funding costs spike while loan quality weakens over the long horizon",
                     "premortem_horizon_end": "2030-09-28",
                     "falsifiers": ["Credit losses exceed the base path"],
                     "earnings_engine": "Deposits fund loans and spreads create recurring earnings",
                     "value_drivers": ["Deposit cost", "Loan growth"],
                     "mechanism_chain": {"catalyst": "C1", "kpi": "Deposit cost",
                                         "earnings": "Net interest income rises",
                                         "valuation": "Cash flow value rises"},
                     "bias_checks": {name: {"status": "CHECKED", "reason": f"Compared contrary evidence for {name} bias and challenged assumptions"}
                                     for name in ("confirmation", "anchoring", "recency", "availability", "overconfidence", "narrative", "authority", "loss_aversion", "sunk_cost")},
                     "incentives": "Management rewards may favor growth over credit quality",
                     "second_order": "Faster growth can require more risk capital",
                     "circle_of_competence": "Deposit pricing is familiar but credit losses remain uncertain",
                     "opportunity_cost": "Other banks require a separate current valuation comparison",
                     "hammer_check": "The same funding diagnosis would not fit a nonbank lender",
                     "price_assessment": "NOT_ASSESSED", "alternatives_assessment": "NOT_ASSESSED",
                     "optionality_assessment": "NOT_ASSESSED"},
    }
    return project, state, catalog, state / "claim_review_runs/review-1.json", _json(tmp_path / "analysis.json", packet), packet, model


def run(data, run_id="analysis-1"):
    project, state, catalog, claim, packet_path, _, _ = data
    return analyze_judgment(packet_path, claim, project, catalog, state, run_id)


def test_calculation_is_internal_and_exact(tmp_path):
    data = setup(tmp_path)
    report = run(data)
    assert report["analysis_status"] == "CALCULATED_MODEL_UNVERIFIED"
    assert report["probability_weighted_fair_value"] == "105.00"
    assert report["publication_allowed"] is False
    assert report["judgment_status"] == "HUMAN_REVIEW_REQUIRED"
    assert report["market_price_status"] == "NOT_ASSESSED"
    assert report["metric_leaves"][0]["metric_id"] == "M1"
    assert report["worksheet"]["valuation_range"]["low"] == "80"
    assert report["worksheet"]["judgment"]["premortem"] == data[5]["judgment"]["premortem"]
    assert run(data) == report


@pytest.mark.parametrize("field,value", [("probability", "1.1"), ("correlation", "SHARED_WITH_OTHER"), ("incremental_attestation", False)])
def test_invalid_debate_cannot_be_summed(tmp_path, field, value):
    data = setup(tmp_path)
    data[5]["debates"][0][field] = value
    _json(data[4], data[5])
    with pytest.raises(ValueError):
        run(data)
    assert not (data[1] / "analysis_runs/analysis-1.json").exists()


def test_changed_model_or_packet_blocks_replay(tmp_path):
    data = setup(tmp_path)
    run(data)
    data[6].write_text("changed model bytes")
    with pytest.raises(ValueError, match="model|inputs"):
        run(data)


def test_forged_reviewed_status_does_not_authorize_claim(tmp_path):
    data = setup(tmp_path)
    claim = json.loads(data[3].read_text())
    claim["results"][0]["status"] = "INTERNAL_REVIEWED"
    claim["results"][0]["decision"]["semantic_decision"] = "UNCERTAIN"
    from src.kb_runtime.claim_lineage import _hash_json
    claim["packet_hash"] = _hash_json({"entity": claim["entity"], "cutoff_timestamp": claim["cutoff_timestamp"], "claim_report_id": claim["claim_report_id"], "passage_report_id": claim["passage_report_id"], "decisions": [claim["results"][0]["decision"]]})
    claim.pop("report_id")
    claim["report_id"] = _hash_json({k: v for k, v in claim.items() if k != "gaps"} | {"gaps": [{k: v for k, v in gap.items() if k != "review_report_id"} for gap in claim["gaps"]]})
    claim["gaps"][0]["review_report_id"] = claim["report_id"]
    _json(data[3], claim)
    data[5]["claim_review_report_id"] = claim["report_id"]
    _json(data[4], data[5])
    with pytest.raises(ValueError, match="review|evidence|safety"):
        run(data)


def test_missing_bias_check_and_generic_judgment_fail(tmp_path):
    data = setup(tmp_path)
    del data[5]["judgment"]["bias_checks"]["confirmation"]
    _json(data[4], data[5])
    with pytest.raises(ValueError, match="bias"):
        run(data)
    data[5]["judgment"]["bias_checks"]["confirmation"] = {"status": "CHECKED", "reason": "Looks good"}
    _json(data[4], data[5])
    with pytest.raises(ValueError, match="generic|reason"):
        run(data)


def test_forged_review_decision_cannot_change_quote_anchor(tmp_path):
    data = setup(tmp_path)
    claim = json.loads(data[3].read_text())
    claim["results"][0]["decision"]["verbatim_quote"] = "A different statement"
    from src.kb_runtime.claim_lineage import _hash_json
    claim["packet_hash"] = _hash_json({"entity": claim["entity"], "cutoff_timestamp": claim["cutoff_timestamp"], "claim_report_id": claim["claim_report_id"], "passage_report_id": claim["passage_report_id"], "decisions": [claim["results"][0]["decision"]]})
    claim.pop("report_id")
    claim["report_id"] = _hash_json({k: v for k, v in claim.items() if k != "gaps"} | {"gaps": [{k: v for k, v in gap.items() if k != "review_report_id"} for gap in claim["gaps"]]})
    claim["gaps"][0]["review_report_id"] = claim["report_id"]
    _json(data[3], claim)
    data[5]["claim_review_report_id"] = claim["report_id"]
    _json(data[4], data[5])
    with pytest.raises(ValueError, match="passage|review|safety"):
        run(data)


def test_missing_exact_metric_blocks_value_without_publication(tmp_path):
    data = setup(tmp_path)
    data[5]["metric_refs"][0]["value_decimal"] = "13"
    _json(data[4], data[5])
    result = run(data)
    assert result["analysis_status"] == "BLOCKED_EVIDENCE"
    assert result["probability_weighted_fair_value"] is None
    assert result["publication_allowed"] is False


def test_replay_rejects_tampered_frozen_report(tmp_path):
    data = setup(tmp_path)
    run(data)
    path = data[1] / "analysis_runs/analysis-1.json"
    stored = json.loads(path.read_text())
    stored["publication_allowed"] = True
    _json(path, stored)
    with pytest.raises(ValueError, match="existing analysis report"):
        run(data)


def test_repeated_bias_explanation_is_not_a_check(tmp_path):
    data = setup(tmp_path)
    for entry in data[5]["judgment"]["bias_checks"].values():
        entry["reason"] = "Compared contrary evidence and challenged the assumption"
    _json(data[4], data[5])
    with pytest.raises(ValueError, match="bias"):
        run(data)


def test_empty_metric_set_does_not_support_valuation(tmp_path):
    data = setup(tmp_path)
    data[5]["metric_refs"] = []
    for layer in data[5]["layers"]:
        layer["metric_ids"] = []
    data[5]["most_likely_path"]["metric_ids"] = []
    data[5]["debates"][0]["metric_ids"] = []
    data[5]["valuation_fragility"]["evidence_ids"] = ["growth"]
    data[5]["catalysts"][0]["metric_ids"] = []
    _json(data[4], data[5])
    with pytest.raises(ValueError, match="metric"):
        run(data)


def test_no_evidenced_catalyst_stays_explicit(tmp_path):
    data = setup(tmp_path)
    data[5]["catalysts"] = []
    data[5]["no_catalyst_reason"] = "No dated company event is supported by current reviewed evidence"
    data[5]["judgment"]["mechanism_chain"]["catalyst"] = "NO_EVIDENCED_CATALYST"
    _json(data[4], data[5])
    report = run(data)
    assert report["worksheet"]["no_catalyst_reason"] == data[5]["no_catalyst_reason"]
    assert report["publication_allowed"] is False


def test_premortem_horizon_must_be_three_to_five_years(tmp_path):
    data = setup(tmp_path)
    data[5]["judgment"]["premortem_horizon_end"] = "2027-09-28"
    _json(data[4], data[5])
    with pytest.raises(ValueError, match="premortem horizon"):
        run(data)


def test_new_run_links_exact_previous_report(tmp_path):
    data = setup(tmp_path)
    first = run(data)
    data[5]["previous_report_id"] = first["report_id"]
    _json(data[4], data[5])
    second = run(data, "analysis-2")
    assert second["previous_report_id"] == first["report_id"]
    assert second["report_id"] != first["report_id"]
    assert json.loads((data[1] / "analysis_runs/analysis-1.json").read_text()) == first


def test_previous_report_link_rejects_missing_parent(tmp_path):
    data = setup(tmp_path)
    data[5]["previous_report_id"] = "0" * 64
    _json(data[4], data[5])
    with pytest.raises(ValueError, match="previous report"):
        run(data, "analysis-2")


def test_previous_report_link_rejects_explicit_null(tmp_path):
    data = setup(tmp_path)
    data[5]["previous_report_id"] = None
    _json(data[4], data[5])
    with pytest.raises(ValueError, match="previous report"):
        run(data, "analysis-2")
    assert not (data[1] / "analysis_runs/analysis-2.json").exists()


def test_previous_report_link_rejects_tampered_parent(tmp_path):
    data = setup(tmp_path)
    first = run(data)
    path = data[1] / "analysis_runs/analysis-1.json"
    damaged = json.loads(path.read_text())
    damaged["publication_allowed"] = True
    _json(path, damaged)
    data[5]["previous_report_id"] = first["report_id"]
    _json(data[4], data[5])
    with pytest.raises(ValueError, match="previous report"):
        run(data, "analysis-2")


def test_previous_report_link_rechecks_parent_model_bytes(tmp_path):
    data = setup(tmp_path)
    first = run(data)
    data[6].write_text("new synthetic model assumptions")
    data[5]["base_fair_value"]["model_sha256"] = hashlib.sha256(data[6].read_bytes()).hexdigest()
    data[5]["previous_report_id"] = first["report_id"]
    _json(data[4], data[5])
    with pytest.raises(ValueError, match="previous report"):
        run(data, "analysis-2")
    assert not (data[1] / "analysis_runs/analysis-2.json").exists()


def test_metric_from_other_reviewed_issuer_cannot_support_packet(tmp_path):
    data = setup(tmp_path)
    project, state, catalog = data[:3]
    metadata = _json(tmp_path / "hdfc-identity-source.json", {
        "source_id": "HDFC_IDENT", "entity": "HDFC", "source_kind": "EXCHANGE_SECURITY_FILE",
        "url": "https://example.org/hdfc-identity", "source_date": "2026-09-28",
        "observed_at": "2026-09-28T09:00:00+05:30",
        "retrieved_at": "2026-09-28T10:05:00+05:30"})
    raw = tmp_path / "hdfc-identity.txt"
    raw.write_text("HDFC INE040A01034")
    identity = record_source(metadata, raw, project)
    register_identity(_json(tmp_path / "hdfc-identity.json", {
        "issuer_id": "HDFC", "legal_name": "HDFC Bank", "isin": "INE040A01034",
        "security_type": "EQUITY", "listed_from": "1995-01-01", "listed_to": None,
        "exchange": "NSE", "symbol": "HDFCBANK", "valid_from": "1995-01-01", "valid_to": None,
        "announced_at": "2026-09-28T09:00:00+05:30", "first_seen_at": "2026-09-28T10:05:00+05:30",
        "source_id": "HDFC_IDENT", "version_id": identity["version_id"],
        "reviewer_id": "analyst-1", "reviewed_at": "2026-09-28T10:06:00+05:30",
        "review_decision": "CONFIRMED", "evidence_locator": "exchange identity row"}), project, catalog)
    metadata = _json(tmp_path / "hdfc-filing-source.json", {
        "source_id": "HDFC_NUMERIC", "entity": "HDFC", "source_kind": "EXCHANGE_FILING",
        "url": "https://example.org/hdfc-results", "source_date": "2026-09-28",
        "observed_at": "2026-09-28T10:00:00+05:30",
        "retrieved_at": "2026-09-28T10:05:00+05:30"})
    raw = tmp_path / "hdfc-results.txt"
    raw.write_text("HDFC revenue")
    filing = record_source(metadata, raw, project)
    request = json.loads((tmp_path / "metric.json").read_text())
    request.update({"issuer_id": "HDFC", "isin": "INE040A01034", "source_id": "HDFC_NUMERIC",
                    "version_id": filing["version_id"], "filing_id": "HDFC_F1"})
    request["metrics"][0].update({"metric_id": "HDFC_M1"})
    register_filing_metrics(_json(tmp_path / "hdfc-filing.json", request), project, catalog)
    data[5]["isin"] = "INE040A01034"
    data[5]["metric_refs"][0].update({"isin": "INE040A01034", "metric_id": "HDFC_M1",
                                       "filing_id": "HDFC_F1"})
    data[5]["most_likely_path"]["metric_ids"] = ["HDFC_M1"]
    data[5]["debates"][0]["metric_ids"] = ["HDFC_M1"]
    data[5]["catalysts"][0]["metric_ids"] = ["HDFC_M1"]
    data[5]["valuation_fragility"]["evidence_ids"] = ["HDFC_M1"]
    _json(data[4], data[5])
    with pytest.raises(ValueError, match="issuer|ISIN"):
        run(data)
    assert not (state / "analysis_runs/analysis-1.json").exists()


@pytest.mark.parametrize("path,value", [
    (("most_likely_path",), None),
    (("most_likely_path", "horizon_end"), None),
    (("base_fair_value",), []),
    (("base_fair_value", "model_path"), []),
    (("debates",), None),
    (("debates",), [None]),
    (("valuation_range",), None),
    (("quality_trajectory",), None),
    (("catalysts",), [None]),
    (("catalysts", 0, "window_start"), None),
    (("judgment",), None),
    (("judgment", "mechanism_chain"), None),
    (("judgment", "bias_checks"), None),
    (("judgment", "premortem_horizon_end"), None),
    (("metric_refs", 0, "period_end"), None),
])
def test_malformed_nested_packet_is_value_error_without_report(tmp_path, path, value):
    data = setup(tmp_path)
    target = data[5]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    _json(data[4], data[5])
    with pytest.raises(ValueError):
        run(data)
    assert not (data[1] / "analysis_runs/analysis-1.json").exists()


def test_non_object_layer_is_value_error_without_report(tmp_path):
    data = setup(tmp_path)
    data[5]["layers"].append(None)
    _json(data[4], data[5])
    with pytest.raises(ValueError, match="layers"):
        run(data)
    assert not (data[1] / "analysis_runs/analysis-1.json").exists()


@pytest.mark.parametrize("path,value", [
    (("base_fair_value", "method"), []),
    (("quality_trajectory", "status"), {}),
    (("catalysts", 0, "debate_id"), []),
    (("judgment", "mechanism_chain", "catalyst"), {}),
    (("judgment", "bias_checks", "confirmation", "status"), []),
])
def test_unhashable_choice_is_value_error_without_report(tmp_path, path, value):
    data = setup(tmp_path)
    target = data[5]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    _json(data[4], data[5])
    with pytest.raises(ValueError):
        run(data)
    assert not (data[1] / "analysis_runs/analysis-1.json").exists()


@pytest.mark.parametrize("damage", ["missing", "altered"])
def test_revision_chain_rejects_damaged_grandparent(tmp_path, damage):
    data = setup(tmp_path)
    first = run(data)
    data[5]["previous_report_id"] = first["report_id"]
    _json(data[4], data[5])
    second = run(data, "analysis-2")
    ancestor_path = data[1] / "analysis_runs/analysis-1.json"
    if damage == "missing":
        ancestor_path.unlink()
    else:
        damaged = json.loads(ancestor_path.read_text())
        damaged["publication_allowed"] = True
        _json(ancestor_path, damaged)
    data[5]["previous_report_id"] = second["report_id"]
    _json(data[4], data[5])
    with pytest.raises(ValueError, match="previous report"):
        run(data, "analysis-3")
    assert not (data[1] / "analysis_runs/analysis-3.json").exists()


def test_revision_link_rejects_self_consistent_false_blocked_status(tmp_path):
    data = setup(tmp_path)
    run(data)
    path = data[1] / "analysis_runs/analysis-1.json"
    previous = json.loads(path.read_text())
    previous["analysis_status"] = "BLOCKED_EVIDENCE"
    previous["report_id"] = _hash_json({key: value for key, value in previous.items()
                                        if key != "report_id"})
    _json(path, previous)
    data[5]["previous_report_id"] = previous["report_id"]
    _json(data[4], data[5])
    with pytest.raises(ValueError, match="previous report"):
        run(data, "analysis-2")
    assert not (data[1] / "analysis_runs/analysis-2.json").exists()


def test_revision_chain_rejects_cycle_and_excessive_depth(tmp_path):
    data = setup(tmp_path)
    first = run(data)
    data[5]["previous_report_id"] = first["report_id"]
    with pytest.raises(ValueError, match="cycle"):
        _previous_report(data[5], data[1], data[0], data[2],
                         "analysis-2", frozenset({first["report_id"]}))
    with pytest.raises(ValueError, match="64 revisions"):
        _previous_report(data[5], data[1], data[0], data[2],
                         "analysis-2", frozenset(f"{i:064x}" for i in range(64)))
