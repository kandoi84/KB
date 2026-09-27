---
kb_id: sector_financials_lending_current_state
layer: sector
entity: Financials - Lending
schema_version: 1.0
as_of: 2026-09-27
source_cutoff: 2026-09-27
freshness_status: PARTIAL
confidence_grade: B
updated_by: sector_agent
---

# Financials — Current State

## Executive state

The sector currently operates with a **5.25% RBI policy repo rate**, **3.0% CRR** and **18.0% SLR**. RBI's official page showed overnight MCLR of **7.80–8.00%**, savings deposit rate **2.50%**, >1-year term deposit rates **6.00–6.75%**, and call rates **4.30–5.25%**, all as of September 24, 2026. The same RBI snapshot showed INR/USD at **95.9099** as of 1pm on September 24. These are Tier 1 / official observations, but market-rate fields are older than the strict 1-day SLA and are therefore not labelled fully fresh. Source: Reserve Bank of India official website.

## Current observable conditions

| Variable | Latest verified value | Observation date | Source tier | Confidence | Freshness |
|---|---:|---|---|---|---|
| Policy repo rate | 5.25% | 2026-09-24 page state | Tier 1 | A | FRESH structural / policy |
| CRR | 3.00% | 2026-09-24 page state | Tier 1 | A | FRESH structural / policy |
| SLR | 18.00% | 2026-09-24 page state | Tier 1 | A | FRESH structural / policy |
| Savings deposit rate | 2.50% | 2026-09-24 | Tier 1 | A | STALE vs 1-day SLA |
| >1y term deposit rate range | 6.00–6.75% | 2026-09-24 | Tier 1 | A | STALE vs 1-day SLA |
| Overnight MCLR range | 7.80–8.00% | 2026-09-24 | Tier 1 | A | STALE vs 1-day SLA |
| Call-rate range | 4.30–5.25% | 2026-09-24 | Tier 1 | A | STALE vs 1-day SLA |
| 6.36% GS 2031 yield | 6.8162% | 2026-09-24 | Tier 1 | A | STALE vs 1-day SLA |
| 6.94% GS 2036 yield | 7.1073% | 2026-09-24 | Tier 1 | A | STALE vs 1-day SLA |
| INR/USD | 95.9099 | 2026-09-24 | Tier 1 | A | STALE vs 1-day SLA |

## What can be concluded now

### 1. Funding benchmark remains materially above policy rate
The verified term-deposit and MCLR ranges show that bank liability and lending rates remain materially above the 5.25% policy rate. This is an observation, not yet a conclusion about bank NIM direction; deposit and loan repricing lags must be handled at industry/company level.

### 2. Reserve requirements are an important sector input
CRR of 3.0% and SLR of 18.0% are directly relevant to bank liquidity/balance-sheet economics. Their effect on NBFCs is indirect through bank liquidity, system rates and funding markets.

### 3. Current sector-quality conclusion is intentionally incomplete
The June 2026 RBI Financial Stability Report is confirmed as an available Tier 1 source, but this run has not yet reliably extracted the required latest system GNPA, CRAR, stress-test and NBFC asset-quality figures from the primary document. Those values remain OPEN gaps rather than being filled from secondary articles.

## Sector state classification — provisional

- Policy/funding regime: **moderate rates / easing-to-neutral context requires industry confirmation**
- Liquidity: **INSUFFICIENT_EVIDENCE for current classification**
- Credit growth: **INSUFFICIENT_EVIDENCE in this sector snapshot**
- Deposit growth: **INSUFFICIENT_EVIDENCE in this sector snapshot**
- Asset-quality cycle: **INSUFFICIENT_EVIDENCE pending FSR extraction**
- Capital adequacy: **INSUFFICIENT_EVIDENCE pending FSR extraction**

This is intentionally not converted into a bullish/bearish sector rating until the missing Tier 1 system data is obtained.
