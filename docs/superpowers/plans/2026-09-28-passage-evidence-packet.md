# Passage Evidence Packet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox syntax for tracking.

**Goal:** Freeze exact quote-presence checks for claims without approving their meaning.

**Architecture:** Consume an intact frozen claim report, validate a quote
packet against it, recheck the pinned raw version, scan supported plain text,
and freeze an immutable passage report. Expose one CLI command.

**Tech Stack:** Python standard library, pytest, JSON files.

**Spec:** docs/superpowers/specs/2026-09-28-passage-evidence-packet-design.md

## Global Constraints

- Keep claim gaps open and real research publication blocked.
- Raw source files and generated state remain outside Git.
- A report means byte presence only, never semantic support.

## Review Focus

- PDF bytes containing a literal quote still return UNSUPPORTED_FORMAT.
- Missing, corrupt, or replaced raw evidence returns INVALID_SOURCE.
- A changed packet or claim report cannot reuse the run ID.
- Duplicate and unknown claim IDs fail before writing a report.
- Large or non-text blobs do not get decoded or scanned as valid text.

### Task 1: Passage evaluator

**Files:** Create `src/kb_runtime/passage_evidence.py`,
`tests/test_passage_evidence.py`.

**Interfaces:** `evaluate_passages(packet_path: Path, claim_report_path:
Path, project_dir: Path, state_dir: Path, run_id: str) -> dict`.

- [ ] Write tests for quote present, absent, missing, and blocked lineage.
- [ ] Run focused tests and observe expected failure.
- [ ] Implement packet validation, pinned raw checks, and bounded text scan.
- [ ] Add failure tests for damaged source, PDF, binary, size, identity, and replay.
- [ ] Run focused and full suite.

### Task 2: CLI and documentation

**Files:** Modify `src/kb_runtime/__main__.py`,
`projects/indian-equities/README.md`, and the program status.

- [ ] Write a failing CLI test and add `evaluate-passages`.
- [ ] Document the packet and status limit.
- [ ] Run focused and full suite, review task-only diff, commit, and push.
