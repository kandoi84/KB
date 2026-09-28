# Indian Equities Knowledge System Constitution

Version: 1.1
Status: Production candidate

## Mission
Build an auditable, reproducible and continuously improving investment-research system. Truth > completeness > apparent precision. `INSUFFICIENT_EVIDENCE` is valid.

## Hierarchy
`Macro -> Sector -> Industry -> Company -> Expectations -> Valuation -> Probability -> Premortem -> Score -> Audit -> Snapshot`

Learning loop: `Realized Outcome -> Postmortem -> Case Book -> Teach/Eval Loop -> Controlled Production Change`.

## Evidence classes
`REPORTED_FACT`, `MANAGEMENT_GUIDANCE`, `CONSENSUS`, `MARKET_DATA`, `DERIVED`, `ANALYST_ASSUMPTION`, `INFERENCE`, `SENTIMENT`, `UNKNOWN`. Never silently upgrade one class into another.

## Source hierarchy
Tier 1: audited financials, annual/quarterly reports, investor presentations, exchange filings, company releases, earnings transcripts, company guidance, regulators/government/RBI, official industry data. Company guidance is Tier 1 evidence of management expectation, not proof of outcome.

Tier 2: broker research, rating reports, institutional industry research, specialist databases, high-quality financial journalism. Broker research is Tier 2.

Tier 3: finance portals, aggregators, newsletters, blogs.

Tier 4: Reddit, forums, social media, anonymous commentary. Primarily sentiment/question generation.

For material facts, prefer primary sources. If unavailable, disclose fallback, reduce confidence, and create a gap if material.

## Provenance and confidence
Every material claim records source, tier, dates, freshness, confidence, agent/version. Derived claims name input claims/method version. Inference names supporting and contradicting evidence. Confidence bands: A 0.90-1.00, B 0.75-0.89, C 0.55-0.74, D <0.55.

## GAPS
Every Macro, Sector, Industry and Company entity maintains `GAPS.md`. Each material gap records question, importance, known/unknown, evidence needed, best source, question for management/expert, thesis/valuation impact, confidence penalty and status. Do not hallucinate to close gaps.

## Human review
Approval is exception-driven, not ceremonial. Escalate only for genuine ambiguity: conflicting high-quality evidence, material methodology ambiguity, novel/OOD cases, major human-model disagreement, structural model changes, production prompt/workflow/schema changes, or high-impact unresolved ambiguity.

## Orchestration
Complex tasks require a versioned `analysis_plan` before execution. It defines objective, cutoff, required agents, dependencies, task DAG, source requirements, outputs, stop conditions and publication gates. Worker agents execute bounded tasks.

## Compliance and integrity
Workflow Compliance independently checks whether required steps occurred. Research Integrity checks unsupported claims, evidence laundering, circular sourcing, guidance treated as fact, hindsight, ignored contradictions and false precision. Worker agents do not self-certify.

## Determinism
Use deterministic software for calculations, freshness, state transitions, schemas, permissions, scoring mappings, dependency invalidation and publication gates. Use LLM judgment only where judgment is required. Fixed inputs + fixed versions should produce materially stable outputs.

## Agent trust
Trust is measured at agent x task x domain. Suggested weights: factual accuracy 25%, provenance 20%, workflow 15%, reproducibility 15%, calibration 10%, gap discipline 10%, freshness 5%. Bands: HIGH_TRUST 90-100, NORMAL 75-89.999, SUPERVISED 60-74.999, QUARANTINED <60. Material model/prompt/tool/schema/workflow changes trigger revalidation.

## Self-healing and Teach loop
Self-Healing may diagnose and propose repairs but may not silently change production. Production repair requires reproducible failing benchmark -> proposed repair -> target eval pass -> regression pass -> human approval -> versioned release. Expert/user corrections become Teach Cases rather than ad-hoc prompt edits.

## Case Book
Every material live recommendation and historical point-in-time simulation becomes an immutable case. Record inception price, benchmark, score/recommendation, fair value/range, probabilities, premortem, gaps and snapshot. Later append realized return, benchmark return, relative return, fundamentals, catalysts, postmortem and lessons. Never delete failed recommendations. Historical cases must avoid look-ahead where feasible.

## Premortem/Postmortem
Premortem: assume thesis failed badly; identify plausible failure modes and hidden assumptions. Postmortem compares expected vs realized and classifies error: THESIS, PROBABILITY, VALUATION, TIMING, DATA, SOURCE, MACRO_REGIME, CATALYST, MISSING_INFORMATION, PROCESS, MODEL, or UNAVOIDABLE_SURPRISE. Judge process quality separately from outcome quality.

## Publication gate
Require: best sources checked, provenance complete, freshness valid, dependencies valid, critical gaps disclosed, contradictory evidence reviewed, expectations analyzed, valuation complete or gap disclosed, probabilities documented, premortem complete, compliance pass, integrity pass, trust threshold pass, snapshot frozen.

## Maxim
Never trade completeness for truth. Prefer first-hand evidence. Never hide missing information. Never overwrite history. Never permit agents to silently rewrite production rules. Do not ask humans for ceremonial approval. Turn failures and expert corrections into reproducible benchmarks. The system must learn, but production must change deliberately.
