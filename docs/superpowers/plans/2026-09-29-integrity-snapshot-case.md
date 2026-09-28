# Integrity, snapshot, and sandbox case implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open an immutable sandbox case only from a replay-verified evidence workflow and internal analysis at one strict cutoff.

**Architecture:** A `case_snapshot` module validates a small analyst packet and exact parent files, replays the existing 06 and 08 entry points, then freezes a case receipt. The CLI exposes case opening while publication stays permanently false.

**Tech Stack:** Installed Python 3.14.6 standard library (`datetime`, `Decimal`, `hashlib`, `json`, `pathlib`, `tempfile`) and existing pytest. Reuse the existing 06/08 APIs and immutable report pattern; no new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-09-29-integrity-snapshot-case-design.md`.

## Global constraints

- Accept only a completed existing 06 workflow and a completed existing 08 analysis report. Do not create missing parents while opening a case.
- Require exact issuer/ISIN/cutoff across all artifacts and recheck raw, catalog, model, claim, metric, and contract bindings by replaying upstream entry points.
- A case is internal sandbox material: `publication_allowed: false`, `live_decision_allowed: false`, `promotion_status: NOT_EVALUATED` in every result.
- No price, score, poker label, order, position size, stance, or real research publication from this command.
- All prediction targets are `ANALYST_HYPOTHESIS`, not observed metrics. Synthetic tests prove contract mechanics only.
- Preserve immutable source, review, analysis, and case history. A revised view gets a new case ID.

## Review focus

1. A digest-valid but rehashed claim or analysis report with a promoted status must fail on parent replay. Add to Task 1.
2. A changed workflow contract or input packet under the same run ID must fail despite intact result files. Add to Task 1.
3. A model file or source blob changed after analysis must block case opening. Add to Task 1.
4. A later revised metric must not enter the old cutoff, and a mixed analysis/workflow cutoff must fail. Add to Task 1.
5. A valid-looking poker hand without a scoring engine must fail; identical case replay must not rewrite the file. Add to Task 2.

---

### Task 1: Replay and cross-artifact integrity

**Files:** Create `src/kb_runtime/case_snapshot.py`; create `tests/test_case_snapshot.py`.

**Interfaces:** Produce `verify_case_parents(packet: dict, *, source_request: Path, claim_request: Path, passage_packet: Path, review_packet: Path, workflow_contract: Path, claim_review_report: Path, analysis_packet: Path, analysis_report: Path, project_dir: Path, catalog: Path, state_dir: Path) -> tuple[dict, dict, dict]`. Return the exact 06 state, 05 report, and 08 report. Task 2 consumes this tuple.

- [ ] Write failing synthetic end-to-end tests using real upstream registration, review, workflow, metric, and analysis fixtures. Check `COMPLETE` three-stage workflow, exact review child ID, exact issuer/ISIN/cutoff, expected state/report roots, safe run IDs, byte hashes for every supplied input, and existing parents before replay.
- [ ] Run `python3 -m pytest -q tests/test_case_snapshot.py`; confirm intended failures.
- [ ] Implement preflight checks before calling `run_evidence_workflow(..., review_packet, ..., workflow_run_id)` and `analyze_judgment(analysis_packet, claim_review_report, ..., analysis_run_id)`. Require the supplied 08 packet to equal the report's frozen `worksheet`. Compare returned values to exact on-disk parents and reject any mutation or mismatch. Require `CALCULATED_MODEL_UNVERIFIED`, no gaps, `MODEL_UNVERIFIED`, `HUMAN_REVIEW_REQUIRED`, and publication false. Bind workflow review `output_id` to 05 report ID and 08 `claim_review_report_id`.
- [ ] Add the five review-focus mutation tests for rehashed parents, changed contract, damaged raw/model, late revised metric, and mixed cutoff. Rerun focused tests.

### Task 2: Prediction contract and frozen case

**Files:** Extend `src/kb_runtime/case_snapshot.py` and `tests/test_case_snapshot.py`.

**Interfaces:** Produce `open_sandbox_case(packet_path: Path, *, source_request: Path, claim_request: Path, passage_packet: Path, review_packet: Path, workflow_contract: Path, claim_review_report: Path, analysis_packet: Path, analysis_report: Path, project_dir: Path, catalog: Path, state_dir: Path) -> dict`. The packet supplies `case_id`, `workflow_run_id`, `analysis_run_id`, `issuer_id`, `isin`, `cutoff_timestamp`, `mode`, `opened_at`, optional `previous_case_id`, `input_sha256` keyed by the eight input names, `hypothesis`, `rationale_claim_ids`, `rationale_metric_ids`, `outcome`, and optional `poker`. `outcome` has `metric_name`, `unit`, `comparison`, `target_decimal`, `target_kind`, `period_end`, and `due_at`.

- [ ] Write failing tests for the exact packet schema; nonempty hypothesis without digits; at least one existing 08 rationale ID; unique citations; nonempty outcome metric/unit; `AT_LEAST|AT_MOST`; finite plain-decimal target; `ANALYST_HYPOTHESIS`; period end after cutoff and due timestamp on or after period end; timezone-aware cutoff/opened/due times; safe IDs; and the only legal poker object `{status: NOT_ASSESSED, hand: null, draw: null}`.
- [ ] Run focused tests and confirm the intended failures.
- [ ] Implement strict parsing and `Decimal` validation. Build one report with parent hashes/IDs, prediction, the 08 fair value and `analysis_report.worksheet.valuation_range` labelled unverified analyst estimate, `case_status: SANDBOX_OPEN`, `timing_class: HISTORICAL_RECONSTRUCTION|ANALYST_DECLARED_PROSPECTIVE`, safety flags, and canonical SHA-256 digest. Freeze it at `state_dir/cases/<case_id>.json` using temporary file, fsync, and link-once. Reject changed same-ID replay; verify old case digest and parents on identical replay. Validate optional previous case exists, is intact, has the same issuer/ISIN, and precedes this case by cutoff or opening time; do not edit it.
- [ ] Rerun focused tests, including changed-ID replay, poker/price injection, previous-case mismatch, and concurrent-create behavior.

### Task 3: CLI, documentation, and delivery

**Files:** Modify `src/kb_runtime/__main__.py`, `projects/indian-equities/README.md`, `docs/superpowers/specs/2026-09-28-kb-mini-spec-program.md`; create `tests/test_case_snapshot_cli.py`.

**Interfaces:** Add `open-sandbox-case --packet --source-request --claim-request --passage-packet --review-packet --workflow-contract --claim-review-report --analysis-packet --analysis-report --project-dir --catalog --state-dir`. Print the frozen JSON case; case ID is in the packet.

- [ ] Write a failing CLI test using a complete synthetic fixture. Assert output is `SANDBOX_OPEN` and all three safety flags remain blocked.
- [ ] Add the command and a short README contract/example. Mark 09 active only after checks and review; state that real publication and historical quality remain unverified.
- [ ] Run `python3 -m pytest -q tests/test_case_snapshot.py tests/test_case_snapshot_cli.py`, then `python3 -m pytest -q`; inspect failures and fix those caused by this slice.
- [ ] Ask a separate reviewer to inspect forged-parent, look-ahead, immutable replay, and publication paths. Inspect `git status`, task-owned diff, staged paths, and `git diff --cached --check`. Deliver only completed 09 files under the repository Stop-hook manifest rule; do not include concurrent work or untracked research files. Record the hook commit SHA and push result.

## Acceptance

A complete, consistent set of upstream artifacts opens one immutable sandbox case with a falsifiable prediction and no live or published decision. Mixed vintages, unsupported claims, changed model/source bytes, fake scores, and changed same-ID inputs fail closed.
