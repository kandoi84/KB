# Point-in-time filings and metrics implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development task by task.

**Goal:** Register reviewed filing versions and typed reported or guidance metrics, then query only facts available at a strict live cutoff.

**Architecture:** One atomic request writes one filing and one or more metrics into the existing identity SQLite catalog. Rows are append-only and point to immutable raw source versions. A read rechecks source bytes, issuer identity, review time, and revision lineage before returning a metric.

**Tech Stack:** Python standard library, SQLite, `Decimal`, pytest.

**Spec:** `../specs/2026-09-28-structured-kb-extension.md`, mini spec 04B.

## Global constraints

- Keep the real research publication gate blocked.
- Do not store consensus, assumptions, derived values, or prices as filing metrics.
- A metric can describe a comparative prior period; its availability comes from its filing, not its `period_end`.
- Historical backfill queries need a separate reviewed archive and identity receipt contract. This slice provides strict live replay only.
- Never query a later restatement at an earlier cutoff.

## Review focus

- A metric bound to the wrong issuer or a damaged raw source must fail on write and read.
- A valid prior-period comparison must remain associated with its later filing date.
- A revision must keep the same complete series key and have one successor.
- A read before first-seen or review time must return no metric.
- Invalid decimals, units, rights decisions, and malformed requests must fail before writing.

## Task 1: Atomic filing and metric registration

**Files:** Create `src/kb_runtime/metric_store.py`, `tests/test_metric_store.py`; modify `src/kb_runtime/identity_store.py` only if a reusable source metadata return is needed.

**Interfaces:** `register_filing_metrics(request_path: Path, project_dir: Path, catalog_path: Path) -> dict`. The request binds filing ID, issuer ID, ISIN, source ID/version, document type, period end, exchange publication time, first-seen time, rights and reviewer decisions, review time, evidence locator, optional filing predecessor, and nonempty metrics. Each metric binds ID, name, finite decimal string, unit, period end/kind, reporting scope, value kind, locator, and optional predecessor. Timestamp and raw hash are inherited from the filing.

- [ ] Write focused failing tests for registration, exact replay, wrong issuer, damaged source, invalid input, and atomic rollback.
- [ ] Run focused tests and confirm the expected failure.
- [ ] Add append-only filing/metric tables, validation, and atomic registration.
- [ ] Run focused tests and confirm they pass.

## Task 2: Revisions and strict cutoff reader

**Files:** Modify `src/kb_runtime/metric_store.py`, `tests/test_metric_store.py`.

**Interfaces:** `query_metrics(catalog_path: Path, project_dir: Path, isin: str, metric_name: str, period_end: str, cutoff_timestamp: str) -> list[dict]`. Returned rows include metric ID, value/unit, period kind/scope, filing/version IDs, publication and first-seen times, and `availability_mode: LIVE_STRICT`. Distinct complete series keys stay distinct.

- [ ] Write focused failing tests for cutoff, comparative periods, later restatements, revision mismatch/branch, and damaged-source reads.
- [ ] Run focused tests and confirm the expected failure.
- [ ] Implement linear revision rules and strict cutoff selection.
- [ ] Run focused tests and confirm they pass.

## Task 3: CLI, documentation, and delivery

**Files:** Modify `src/kb_runtime/__main__.py`, `README.md`, `docs/superpowers/specs/2026-09-28-kb-mini-spec-program.md`; add CLI tests in `tests/test_metric_store.py`.

- [ ] Write failing CLI tests for registration and query JSON output.
- [ ] Run them and confirm the expected failure.
- [ ] Add the commands and concise request contract. Mark 04B active only after checks pass.
- [ ] Run focused and full pytest, inspect Git diff and staged files, run `git diff --cached --check`, commit owned files, and push the feature branch.
