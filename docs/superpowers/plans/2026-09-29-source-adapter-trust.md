# Source Adapter and Trust Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Choose a source route only for an observed, eligible gap with exact rights scope, and report evidence-workflow trust from independently reviewed samples without affecting investment scores.

**Architecture:** Reuse mini spec 07 parent validation, local attempt, and immutable source registration. Add an append-only observed-gap activation packet and deterministic, non-fetching route plan. Aggregate independently labeled attempt observations into stratified diagnostic reports. Defer every live HTTP adapter until a real gap and endpoint-specific permission justify a separate connector spec.

**Tech Stack:** Existing Python standard-library JSON/digest/runtime patterns and pytest. No new RAG or exchange wrapper dependency.

**Spec:** `docs/superpowers/specs/2026-09-29-source-adapter-trust-design.md`

## Global Constraints

- No network fetch, credentials, or undocumented NSE/BSE endpoint in this plan's first implementation slice.
- Keep `reviewed_local_primary_v1` as the sole executable route. No gap closure, source backdating, real publication, or investment-score input.
- Real activation requires a real open gap plus a rights receipt for the exact method; synthetic tests cannot establish that gate.
- Preserve unrelated files. For each completed task, run affected checks, inspect the diff/staged paths, commit only owned files, and push the feature branch under repository rules.

## Review Focus

- A rehashed/fake parent or relabeled restricted gap must not produce a route.
- Rights must name actor, endpoint, method, frequency, storage, retention, purpose, and limits. A public URL or package license is inadequate.
- Old cutoff and attempt records remain frozen on retry and after later retrieval.
- Error/rate evidence must be recorded even when no document is accepted.
- Sample denominator, unresolved labels, cohort drift, and synthetic exclusion must be explicit; no trust metric may enter an investment score.

---

### Task 1: Inventory observed gaps and approved routes

**Files:** Add `src/kb_runtime/source_route.py`, `tests/test_source_route.py`; update `projects/indian-equities/README.md` after behavior exists.

**Interface:** `select_gap_route(activation_packet_path, claim_report_path, source_report_path, source_request_path, claim_request_path, project_dir, state_dir, route_id) -> dict`. Return a digest-bound, write-once plan status (`REVIEWED_LOCAL`, `RIGHTS_REVIEW_REQUIRED`, `NO_APPROVED_ROUTE`, `HUMAN_WORK_REQUIRED`) with exact parent/packet/rights hashes, cutoff, and `publication_allowed: false`. It must never call a fetcher or `record_source`.

- [ ] Inventory actual frozen reports/07 attempts. Record the observed gap count and relevant classifications before enabling any route; if there are none, keep the route dormant and use synthetic fixtures only for tests.
- [ ] Write failing tests for valid synthetic missing/stale primary packets, empty real-gap inventory, missing/expired/narrow rights, internal/restricted/linked/after-cutoff gaps, changed source/claim request, self-consistently rehashed fake parents, cross-entity data, and route ID collision.
- [ ] Run `pytest tests/test_source_route.py -q` to observe the intended failure.
- [ ] Implement exact-schema packet parsing, 07 parent/eligibility reuse, capability matching, canonical digest/write-once plan and stable replay. Use existing atomic JSON and safe-ID helpers; avoid a generic plugin registry.
- [ ] Run the focused test. Check that route selection writes no raw document, source version, claim, or closed-gap result.

### Task 2: Capture independent trust observations

**Files:** Add `src/kb_runtime/trust_observation.py`, `tests/test_trust_observation.py`.

**Interface:** `record_trust_observation(observation_path, attempt/result paths, state_dir) -> dict` binds one independently adjudicated label to exact frozen attempt/source/report identities and rubric version. Append-only observation IDs; changed replay fails. A disputed or excluded case remains visible, not a pass.

- [ ] Write failing tests for correct accepted and blocked attempt labels, reviewer equal to operator, nonexistent/tampered attempt, wrong bytes hash, changed label on retry, future/absent adjudication time, duplicate observation, and synthetic-versus-real origin.
- [ ] Run focused tests to see failure, then implement against 07 frozen receipts and source hashes. Store only references/labels, never duplicate licensed raw content or credentials.
- [ ] Run focused tests and verify a blocked attempt can be sampled and one altered parent cannot.

### Task 3: Produce diagnostics with sample gates

**Files:** Add `src/kb_runtime/trust_report.py`, `tests/test_trust_report.py`.

**Interface:** `build_trust_report(observation_ids, cohort_filter, state_dir, report_id) -> dict` emits cohort definition, inclusion/exclusion counts, separate metric numerators/denominators, 95% Wilson intervals, failure classes, lag summaries, and states `INSUFFICIENT_SAMPLE`, `NO_ESTIMATE`, or `NOT_CALIBRATABLE`. No scalar investment score.

- [ ] Write failing tests for empty cohort, sub-threshold sample, sufficient multi-issuer/multi-period sample, unresolved labels, duplicate observations of one attempt, adapter-version and rights-policy splits, blocked attempts, and altered observation replay. Assert no `poker_score`, fair-value, publication, or promotion field.
- [ ] Run focused tests to see failure, implement deterministic cohort grouping and interval math, then rerun. Use fixed synthetic cases to verify formulas and explicit sample limits; do not call fixture performance “calibrated.”
- [ ] Add a guard test that 09/12 investment outputs cannot read trust reports or change when trust data changes, using the existing relevant entry point.

### Task 4: CLI, review, and activation decision

**Files:** Update `src/kb_runtime/__main__.py`, project README, and the mini-spec program status; add CLI tests to the three focused test files. Do not add an HTTP adapter in this task.

- [ ] Add CLI commands for plan, adjudicate, and trust report with explicit synthetic/real origin and no network-capable option. Test a successful local-route plan and a blocked/insufficient sample path.
- [ ] Document rights packet review and current NSE/BSE prohibitions/unknowns from the spec. State the exact observed real-gap count and whether any connector activation criterion is met.
- [ ] Run `pytest tests/test_source_route.py tests/test_trust_observation.py tests/test_trust_report.py -q`, `python3 -m compileall -q src/kb_runtime`, and `pytest -q`. Fix failures caused by this slice and report unrelated blockers.
- [ ] Inspect `git status`, task diff, staged paths, and `git diff --cached --check`; commit owned completed files and push the feature branch according to repository delivery rules.
- [ ] If a real gap plus scoped endpoint rights and a credible adjudicated sample later exist, draft a separate single-endpoint connector spec with exact rate/retry/security tests and source-specific permission. Until then, leave automated acquisition disabled and report trust as diagnostic only.
