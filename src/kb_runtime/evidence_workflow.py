"""Execute the fixed evidence DAG from pinned, versioned skill contracts."""

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .claim_lineage import _claim_status, _gap, _hash_json as _claim_hash
from .claim_lineage import _read_request as _read_claim_request
from .claim_lineage import load_claim_report
from .claim_review import _evaluate as _review_evaluate
from .claim_review import catalog_review_digest
from .claim_review import _packet as _review_packet
from .claim_review import _read_existing as _read_review
from .claim_review import _upstream as _review_upstream
from .claim_review import review_claims
from .evidence_refresh import _claim_impacts, _read_manifest, _source_changes, refresh_evidence
from .passage_evidence import _hash_json as _passage_hash
from .passage_evidence import _presence, _read_frozen as _read_passage
from .passage_evidence import _read_packet as _read_passage_packet
from .passage_evidence import evaluate_passages
from .source_refresh import _hash_json as _source_hash
from .source_refresh import _read_request as _read_source_request
from .source_refresh import _source_status, load_refresh_report


_BINDINGS = {
    "refresh": ("evidence_refresh.v1.json", "evidence_refresh", "refresh_evidence",
                ["source_request", "claim_request"], "evidence_manifest", []),
    "passages": ("passage_presence.v1.json", "passage_presence", "evaluate_passages",
                 ["passage_packet", "claim_report"], "passage_report", ["refresh"]),
    "review": ("claim_integrity_review.v1.json", "claim_integrity_review", "review_claims",
               ["review_packet", "claim_report", "passage_report"], "claim_review_report",
               ["refresh", "passages"]),
}
_WORKFLOW_FIELDS = {"contract_id", "version", "workflow_id", "stages", "publication_allowed"}
_STAGE_FIELDS = {"stage_id", "skill_contract_path", "skill_contract_sha256", "depends_on"}
_SKILL_FIELDS = {"skill_id", "version", "handler", "required_inputs", "output_type",
                 "entity_policy", "cutoff_policy", "retry_policy", "publication_allowed"}
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}\Z")


def _read_json(path):
    try:
        raw = Path(path).read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid or missing contract: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError("contract must be a JSON object")
    return value, hashlib.sha256(raw).hexdigest()


def plan_stages(contract: dict) -> tuple[str, ...]:
    """Validate the exact first-slice DAG and return its stable topological order."""
    if not isinstance(contract, dict) or set(contract) != _WORKFLOW_FIELDS:
        raise ValueError("workflow fields are invalid")
    if (contract["contract_id"] != "indian_equities_evidence_review"
            or type(contract["version"]) is not int or contract["version"] != 1
            or contract["workflow_id"] != "evidence_review_v1"
            or contract["publication_allowed"] is not False
            or not isinstance(contract["stages"], list) or len(contract["stages"]) != 3):
        raise ValueError("workflow identity or safety policy is invalid")
    stages = {}
    for stage in contract["stages"]:
        if not isinstance(stage, dict) or set(stage) != _STAGE_FIELDS:
            raise ValueError("stage fields are invalid")
        name = stage["stage_id"]
        if not isinstance(name, str) or name not in _BINDINGS or name in stages:
            raise ValueError("stage ID is invalid or duplicate")
        filename, _, _, _, _, deps = _BINDINGS[name]
        if (stage["skill_contract_path"] != filename
                or not isinstance(stage["skill_contract_sha256"], str)
                or not _DIGEST.fullmatch(stage["skill_contract_sha256"])
                or stage["depends_on"] != deps):
            raise ValueError("stage dependency or skill pin is invalid")
        stages[name] = stage
    if set(stages) != set(_BINDINGS):
        raise ValueError("workflow stages are incomplete")
    return tuple(_BINDINGS)


