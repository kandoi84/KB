# Indian Equities KB --- Runtime Implementation Handoff

**Date:** 2026-09-28\
**Purpose:** Preserve the latest decisions from the ChatGPT
architecture/research discussion in the Git repository.\
**Status:** Approved implementation direction. This document supplements
existing KB architecture/spec files; it does not replace the existing
research ontology.

## 1. Product Goal

Build a deterministic, auditable Indian-equities research system capable
of evaluating roughly 50 companies and identifying approximately 5
candidates with the strongest probability-weighted expectation gaps.

The research hierarchy remains:

**Macro → Sector → Industry → Company**

The analytical chain is:

**Raw evidence → Current state → Fundamentals → Market-implied
expectations → Expectation gap → Valuation → Catalyst EV → Score +
confidence/error band**

Central metric:

**Expectation Gap = Most-likely fundamental path − Market-implied path**

The system should emphasize: - current information first; - one
most-likely operating path rather than mechanically correlated
bull/base/bear cases; - independent probabilities for major debates; -
probability-weighted fair value; - explicit analysis of what the market
appears to believe differently; - catalysts, capital allocation, FCF and
downside asymmetry; - valuation triangulation rather than dependence on
one methodology.

## 2. Preserve Existing Ontology

Do **not** redesign or delete the existing KB hierarchy, research
content, legacy agent specifications, framework specifications, company
research, manifests, schemas, gaps or derived outputs during the first
runtime implementation.

Legacy material stays in place until migration tests pass.

## 3. Runtime Diagnosis

The current system is **spec-heavy and runtime-light**.

The architecture contains strong research concepts, but the following
are not yet sufficiently operational: - enforceable orchestration/state
transitions; - persisted/resumable workflow state; - automatic
evidence-gap resolution; - automatic Case Book creation at
publication; - outcome-driven postmortems; - regression-gated framework
changes; - a fully active learning loop.

The priority is therefore execution, not additional architecture design.

## 4. Approved Six-Responsibility Runtime

Implement the runtime under:

`src/kb_runtime/`

### 4.1 Orchestrator / State Machine

The orchestrator performs control-plane work, not investment analysis.

Responsibilities: - accept task/entity; - resolve workflow; - check
freshness; - enforce dependency DAG; - persist run state; - retry
deterministic failures; - block invalid downstream work; - create run
manifest; - publish only after validation; - automatically open/update
Case Book.

Required states:

`CREATED → PLAN_READY → INGESTING → NORMALIZED → ANALYZED → JUDGMENT_REVIEWED → VALIDATED → SNAPSHOT_FROZEN → PUBLISHED → CASE_OPENED`

Failure/review states: - `BLOCKED_MISSING_DATA` -
`BLOCKED_SOURCE_CONFLICT` - `BLOCKED_VALIDATION` - `FAILED_RUNTIME` -
`HUMAN_REVIEW_REQUIRED`

Transitions must be machine-checkable and resumable.

### 4.2 Evidence Engine

Merge evidence/source handling, market data, web/sentiment, earnings
ingestion and extraction into one engine with adapters.

Responsibilities: - primary-source-first retrieval; - filings,
transcripts and IR; - RBI/government/exchange sources; - market data and
consensus; - immutable raw storage; - source manifests; - Claim IDs /
Evidence IDs; - freshness; - conflicts; - explicit gap resolution.

Hard rule:

**Web fetch exists to resolve explicit evidence gaps, not to generate
narrative.**

Every gap should track: - `web_resolvable` - `preferred_source` -
`fallback_source` - `last_attempt` - `status` - `reason_unresolved`

Gap/source-access classes: - `PUBLIC_WEB_PRIMARY` -
`PUBLIC_WEB_SECONDARY` - `INTERNAL_RESEARCH` - `EXPERT_NETWORK` -
`MANAGEMENT_ACCESS` - `PROPRIETARY_DATA` - `UNRESOLVABLE`

