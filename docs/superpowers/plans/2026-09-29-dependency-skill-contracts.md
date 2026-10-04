# Dependency and Skill Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the reviewed evidence chain through a validated, versioned DAG contract with a durable execution trace.

**Architecture:** A workflow JSON pins three separate versioned skill contract files by SHA-256. A runner loads all four files, validates the graph and each skill's handler/input/output/cutoff rules before execution, verifies each frozen output and parent link, and resumes by replaying only an incomplete idempotent stage.

**Tech Stack:** Python standard library, JSON, pytest.

**Spec:** `docs/superpowers/specs/2026-09-29-dependency-skill-contracts-design.md`

## Global Constraints

- First slice is `refresh -> passages -> review` only; adapt the review handler to the actual shipped 05 interface.
- Every trace and output keeps `publication_allowed: false`; preserve the fixture-only `company-research` gate.
- No arbitrary imports, commands, model-selected handlers, network fetch, research publication, or learning stage.
- Keep legacy agent contracts and `config/workflow.yaml` as descriptive material; do not claim they execute.
- Stage only this task's files, verify affected and full checks, review the staged diff, then deliver under KB Git rules.

## Review Focus

- A syntactically valid workflow with a cycle, missing skill file, wrong skill digest, or wrong input type must fail before stage one.
- A digest-valid but unsafe or cross-entity parent report must not satisfy a dependency.
- An existing output without a state receipt after a crash must be adopted only after full verification.
- A source or claim blocked for evidence quality must produce a blocked diagnostic, not a success or publication claim.
- A changed packet or contract under one run ID must fail without altering prior frozen reports.

### Task 1: Contract loader and graph validation

**Files:** Create `projects/indian-equities/config/runtime_contracts/evidence_review.v1.json`, `evidence_refresh.v1.json`, `passage_presence.v1.json`, and `claim_integrity_review.v1.json` in that directory; create `src/kb_runtime/evidence_workflow.py` and `tests/test_evidence_workflow.py`.

**Interfaces:** `load_contract(path: Path) -> tuple[dict, str, dict[str, tuple[dict, str]]]` returns the validated workflow, its byte digest, and loaded skill contracts with byte digests keyed by stage ID. `plan_stages(contract: dict) -> tuple[str, ...]` returns the validated topological order. The handler registry is a fixed code map for the three shipped operations.

- [x] Contract tests cover the three-node order, invalid pins/paths/schemas/handlers/policies/dependencies, missing skills, and unsafe graphs before execution.
- [x] The workflow loader verifies all four contracts, exact byte digests, strict fields, and fixed stage-to-skill bindings without dynamic handlers.
- [x] Verified: `python3 -m pytest tests/test_evidence_workflow.py -q` → 41 passed.

### Task 2: Frozen input and artifact verification

**Files:** Extend `src/kb_runtime/evidence_workflow.py` and `tests/test_evidence_workflow.py`; expose narrow report loader functions from existing modules only where needed.

**Interfaces:** `run_evidence_workflow(source_request: Path, claim_request: Path, passage_packet: Path, review_packet: Path | None, contract_path: Path, project_dir: Path, catalog: Path, state_dir: Path, run_id: str) -> dict` returns a run trace with stage receipts and `publication_allowed: False`. A first call without the review packet pauses after refresh and passages; a later call resumes with a review packet bound to their exact report IDs.

- [x] Synthetic three-stage tests cover entity/cutoff, report IDs, child and parent bindings, contract identities, unsafe artifacts, and two-phase review resume.
- [x] Existing evaluators run in contract order; each frozen output is reloaded and checked before the next stage completes.
- [x] Verified: `python3 -m pytest tests/test_evidence_workflow.py -q` → 41 passed.

### Task 3: Replay, retry, and durable trace

**Files:** Extend `src/kb_runtime/evidence_workflow.py` and `tests/test_evidence_workflow.py`.

- [x] Replay, changed input/contract/relevant filing rows, pre-output and post-output failures, tampered artifacts, and retry behavior have focused coverage.
- [x] Trace state is atomic, binds workflow/skill/input and relevant catalog-row hashes, re-verifies completed artifacts, and retries runtime failures once while validation errors stop immediately.
- [x] Verified: `python3 -m pytest tests/test_evidence_workflow.py -q` → 42 passed.

### Task 4: CLI, documentation, and delivery

**Files:** Modify `src/kb_runtime/__main__.py` and `projects/indian-equities/README.md`; extend `tests/test_evidence_workflow.py`. Update the program status only after the implemented acceptance tests pass.

- [x] CLI test covers the required input paths, optional review packet, explicit contract, state/catalog/project paths, run ID, and JSON trace.
- [x] README documents invocation, contract activation, limits of legacy agent documents, and disabled downstream stages.
- [x] Verified 2026-10-04: focused tests → 42 passed; full suite `python3 -m pytest -q` → 627 passed, 2 skipped.

**Slice status:** Complete for the reviewed three-stage evidence workflow. Review now binds only the filing rows used for direct claims, so unrelated catalog writes do not break replay. Analysis, publication, and learning stages remain unavailable by design.

## Acceptance

An executed synthetic evidence workflow has a validated contract identity, verified stage outputs, immutable parent bindings, and a resumable trace. Missing or damaged artifacts block dependents. Neither a successful trace nor a reviewed claim enables real publication.
