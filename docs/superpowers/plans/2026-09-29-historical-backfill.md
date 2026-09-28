# Historical Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconstruct typed metrics at a past cutoff only when manually reviewed exchange archive attestations pin the exact filing bytes and ISIN relationship.

**Architecture:** Separate reviewed, append-only filing and identity receipts bind raw `EXCHANGE_ARCHIVE` manifests. A separate query checks every eligible revision and both proofs before selecting a series leaf. The existing `LIVE_STRICT` query stays untouched.

**Tech Stack:** Python, SQLite, pytest.

**Spec:** `docs/superpowers/specs/2026-09-28-structured-kb-extension.md`

## Global Constraints

- Both raw archive captures must predate the queried cutoff; a later archive page is insufficient.
- Filing archive bytes bind source ID, version ID, raw SHA-256, issuer, ISIN, and publication time. Identity archive bytes bind issuer, ISIN, company and security source versions, and announcement time.
- Reviewed receipts and source rows are append-only. Backfill never enables publication.
- The metadata clock is caller supplied. Both receipts are manual reviewer attestations, not independently authenticated timestamps. Real historic availability remains conditional on external source validation.

## Review Focus

- A future revision must not replace a past value.
- Missing proof for an earlier eligible revision must block a later one.
- A conflicting revision branch must fail closed.
- Tampered raw archive or filing bytes must fail on replay and query.
- A current URL and claimed old publication time are not authenticated proof. This slice records a named reviewer's historical-source attestation, labels the result research-only, and keeps publication blocked. Independent timestamp validation remains future work.

---

### Task 1: Proof receipt

**Files:** Create `src/kb_runtime/historical_backfill.py`; test `tests/test_historical_backfill.py`.

**Interfaces:** `register_backfill_proof(request_path: Path, project_dir: Path, catalog_path: Path) -> dict` consumes a JSON request naming an existing filing, separate filing and identity archive source versions, separate proof IDs and locators, reviewer, and review time. Raw archive JSON names exact filing and identity facts.

- [x] Write a failing positive test for both archive receipts and idempotent replay.
- [x] Run `python3 -m pytest -q tests/test_historical_backfill.py` and see the missing feature fail.
- [x] Implement input validation, archive/raw/source verification, and append-only SQLite receipts.
- [x] Add mismatch, late capture, replay conflict, and tamper tests; run affected tests.

### Task 2: Backfilled query

**Files:** Modify `src/kb_runtime/historical_backfill.py`; test `tests/test_historical_backfill.py`.

**Interfaces:** `query_backfilled_metrics(catalog_path: Path, project_dir: Path, isin: str, metric_name: str, period_end: str, cutoff_timestamp: str) -> list[dict]` returns reviewed leaves with `availability_mode: BACKFILLED`, proof IDs/times, reconstruction time, and `publication_allowed: false`.

- [x] Write a failing test showing a proven old filing despite later ingestion and strict live exclusion.
- [x] Run affected test and see the expected failure.
- [x] Implement cutoff proof checks and revision leaf resolution.
- [x] Add future revision, missing predecessor, branch, and tamper tests; run affected suite (10 passed).
- [x] Confirm full pytest after concurrent 05 claim-review failure is fixed; then independent review and delivery.