Attempt `PUBLIC_WEB_PRIMARY` automatically before publication when
appropriate.

### 4.3 Analysis Engine

Macro, Sector, Industry, Company, Expectations, Valuation, Probability
and Catalyst should normally be modules/services rather than independent
runtime agents.

Outputs should include: - current state; - business quality; - quality
trajectory; - market-implied expectations; - expectation gap; -
valuation; - catalyst map; - downside map; - probability-weighted fair
value; - evidence grade; - error bands.

### 4.4 Judgment Engine

Expert frameworks are judgment modules, not personas.

Recommended sequence:

**Facts/KB → Business economics → Expectations/valuation → Munger
inversion → Kahneman bias audit → Feynman mechanism check → Optionality
check → Premortem → Score + Poker**

Munger checks: - inversion; - margin of safety; - circle of
competence; - opportunity cost; - incentives; - second-order effects.

Kahneman checks: - anchoring; - recency; - extrapolation; - small-sample
error; - regression to mean; - narrative coherence; - confirmation
bias; - availability bias; - base-rate neglect.

Feynman checks: - explain earnings engine simply; - identify 2--3
variables that drive intrinsic value; - explain causal chain from
catalyst → KPI → earnings → valuation. If the mechanism cannot be
explained clearly, reduce thesis confidence.

Optionality/Naval checks are selective: - asymmetric upside; - real
versus narrative optionality; - scalability without proportional
capital; - measurable milestones; - principal/owner mindset.

Mandatory hammer check:

**Would this framework produce the same diagnosis regardless of
company?**

If yes, reduce its weight/confidence.

### 4.5 Integrity & Validation Engine

Combine workflow compliance, research integrity and snapshot/audit into
validators.

Workflow validation: - required tasks; - dependencies; - freshness; -
permissions; - manifest completeness.

Epistemic validation: - unsupported claims; - evidence laundering; -
guidance presented as fact; - circular sourcing; - ignored
contradictions; - false precision; - thesis-first sourcing; - stale
consensus; - hindsight contamination.

Scoring validation: - deterministic thresholds; - error bars; - evidence
grade; - poker representation derives from structured output; - no
overclaim when intervals overlap.

Snapshot validation: - same cutoff; - no mixed vintages; - complete
lineage.

### 4.6 Learning Engine

Combine Case Book, postmortem, historical/counterfactual cases, learning
and self-healing into an event-driven service.

The learning loop is active only when this lifecycle executes:

`PUBLISHED RESEARCH → CASE_OPENED → OUTCOME_OBSERVED → CASE_UPDATED → POSTMORTEM → ERROR_CLASSIFICATION → EVAL/BENCHMARK GENERATED → CHANGE_PROPOSAL → REGRESSION TEST → HUMAN APPROVAL IF STRUCTURAL → VERSION BUMP`

There must be **no silent self-modification**.

## 5. Case Book

Every published opinion automatically creates a frozen Case Book record
as part of publication.

Inception fields: - `case_id` - `entity` - `decision_date` -
`cutoff_timestamp` - `snapshot_id` - `price` - `benchmark` -
`business_quality` - `quality_trajectory` -
`market_implied_expectations` - `most_likely_path` - `expectation_gap` -
`valuation` - `valuation_fragility` - `multiple_compression_risk` -
`catalysts` - `probabilities` - `timing` - `downside_mechanism` -
`premortem` - `score` - `score_error_band` - `evidence_grade` -
`poker_hand` - `poker_draw` - `critical_gaps` - `falsifiers`

Later observations append; they never overwrite inception data: -
evaluation date; - stock return; - benchmark return; - relative
return; - actual operating outcome; - actual quality trajectory; -
multiple change; - earnings-revision outcome; - catalyst outcome; -
thesis correctness; - valuation correctness; - timing correctness; -
process correctness; - error classification; - lessons.

