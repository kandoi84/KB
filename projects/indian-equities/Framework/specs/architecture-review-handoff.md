# Handoff: Indian Equities KB Architecture Review

## Objective

Critically review and simplify the `kandoi84/KB` Indian Equities architecture so it becomes an executable research-and-learning system rather than a collection of design documents and overlapping agents.

This handoff is based on the persisted project design in ChatGPT Library. Before changing code, reconcile every recommendation below against the live GitHub repo and report any mismatch.

## Executive diagnosis

The project has a strong research philosophy and good source/scoring discipline, but the architecture is over-agentized and under-wired.

The biggest issue is not missing agents. It is that the **orchestrator and learning loop are primarily design concepts, not enforced runtime behavior**.

Current conceptual agents include Orchestrator, Workflow Compliance, Research Integrity, Evidence/Source, Earnings, Macro, Market Data, Web/Sentiment, Sector, Industry, Company Fundamentals, Expectations, Valuation, Probability, Premortem, Historical Case, Snapshot/Audit, Postmortem, Case Book, Learning, and Self-Healing.

This is too many independent nodes unless they have distinct state, contracts, tools, and execution ownership.

# 1. Verify current repo before editing

Inspect the live repo and answer:

1. Which agents currently have executable code versus only Markdown/specs?
2. Is there a real orchestrator entrypoint?
3. Is there a persisted run state?
4. Is there a dependency DAG implemented in code/config?
5. Does every research run create a run manifest?
6. Does every published company score create or update a Case Book record?
7. Is there a scheduled/event-driven path that revisits open cases?
8. Are postmortems actually triggered from realized outcomes?
9. Can a postmortem automatically create a benchmark/eval case?
10. Is there a production-change gate that prevents silent prompt/weight/schema changes?

If any answer is "no", treat that component as **designed but not activated**.

# 2. Recommended runtime architecture

Reduce the system to six runtime responsibilities.

## A. Orchestrator / State Machine

Make this executable, not descriptive.

Responsibilities:
- receive task/entity
- resolve required workflow
- check freshness
- build dependency DAG
- track state
- retry deterministic failures
- block invalid downstream execution
- write run manifest
- publish only after validation
- open/update Case Book

The orchestrator should NOT do investment analysis itself.

Required states:

```text
CREATED
-> PLAN_READY
-> INGESTING
-> NORMALIZED
-> ANALYZED
-> JUDGMENT_REVIEWED
-> VALIDATED
-> SNAPSHOT_FROZEN
-> PUBLISHED
-> CASE_OPENED
```

Failure states:

```text
BLOCKED_MISSING_DATA
BLOCKED_SOURCE_CONFLICT
BLOCKED_VALIDATION
FAILED_RUNTIME
HUMAN_REVIEW_REQUIRED
```

Every transition should be machine-checkable.

## B. Evidence Engine

Merge conceptual roles:
- Evidence / Source
- Market Data
- Web / Sentiment
- Earnings ingestion/extraction

Use adapters instead of separate agents where possible.

Responsibilities:
- primary-source-first retrieval
- web fetch
- filings/transcripts/IR
- RBI/government/exchange data
- market data
- consensus where available
- immutable raw storage
- source manifests
- claim IDs
- freshness
- conflict flags
- GAPS resolution

Hard rule:
**Web fetch exists to resolve explicit gaps, not to generate narrative.**

Every `GAPS.md` item should include:

```yaml
web_resolvable: true
preferred_source:
fallback_source:
last_attempt:
status:
reason_unresolved:
```

If `web_resolvable=true`, the orchestrator should attempt resolution automatically before publication.

## C. Analysis Engine

Do not keep Macro, Sector, Industry, Company, Expectations, Valuation, Probability and Catalyst logic as separate runtime agents unless technically necessary.

Implement them as reusable modules under one analysis engine.

Inheritance:

```text
Macro
-> Sector
-> Industry
-> Company
```

Required outputs:
- current state
- business quality
- quality trajectory
- market-implied expectations
- expectation gap
- valuation
- catalyst map
- downside map
- probability-weighted fair value
- evidence grade
- error bands

## D. Judgment Engine

Add the expert-framework layer here.

Do NOT create Munger/Kahneman/Feynman/Naval as independent agents.

### Munger module

Mandatory:
- Inversion
- Margin of Safety
- Circle of Competence
- Opportunity Cost
- Incentive analysis
- Second-order effects

Required questions:
1. If this investment disappoints badly in 3-5 years, what most likely caused it?
2. Is this genuinely cheap or merely low-multiple?
3. What must remain true for intrinsic value to compound?
4. What is the opportunity cost versus the next-best stock?
5. Are management incentives aligned?

### Kahneman module

Bias audit:
- anchoring
- recency
- extrapolation
- small-sample error
- regression to mean
- narrative coherence
- confirmation bias
- availability bias
- base-rate neglect

Required output:
`bias_flags.yaml`

### Feynman module

Mechanism test:
- explain the earnings engine simply
- identify 2-3 variables that actually move intrinsic value
- causal chain from catalyst -> KPI -> earnings -> valuation