def load_contract(path: Path) -> tuple[dict, str, dict[str, tuple[dict, str]]]:
    """Load and pin all handler contracts before any stage can run."""
    path = Path(path)
    workflow, workflow_digest = _read_json(path)
    order = plan_stages(workflow)
    by_id = {item["stage_id"]: item for item in workflow["stages"]}
    skills = {}
    seen = set()
    directory = path.parent.resolve()
    for name in order:
        stage = by_id[name]
        filename, skill_id, handler, required_inputs, output_type, _ = _BINDINGS[name]
        skill_path = path.parent / stage["skill_contract_path"]
        if skill_path.resolve().parent != directory or skill_path.name != filename:
            raise ValueError("skill contract path escapes contract directory")
        skill, digest = _read_json(skill_path)
        if digest != stage["skill_contract_sha256"]:
            raise ValueError("skill contract digest differs from pin")
        if (set(skill) != _SKILL_FIELDS or skill.get("skill_id") != skill_id
                or skill_id in seen or type(skill.get("version")) is not int
                or skill["version"] != 1 or skill["handler"] != handler
                or skill["required_inputs"] != required_inputs
                or skill["output_type"] != output_type
                or skill["entity_policy"] != "EXACT_RUN_ENTITY"
                or skill["cutoff_policy"] != "EXACT_RUN_CUTOFF"
                or skill["retry_policy"] != "REPLAY_IDEMPOTENT"
                or skill["publication_allowed"] is not False):
            raise ValueError("skill contract binding or safety policy is invalid")
        seen.add(skill_id)
        skills[name] = skill, digest
    return workflow, workflow_digest, skills


def _input(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"workflow input is missing or invalid: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError("workflow input must be a JSON object")
    return value, hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                            ensure_ascii=False).encode("utf-8")).hexdigest()