Process/result matrix: - GOOD PROCESS / GOOD RESULT - GOOD PROCESS / BAD
RESULT - BAD PROCESS / GOOD RESULT - BAD PROCESS / BAD RESULT

Error taxonomy: - `THESIS_ERROR` - `PROBABILITY_ERROR` -
`VALUATION_ERROR` - `TIMING_ERROR` - `DATA_ERROR` - `SOURCE_ERROR` -
`MACRO_REGIME_ERROR` - `CATALYST_ERROR` - `MISSING_INFORMATION` -
`PROCESS_VIOLATION` - `MODEL_ERROR` - `UNAVOIDABLE_SURPRISE`

## 6. Scoring and Poker

Current provisional score: - Macro: 15% - Sector attractiveness: 20% -
Multiple attractiveness / % to FV: 25% - Long-term FV durability: 25% -
Catalyst probability: 15%

Do not change these weights during the first runtime implementation.

Poker mapping: - 95--100: AA - 90--94: KK - 85--89: QQ - 80--84: JJ -
75--79: TT - 70--74: 99 - 65--69: 88 - 60--64: 77

Draw labels: - No draw - Gutshot - OESD - Flush draw - Combo draw

Interpretation: - Made hand = current quality + current fundamental
position - Draw = credible positive expectation-revision paths - Board =
what market already knows/prices - Pot odds = expected payoff versus
downside

Poker must be derived from structured outputs, not written as post-hoc
storytelling.

Current scoring weakness to diagnose before changing weights: - Business
Quality - Quality Trajectory - Valuation Fragility - Multiple
Compression Risk - Expectation Gap - Downside Asymmetry

Add these initially as diagnostics and backtest before making them
weighted score components.

## 7. Research Integrity / Source Policy

Raw evidence is immutable.

Separate: - facts; - management guidance; - consensus; - derived
calculations; - assumptions; - inference; - sentiment; - unknowns.

Every material analytical claim should ultimately be traceable through:

**Score → Probability → Valuation → Research conclusion → Claim ID →
Normalized fact → Evidence ID/Source ID → Raw evidence**

Primary-source supremacy: Tier 1: - audited financials; - annual
reports; - results; - investor presentations; - exchange filings; -
company announcements/releases; - transcripts; - management guidance; -
regulator/government/RBI; - official industry associations.

Tier 2: - broker research; - credit rating research; - institutional
research; - specialist databases; - sourced financial media.

Tier 3: - general portals; - aggregators; - newsletters; - blogs.

Tier 4: - Reddit/social/forums only for sentiment and question
generation unless independently verified.

Source tier is not the same thing as certainty.

## 8. GAPS

Every entity should maintain `GAPS.md`.

Each gap should include: - question; - importance; - known; - unknown; -
evidence required; - best source; - management/expert question; - thesis
impact; - valuation impact; - confidence penalty; - status.

The system must distinguish web-resolvable gaps from
institutional/proprietary gaps and must never fabricate resolution.

## 9. Historical Evaluation

Priority historical case types: - high-quality compounder de-rated; -
expensive quality continued compounding; - low-multiple value trap; -
turnaround worked; - turnaround failed; - cyclical peak margins; -
improving business before rerating; - great company bought too
expensive.

Historical testing must: 1. freeze historical cutoff; 2. prohibit
look-ahead; 3. run the workflow; 4. freeze the output; 5. reveal later
outcome only afterward.

Longer-term target: at least \~100 historical company snapshots before
trusting a 50-to-5 production selector.

A 20-case regression gate is only a bootstrap minimum for prompt/config
changes; it is not proof of model validation.

## 10. Runtime Acceptance Tests

### Orchestrator is not considered real until:

1.  one command runs a company workflow end-to-end;
2.  run state persists;
3.  failed steps resume without rerunning completed steps;
4.  invalid dependencies block publication;
5.  web-resolvable gaps are attempted automatically;
6.  human review is requested only for material ambiguity;
7.  a complete run manifest exists;
8.  publication automatically creates a Case Book entry;
9.  the same frozen snapshot reruns reproducibly;
10. logs identify which module changed the final decision.

