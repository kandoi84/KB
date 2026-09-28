# Historical Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze point-in-time evaluation cohorts, enforce decision-before-outcome separation, and report honest investment-evaluation readiness and results without promoting the current research runtime.

**Architecture:** A cohort receipt replays 09 cases and records independent time-proof status without future data. A registered scorer freezes decisions before a separate reveal adapter can consume reviewed market, benchmark and baseline feeds. An evaluation report computes EVAL_PLAN measures only when the required reviewed inputs exist; all receipts permanently block publication and activation.

**Tech Stack:** Installed Python 3.14.6 standard library, existing 09 case replay and 04E digest/JSONL conventions, pytest. No new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-09-29-historical-evaluation-design.md`.

## Global Constraints

- 08 fair value is unverified and 09 has no investment score or price; never derive a score or return from them.
- 04E retrieval quality and 10 operating postmortems are separate from investment ranking quality.
- Existing historical reconstructions and locally declared prospective cases do not prove a pre-outcome decision seal.
- The current project has no reviewed scorer, market/benchmark feed, or independent time seal; all real investment promotion remains blocked.
- Every receipt fixes `publication_allowed: false`, `live_decision_allowed: false`, and `promotion_allowed: false`; no activation API or production pointer write.
- Preserve exact immutable replay, issuer/cutoff binding, rights, input and output hashes, and dataset class across all stages.

## Review Focus

1. A rehashed 09 case or retrospective local decision cannot count as independently sealed (Task 1).
2. An outcome path or future metric entering scorer inputs blocks score freezing (Task 2).
3. An unreviewed price, missing delisting event, sector mismatch, or incomplete horizon cannot turn into a return or win (Task 3).
4. Duplicate company/cutoff rows or incomplete quarterly universes cannot inflate the 100-observation gate (Tasks 1 and 4).
5. A synthetic mechanics pass or incomplete baseline/calibration report cannot authorize promotion (Task 4).

---

### Task 1: Frozen cohort and readiness receipt

**Files:** Create `src/kb_runtime/historical_cohort.py` and `tests/test_historical_cohort.py`; modify `src/kb_runtime/case_snapshot.py` to expose `verify_frozen_case` and extend `tests/test_case_snapshot.py`.

**Interface:** `verify_frozen_case(case_path: Path, *, source_request: Path, claim_request: Path, passage_packet: Path, review_packet: Path, workflow_contract: Path, claim_review_report: Path, analysis_packet: Path, analysis_report: Path, project_dir: Path, catalog: Path, state_dir: Path) -> dict` replays and reconstructs the whole 09 body. `register_evaluation_cohort(manifest_path: Path, *, state_dir: Path, project_dir: Path, catalog: Path, case_replay_inputs: Mapping[str, Mapping[str, Path]]) -> dict` uses that helper; `case_replay_inputs` maps each case ID to its exact eight 09 paths. The strict manifest pins ID, dataset kind, rubric, quarter cutoffs, case IDs/digests/ISINs, scorer identity if present, reviewer, universe rule, and per-case independent seal proof. Output is link-once `state_dir/historical_evaluation/cohorts/<cohort_id>.json` with each case's `REPLAY_ONLY|SEALED_PROSPECTIVE|SYNTHETIC_FIXTURE` class and blocker list.

- [ ] Write failing tests for 30–50 unique ISINs in a quarter, valid case replay, exact retry, and `REPLAY_ONLY` for a local 09 timing label. Assert output has no outcome or price path and all three safety flags are false.
- [ ] Run `python3 -m pytest -q tests/test_historical_cohort.py`; confirm the intended failures.
- [ ] Implement `verify_frozen_case` by deriving the expected 09 body from replayed parents and comparing every field to the stored body; then implement strict bounded JSON, safe IDs/paths, independent proof validation, duplicate `(ISIN, cutoff)` rejection, quarter counts, immutable receipt and changed-ID conflict. An incomplete quarter is recorded as blocked, never omitted.
- [ ] Add tests for forged/rehashed case, wrong issuer, mixed rubric, duplicate observation, 29/51-name quarter, malformed nested fields, proof timestamp after outcome, future source, symlink escape and concurrent retry. Rerun focused tests.

### Task 2: Sealed score contract and no-reveal boundary

**Files:** Create `src/kb_runtime/historical_score.py` and `tests/test_historical_score.py`.

**Interface:** `freeze_historical_scores(request_path: Path, *, state_dir: Path, scorer_registry: Mapping[str, ScoreAdapter]) -> dict`. Request pins cohort ID/digest, rubric, scorer ID/version/source SHA-256 and run ID. A registered adapter consumes only a read-only, cutoff-filtered case view and produces a 0–100 score, five factor values, error band, frozen catalyst forecasts and fair value. The receipt is immutable at `state_dir/historical_evaluation/scores/<run_id>.json`; no outcome feed parameter is accepted.

- [ ] Write failing tests for `BLOCKED_NO_SCORER` on the real current runtime and deterministic synthetic paired runs. Assert no market/outcome fields enter the adapter input and synthetic output is `MECHANICS_ONLY`.
- [ ] Run `python3 -m pytest -q tests/test_historical_score.py`; confirm the intended failures.
- [ ] Implement allowlisted adapters, source-hash/consumption checks, isolated input view, strict score schema, independent repeat IDs, link-once receipt and blocked reason.
- [ ] Add tests for packet-supplied code/commands, future evidence, changed scorer hash, same-ID changed retry, malformed factors, nonindependent repeats, and attempt to use a test adapter for real reviewed scoring. Rerun focused tests.

### Task 3: Reviewed outcome reveal and horizon arithmetic

**Files:** Create `src/kb_runtime/historical_reveal.py` and `tests/test_historical_reveal.py`.

**Interface:** `reveal_historical_outcomes(request_path: Path, *, state_dir: Path, feed_registry: Mapping[str, MarketFeedAdapter]) -> dict`. Request pins cohort and score receipt digests, reviewed feed IDs/hashes, execution lag, calendar/rubric version, and reveal run ID. A registered feed returns versioned ISIN prices, corporate actions, delisting cash flows, point-in-time sector/Nifty membership and total-return benchmark levels. Output is link-once `state_dir/historical_evaluation/reveals/<run_id>.json` with per-observation 6/12/24/36 month eligibility and Decimal returns.

- [ ] Write failing tests that a missing real feed yields `BLOCKED_NO_MARKET_FEED`, while a deterministic test feed computes a post-freeze synthetic return and records the exact sample denominator.
- [ ] Run `python3 -m pytest -q tests/test_historical_reveal.py`; confirm the intended failures.
- [ ] Implement score-receipt replay, strict feed rights/reviewer/hash/time checks, entry at first eligible close after freeze and lag, pinned calendar window, total-return math, and per-horizon missing status.
- [ ] Add tests for early reveal, predecision price used as entry, future benchmark constituent, incomplete 36-month window, stock split/dividend, delisting, stale/unreviewed/wrong-ISIN feed, changed same-ID retry and torn write. Rerun focused tests.

### Task 4: EVAL_PLAN report and nonpromotion gate

**Files:** Create `src/kb_runtime/historical_eval.py` and `tests/test_historical_eval.py`.

**Interface:** `evaluate_historical_cohort(request_path: Path, *, state_dir: Path) -> dict`. Request pins cohort, score and reveal receipt digests, five reviewed baseline input receipts, predeclared thresholds and report ID. Output is immutable `state_dir/historical_evaluation/reports/<report_id>.json`, with dataset class, numerator/denominator and missing counts for every measure, blocker list, `MECHANICS_ONLY|BLOCKED|GATE_ELIGIBLE_FOR_HUMAN_REVIEW`, and all safety flags false.

- [ ] Write failing tests for synthetic 30–50-name quarters and 100 distinct company snapshots: repeatability, factor agreement, zero-tolerance look-ahead, quintile 12/24-month median spread, top-five hit rate, probability bins/Brier, fair-value revisions, 6/12/24/36-month counts, drawdown, factor buckets, and five named baselines. Assert synthetic stays `MECHANICS_ONLY` even when all numbers pass.
- [ ] Run `python3 -m pytest -q tests/test_historical_eval.py`; confirm the intended failures.
- [ ] Implement deterministic grouping and Decimal/statistics calculations, rubric-pinned formulas, missing denominators as `NOT_EVALUABLE`, complete baseline matching, exact receipt replay and immutable output. Gate real review eligibility only when all spec dependencies and numeric criteria pass; keep promotion false.
- [ ] Add tests for 99 observations, duplicate ISIN/cutoff, 29-name quarter, one look-ahead violation, score median >3, factor agreement <80%, 12/24 spread failure, unresolved catalyst, missing baseline, error-band tie, delisting, empty horizon and changed report ID. Rerun focused tests.

### Task 5: CLI, documentation and delivery review

**Files:** Modify `src/kb_runtime/__main__.py`, `projects/indian-equities/README.md`, and `docs/superpowers/specs/2026-09-28-kb-mini-spec-program.md`; create `tests/test_historical_eval_cli.py`.

**Interface:** CLI commands `register-evaluation-cohort`, `freeze-historical-scores`, `reveal-historical-outcomes`, and `evaluate-historical-cohort` accept explicit local paths/IDs and print JSON receipts. No command publishes, activates or changes active scoring configuration.

- [ ] Write failing CLI tests for blocked current-runtime results, malformed paths and JSON error handling; assert no promotion/activate command exists.
- [ ] Run `python3 -m pytest -q tests/test_historical_eval_cli.py`; confirm the intended failures.
- [ ] Implement thin CLI wiring and README examples that show the current real-data blockers, then mark 12 as contract/mechanics active with empirical promotion pending.
- [ ] Run focused 12 suites and `python3 -m pytest -q`; fix caused failures and rerun. Ask an independent reviewer to inspect two-phase separation, case replay, feed rights, missing-data denominators and false safety flags.
- [ ] Inspect `git status`, owned diff and staged files; run `git diff --cached --check`. Commit/push only completed owned files through the repository's authorized delivery flow, preserving concurrent changes.

## Acceptance

Synthetic fixtures demonstrate deterministic contract mechanics, complete sample accounting and no publication. The real current runtime reports concrete missing independent seal, scorer and reviewed feed/baseline blockers. A future reviewed cohort can become eligible for **human review** only after all provenance and EVAL_PLAN gates pass; this mini spec never activates the selector.
