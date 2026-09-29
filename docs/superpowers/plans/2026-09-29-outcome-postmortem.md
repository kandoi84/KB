# Outcome and Postmortem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Append sourced outcomes to immutable sandbox cases and freeze a due human postmortem with a result quadrant and controlled eval candidate.

**Architecture:** An `outcome_postmortem` module replays the 09 case parent, resolves a reviewed reported metric at the declared observation cutoff, and writes link-once event receipts. A due command separates mechanical target comparison from the human process assessment; reproducible bad process produces an unreviewed eval candidate only.

**Tech Stack:** Python 3.14 standard library, existing `metric_store.query_metrics`, 09 case replay validator, JSON receipt helpers, and pytest. No new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-09-29-outcome-postmortem-design.md`.

## Global constraints

- Implement only after 09's case-opening and parent-replay API is stable; do not trust a case hash by itself.
- Preserve `publication_allowed: false`, `live_decision_allowed: false`, and `promotion_status: NOT_EVALUATED` in all outputs.
- Operating target attainment is not investment return, thesis correctness, or process quality.
- Observed actuals must be reviewed `REPORTED` typed metric leaves at the event's strict cutoff, with full source citation.
- Case, observation, due receipt, review, and candidate history are immutable; changed same-ID replay fails.
- Historical reconstructions remain ineligible as prospective forecasts without an independent pre-outcome receipt.
- Synthetic tests prove mechanics only; mini spec 12 owns empirical evaluation and promotion.

## Review focus

1. A rehashed forged 09 parent must fail event append when it differs from the supplied original packet or replayed inputs. A coordinated rewrite of the case and caller-supplied packet is outside the proof of this local contract (Task 1).
2. A metric revision filed after `observed_at` must not change the earlier observation or be selected during retry (Task 1).
3. Two metrics matching name/period but differing scope must require an explicit selected `metric_id`, with no silent fallback (Task 1).
4. A due receipt with no sourced actual or no human review must stay pending, never enter a quadrant (Task 2).
5. A crash between postmortem and eval candidate writes must resume without a false complete state or duplicate candidate (Task 2).

---

### Task 1: Append a sourced observation

**Files:** Create `src/kb_runtime/outcome_postmortem.py` and `tests/test_outcome_postmortem.py`. Reuse 09's `open_sandbox_case` and `verify_case_parents`; expose a narrow frozen-case replay helper in `case_snapshot.py` with 09 tests if the case equality check cannot be done cleanly through the public entry point. Do not copy the 09 validators.

**Interface:** `append_outcome_observation(packet_path: Path, *, case_packet_path: Path, project_dir: Path, catalog: Path, state_dir: Path, case_replay_inputs: Mapping[str, Path]) -> dict`. The packet uses the exact observation fields in the spec. `case_packet_path` and `case_replay_inputs` supply the original 09 packet and its eight input paths for full frozen-case reconstruction. Return the frozen event.

- [ ] Write a failing synthetic integration test that opens a real 09 sandbox case, registers a reviewed reported metric for the future outcome period, appends an observation, and checks exact citation, decimal, source raw hash, cutoff, and three safety flags.
- [ ] Run `python3 -m pytest -q tests/test_outcome_postmortem.py`; confirm the intended failure.
- [ ] Implement strict packet parsing, expected-root/safe-ID parent lookup, exact frozen case equality plus 09 parent replay, exact metric-ID selection via `query_metrics`, series/period/ISIN/unit match, availability checks, and atomic link-once JSON with canonical digest. Recompute and compare on retry.
- [ ] Add tests for a rehashed case changed without its supplied packet, damaged parents, ambiguous series, guidance actual, rights failure, wrong metric identity/unit/period, source-byte damage, late observation, future revision, conflicting retry, and two concurrent writers. Rerun focused tests.

### Task 2: Due postmortem and eval candidate

**Files:** Extend `src/kb_runtime/outcome_postmortem.py` and `tests/test_outcome_postmortem.py`.

**Interface:** `evaluate_due_case(packet_path: Path, *, case_packet_path: Path, project_dir: Path, catalog: Path, state_dir: Path, case_replay_inputs: Mapping[str, Path]) -> dict`. The strict due packet uses the fields and review object in the spec. Return either a pending or complete immutable postmortem; on reproducible bad process, also create the unreviewed eval candidate.

- [ ] Write failing tests for a due event before deadline, missing observation, missing review, each of four process/result quadrants, and decimal boundaries under both case comparators. Confirm process status comes only from the review packet.
- [ ] Run the focused test and confirm intended failures.
- [ ] Implement due validation against `case.prediction.due_at`, case/event replay and digest checks, result comparison with `Decimal`, human review fields/taxonomy, and frozen postmortem. The postmortem itself is the due-event receipt; omit a separate `due_event_id`. For a candidate, precompute both bodies, verify any existing same-ID receipts, link the candidate first and postmortem second, then verify both before returning complete. A retry finishes an intact candidate-only state and rejects a postmortem with a missing candidate.
- [ ] Add tests for reviewer-time/look-ahead errors, `NONE`/`UNAVOIDABLE_SURPRISE` constraints, reproducible failure invariant, luck no-change control, changed same-ID review, damaged event, missing candidate on retry, and exact outcome exclusion from candidate decision inputs. Rerun focused tests.

### Task 3: CLI and user contract

**Files:** Modify `src/kb_runtime/__main__.py`, `projects/indian-equities/README.md`, and `docs/superpowers/specs/2026-09-28-kb-mini-spec-program.md`; create `tests/test_outcome_postmortem_cli.py`.

**Interfaces:** Add `append-case-outcome --packet --case-packet --project-dir --catalog --state-dir` and `evaluate-due-case --packet --case-packet --project-dir --catalog --state-dir`, each with the required eight 09 replay input paths, following 09 CLI names. Print one JSON receipt with safety flags; exit nonzero without success JSON on rejection.

- [ ] Write failing CLI tests for accepted observation, completed due evaluation, pending due state, and rejected changed replay.
- [ ] Run `python3 -m pytest -q tests/test_outcome_postmortem_cli.py`; confirm intended failures.
- [ ] Add commands and concise README packet examples. Mark 10 active in the program only after accepted checks/review; state 11–12 and real publication remain pending.
- [ ] Run `python3 -m pytest -q tests/test_outcome_postmortem.py tests/test_outcome_postmortem_cli.py`, then `python3 -m pytest -q`. Fix caused failures and rerun affected checks.
- [ ] Ask an independent reviewer to inspect source provenance, look-ahead, forged-parent, concurrent/replay, taxonomy, and publication paths. Inspect `git status`, task-owned diff, staged paths, and `git diff --cached --check`. Deliver completed task-owned files via the repository Stop-hook manifest and record commit/push result; preserve unrelated untracked files.

## Acceptance

A due sandbox case can record an exact sourced metric observation and human process judgment without changing inception. Completed reviews produce the four quadrants and a named class. A reproducible bad-process failure yields an unreviewed eval candidate. Invalid or missing evidence stays pending or blocked, and no receipt enables live publication or autonomous changes.