### Learning loop is not active until:

1.  publish automatically creates Case Book + frozen snapshot/cutoff;
2.  later outcome appends rather than overwrites;
3.  due evaluation triggers postmortem + error category + process/result
    classification;
4.  reproducible failure creates benchmark/eval;
5.  proposed prompt/scoring change leaves production unchanged until
    regression passes;
6.  structural changes require explicit human approval;
7.  luck/unavoidable surprise is recorded without forcing framework
    change.

## 11. Immediate Implementation Order

Do not expand architecture before these work.

1.  Create `src/kb_runtime/` skeleton.
2.  Implement persisted orchestrator/state machine.
3.  Implement run manifest.
4.  Implement minimal executable `company_research` workflow.
5.  Implement evidence-gap resolver.
6.  Make publication automatically create frozen Case Book.
7.  Implement outcome event + postmortem trigger.
8.  Implement eval generation.
9.  Add Judgment Engine modules.
10. Add Valuation Fragility + Quality Trajectory diagnostics.
11. Add 20-case regression gate for prompt/config changes.

## 12. First Integration Test

Use **HDFC Bank** as the first integration test because existing
research artifacts already exist.

The first runtime does not need to recreate the full research stack. It
may use adapters over existing HDFC research outputs to prove
orchestration.

Minimum test: - one CLI command starts HDFC company research; - state
persists; - completed steps are recorded; - a named step can fail
once; - rerunning the same `run_id` resumes from the failed point; -
already-completed steps are not repeated; - validation gates
publication; - publication creates a frozen Case Book entry; - failure
in Case Book creation must not leave a false terminal-success state.

Potential CLI shape, subject to existing packaging conventions:

`python -m kb_runtime company-research --entity "HDFC Bank"`

Inspect the repository and dependency files before choosing YAML/PyYAML
or any framework. Prefer Python standard library where practical. Do not
introduce a heavy orchestration framework for the first implementation.

## 13. Git / Change-Control Rules

-   Local authoritative repo: `~/code/KB`
-   Remote: `kandoi84/KB`
-   Inspect current tree/imports before editing.
-   Create a feature branch.
-   Do not work directly on `main`.
-   Do not delete legacy architecture/agent files.
-   Keep changes incremental.
-   Run tests before commit.
-   Report files changed, tests run and commit SHA.
-   Structural methodology changes require explicit approval.
-   Routine state/data refreshes may be automated once validators are
    working.

## 14. Core Research Philosophy

The system must distinguish: - excellent business at a fair/cheap
price; - good business becoming excellent before recognition; -
excellent business priced for perfection; - average/bad business
masquerading as value.

The objective is not to produce generic "good company" research. The
system should find where **quality, trajectory, expectations and price
disagree in a way that creates asymmetric alpha**.

Valuation lenses should remain independent: - DCF/SOTP; - historical
multiples; - peers; - growth-adjusted valuation; - reverse DCF /
market-implied expectations; - probability-weighted fair value.

When independent valuation lenses disagree, widen the error bar rather
than force convergence.

Every final company view should ultimately support a concise stance
(target ≤100 words) plus a structured poker-hand metaphor, but the
metaphor must remain downstream of evidence and analysis.

## 15. Implementation Instruction for Codex

Before modifying the repository:

1.  Inspect the complete repository.
2.  Check git status, current branch and remote.
3.  Locate existing architecture/specification files.
4.  Confirm whether `src/kb_runtime` already exists.
5.  Identify dependency/packaging/test conventions.
6.  Report exact files proposed for the first implementation.

Then implement only the first executable slice: - runtime skeleton; -
persisted state machine; - run manifest; - minimal company workflow; -
`PUBLISHED → CASE_OPENED`; - HDFC integration test; - failure/resume
test.

Do not redesign the ontology, scoring model or research framework during
this slice.