If the mechanism cannot be expressed clearly, lower thesis confidence.

### Naval / Optionality module

Use selectively.

Questions:
- where is asymmetric upside?
- is optionality real or narrative?
- can upside scale without proportional capital?
- is there an owner/principal mindset in capital allocation?
- does optionality have measurable evidence and milestones?

### Hammer check

Mandatory:
> Would this framework produce the same diagnosis regardless of the company?

If yes, reduce its weight/confidence.

## E. Integrity & Validation Engine

Merge:
- Workflow Compliance
- Research Integrity
- Snapshot / Audit

Keep separate validators inside one service.

Validators:

### Workflow validator
- required tasks executed
- dependencies valid
- freshness rules passed
- no unauthorized write
- run manifest complete

### Epistemic validator
- unsupported claims
- evidence laundering
- guidance treated as fact
- circular sourcing
- contradiction ignored
- false precision
- thesis-first sourcing
- stale consensus
- hindsight contamination

### Scoring validator
- deterministic thresholds followed
- no arbitrary decimals where prohibited
- error bars present
- evidence grade valid
- poker label derives from score
- no small-score overclaim when intervals overlap

### Snapshot validator
- same information cutoff
- no mixed vintages
- complete source lineage

## F. Learning Engine

Merge:
- Case Book
- Postmortem
- Historical Case
- Learning
- Self-Healing

This should be an event-driven service, not five agents.

The learning loop is only "activated" if this lifecycle actually executes:

```text
PUBLISHED RESEARCH
-> CASE_OPENED
-> OUTCOME_OBSERVED
-> CASE_UPDATED
-> POSTMORTEM
-> ERROR_CLASSIFICATION
-> EVAL/BENCHMARK GENERATED
-> CHANGE_PROPOSAL
-> REGRESSION TEST
-> HUMAN APPROVAL IF STRUCTURAL
-> VERSION BUMP
```

No silent self-modification.

# 3. Case Book is a first-class production component

Every published company opinion should create a frozen case.

Required inception fields:

```yaml
case_id:
entity:
decision_date:
cutoff_timestamp:
snapshot_id:

price:
benchmark:

business_quality:
quality_trajectory:

market_implied_expectations:
most_likely_path:
expectation_gap:

valuation:
valuation_fragility:
multiple_compression_risk:

catalysts:
catalyst_probabilities:
catalyst_timing:

downside_mechanism:
premortem:

score:
score_error_band:
evidence_grade:
poker_hand:
poker_draw:

critical_gaps:
falsifiers:
```

Later append, never overwrite:

```yaml
evaluation_date:
stock_return:
benchmark_return:
relative_return:

actual_operating_outcome:
actual_quality_trajectory:
multiple_change:
earnings_revision_outcome:
catalyst_outcome:

thesis_correct:
valuation_correct:
timing_correct:
process_correct:

error_classification:
lessons:
```

Mandatory matrix:

```text
GOOD PROCESS / GOOD RESULT
GOOD PROCESS / BAD RESULT
BAD PROCESS / GOOD RESULT
BAD PROCESS / BAD RESULT
```

# 4. Critical scoring change

Current score uses Macro 15%, Sector 20%, Valuation 25%, FV Durability 25%, Catalyst 15%.

This misses an issue exposed by ICICI Bank:

**A very good business can still be a fragile stock when the starting multiple requires continued excellence.**

Do NOT immediately add another weighted factor before backtesting.

Instead add mandatory diagnostics:

```text
Business Quality
Quality Trajectory
Valuation Fragility
Multiple Compression Risk
Expectation Gap
Downside Asymmetry
```

Then test historically whether one or more deserve explicit weight.

The system must distinguish:

1. excellent business + cheap/fair price
2. excellent business + expensive price
3. good business improving toward excellent
4. average business temporarily improving
5. poor business at a low multiple
6. turnaround / special situation

Important archetype:
> **good business becoming excellent while the market still prices "good"**

# 5. Poker framework refinement

Poker should not be post-hoc storytelling.

Interpretation:
- **Made hand** = current quality + current fundamental position
- **Draw** = credible positive expectation-revision paths
- **Board** = what the market already knows/prices
- **Pot odds** = expected payoff versus downside

Add a validation rule:
If the poker description cannot be traced to business-quality, expectation-gap, catalyst and valuation inputs, reject it.

# 6. Learning-loop acceptance tests

The loop is NOT active until these pass.

## Test 1: automatic case creation
Publish a company recommendation.
Expected:
- Case Book entry created automatically
- snapshot_id and source cutoff frozen

## Test 2: outcome update
Inject a later price/earnings result.
Expected:
- prior thesis not overwritten
- outcome appended

## Test 3: postmortem trigger
Mark case evaluation due.
Expected:
- postmortem generated
- error category assigned
- process/result classified

## Test 4: eval generation
Postmortem identifies reproducible failure.
Expected:
- benchmark/eval case generated

