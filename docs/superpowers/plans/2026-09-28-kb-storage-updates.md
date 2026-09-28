# KB Source Storage and Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox syntax for tracking.

**Goal:** Record immutable raw sources and versioned metadata for Indian Equities.

**Architecture:** A focused source store accepts metadata and a local raw file. Content hashes deduplicate raw files; canonical record hashes identify versions. The CLI exposes one update operation.

**Tech Stack:** Python standard library, pytest, local file storage.

**Spec:** docs/superpowers/specs/2026-09-28-kb-storage-updates-design.md

## Global Constraints

- Preserve the current KB folders and existing research.
- Keep raw source bytes out of Git under data/raw/.
- Keep real research publication blocked.
- No network fetch, extra dependency, or automatic Git staging.

## Review Focus

- A repeated update returns the existing version without changing bytes.
- A reused source ID with a different URL, entity, or kind is rejected.
- Malformed or timezone-free timestamps are rejected.
- An altered existing registry record is never silently replaced.
- A failed metadata write cannot create a success response.

---

### Task 1: Source store

**Files:** Create src/kb_runtime/source_store.py and tests/test_source_store.py.

**Interface:** record_source(metadata_path: Path, raw_path: Path, project_dir: Path) -> dict[str, str]. Raise ValueError for invalid metadata or identity conflicts; OSError for file failures.

- [ ] Write tests for valid storage, repeat input, changed content, identity conflict, timestamp validation, and altered existing record.
- [ ] Run python3 -m pytest tests/test_source_store.py -q and confirm new tests fail for the absent function.
- [ ] Implement validated content-addressed raw storage and immutable JSON version records.
- [ ] Run python3 -m pytest tests/test_source_store.py -q and confirm all pass.

### Task 2: CLI and documentation

**Files:** Modify src/kb_runtime/__main__.py, projects/indian-equities/README.md, projects/indian-equities/GOVERNANCE/INGESTION_POLICY.md, and tests/test_source_store.py.

**Interface:** The record-source CLI consumes record_source and produces JSON success output or a nonzero error result.

- [ ] Add a CLI test and confirm it fails before the command exists.
- [ ] Add the command and document the storage and update rules.
- [ ] Run the affected tests and the project suite.
- [ ] Inspect status, diff and staged files; run git diff --cached --check; commit owned files and push this feature branch.
