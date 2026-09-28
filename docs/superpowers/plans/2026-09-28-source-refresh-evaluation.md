# Source Refresh Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox syntax for tracking.

**Goal:** Evaluate source readiness at a fixed cutoff and freeze each report.

**Architecture:** Read the versioned source register, select eligible versions,
verify raw bytes and age, and persist an immutable report. Expose the operation
through one CLI command.

**Tech Stack:** Python standard library, pytest, JSON files.

**Spec:** docs/superpowers/specs/2026-09-28-source-refresh-evaluation-design.md

## Global Constraints

- Do not fetch external data or publish research.
- Keep reports under ignored state/.
- Use explicit request max_age_days; do not reinterpret existing YAML policy yet.
- Do not alter the existing source registration interface.

## Review Focus

- Source versions after the cutoff never enter historical evaluations.
- A missing or corrupted raw blob blocks readiness.
- Altered register records block readiness.
- A run ID cannot silently change a frozen request or result.
- A later source version requires a new evaluation run ID.

---

### Task 1: Source readiness evaluator

**Files:** Create src/kb_runtime/source_refresh.py and tests/test_source_refresh.py.

**Interface:** evaluate_sources(request_path: Path, project_dir: Path,
state_dir: Path, run_id: str) -> dict. Invalid requests raise ValueError;
registry problems produce per-source blocked results.

- [x] Write tests for current, missing, after-cutoff, stale, missing raw,
  corrupted raw, invalid registry, and frozen run behavior.
- [x] Run the focused tests and observe failure for the missing evaluator.
- [x] Implement validation, selection, checks, and immutable report write.
- [x] Run the focused tests and confirm they pass.

### Task 2: CLI and documentation

**Files:** Modify src/kb_runtime/__main__.py,
projects/indian-equities/README.md, and tests/test_source_refresh.py.

- [x] Add and run a failing CLI test.
- [x] Add evaluate-sources command and usage guidance.
- [x] Run the focused tests and the full repository suite.
- [x] Inspect and stage only these files and check the staged diff.
- [ ] Commit and push the current feature branch.
