---
kb_id: sector_financials_lending_gaps
layer: sector
entity: Financials - Lending
schema_version: 1.0
last_updated: 2026-09-27
---

# Financials — Knowledge Gaps

## GAP-FIN-001 — Latest system credit growth
- Importance: HIGH
- Status: OPEN
- Known: RBI is the preferred Tier 1 source.
- Unknown: latest verified YoY scheduled-commercial-bank credit growth at the common snapshot cutoff.
- Evidence needed: RBI Weekly Statistical Supplement / DBIE point-in-time series.
- Why it matters: determines sector volume backdrop and interacts with deposit growth/liquidity.
- Downstream question: is credit demand accelerating, stable or slowing?
- Confidence penalty: material.

## GAP-FIN-002 — Latest system deposit growth
- Importance: HIGH
- Status: OPEN
- Evidence needed: RBI Weekly Statistical Supplement / DBIE.
- Why it matters: deposit growth versus credit growth drives competition, funding pressure and bank NIM risk.
- Required derived field: credit-deposit growth gap.

## GAP-FIN-003 — Current system liquidity
- Importance: HIGH
- Status: OPEN
- Evidence needed: latest RBI liquidity operations / net absorption-injection / WACR conditions.
- Why it matters: affects marginal funding pressure and transmission.

## GAP-FIN-004 — Banking-system asset quality
- Importance: HIGH
- Status: OPEN
- Known: RBI Financial Stability Report, June 2026 is confirmed as Tier 1 source.
- Unknown: current verified GNPA/NNPA, credit cost and stress-test outputs from the primary document.
- Evidence needed: direct FSR table extraction.
- Why it matters: determines whether current credit costs are below/at/above through-cycle levels.

## GAP-FIN-005 — Banking-system capital
- Importance: HIGH
- Status: OPEN
- Evidence needed: June 2026 RBI FSR system CRAR/CET1 and stress-test results.
- Why it matters: supports growth capacity and downside resilience.

## GAP-FIN-006 — NBFC system asset quality and leverage
- Importance: HIGH
- Status: OPEN
- Evidence needed: RBI FSR and latest official NBFC supervisory/system publication.
- Why it matters: sector layer must distinguish healthy bank balance sheets from potential NBFC pockets of stress.

## GAP-FIN-007 — Deposit competition / repricing direction
- Importance: MEDIUM-HIGH
- Status: OPEN
- Known: RBI official Sep 24 deposit-rate range is available.
- Unknown: direction versus prior month/quarter and effective deposit beta.
- Evidence needed: historical RBI deposit-rate series plus industry-company disclosures.

## GAP-FIN-008 — Proprietary institutional research
- Importance: MEDIUM
- Status: OPEN
- Missing: broker channel checks, private management interactions and detailed consensus datasets.
- Treatment: do not fabricate. Broker research, if provided later, is Tier 2 and may improve expectations/context rather than reported facts.
