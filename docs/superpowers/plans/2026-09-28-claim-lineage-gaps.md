# Claim Lineage and Gap Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox syntax for tracking.

**Goal:** Freeze a claim lineage report with explicit gaps against one source-readiness report.

**Architecture:** Validate a strict claim request and an intact frozen source
report; check each selected source version and raw blob; persist one immutable
report with claim outcomes and gaps. The CLI exposes one command.

**Tech Stack:** Python standard library, pytest, JSON files.

**Spec:** docs/superpowers/specs/2026-09-28-claim-lineage-gaps-design.md

## Global Constraints

- Real research publication remains blocked.
- A source pointer does not prove passage meaning.
- Generated reports remain under ignored `state/`.
- No network retrieval or silent gap filling.

## Review Focus

- Mismatched source report, cutoff, version, or raw hash blocks lineage.
- Derived and inferred claims do not masquerade as direct facts.
- Every blocked or unverified claim appears in a structured gap.
- A frozen run cannot change when its input or source report changes.
- Malformed and tampered inputs fail closed.

### Task 1: Evaluator and gap ledger

**Files:** Create `src/kb_runtime/claim_lineage.py` and
`tests/test_claim_lineage.py`; minimally expose report integrity validation
from `src/kb_runtime/source_refresh.py`.

- [x] Write focused tests for linked, blocked, derived, damaged, and frozen cases.
- [x] Observe failure before implementation.
- [x] Implement validation, lineage checks, gaps, and frozen report.
- [x] Run focused checks and review failures.

### Task 2: CLI, guidance, delivery

**Files:** Modify `src/kb_runtime/__main__.py` and
`projects/indian-equities/README.md`.

- [x] Add a failing command test, then expose `evaluate-claims`.
- [x] Document input and limits.
- [x] Run focused and full repository checks.
- [ ] Inspect status and staged diff; commit owned files and push feature branch.