## Test 5: self-healing safety
A prompt/scoring change is proposed.
Expected:
- production unchanged
- proposal versioned
- regression runs
- structural change waits for human approval

## Test 6: no-learning control
If outcome is mainly luck/unavoidable surprise:
Expected:
- outcome recorded
- framework unchanged

# 7. Orchestrator acceptance tests

The orchestrator is NOT real until:

1. One command runs a company workflow end-to-end.
2. Run state is persisted.
3. Failed steps resume without repeating completed steps.
4. Invalid dependencies block publication.
5. Open web-resolvable gaps are attempted automatically.
6. Human review is requested only for material ambiguity.
7. A complete run manifest is written.
8. Publication automatically creates/updates Case Book.
9. Same snapshot rerun is reproducible.
10. Logs show which module changed the final decision.

# 8. Recommended directory structure

```text
agents/
  orchestrator/
  evidence/
  analysis/
  judgment/
  validation/
  learning/

skills/
  analysis/
    macro/
    sector/
    industry/
    company/
    expectations/
    valuation/
    catalysts/
  judgment/
    munger/
    kahneman/
    feynman/
    optionality/

workflows/
  company_research.yaml
  earnings_update.yaml
  sector_refresh.yaml
  case_review.yaml
  historical_counterfactual.yaml

state/
  runs/
  cases/
  trust/

evals/
benchmarks/
prompts/
schemas/
```

If old agent folders exist, do not delete until imports/references migrate and tests pass.

# 9. Do not overbuild trust scores yet

Track:
- factual accuracy
- provenance accuracy
- reproducibility
- calibration
- workflow compliance

But do not let trust scores affect investment scores until sample sizes are credible.

# 10. Historical Case Book program

Build point-in-time historical cases for:
- high-quality compounder that de-rated
- expensive quality stock that kept compounding
- low-multiple value trap
- turnaround that worked
- turnaround that failed
- cyclical at peak margins
- improving business before re-rating
- great company bought too expensively

For every case:
- freeze historical date
- use only information available then
- run full workflow
- reveal actual outcome only after output freezes
- record what the framework got right/wrong

Target:
>=100 company snapshots before trusting the 50-to-5 production ranking.

# 11. Web-fetch priority

Every gap should be classified:

```yaml
resolution_type:
  - PUBLIC_WEB_PRIMARY
  - PUBLIC_WEB_SECONDARY
  - INTERNAL_RESEARCH
  - EXPERT_NETWORK
  - MANAGEMENT_ACCESS
  - PROPRIETARY_DATA
  - UNRESOLVABLE
```

Attempt `PUBLIC_WEB_PRIMARY` automatically.

Preferred order:
1. company / exchange / regulator / government
2. industry associations
3. broker / rating / institutional research
4. reputable media
5. aggregators
6. social sentiment only

Never allow an LLM to narratively fill an unresolved institutional-information gap.

# 12. Architecture principles to preserve

Do not weaken:
- raw evidence immutable
- facts/guidance/consensus/assumptions/inference separate
- source once, reference many
- no silent interpolation
- no look-ahead
- same cutoff for rankings
- old snapshots preserved
- DCF and multiples remain independent
- confidence separate from attractiveness
- production methodology changes require human approval
- poker cannot override numeric analysis
- rankings remain research-grade until eval gates pass

# 13. Requested Claude review output

Please respond with:

## A. Repo reality check
For each major component:
- exists in code?
- exists only as spec?
- missing?

## B. Simplification map
For each current agent:
- KEEP as runtime agent
- MERGE into another engine
- CONVERT to module/validator
- DELETE after migration

## C. Learning-loop status
State clearly:
- DESIGNED
- PARTIALLY WIRED
- ACTIVE

Provide evidence.

## D. Orchestrator status
State clearly:
- DOCUMENT ONLY
- PARTIAL EXECUTION
- REAL STATE MACHINE

Provide evidence.

## E. File-by-file implementation changes
List exact files to add/modify/deprecate/delete later.

## F. Minimal implementation sequence
Prefer the smallest path to a real system:

1. executable orchestrator state machine
2. run manifest
3. web-resolvable gap resolver
4. Case Book auto-create
5. postmortem trigger
6. eval generation
7. Judgment Engine
8. valuation-fragility / quality-trajectory diagnostics
9. historical case pipeline
10. trust calibration later

## G. Tests
Provide unit/integration tests and exact acceptance criteria.

## H. Risks
Flag:
- over-engineering
- circular dependencies
- prompt sprawl
- state duplication
- silent self-modification
- LLM shortcut risks

# Final design principle

The system's objective is not to produce "good research."

Generic AI can already do that.

The system exists to improve the probability of finding **excellent risk/reward setups that a good generic analysis would miss**, while learning from its own historical decisions.

The core distinction to optimize is:

```text
Excellent business at fair/cheap price
Good business becoming excellent before recognition
Excellent business priced for perfection
Average/bad business masquerading as value
```

If the architecture does not measurably improve that distinction over baseline AI plus simple quality/valuation screens, it is not earning its complexity.