def _atomic_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".incoming-", delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(state, output, indent=2, sort_keys=True, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _timestamp():
    return datetime.now(timezone.utc).isoformat()


def _valid_interval(start, finish):
    try:
        started, finished = datetime.fromisoformat(start), datetime.fromisoformat(finish)
    except (TypeError, ValueError):
        return False
    return (started.utcoffset() is not None and finished.utcoffset() is not None
            and started <= finished)


def _verify_refresh(state_dir, run_id, entity, cutoff, source_request, claim_request,
                    source_request_path, claim_request_path,
                    project_dir):
    manifest = _read_manifest(state_dir / "evidence_runs" / f"{run_id}.json")
    source = load_refresh_report(state_dir / "refresh_runs" / f"{run_id}.json")
    claim = load_claim_report(state_dir / "claim_runs" / f"{run_id}.json")
    if (manifest.get("run_id") != run_id or source.get("run_id") != run_id
            or claim.get("run_id") != run_id
            or any(item.get("entity") != entity or item.get("cutoff_timestamp") != cutoff
                   for item in (manifest, source, claim))
            or manifest.get("publication_allowed") is not False
            or manifest.get("previous_run_id") is not None
            or manifest.get("source_report_id") != source.get("report_id")
            or manifest.get("claim_report_id") != claim.get("report_id")
            or manifest.get("source_status") != source.get("status")
            or manifest.get("claim_status") != claim.get("status")
            or claim.get("source_report_id") != source.get("report_id")
            or source.get("request_hash") != _source_hash(source_request)
            or claim.get("request_hash") != _claim_hash(claim_request)
            or manifest.get("source_request_hash") != source.get("request_hash")
            or manifest.get("claim_request_hash") != claim.get("request_hash")
            or manifest.get("source_changes") != _source_changes(None, source)
            or manifest.get("claim_impacts") != _claim_impacts(
                None, claim, _source_changes(None, source))
            or source.get("status") not in {"SOURCE_READY", "SOURCE_BLOCKED"}
            or claim.get("status") != "CLAIMS_BLOCKED"
            or not isinstance(source.get("sources"), list)
            or not isinstance(claim.get("claims"), list)
            or not isinstance(claim.get("gaps"), list)
            or manifest.get("open_gap_ids") != [gap.get("gap_id") for gap in claim["gaps"]
                                                if isinstance(gap, dict) and gap.get("status") == "OPEN"]):
        raise ValueError("refresh manifest safety fields or parent bindings are invalid")
    _, source_cutoff = _read_source_request(source_request_path)
    _, claim_cutoff = _read_claim_request(claim_request_path)
    if source["sources"] != [_source_status(target, project_dir, source_cutoff)
                              for target in source_request["required_sources"]]:
        raise ValueError("source report differs from current raw evidence")
    if source["status"] != ("SOURCE_READY" if all(item.get("status") == "CURRENT"
                                                     for item in source["sources"])
                            else "SOURCE_BLOCKED"):
        raise ValueError("source report status differs from source readiness")
    if claim["claims"] != [_claim_status(item, source, project_dir, claim_cutoff)
                           for item in claim_request["claims"]]:
        raise ValueError("claim report differs from current source evidence")
    if claim["gaps"] != [_gap(item, run_id) for item in claim["claims"]]:
        raise ValueError("claim gaps differ from verified claim lineage")
    return manifest


def _verify_passages(state_dir, run_id, entity, cutoff, packet_path, project_dir,
                     claim_report_id):
    claim = load_claim_report(state_dir / "claim_runs" / f"{run_id}.json")
    packet = _read_passage_packet(packet_path, claim)
    report = _read_passage(state_dir / "passage_runs" / f"{run_id}.json", run_id,
                           _passage_hash(packet), claim_report_id)
    if (report.get("entity") != entity or report.get("cutoff_timestamp") != cutoff
            or len(report["results"]) != len(claim["claims"])):
        raise ValueError("passage report entity, cutoff, or coverage differs")
    by_claim = {item["claim_id"]: item for item in claim["claims"]}
    quotes = {item["claim_id"]: item["verbatim_quote"] for item in packet["quotes"]}
    if len({item.get("claim_id") for item in report["results"]}) != len(report["results"]):
        raise ValueError("passage report has duplicate claims")
    for result in report["results"]:
        item = by_claim.get(result.get("claim_id"))
        if item is None or any(result.get(key) != item.get(key)
                               for key in ("source_id", "version_id", "raw_sha256", "passage_locator")):
            raise ValueError("passage result differs from claim lineage")
        if result.get("verbatim_quote") != quotes.get(result["claim_id"]):
            raise ValueError("passage result quote differs from bound packet")
        actual_status, actual_offset = _presence(item, result.get("verbatim_quote"), project_dir)
        if (result.get("status") != actual_status or result.get("byte_offset") != actual_offset
                or result.get("semantic_status") != "UNVERIFIED"):
            raise ValueError("passage result differs from raw source")
    return report


def _verify_review(state_dir, run_id, entity, cutoff, packet_path, project_dir,
                   catalog_path, claim_report_id, passage_report_id):
    claim_path = state_dir / "claim_runs" / f"{run_id}.json"
    passage_path = state_dir / "passage_runs" / f"{run_id}.json"
    claim, passage = _review_upstream(claim_path, passage_path, state_dir)
    packet, parsed_cutoff = _review_packet(packet_path, claim, passage)
    expected_results, expected_gaps = _review_evaluate(packet, claim, passage, project_dir,
                                                        catalog_path, parsed_cutoff)
    report = _read_review(state_dir / "claim_review_runs" / f"{run_id}.json", packet,
                          claim, passage, run_id, expected_results, expected_gaps)
    if (report.get("entity") != entity or report.get("cutoff_timestamp") != cutoff
            or report.get("claim_report_id") != claim_report_id
            or report.get("passage_report_id") != passage_report_id):
        raise ValueError("review report entity, cutoff, or parent differs")
    return report


def _verify(stage, state_dir, run_id, entity, cutoff, inputs, project_dir, catalog_path,
            prior, expected_catalog_digest):
    if stage == "refresh":
        report = _verify_refresh(state_dir, run_id, entity, cutoff, inputs["source_request"][0],
                                 inputs["claim_request"][0], inputs["source_request"][2],
                                 inputs["claim_request"][2], project_dir)
        return report, [], {"source_report_id": report["source_report_id"],
                            "claim_report_id": report["claim_report_id"]}
    refresh = prior["refresh"]
    claim_id = refresh["child_ids"]["claim_report_id"]
    if stage == "passages":
        report = _verify_passages(state_dir, run_id, entity, cutoff,
                                  inputs["passage_packet"][2], project_dir, claim_id)
        return report, [claim_id], {}
    passage_id = prior["passages"]["output_id"]
    if catalog_review_digest(catalog_path, inputs["claim_request"][0]["claims"]) != expected_catalog_digest:
        raise ValueError("workflow catalog changed during review")
    report = _verify_review(state_dir, run_id, entity, cutoff, inputs["review_packet"][2],
                            project_dir, catalog_path, claim_id, passage_id)
    if catalog_review_digest(catalog_path, inputs["claim_request"][0]["claims"]) != expected_catalog_digest:
        raise ValueError("workflow catalog changed during review")
    return report, [claim_id, passage_id], {}


def run_evidence_workflow(source_request: Path, claim_request: Path, passage_packet: Path,
                          review_packet: Path | None, contract_path: Path, project_dir: Path,
                          catalog: Path, state_dir: Path, run_id: str) -> dict:
    """Run or resume a pinned, internal-only evidence review trace."""
    if not isinstance(run_id, str) or not _SAFE_ID.fullmatch(run_id):
        raise ValueError("run_id is invalid")
    workflow, workflow_digest, skills = load_contract(contract_path)
    paths = {"source_request": Path(source_request), "claim_request": Path(claim_request),
             "passage_packet": Path(passage_packet)}
    if review_packet is not None:
        paths["review_packet"] = Path(review_packet)
    inputs = {}
    for name, path in paths.items():
        value, digest = _input(path)
        inputs[name] = (value, digest, path)
    entity = inputs["source_request"][0].get("entity")
    cutoff = inputs["source_request"][0].get("cutoff_timestamp")
    _read_source_request(paths["source_request"])
    _read_claim_request(paths["claim_request"])
    for value, _, _ in inputs.values():
        if value.get("entity") != entity or value.get("cutoff_timestamp") != cutoff:
            raise ValueError("workflow input entity or cutoff differs")
    passage_value = inputs["passage_packet"][0]
    if (set(passage_value) != {"entity", "cutoff_timestamp", "quotes"}
            or not isinstance(passage_value["quotes"], list)
            or any(not isinstance(item, dict) or set(item) != {"claim_id", "verbatim_quote"}
                   or not isinstance(item["claim_id"], str)
                   or not isinstance(item["verbatim_quote"], str)
                   for item in passage_value["quotes"])):
        raise ValueError("passage packet type is invalid")
    if review_packet is not None:
        review_value = inputs["review_packet"][0]
        if (set(review_value) != {"entity", "cutoff_timestamp", "claim_report_id",
                                  "passage_report_id", "decisions"}
                or not isinstance(review_value["claim_report_id"], str)
                or not isinstance(review_value["passage_report_id"], str)
                or not isinstance(review_value["decisions"], list)
                or any(not isinstance(item, dict) for item in review_value["decisions"])):
            raise ValueError("review packet type is invalid")
    project_dir, catalog, state_dir = Path(project_dir), Path(catalog), Path(state_dir)
    bindings = {"workflow_sha256": workflow_digest,
                "skills": {name: skills[name][1] for name in plan_stages(workflow)},
                "inputs": {name: item[1] for name, item in inputs.items()},
                "catalog_sha256": catalog_review_digest(
                    catalog, inputs["claim_request"][0]["claims"]),
                "entity": entity, "cutoff_timestamp": cutoff, "run_id": run_id}
    state_path = state_dir / "workflow_runs" / run_id / "state.json"
    if state_path.exists():
        state, _ = _read_json(state_path)
        if (state.get("publication_allowed") is not False
                or state.get("contract_path") != str(Path(contract_path).resolve())
                or state.get("workflow_id") != workflow["workflow_id"]
                or state.get("entity") != entity or state.get("cutoff_timestamp") != cutoff
                or state.get("run_id") != run_id
                or state.get("status") not in {"RUNNING", "BLOCKED", "COMPLETE", "AWAITING_REVIEW"}
                or not isinstance(state.get("stages"), list)
                or len(state["stages"]) > 3
                or [item.get("stage_id") if isinstance(item, dict) else None
                    for item in state["stages"]] != list(plan_stages(workflow))[:len(state["stages"])]):
            raise ValueError("workflow trace is invalid")
        prior_bindings = state.get("bindings")
        if prior_bindings != bindings:
            can_add_review = (
                review_packet is not None and isinstance(prior_bindings, dict)
                and state.get("status") == "AWAITING_REVIEW"
                and isinstance(prior_bindings.get("inputs"), dict)
                and "review_packet" not in prior_bindings["inputs"]
                and {**prior_bindings, "inputs": {**prior_bindings["inputs"],
                                                  "review_packet": inputs["review_packet"][1]}} == bindings
            )
            if not can_add_review:
                raise ValueError("run_id cannot be reused with changed workflow input or contract")
            completed = state.get("stages")
            if (not isinstance(completed, list) or len(completed) != 2
                    or [item.get("stage_id") for item in completed] != ["refresh", "passages"]
                    or any(item.get("status") != "COMPLETE" for item in completed)
                    or review_value["claim_report_id"] != completed[0].get("child_ids", {}).get("claim_report_id")
                    or review_value["passage_report_id"] != completed[1].get("output_id")):
                raise ValueError("review packet parent binding differs from frozen stages")
            verified_refresh, _, children = _verify(
                "refresh", state_dir, run_id, entity, cutoff, inputs, project_dir, catalog, {},
                bindings["catalog_sha256"])
            if (completed[0].get("output_id") != verified_refresh.get("manifest_id")
                    or completed[0].get("child_ids") != children):
                raise ValueError("review parent refresh differs from frozen artifact")
            verified_passage, parents, _ = _verify(
                "passages", state_dir, run_id, entity, cutoff, inputs, project_dir, catalog,
                {"refresh": completed[0]}, bindings["catalog_sha256"])
            if (completed[1].get("output_id") != verified_passage.get("report_id")
                    or completed[1].get("parent_ids") != parents):
                raise ValueError("review parent passage differs from frozen artifact")
            claim_report, passage_report = _review_upstream(
                state_dir / "claim_runs" / f"{run_id}.json",
                state_dir / "passage_runs" / f"{run_id}.json", state_dir)
            _review_packet(paths["review_packet"], claim_report, passage_report)
            state["bindings"] = bindings
            state["status"] = "RUNNING"
            _atomic_state(state_path, state)
    else:
        state = {"run_id": run_id, "entity": entity, "cutoff_timestamp": cutoff,
                 "workflow_id": workflow["workflow_id"], "contract_path": str(Path(contract_path).resolve()),
                 "bindings": bindings, "stages": [], "status": "RUNNING",
                 "publication_allowed": False}
        _atomic_state(state_path, state)
    prior = {}
    for stage_id in plan_stages(workflow):
        if stage_id == "review" and review_packet is None:
            state["status"] = "AWAITING_REVIEW"
            _atomic_state(state_path, state)
            return state
        old = next((item for item in state["stages"] if item.get("stage_id") == stage_id), None)
        if old and old.get("status") == "COMPLETE":
            report, parents, children = _verify(stage_id, state_dir, run_id, entity, cutoff,
                                                inputs, project_dir, catalog, prior,
                                                bindings["catalog_sha256"])
            expected_path = state_dir / {"refresh": "evidence_runs", "passages": "passage_runs",
                                         "review": "claim_review_runs"}[stage_id] / f"{run_id}.json"
            if (old.get("output_id") != report.get("manifest_id", report.get("report_id"))
                    or old.get("parent_ids") != parents or old.get("child_ids") != children
                    or old.get("workflow_sha256") != workflow_digest
                    or old.get("skill_sha256") != skills[stage_id][1]
                    or old.get("input_hashes") != {
                        name: inputs[name][1] for name in skills[stage_id][0]["required_inputs"]
                        if name in inputs}
                    or old.get("output_type") != _BINDINGS[stage_id][4]
                    or old.get("output_path") != str(expected_path)
                    or old.get("skill_id") != skills[stage_id][0]["skill_id"]
                    or old.get("handler") != skills[stage_id][0]["handler"]
                    or old.get("version") != skills[stage_id][0]["version"]
                    or old.get("skill_contract_path") != str((Path(contract_path).parent /
                                                              _BINDINGS[stage_id][0]).resolve())
                    or not isinstance(old.get("attempts"), list)
                    or not 1 <= len(old["attempts"]) <= 2
                    or any(not isinstance(item, dict) for item in old["attempts"])
                    or [item.get("number") for item in old["attempts"]] != list(
                        range(1, len(old["attempts"]) + 1))
                    or [item.get("status") for item in old["attempts"][:-1]] != [
                        "FAILED"] * (len(old["attempts"]) - 1)
                    or old["attempts"][-1].get("status") != "COMPLETE"
                    or not _valid_interval(old.get("started_at"), old.get("finished_at"))):
                raise ValueError("completed stage differs from frozen artifact or contract")
            prior[stage_id] = old
            continue
        skill, skill_digest = skills[stage_id]
        stage_input_names = skill["required_inputs"]
        input_hashes = {name: inputs[name][1] for name in stage_input_names if name in inputs}
        receipt = {"stage_id": stage_id, "skill_id": skill["skill_id"],
                   "handler": skill["handler"], "version": skill["version"],
                   "skill_contract_path": str((Path(contract_path).parent /
                                              _BINDINGS[stage_id][0]).resolve()),
                   "skill_sha256": skill_digest, "workflow_sha256": workflow_digest,
                   "input_hashes": input_hashes, "output_type": skill["output_type"],
                   "started_at": _timestamp(), "attempts": [], "status": "RUNNING"}
        if old:
            state["stages"].remove(old)
        state["stages"].append(receipt)
        _atomic_state(state_path, state)
        for attempt in range(1, 3):
            try:
                if stage_id == "refresh":
                    refresh_evidence(source_request, claim_request, project_dir, state_dir, run_id)
                elif stage_id == "passages":
                    evaluate_passages(passage_packet, state_dir / "claim_runs" / f"{run_id}.json",
                                      project_dir, state_dir, run_id)
                else:
                    review_claims(review_packet, state_dir / "claim_runs" / f"{run_id}.json",
                                  state_dir / "passage_runs" / f"{run_id}.json", project_dir,
                                  catalog, state_dir, run_id)
                report, parents, children = _verify(stage_id, state_dir, run_id, entity, cutoff,
                                                    inputs, project_dir, catalog, prior,
                                                    bindings["catalog_sha256"])
                receipt.update(status="COMPLETE", parent_ids=parents, child_ids=children,
                               output_id=report.get("manifest_id", report.get("report_id")),
                               output_path=str(state_dir / {"refresh": "evidence_runs",
                                                            "passages": "passage_runs",
                                                            "review": "claim_review_runs"}[stage_id] /
                                               f"{run_id}.json"), finished_at=_timestamp())
                receipt["attempts"].append({"number": attempt, "status": "COMPLETE"})
                _atomic_state(state_path, state)
                prior[stage_id] = receipt
                break
            except (ValueError, OSError, RuntimeError) as exc:
                if receipt["attempts"] and receipt["attempts"][-1] == {"number": attempt, "status": "COMPLETE"}:
                    receipt["attempts"].pop()
                for field in ("parent_ids", "child_ids", "output_id", "output_path", "finished_at"):
                    receipt.pop(field, None)
                receipt["attempts"].append({"number": attempt, "status": "FAILED",
                                            "reason": type(exc).__name__, "detail": str(exc)})
                receipt["status"] = "FAILED"
                receipt["finished_at"] = _timestamp()
                state["status"] = "BLOCKED"
                _atomic_state(state_path, state)
                if isinstance(exc, ValueError) or attempt == 2:
                    raise
                state["status"] = "RUNNING"
                receipt["status"] = "RUNNING"
                _atomic_state(state_path, state)
    state["status"] = "COMPLETE"
    _atomic_state(state_path, state)
    return state
