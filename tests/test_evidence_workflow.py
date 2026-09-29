"""Executable evidence workflow contract and replay checks."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

from src.kb_runtime.evidence_workflow import load_contract, plan_stages
from src.kb_runtime.evidence_workflow import run_evidence_workflow
from src.kb_runtime.__main__ import main
from src.kb_runtime.evidence_refresh import refresh_evidence
from src.kb_runtime.passage_evidence import evaluate_passages
from src.kb_runtime.source_store import record_source


CONTRACT_DIR = Path(__file__).resolve().parents[1] / "projects/indian-equities/config/runtime_contracts"


def _copy_contracts(tmp_path):
    for path in CONTRACT_DIR.glob("*.json"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    return tmp_path / "evidence_review.v1.json"


def _write(path, data):
    path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")


def _change_skill(path, skill_name, change):
    workflow = json.loads(path.read_text())
    stage = next(stage for stage in workflow["stages"] if stage["stage_id"] == skill_name)
    skill_path = path.parent / stage["skill_contract_path"]
    skill = json.loads(skill_path.read_text())
    change(skill)
    _write(skill_path, skill)
    stage["skill_contract_sha256"] = hashlib.sha256(skill_path.read_bytes()).hexdigest()
    _write(path, workflow)


def test_shipped_contract_loads_three_pinned_skills():
    workflow, digest, skills = load_contract(CONTRACT_DIR / "evidence_review.v1.json")
    assert plan_stages(workflow) == ("refresh", "passages", "review")
    assert len(digest) == 64
    assert set(skills) == {"refresh", "passages", "review"}
    assert [skills[stage][0]["handler"] for stage in plan_stages(workflow)] == [
        "refresh_evidence", "evaluate_passages", "review_claims",
    ]


def test_cli_runs_two_phase_evidence_workflow(tmp_path, monkeypatch, capsys):
    project, state, sources, claims, passages, reviews = _inputs(tmp_path)
    args = ["kb_runtime", "run-evidence-workflow", "--source-request", str(sources),
            "--claims", str(claims), "--passage-packet", str(passages),
            "--contract", str(CONTRACT_DIR / "evidence_review.v1.json"),
            "--project-dir", str(project), "--catalog", str(project / "catalog.sqlite"),
            "--state-dir", str(state), "--run-id", "flow-1"]
    monkeypatch.setattr(sys, "argv", args)
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "AWAITING_REVIEW"
    monkeypatch.setattr(sys, "argv", args + ["--review-packet", str(reviews)])
    assert main() == 0
    complete = json.loads(capsys.readouterr().out)
    assert complete["status"] == "COMPLETE"
    assert complete["publication_allowed"] is False


@pytest.mark.parametrize("mutation", [
    lambda data: data["stages"][0].update(skill_contract_sha256="0" * 64),
    lambda data: data["stages"][0].update(skill_contract_path="../../outside.json"),
    lambda data: data["stages"][0].update(stage_id="review"),
    lambda data: data["stages"][2].update(depends_on=["passages"]),
    lambda data: data["stages"][0].update(depends_on=["review"]),
    lambda data: data.update(version=2),
    lambda data: data.update(publication_allowed=True),
    lambda data: data.update(extra="unsafe"),
])
def test_workflow_rejects_unsafe_graph_before_execution(tmp_path, mutation):
    path = _copy_contracts(tmp_path)
    data = json.loads(path.read_text())
    mutation(data)
    _write(path, data)
    with pytest.raises(ValueError):
        load_contract(path)


@pytest.mark.parametrize("field,value", [
    ("handler", "os.system"),
    ("output_type", "claim_review_report"),
    ("required_inputs", ["source_request"]),
    ("entity_policy", "ANY"),
    ("cutoff_policy", "BACKDATE"),
    ("retry_policy", "UNLIMITED"),
    ("publication_allowed", True),
    ("version", 2),
    ("extra", "unsafe"),
])
def test_skill_contract_rejects_unsafe_binding_even_with_updated_digest(tmp_path, field, value):
    path = _copy_contracts(tmp_path)
    _change_skill(path, "refresh", lambda skill: skill.update({field: value}))
    with pytest.raises(ValueError):
        load_contract(path)


def test_missing_skill_file_fails_before_execution(tmp_path):
    path = _copy_contracts(tmp_path)
    (tmp_path / "passage_presence.v1.json").unlink()
    with pytest.raises(ValueError):
        load_contract(path)


def _inputs(tmp_path, run_id="flow-1", make_review=True):
    project, state, seed = tmp_path / "project", tmp_path / "state", tmp_path / "seed"
    metadata = tmp_path / "source-metadata.json"
    _write(metadata, {"source_id": "SBI_TEXT", "entity": "SBI",
                      "source_kind": "COMPANY_PRESENTATION", "url": "https://example.org/sbi.txt",
                      "source_date": "2026-08-07", "observed_at": "2026-09-28T10:00:00+05:30",
                      "retrieved_at": "2026-09-28T10:05:00+05:30"})
    raw = tmp_path / "source.txt"
    raw.write_text("Deposits grew by 12 percent.\n", encoding="utf-8")
    version = record_source(metadata, raw, project)
    cutoff = "2026-09-28T18:00:00+05:30"
    source_request = tmp_path / "sources.json"
    _write(source_request, {"entity": "SBI", "cutoff_timestamp": cutoff,
                            "required_sources": [{"source_id": "SBI_TEXT", "max_age_days": 60}]})
    claim_request = tmp_path / "claims.json"
    _write(claim_request, {"entity": "SBI", "cutoff_timestamp": cutoff,
                           "claims": [{"claim_id": "growth", "claim_type": "REPORTED_FACT",
                                       "statement": "Deposits grew", "as_of": "2026-06-30",
                                       "source_id": "SBI_TEXT", "version_id": version["version_id"],
                                       "passage_locator": "sentence 1"}]})
    passage_packet = tmp_path / "passages.json"
    _write(passage_packet, {"entity": "SBI", "cutoff_timestamp": cutoff,
                            "quotes": [{"claim_id": "growth", "verbatim_quote": "Deposits grew"}]})
    # The packet pins the IDs that an independent, deterministic evidence pass will produce.
    review_packet = None
    if make_review:
        manifest = refresh_evidence(source_request, claim_request, project, seed, run_id)
        passage = evaluate_passages(passage_packet, seed / "claim_runs" / f"{run_id}.json",
                                    project, seed, run_id)
        review_packet = tmp_path / "review.json"
        _write(review_packet, {"entity": "SBI", "cutoff_timestamp": cutoff,
                               "claim_report_id": manifest["claim_report_id"],
                               "passage_report_id": passage["report_id"], "decisions": []})
    return project, state, source_request, claim_request, passage_packet, review_packet


def _run(data, run_id="flow-1", contract=None):
    project, state, sources, claims, passages, reviews = data
    return run_evidence_workflow(sources, claims, passages, reviews,
                                 contract or CONTRACT_DIR / "evidence_review.v1.json",
                                 project, project / "catalog.sqlite", state, run_id)


def test_workflow_runs_in_order_and_freezes_blocked_internal_trace(tmp_path):
    data = _inputs(tmp_path)
    trace = _run(data)
    assert trace["publication_allowed"] is False
    assert trace["entity"] == "SBI"
    assert trace["cutoff_timestamp"] == "2026-09-28T18:00:00+05:30"
    assert [item["stage_id"] for item in trace["stages"]] == ["refresh", "passages", "review"]
    assert [item["output_type"] for item in trace["stages"]] == [
        "evidence_manifest", "passage_report", "claim_review_report"]
    assert all(item["status"] == "COMPLETE" for item in trace["stages"])
    assert trace["stages"][1]["parent_ids"] == [trace["stages"][0]["child_ids"]["claim_report_id"]]
    assert trace["stages"][2]["parent_ids"] == [
        trace["stages"][0]["child_ids"]["claim_report_id"],
        trace["stages"][1]["output_id"]]
    assert json.loads((data[1] / "workflow_runs/flow-1/state.json").read_text()) == trace
    assert _run(data) == trace


def test_changed_input_rejects_replay_before_mutating_reports(tmp_path):
    data = _inputs(tmp_path)
    trace = _run(data)
    packet = data[4]
    changed = json.loads(packet.read_text())
    changed["quotes"][0]["verbatim_quote"] = "by 12 percent"
    _write(packet, changed)
    with pytest.raises(ValueError, match="run_id|input"):
        _run(data)
    assert json.loads((data[1] / "workflow_runs/flow-1/state.json").read_text()) == trace


def test_tampered_completed_report_blocks_replay(tmp_path):
    data = _inputs(tmp_path)
    _run(data)
    report_path = data[1] / "passage_runs/flow-1.json"
    report = json.loads(report_path.read_text())
    report["publication_allowed"] = True
    _write(report_path, report)
    with pytest.raises(ValueError):
        _run(data)


def test_self_consistent_unsafe_passage_report_blocks_replay(tmp_path):
    data = _inputs(tmp_path)
    _run(data)
    report_path = data[1] / "passage_runs/flow-1.json"
    report = json.loads(report_path.read_text())
    report["publication_allowed"] = True
    body = {key: value for key, value in report.items() if key != "report_id"}
    report["report_id"] = hashlib.sha256(json.dumps(body, sort_keys=True,
                                separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    _write(report_path, report)
    with pytest.raises(ValueError, match="safety"):
        _run(data)


def test_rehashed_passage_cannot_replace_bound_quote(tmp_path):
    data = _inputs(tmp_path, make_review=False)
    packet = json.loads(data[4].read_text())
    packet["quotes"][0]["verbatim_quote"] = "NOT IN RAW"
    _write(data[4], packet)
    _run(data)
    report_path = data[1] / "passage_runs/flow-1.json"
    report = json.loads(report_path.read_text())
    report["results"][0].update(verbatim_quote="Deposits grew", status="QUOTE_PRESENT",
                                 byte_offset=0)
    report["report_id"] = hashlib.sha256(json.dumps(
        {key: value for key, value in report.items() if key != "report_id"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    _write(report_path, report)
    trace_path = data[1] / "workflow_runs/flow-1/state.json"
    trace = json.loads(trace_path.read_text())
    trace["stages"][1]["output_id"] = report["report_id"]
    _write(trace_path, trace)
    with pytest.raises(ValueError, match="quote"):
        _run(data)


def test_rehashed_manifest_cannot_change_diagnostics(tmp_path):
    data = _inputs(tmp_path, make_review=False)
    _run(data)
    path = data[1] / "evidence_runs/flow-1.json"
    manifest = json.loads(path.read_text())
    manifest["source_changes"][0]["status"] = "BLOCKED"
    manifest["manifest_id"] = hashlib.sha256(json.dumps(
        {key: value for key, value in manifest.items() if key != "manifest_id"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    _write(path, manifest)
    trace_path = data[1] / "workflow_runs/flow-1/state.json"
    trace = json.loads(trace_path.read_text())
    trace["stages"][0]["output_id"] = manifest["manifest_id"]
    _write(trace_path, trace)
    with pytest.raises(ValueError, match="manifest"):
        _run(data)


def test_rehashed_claim_cannot_change_gap_policy(tmp_path):
    import src.kb_runtime.evidence_workflow as workflow

    data = _inputs(tmp_path, make_review=False)
    _run(data)
    claim_path = data[1] / "claim_runs/flow-1.json"
    claim = json.loads(claim_path.read_text())
    claim["gaps"][0]["web_resolvable"] = True
    claim["gaps"][0]["resolution_type"] = "OPEN_WEB"
    claim["report_id"] = hashlib.sha256(json.dumps(
        {key: value for key, value in claim.items() if key != "report_id"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    _write(claim_path, claim)
    manifest_path = data[1] / "evidence_runs/flow-1.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["claim_report_id"] = claim["report_id"]
    manifest["manifest_id"] = hashlib.sha256(json.dumps(
        {key: value for key, value in manifest.items() if key != "manifest_id"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    _write(manifest_path, manifest)
    with pytest.raises(ValueError, match="gaps"):
        workflow._verify_refresh(data[1], "flow-1", "SBI", manifest["cutoff_timestamp"],
                                 json.loads(data[2].read_text()), json.loads(data[3].read_text()),
                                 data[2], data[3], data[0])


def test_trace_rejects_changed_recorded_input_hash(tmp_path):
    data = _inputs(tmp_path, make_review=False)
    _run(data)
    path = data[1] / "workflow_runs/flow-1/state.json"
    trace = json.loads(path.read_text())
    trace["stages"][0]["input_hashes"]["source_request"] = "0" * 64
    _write(path, trace)
    with pytest.raises(ValueError, match="completed stage"):
        _run(data)


def test_missing_completed_artifact_blocks_replay(tmp_path):
    data = _inputs(tmp_path)
    _run(data)
    (data[1] / "claim_runs/flow-1.json").unlink()
    with pytest.raises((ValueError, OSError)):
        _run(data)


def test_existing_frozen_output_is_adopted_after_trace_crash(tmp_path):
    data = _inputs(tmp_path)
    project, state, sources, claims, _, _ = data
    manifest = refresh_evidence(sources, claims, project, state, "flow-1")
    trace = _run(data)
    assert trace["stages"][0]["output_id"] == manifest["manifest_id"]
    assert len(list((state / "evidence_runs").glob("flow-1.json"))) == 1


def test_changed_valid_contract_cannot_reuse_run_id(tmp_path):
    data = _inputs(tmp_path)
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    contract = _copy_contracts(contracts_dir)
    trace = _run(data, contract=contract)
    # Changing a pinned file and repinning it creates a valid new contract identity.
    skill_path = contracts_dir / "passage_presence.v1.json"
    skill_path.write_bytes(skill_path.read_bytes() + b"\n")
    workflow = json.loads(contract.read_text())
    workflow["stages"][1]["skill_contract_sha256"] = hashlib.sha256(skill_path.read_bytes()).hexdigest()
    _write(contract, workflow)
    with pytest.raises(ValueError, match="run_id"):
        _run(data, contract=contract)
    assert json.loads((data[1] / "workflow_runs/flow-1/state.json").read_text()) == trace


def test_wrong_packet_type_fails_before_any_output(tmp_path):
    data = _inputs(tmp_path)
    _write(data[4], {"entity": "SBI", "cutoff_timestamp": "2026-09-28T18:00:00+05:30",
                     "quotes": "wrong type"})
    with pytest.raises(ValueError, match="packet|quotes"):
        _run(data)
    assert not (data[1] / "evidence_runs/flow-1.json").exists()


@pytest.mark.parametrize("tamper", [
    lambda trace: trace["stages"][0].update(handler="os.system"),
    lambda trace: trace["stages"][0].update(output_path="/tmp/forged.json"),
    lambda trace: trace["stages"].append(trace["stages"][0]),
])
def test_forged_trace_cannot_activate_a_stage(tmp_path, tamper):
    data = _inputs(tmp_path)
    _run(data)
    state_path = data[1] / "workflow_runs/flow-1/state.json"
    trace = json.loads(state_path.read_text())
    tamper(trace)
    _write(state_path, trace)
    with pytest.raises(ValueError):
        _run(data)


def test_transient_failure_before_output_retries_only_refresh(tmp_path, monkeypatch):
    import src.kb_runtime.evidence_workflow as workflow

    data = _inputs(tmp_path)
    real_refresh = workflow.refresh_evidence
    calls = 0

    def transient(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("temporary disk error")
        return real_refresh(*args, **kwargs)

    monkeypatch.setattr(workflow, "refresh_evidence", transient)
    trace = _run(data)
    assert calls == 2
    assert [item["status"] for item in trace["stages"][0]["attempts"]] == ["FAILED", "COMPLETE"]
    assert [len(item["attempts"]) for item in trace["stages"][1:]] == [1, 1]


def test_failure_after_frozen_output_adopts_it_on_retry(tmp_path, monkeypatch):
    import src.kb_runtime.evidence_workflow as workflow

    data = _inputs(tmp_path)
    real_write = workflow._atomic_state
    failed = False

    def fail_after_output(path, state):
        nonlocal failed
        if not failed and state["stages"] and state["stages"][0]["status"] == "COMPLETE":
            failed = True
            raise OSError("trace write interrupted")
        return real_write(path, state)

    monkeypatch.setattr(workflow, "_atomic_state", fail_after_output)
    trace = _run(data)
    assert failed
    assert [item["status"] for item in trace["stages"][0]["attempts"]] == ["FAILED", "COMPLETE"]
    assert len(list((data[1] / "evidence_runs").glob("flow-1.json"))) == 1


def test_fresh_run_waits_for_human_review_then_resumes_with_frozen_parent_ids(tmp_path):
    data = _inputs(tmp_path, make_review=False)
    waiting = _run(data)
    assert waiting["status"] == "AWAITING_REVIEW"
    assert [item["stage_id"] for item in waiting["stages"]] == ["refresh", "passages"]
    assert not (data[1] / "claim_review_runs/flow-1.json").exists()
    manifest = json.loads((data[1] / "evidence_runs/flow-1.json").read_text())
    passage = json.loads((data[1] / "passage_runs/flow-1.json").read_text())
    review = tmp_path / "review-after-passages.json"
    _write(review, {"entity": "SBI", "cutoff_timestamp": "2026-09-28T18:00:00+05:30",
                    "claim_report_id": manifest["claim_report_id"],
                    "passage_report_id": passage["report_id"], "decisions": []})
    resumed = (*data[:-1], review)
    complete = _run(resumed)
    assert complete["status"] == "COMPLETE"
    assert len(complete["stages"]) == 3
    assert complete["stages"][0] == waiting["stages"][0]
    assert complete["stages"][1] == waiting["stages"][1]
    assert complete["bindings"]["inputs"]["review_packet"]
    assert _run(resumed) == complete
    changed = json.loads(review.read_text())
    changed["decisions"] = [{"claim_id": "growth"}]
    _write(review, changed)
    with pytest.raises(ValueError, match="run_id|input"):
        _run(resumed)


def test_invalid_parent_does_not_bind_later_review_packet(tmp_path):
    data = _inputs(tmp_path, make_review=False)
    waiting = _run(data)
    manifest = json.loads((data[1] / "evidence_runs/flow-1.json").read_text())
    passage_path = data[1] / "passage_runs/flow-1.json"
    passage = json.loads(passage_path.read_text())
    review = tmp_path / "review-after-passages.json"
    _write(review, {"entity": "SBI", "cutoff_timestamp": waiting["cutoff_timestamp"],
                    "claim_report_id": manifest["claim_report_id"],
                    "passage_report_id": passage["report_id"], "decisions": []})
    passage_path.write_text(passage_path.read_text().replace("QUOTE_PRESENT", "QUOTE_ABSENT"))
    with pytest.raises(ValueError):
        _run((*data[:-1], review))
    trace = json.loads((data[1] / "workflow_runs/flow-1/state.json").read_text())
    assert trace == waiting


def test_wrong_review_parent_does_not_bind_packet_or_prevent_correction(tmp_path):
    data = _inputs(tmp_path, make_review=False)
    waiting = _run(data)
    review = tmp_path / "review.json"
    _write(review, {"entity": "SBI", "cutoff_timestamp": "2026-09-28T18:00:00+05:30",
                    "claim_report_id": "0" * 64, "passage_report_id": "0" * 64,
                    "decisions": []})
    resumed = (*data[:-1], review)
    with pytest.raises(ValueError, match="parent|binding"):
        _run(resumed)
    assert json.loads((data[1] / "workflow_runs/flow-1/state.json").read_text()) == waiting
    manifest = json.loads((data[1] / "evidence_runs/flow-1.json").read_text())
    passage = json.loads((data[1] / "passage_runs/flow-1.json").read_text())
    _write(review, {"entity": "SBI", "cutoff_timestamp": "2026-09-28T18:00:00+05:30",
                    "claim_report_id": manifest["claim_report_id"],
                    "passage_report_id": passage["report_id"], "decisions": []})
    assert _run(resumed)["status"] == "COMPLETE"


def test_rehashed_manifest_and_trace_cannot_invent_blocked_source_status(tmp_path):
    data = _inputs(tmp_path, make_review=False)
    _run(data)
    manifest_path = data[1] / "evidence_runs/flow-1.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["source_status"] = "SOURCE_BLOCKED"
    body = {key: value for key, value in manifest.items() if key != "manifest_id"}
    manifest["manifest_id"] = hashlib.sha256(json.dumps(body, sort_keys=True,
                                   separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    _write(manifest_path, manifest)
    trace_path = data[1] / "workflow_runs/flow-1/state.json"
    trace = json.loads(trace_path.read_text())
    trace["stages"][0]["output_id"] = manifest["manifest_id"]
    _write(trace_path, trace)
    with pytest.raises(ValueError, match="safety|status"):
        _run(data)
