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

- [ ] Write failing tests for the exact three-node contract, stage order, missing or changed skill file, wrong pinned digest, outside-directory path, unknown field/version/handler, duplicate IDs, wrong entity/cutoff policy, missing or wrong typed dependency, and cycle. Assert no handler ran.
- [ ] Run `python3 -m pytest tests/test_evidence_workflow.py -q` and confirm the intended failures.
- [ ] Load all four files, verify each skill byte digest against its workflow reference, and validate strict JSON schemas plus the fixed stage-to-skill binding. Use no dynamic import or path supplied handler.
- [ ] Rerun the focused tests and confirm the contract tests pass.

### Task 2: Frozen input and artifact verification

**Files:** Extend `src/kb_runtime/evidence_workflow.py` and `tests/test_evidence_workflow.py`; expose narrow report loader functions from existing modules only where needed.

**Interfaces:** `run_evidence_workflow(source_request: Path, claim_request: Path, passage_packet: Path, review_packet: Path | None, contract_path: Path, project_dir: Path, catalog: Path, state_dir: Path, run_id: str) -> dict` returns a run trace with stage receipts and `publication_allowed: False`. A first call without the review packet pauses after refresh and passages; a later call resumes with a review packet bound to their exact report IDs.

- [ ] Write failing tests for a synthetic three-stage run, exact entity/cutoff, report IDs, source and claim child reports, parent links, and trace workflow/skill path, digest, handler, and version identities.
- [ ] Add failing cases for missing, damaged, forged-safe, wrong-entity, wrong-cutoff, wrong-parent-ID, or wrong-type artifacts; assert no later handler executes.
- [ ] Run the focused tests to observe the intended failures.
- [ ] Invoke the existing evaluators in contract order. Re-read each frozen output with its module's safety checks and verify upstream IDs before recording completion. Preserve blocked diagnostic statuses without treating them as approval.
- [ ] Rerun focused tests and confirm these cases pass.

### Task 3: Replay, retry, and durable trace

**Files:** Extend `src/kb_runtime/evidence_workflow.py` and `tests/test_evidence_workflow.py`.

- [ ] Write failing tests for exact replay, changed input or contract with the same run ID, failure before stage output, failure after output but before trace write, tampered completed output on resume, and blocked dependent execution.
- [ ] Run the focused tests and confirm the intended failures.
- [ ] Persist atomic trace state in `state/workflow_runs/<run_id>/state.json`, bind workflow, three skill, and input hashes, and resume only after re-verifying completed artifacts. Give runtime failures one recorded automatic retry; do not retry validation failures.
- [ ] Rerun focused tests and confirm replay, retry, and crash recovery pass without duplicate frozen output.

### Task 4: CLI, documentation, and delivery

**Files:** Modify `src/kb_runtime/__main__.py` and `projects/indian-equities/README.md`; extend `tests/test_evidence_workflow.py`. Update the program status only after the implemented acceptance tests pass.

- [ ] Write a failing CLI test for `run-evidence-workflow` with explicit contract, three required input paths, optional review packet, project/catalog/state directories, and run ID.
- [ ] Run the CLI test to confirm failure, add the command, and rerun it to confirm the JSON trace and blocked publication field.
- [ ] Document the command, contract activation meaning, old agent-document limit, and disabled downstream stages.
- [ ] Run focused checks and `python3 -m pytest -q`; inspect failures and fix causes before rerun.
- [ ] Get an independent code/design review. Inspect `git status`, task diff, staged paths, and `git diff --cached --check`; commit and push only owned completed files through the repository delivery process.

## Acceptance

An executed synthetic evidence workflow has a validated contract identity, verified stage outputs, immutable parent bindings, and a resumable trace. Missing or damaged artifacts block dependents. Neither a successful trace nor a reviewed claim enables real publication.
