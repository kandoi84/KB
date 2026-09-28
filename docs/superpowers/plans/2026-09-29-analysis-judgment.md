# Analysis and judgment worksheet implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze a sourced, point-in-time internal analysis worksheet with deterministic fair-value arithmetic and explicit judgment checks.

**Architecture:** A focused `analysis_judgment` module validates a strict analyst packet against frozen claim review and live typed metric leaves. It calculates only declared additive debate effects, then writes an immutable internal report. CLI and README expose the contract without changing `company-research` or publication.

**Tech Stack:** Python standard library (`Decimal`, `hashlib`, `json`, `pathlib`) and pytest.

**Spec:** `docs/superpowers/specs/2026-09-29-analysis-judgment-design.md`.

## Global constraints

- Keep `publication_allowed: false` on every result. No score, poker label, investment stance, or real-company publication in this slice.
- Use a timezone-aware strict live cutoff. `query_metrics` is the numeric authority; a reviewed quote is not a numeric query.
- Use plain decimal strings and `Decimal`, never binary floats, for probabilities and values.
- Preserve existing raw sources, catalog records, claim reports, thesis, and valuation history. A new run ID creates a new report.
- Synthetic fixtures demonstrate mechanics only, not model accuracy or real research quality.

## Review focus

1. A self-consistently rehashed parent report with a forged `INTERNAL_REVIEWED` status must not pass. Add a test in Task 1.
2. A revised typed metric selected after the cutoff must not replace the earlier leaf, while a later cutoff must select the revision. Add a test in Task 1.
3. A model file whose bytes change after a successful run must make replay fail, even with the same packet. Add a test in Task 2.
4. Two debates that share a driver or declare correlation must not be summed as independent effects. Add a test in Task 2.
5. Filled but generic judgment text, or an omitted bias/mechanism/inversion check, must not look reviewed. Add a test in Task 3.

---

### Task 1: Bind evidence and packet

**Files:** Create `src/kb_runtime/analysis_judgment.py`; create `tests/test_analysis_judgment.py`.

**Interfaces:** Produce `load_analysis_inputs(packet_path: Path, claim_review_path: Path, project_dir: Path, catalog_path: Path, state_dir: Path) -> tuple[dict, dict, list[dict]]`. It returns the normalized packet, verified 05 report, and exact selected metric leaves. Task 2 consumes this tuple.

- [ ] Write failing tests for exact schema, safe IDs, timezone cutoff, `prepared_at <= cutoff`, entity/ISIN matching, complete macro→sector→industry→company chain, exact claim review ID and `INTERNAL_REVIEWED` refs, source/catalog damage, strict metric leaf selection, late revision, ambiguous series, and forged parent safety fields. Reuse existing claim-review test setup instead of inventing a weaker parent report.
- [ ] Run `python -m pytest -q tests/test_analysis_judgment.py`; confirm the intended failures.
- [ ] Implement the strict packet reader and upstream verifier. Reuse 05's raw/catalog recheck through a public verification wrapper if needed; do not trust digest alone or private output status. For each metric ref call `query_metrics(catalog_path, project_dir, isin, metric_name, period_end, cutoff_timestamp)` and match the exact leaf, including unit/scope/kind/value/filing ID.
- [ ] Rerun the focused tests and inspect actual pass/fail output.

### Task 2: Calculate and freeze internal valuation

**Files:** Extend `src/kb_runtime/analysis_judgment.py` and `tests/test_analysis_judgment.py`.

**Interfaces:** Produce `analyze_judgment(packet_path: Path, claim_review_path: Path, project_dir: Path, catalog_path: Path, state_dir: Path, run_id: str) -> dict`. It writes `state_dir / "analysis_runs" / f"{run_id}.json"` and returns the frozen report. Task 3 exposes it through the CLI.

- [ ] Write failing tests for `base + Σ(p × incremental_impact)` using exact decimal strings, positive result, range inclusion and width, model snapshot SHA-256/path confinement/as-of, duplicate driver and correlation rejection, catalyst double-count guard, source/assumption labels, blocked evidence with no fair value, atomic create, changed packet or model bytes on replay, and report tamper. Include one valid but still unpublished synthetic result.
- [ ] Run the focused tests and confirm failure before implementation.
- [ ] Implement `Decimal` arithmetic with one documented output precision/rounding rule, model hash verification, distinct blocked reasons, immutable report digest and atomic create. Re-evaluate parent/raw/catalog/model inputs on replay before returning an old report. If a syntactically valid packet has unavailable evidence, freeze a blocked report without a computed value; malformed or inconsistent bindings raise without a report.
- [ ] Rerun focused tests. Review status and diff for unintended writes.

### Task 3: Judgment checks and CLI

**Files:** Extend `src/kb_runtime/analysis_judgment.py`, `src/kb_runtime/__main__.py`, `tests/test_analysis_judgment.py`; update `projects/indian-equities/README.md` and `docs/superpowers/specs/2026-09-28-kb-mini-spec-program.md`.

**Interfaces:** Add `analyze-judgment --packet --claim-review-report --project-dir --catalog --state-dir --run-id`. JSON output is the frozen report from Task 2.

- [ ] Write failing tests for all nine named bias checks, substantive inversion/falsifiers, 2–3 named value drivers, catalyst→KPI→earnings→valuation chain, missing/generic explanations, diagnostic labels, and explicit `NOT_ASSESSED` fields for price/consensus/opportunity cost when data is missing. Add a CLI invocation test.
- [ ] Run the focused tests and confirm failure.
- [ ] Implement judgment field validation and `HUMAN_REVIEW_REQUIRED` output. Document the packet and exact limits in README. Mark 08 as an active first slice in the program table, with model and market-data validation still open.
- [ ] Run focused tests and the full project gate (`python -m pytest -q`), then inspect failures and fix those caused by this slice.
- [ ] Get independent design/code review. Check `git status`, task-owned diff, staged paths, and `git diff --cached --check`. Deliver only completed 08 files using the repository's current Stop-hook manifest rule; do not stage concurrent 06/07 work or untracked research files. Record hook commit SHA and push result.

## Acceptance

The report ties every usable claim and metric to the exact cutoff, recomputes declared arithmetic, exposes missing judgment, and stays internal. A complete looking packet still cannot become a published recommendation, ranking, or validated model result through this command.
