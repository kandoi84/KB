# Claim integrity review implementation plan

> **For agentic workers:** Use superpowers:executing-plans or superpowers:subagent-driven-development task by task.

**Goal:** Freeze a human review of exact direct-claim evidence, with explicit rights, semantic, conflict, and gap decisions. Keep real publication blocked.

**Architecture:** A new review module consumes frozen claim and passage reports, the reviewed filing catalog, and a strict review packet. It rechecks report safety fields and raw quote bytes, applies direct-claim gates, then atomically writes an append-only report. It never mutates original gaps or research output.

**Tech stack:** Python standard library and pytest.

**Spec:** `../specs/2026-09-29-claim-integrity-review-design.md` (mini spec 05, first slice).

## Task 1: Validate a pinned review packet

**Files:** Add `src/kb_runtime/claim_review.py`, `tests/test_claim_review.py`.

- [x] Write failing tests for exact claim/passage report binding, unique and known IDs, exact source/version/raw hash/quote/offset, matching reviewed filing, entity/cutoff, safe run ID, review time, rights evidence, reviewer, and decision enums.
- [x] Confirm the focused tests fail for the intended missing behavior.
- [x] Implement strict parsing and cross-report checks. Validate frozen safety fields as well as hashes; a self-consistent rewrite to an approved upstream status must fail.
- [x] Confirm focused tests pass.

## Task 2: Apply direct-claim gates and freeze results

**Files:** Extend `src/kb_runtime/claim_review.py`, `tests/test_claim_review.py`.

- [x] Test a supported plain-text direct claim, semantic rejection, absent quote, damaged raw, blocked rights, review timing, unsupported types, and open contradiction. Period, unit, entity, and negation meaning remain the named human reviewer's judgment; byte presence alone cannot verify them.
- [x] Test conflicting related claims together and a documented resolution. `NO_KNOWN_CONFLICT` remains a limited reviewer attestation.
- [x] Test original `OPEN` gap remains unchanged; only a passing direct claim gets a new `CLOSED_BY_REVIEW` receipt inside the frozen review report. All other gaps stay open.
- [x] Test replay, changed payload under one run ID, self-consistent tampered report, atomic create, and recheck after raw damage.
- [x] Confirm focused tests fail, implement per-gate statuses and atomic immutable write, then confirm they pass.

## Task 3: CLI and delivery

**Files:** Update `src/kb_runtime/__main__.py`, `README.md`, `docs/superpowers/specs/2026-09-28-kb-mini-spec-program.md`; add CLI tests in `tests/test_claim_review.py`.

- [x] Add `review-claims` CLI with explicit packet, claim report, passage report, project/catalog/state directory, and run ID arguments. Print report JSON with `publication_allowed: false`.
- [x] Document the manual review packet, `INTERNAL_REVIEWED` meaning, blocked type contracts, rights limit, and remaining PDF/contradiction limits. Mark 05 as a first slice.
- [x] Run focused and full required checks, review independent code/design feedback, inspect status/diff/staged paths, run `git diff --cached --check`, and deliver only owned completed files under repository Git rules.

## Acceptance

- A reviewer can freeze a defensible internal decision for exact supported direct claims; semantic support is never inferred from quote presence.
- Rights, meaning, contradictions, cutoff, and source damage each have a distinct blocked result. Derived claims and assumptions remain blocked with an explicit missing-contract reason.
- No claim review turns on real publication, changes an old report or gap, or silently closes unresolved evidence.
