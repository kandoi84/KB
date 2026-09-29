# Classified Gap Attempts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze rights-gated, local primary source attempts for classified open gaps without closing claims or enabling publication.

**Architecture:** Validate immutable parent reports and an exact human classification packet, use one hardcoded local source adapter, and write an intent plus final receipt for safe replay. The adapter delegates immutable storage to `record_source` and performs no network access.

**Tech Stack:** Python standard library, existing `kb_runtime` JSON source store, pytest.

**Spec:** `docs/superpowers/specs/2026-09-29-gap-adapter-design.md`

## Global Constraints

- No live HTTP, NSE MCP, web search, inferred source URL, or auto gap closure.
- No synthetic input becomes a real-company result. Keep `publication_allowed: false`.
- Preserve existing source version schema, source and claim reports, and the `company-research` gate.
- Stage and commit only completed 07 files after affected and full checks; push the feature branch under repository rules.

## Review Focus

- A rights reference that is merely a public URL cannot authorize local collection; test blocked input.
- A self-consistent forged report or cross-entity gap cannot trigger import; test parent binding and exact IDs.
- A future retrieval cannot make an earlier cutoff current; test old report unchanged and later run required.
- A crash after `record_source` cannot create another version or lose the attempt; test resume.
- A symlink, empty/oversize raw file, lookalike exchange domain, or URL with credentials/query/private host cannot pass; test each unsafe class.

---

### Task 1: Validate classification and eligibility

**Files:** Create `src/kb_runtime/gap_attempt.py`; create `tests/test_gap_attempt.py`.

**Interfaces:** `attempt_gap(packet_path: Path, claim_report_path: Path, source_report_path: Path, source_request_path: Path, claim_request_path: Path, raw_path: Path | None, metadata_path: Path | None, project_dir: Path, state_dir: Path, attempt_id: str) -> dict`. It consumes the exact fields and classes in the spec; it returns a frozen attempt receipt. Original request paths are required to verify parent semantics. Raw and metadata paths are required only for eligible classes.

- [ ] Write tests for a valid synthetic `PUBLIC_PRIMARY_MISSING` packet, then for each blocked classification and ineligible readiness status. Check that no source version is created in blocked cases.
- [ ] Run `pytest tests/test_gap_attempt.py -q` and see the expected import or missing-function failure.
- [ ] Implement strict packet parsing, parent digest, request hash and historical semantic checks, exact gap lookup, source readiness binding, URL/metadata/raw validation, and eligibility results. Reuse existing report loaders and safe ID style.
- [ ] Run `pytest tests/test_gap_attempt.py -q`; fix validation until the focused cases pass.

### Task 2: Store an idempotent attempt

**Files:** Continue `src/kb_runtime/gap_attempt.py` and `tests/test_gap_attempt.py`.

**Interfaces:** `attempt_gap(...)` creates a temporary registration metadata file with the actual retrieval time, then calls `record_source(registration_metadata_path, raw_path, project_dir)` only after eligibility and writes `state/gap_attempts/<attempt_id>/intent.json` and `result.json`. The result carries `attempt_id`, parent IDs, packet/raw/metadata digests, rights decision, adapter version, status/reason, source version when present, `gap_status: OPEN`, and `publication_allowed: false`.

- [ ] Write tests for one successful import, replay, changed input collision, tampered receipt or source, blocked receipt, and interrupted intent after storage.
- [ ] Run the focused test and see the new cases fail before implementation.
- [ ] Implement canonical hashing and atomic write-once intent/result records. Generate registration metadata with the attempt time frozen in intent as `retrieved_at`; never accept a backdated retrieval time. On resume, regenerate the same metadata, verify the existing source version and hashes, and write only the missing result. Never overwrite a completed result.
- [ ] Run the focused test and verify all cases pass.

### Task 3: CLI, documentation, and delivery

**Files:** Modify `src/kb_runtime/__main__.py`, `projects/indian-equities/README.md`, and `docs/superpowers/specs/2026-09-28-kb-mini-spec-program.md`; extend `tests/test_gap_attempt.py`.

**Interfaces:** CLI `attempt-gap --packet --claim-report --source-report --source-request --claims [--raw-file --metadata] --project-dir --state-dir --attempt-id` prints receipt JSON or exits nonzero with a clear validation error. Both optional flags are required for eligible classes.

- [ ] Add a CLI test for successful synthetic local import and blocked/no-network result; observe failure.
- [ ] Wire the CLI and document that rights are human-attested, the old gap stays open, and a new cutoff refresh plus 05 review is needed.
- [ ] Run `pytest tests/test_gap_attempt.py -q` and `python3 -m compileall -q src/kb_runtime`; confirm success.
- [ ] Run `pytest -q`; inspect the full result and fix failures caused by 07.
- [ ] Review `git status --short`, the exact task diff, and the staged paths; run `git diff --cached --check`.
- [ ] Commit task-owned files with `feat: add classified gap attempts` and push the feature branch to `origin` under repository delivery rules. Record the commit and any remaining rights or real-source limit.
