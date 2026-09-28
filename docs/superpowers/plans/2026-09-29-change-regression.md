# Change Proposals and Regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze versioned methodology proposals, compare candidate and baseline through a verified regression runner, and record structural approval without changing production.

**Architecture:** A proposal module pins artifacts and 10 eval candidates in immutable receipts. A regression module validates a reviewed manifest and calls only registered artifact-aware adapters. A separate approval receipt records a human decision; no activation API exists in this slice.

**Tech Stack:** Installed Python 3.14.6 standard library, existing immutable report helpers and `retrieval_eval` evidence conventions, pytest 9.1.1. No new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-09-29-change-regression-design.md`.

## Global constraints

- Build after 10's postmortem/eval-candidate contract is stable; require its exact frozen link and reproducible bad-process classification.
- Store prompt, weight, schema, and rule changes as data proposals only. Do not execute untrusted code or arbitrary commands from packets.
- The present runtime has no production active-version registry or general candidate executor. Missing capabilities must give blocked statuses, not fabricated passes.
- Synthetic fixtures can reach `MECHANICS_PASS` only. Reviewed real cases and a genuine artifact-aware adapter are required for `REGRESSION_PASS_FOR_REVIEW`.
- Structural changes require an independent human approval receipt after passing regression. Approval never activates a candidate in 11.
- Preserve `publication_allowed: false`, `live_decision_allowed: false`, and `promotion_status: NOT_EVALUATED` in all outputs.
- Mini spec 12 owns historical investment results and any separate promotion decision.

## Review focus

1. A forged or rehashed 10 eval candidate must fail because its source postmortem and case are replayed (Task 1).
2. A candidate artifact that differs after proposal creation must fail before regression (Task 1).
3. A runner that ignores candidate bytes cannot report a pass (Task 2).
4. Synthetic results, absent real gold, baseline failure, or missing executor cannot become a promotion claim (Task 2).
5. A structural proposal cannot be self-approved or use a stale regression receipt, and no operation changes active files (Task 3).

---

### Task 1: Immutable proposals and input provenance

**Files:** Create `src/kb_runtime/change_proposal.py` and `tests/test_change_proposal.py`.

**Interface:** `register_change_proposal(packet_path: Path, *, baseline_artifact: Path, candidate_artifact: Path, state_dir: Path, case_replay_inputs: Mapping[str, Path]) -> dict`. The strict packet pins proposal/change/version IDs, author/time, changed contract paths, rationale, and zero or more 10 eval candidate IDs. Store artifact bytes under `state_dir/change_artifacts/sha256/<digest>` and receipt at `state_dir/change_proposals/<proposal_id>.json`.

- [ ] Write failing tests for a valid proposal linked to a replay-verified reproducible 10 error, all four allowed change types, exact retry, and changed same-ID conflict.
- [ ] Run `python3 -m pytest -q tests/test_change_proposal.py`; confirm intended failures.
- [ ] Implement strict field/ID/path checks, 10 case/postmortem/candidate replay, source-digest binding, artifact link-once storage, immutable receipt, and permanently false safety flags.
- [ ] Add tests for forged eval candidate, luck/surprise trigger, swapped artifact, baseline/candidate same version, path traversal, and concurrent same-ID creation. Rerun focused tests.

### Task 2: Frozen paired regression and fail-closed adapter registry

**Files:** Create `src/kb_runtime/change_regression.py` and `tests/test_change_regression.py`. Reuse `retrieval_eval` dataset/digest conventions; do not copy its domain scoring into an investment scorer.

**Interface:** `run_change_regression(packet_path: Path, *, state_dir: Path, project_dir: Path, adapter_registry: Mapping[str, RegressionAdapter]) -> dict`. A registered adapter must expose `runner_id`, `runner_version`, `source_sha256`, `supported_change_types`, and `evaluate(artifact_bytes, frozen_case) -> structured result`. Packet pins `run_id`, proposal ID/digest, manifest path/hash, runner ID, and exact baseline/candidate digests. Production registry supplies adapters; packet never supplies code or commands.

- [ ] Write failing tests for strict >=20 unique-case manifest, uniform dataset/rubric, frozen input hashes, paired baseline/candidate execution, per-case outputs, counts, and zero newly failed hard cases. Use a test-only deterministic adapter whose output changes with artifact bytes; label the synthetic result `MECHANICS_PASS`.
- [ ] Run `python3 -m pytest -q tests/test_change_regression.py`; confirm intended failures.
- [ ] Implement manifest validation, registered adapter checks, runner source hash, read-only paired execution, guardrail checks, immutable receipt, and retry semantics. Refuse a pass if adapter consumption of pinned artifact bytes cannot be established.
- [ ] Add tests for missing executor, no artifact effect, baseline failure, missing/duplicate case, future outcome leak, changed runner, mixed dataset, real reviewed sample and reviewer requirement, synthetic cap, changed same-ID run, and active-tree byte equality. Rerun focused tests.
- [ ] Keep all shipped production adapters disabled until a real candidate injection point is implemented and reviewed. A test-only adapter cannot be selected from the CLI or yield `REGRESSION_PASS_FOR_REVIEW`.

### Task 3: Approval receipts, CLI, and contract documentation

**Files:** Create `src/kb_runtime/change_approval.py`, `tests/test_change_approval.py`, and `tests/test_change_cli.py`; modify `src/kb_runtime/__main__.py`, `projects/indian-equities/README.md`, and `docs/superpowers/specs/2026-09-28-kb-mini-spec-program.md`.

**Interface:** `record_change_approval(packet_path: Path, *, state_dir: Path) -> dict`. Packet pins proposal ID/digest, regression run ID/digest, reviewer ID, decision time, `APPROVED|REJECTED`, scope, and rationale. CLI exposes `register-change-proposal`, `run-change-regression`, and `record-change-approval` with explicit paths/IDs, but no activate command.

- [ ] Write failing tests for structural versus nonstructural classification, independent reviewer, stale/missing/failed regression, synthetic-only rejection, exact retry, and changed same-ID conflict.
- [ ] Run focused approval/CLI tests; confirm intended failures.
- [ ] Implement classification from changed contract paths and diff evidence, approval receipt validation, CLI errors/JSON, and README examples. Mark 11 active only as proposal/control plumbing until real regression adapter and reviewed cases exist.
- [ ] Run `python3 -m pytest -q tests/test_change_proposal.py tests/test_change_regression.py tests/test_change_approval.py tests/test_change_cli.py`, then `python3 -m pytest -q`. Fix caused failures and rerun.
- [ ] Ask an independent reviewer to inspect forged provenance, runner bypass, approval ordering, and active-version invariance. Inspect `git status`, owned diff, staged paths, and `git diff --cached --check`; deliver only completed files through the repository Stop-hook manifest. Do not include concurrent files or untracked research artifacts.

## Acceptance

All supported proposals preserve candidate and baseline identity. Regression receipts describe actual paired execution or a precise blocked reason. Structural approval requires an independent human and a reviewed real passing regression, and still changes no active version. Where no production adapter or reviewed gold exists, the honest output is blocked; synthetic tests cannot promote the research framework.
