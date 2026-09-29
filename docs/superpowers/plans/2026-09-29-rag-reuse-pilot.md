# RAG Reuse Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure maintained parsing and retrieval components against the KB's immutable, cutoff-aware evidence path before replacing any baseline.

**Architecture:** Docling creates a separate derived PDF representation and chunks; Haystack indexes only chunks that existing KB readers prove eligible at a query cutoff. Both adapters retain source identities, while the current `pypdf` and token-overlap paths remain the baseline. No pilot result can publish real research.

**Tech Stack:** Python 3.10+, SQLite catalog, Docling 2.130.0, Haystack AI 3.2.0, pytest.

**Spec:** `docs/superpowers/specs/2026-09-29-rag-reuse-assessment.md`

## Global Constraints

- Pin pilot dependencies in a separate requirements file; do not add them to the minimal runtime requirements until a measured promotion.
- Record exact distribution versions, top-level licenses, and dependency resolution in the pilot report. The reviewed upstream commits in the spec are provenance, not package pins.
- Keep raw files, source versions, existing extractions, and typed metrics authoritative and immutable. Pilot output is derived and rebuildable.
- Reject wrong issuer, future publication/first-seen/extraction time, missing rights, broken raw hash, ambiguous citation, and mixed corpus identity.
- Keep `publication_allowed: false`; synthetic fixtures never establish real retrieval quality.
- Stage only task-owned files, run affected and full checks, review staged diff, commit, and push verified slices.

## Review Focus

- Scanned or badly ordered PDF text can create plausible but wrong citations; test explicit blocked or review-required output.
- A parser rerun after a cutoff cannot make old chunks visible at that cutoff; test extraction arrival.
- Two versions of the same filing cannot silently overwrite each other in the derived index; test distinct source/version/hash identities.
- A retrieval query with a valid ISIN from another issuer must fail before ranking; test identity binding.
- A framework recall score can pass while the quote, page, or source hash is wrong; test the local anchor gate separately.

---

### Task 1: Pin and probe maintained dependencies

**Files:** Create `requirements-rag-pilot.txt`; create `docs/superpowers/specs/2026-09-29-rag-pilot-environment.md`.

**Interfaces:** The pilot environment is separate from `requirements.txt`; the document records exact package versions, resolved transitive licenses, installation commands, platform, and a local parse/index smoke result. No runtime import is added in this task.

- [ ] Verify Docling 2.130.0 and Haystack AI 3.2.0 package metadata from their published distributions; record licenses and Python floor.
- [ ] Pin both distributions in `requirements-rag-pilot.txt` and resolve in an isolated environment. Record the resolved environment and any restricted or incompatible transitive license.
- [ ] Run a local synthetic PDF conversion and in-memory document-store smoke probe. Record success or exact blocker; do not fetch third-party documents in this probe.
- [ ] Review package and environment diff, run `git diff --cached --check`, commit `docs: pin RAG pilot dependencies`, and push the feature branch.

### Task 2: Add a Docling-derived extraction path

**Files:** Create `src/kb_runtime/docling_pilot.py`; create `tests/test_docling_pilot.py`; update `docs/superpowers/specs/2026-09-29-rag-pilot-environment.md`.

**Interfaces:** `extract_docling_pilot(catalog_path: Path, project_dir: Path, filing_id: str) -> dict` reads a reviewed PDF filing and its exact raw hash, parses local bytes with a pinned Docling version, and writes a versioned derived receipt and chunks. `query_docling_pilot(catalog_path: Path, project_dir: Path, filing_id: str, cutoff_timestamp: str) -> list[dict]` returns only verified, time-eligible chunks with stable IDs, source version/raw hash, physical page, and reviewed role or `UNKNOWN`.

- [ ] Write failing tests for a two-page synthetic PDF, raw-hash mismatch, missing rights, empty/ambiguous page mapping, late extraction, replay, and changed parser version. Pin page and source anchor assertions.
- [ ] Run `pytest -q tests/test_docling_pilot.py`; observe the expected failure.
- [ ] Implement the smallest adapter using Docling `DocumentConverter` and `HierarchicalChunker` or `HybridChunker`. Store Docling's structured output as a distinct derived version; validate all returned page references and chunk identities before writing. Reuse existing filing and source readers instead of reproducing their rules.
- [ ] Run focused tests, `python3 -m compileall -q src/kb_runtime`, and `pytest -q`. Record parser failures and limits. Review and commit only Task 2 files, then push.

### Task 3: Add a filtered Haystack retrieval candidate

**Files:** Create `src/kb_runtime/haystack_pilot.py`; create `tests/test_haystack_pilot.py`; update the pilot environment document.

**Interfaces:** `search_haystack_pilot(catalog_path: Path, project_dir: Path, issuer_id: str, query: str, cutoff_timestamp: str, *, isin: str | None = None, document_types: list[str] | None = None, speaker_role: str | None = None, limit: int = 5) -> list[dict]`. Build a disposable Haystack index from source-verified cutoff-eligible chunks, apply metadata filters before ranking, and return the same citation identity fields as `search_chunks`. No answer generation.

- [ ] Write failing tests for issuer, ISIN, document, role, revision, cutoff, tampered raw, and stable top-k behavior. Include no-match and mixed-issuer cases.
- [ ] Run `pytest -q tests/test_haystack_pilot.py`; observe the expected failure.
- [ ] Implement the adapter with Haystack `Document`, an in-memory document store, and a maintained retriever. Select verified eligible chunks through the existing readers. Apply framework metadata filters and repeat the issuer/cutoff assertions on returned records.
- [ ] Run focused tests and `pytest -q`; record corpus and runtime limits. Review and commit only Task 3 files, then push.

### Task 4: Compare against the frozen baseline

**Files:** Create `src/kb_runtime/rag_pilot_eval.py`; create `tests/test_rag_pilot_eval.py`; create `docs/superpowers/specs/2026-09-29-rag-pilot-results.md`.

**Interfaces:** `compare_rag_pilot(gold_path: Path, catalog_path: Path, project_dir: Path) -> dict` runs the existing lexical path and the Haystack candidate against the identical validated gold cases. It reports source-anchor recall@5, optional rank metrics, issuer/cutoff violations, parse failures, corpus hashes, package versions, per-case results, and whether a reviewed-real 04E promotion gate is met. Missing reviewed real gold or baseline means `NOT_PROMOTED`.

- [ ] Write failing tests for a deterministic synthetic 30-case set, changed corpus/gold input, wrong-page citation, future chunk, zero denominator, and absent/conflict cases. Verify synthetic data always reports `NOT_PROMOTED`.
- [ ] Run `pytest -q tests/test_rag_pilot_eval.py`; observe the expected failure.
- [ ] Reuse Haystack recall/rank evaluators where label semantics match. Keep local exact quote, raw-hash, page, issuer, abstention, and cutoff checks. Freeze both candidate and baseline identities in the report.
- [ ] Run focused and full checks, inspect the full task diff, staged paths, and `git diff --cached --check`. Commit `feat: compare reused RAG components` and push. Document the measured result and the remaining real-sample review gate.
