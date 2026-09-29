# Evidence Refresh Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox syntax for tracking.

**Goal:** Run source and claim checks together, freeze a manifest, and compare a prior run.

**Architecture:** Compose the existing evaluators; validate two request headers;
record report digests and deterministic changes in an immutable manifest.

**Tech Stack:** Python standard library, pytest, JSON files.

**Spec:** docs/superpowers/specs/2026-09-28-evidence-refresh-run-design.md

## Global Constraints

- No real research publication or automatic gap resolution.
- Reuse the existing evaluator contracts and frozen report paths.
- Keep generated state ignored by Git.

## Review Focus

- A changed source version triggers claim recheck.
- Unresolved or damaged evidence remains blocked.
- Interrupted and repeated runs do not alter frozen reports.
- Prior run integrity, identity, and cutoff are checked.
- Changed inputs cannot reuse a run ID.

### Task 1: Refresh execution

**Files:** Create `src/kb_runtime/evidence_refresh.py` and
`tests/test_evidence_refresh.py`; expose a read-only claim report loader in
`src/kb_runtime/claim_lineage.py`.

- [x] Write focused success, update, blocked, tamper, and resume tests.
- [x] Observe failure before implementation.
- [x] Compose evaluators and freeze a manifest.
- [x] Run focused checks.

### Task 2: CLI and delivery

**Files:** Modify `src/kb_runtime/__main__.py` and
`projects/indian-equities/README.md`.

- [x] Add a failing CLI test and implement `refresh-evidence`.
- [x] Document first and subsequent runs.
- [x] Run focused and full checks.
