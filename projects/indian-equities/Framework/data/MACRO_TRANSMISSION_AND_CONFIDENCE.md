# Macro Transmission & Data Confidence Spec

## Objective
Make macro and sector scoring deterministic, comparable and auditable across the Indian Equities universe.

## Three-layer architecture

### Layer 1 — Universal raw factors
Stored once per snapshot date, never re-created company by company.

Examples:
- India real GDP growth
- CPI inflation
- RBI policy rate / 10Y G-Sec yield
- System liquidity / credit growth
- INR/USD
- Brent crude
- Natural gas / coal where relevant
- Global policy rates / US 10Y
- Global PMI / trade indicators
- India industrial production
- Urban/rural consumption indicators
- Government capex / fiscal impulse

Each raw observation must include:
- as_of_date
- observation_date
- source
- source_posture
- vintage/revision identifier where available
- raw value
- unit
- frequency

### Layer 2 — Sector transmission model
Each sector has a fixed sensitivity map showing how each raw factor affects revenue, margin, balance-sheet economics and valuation.

Examples:
- Banks: policy rates, liquidity, credit growth, deposit growth, asset quality.
- NBFCs: funding cost, liquidity, credit demand, asset quality.
- IT services: US/Europe growth, enterprise tech spend, INR/USD, wage inflation.
- Cement: volume growth, petcoke/coal/freight, utilization, capacity additions.
- Industrials: government/private capex, order inflow, commodity inputs, rates.
- Pharma: US generic pricing, FDA/regulatory, INR/USD, domestic formulation growth.
- Consumer staples: rural/urban demand, commodity inputs, inflation, monsoon, pricing power.

Transmission signs and weights must be defined in advance and cannot be changed because the current stock outcome is inconvenient.

### Layer 3 — Company exposure / beta
Companies inside one sector can have different exposures.

For every material factor store:
- exposure intensity: 0 to 1
- direction: +1 / -1
- lag: immediate / 1Q / 2Q / longer
- evidence basis
- confidence

Example:
Macro impact = standardized factor state × sector sensitivity × company exposure.

The same macro state can therefore produce different company scores without narrative overrides.

## Data-source hierarchy

### Tier A — Primary / official
- Company exchange filings and annual/quarterly reports
- RBI
- NSE/BSE/Nifty Indices
- Government statistical releases / ministries
- Industry regulators and official associations where authoritative

### Tier B — Institutional market data
- Reputable consensus/market-data vendors
- Exchange-derived price/valuation history

### Tier C — High-quality secondary
- Reuters and similarly sourced financial reporting
- Industry publications with transparent methodology

### Tier D — Analyst assumption
Used only when no direct observation exists. Must never be displayed as reported data.

## Data-confidence scoring
Every raw field gets a confidence score.

- 1.00: audited/official reported fact
- 0.95: exchange / regulator / official macro release
- 0.90: robust market price/index data
- 0.80: reputable consensus with timestamp and contributor coverage
- 0.70: high-quality secondary source
- 0.50: derived estimate using sourced inputs
- 0.30: analyst assumption
- 0.00: missing

Parameter confidence = weighted average of the confidence of its required inputs, capped by completeness.

No factor may receive an A evidence grade if a conclusion-driving input is below 0.80 confidence.

## Deterministic transformation rules
1. Raw data are never manually scored directly.
2. Convert raw variables into percentiles/z-scores versus a predefined history.
3. Apply pre-specified direction and sector sensitivity.
4. Apply company exposure.
5. Aggregate using frozen weights.
6. Record output plus confidence and error band.
7. Any override must be stored separately and never overwrite the mechanical score.

## Missing-data rules
- No silent interpolation.
- No narrative replacement.
- Missing conclusion-driving input reduces confidence and widens error bars.
- If completeness falls below the parameter threshold, output `insufficient_data` instead of a number.

## Snapshot comparability
All companies in a cross-sectional ranking use the same information cutoff date.
Later releases are prohibited from historical snapshots.
Revised macro data must preserve both the original vintage and the revised value.

## Correlation guardrail
Do not double count one economic driver across multiple parameters.

Examples:
- High oil price may affect India macro, cement fuel cost and consumer inflation.
- The universal raw oil observation is stored once.
- Each downstream parameter receives only its pre-specified transmission effect.
- Cross-factor covariance is measured in the error model rather than pretending factors are independent.

## Confidence target before production ranking
A 50-to-5 ranking is not production-grade until:
- >90% of conclusion-driving fields are Tier A/B;
- all 14 validation companies have identical snapshot-date rules;
- factor repeatability is within ±2–3 score points;
- point-in-time historical tests show no look-ahead;
- score error bands are estimated from actual model instability/backtests;
- factor weights and transformations are frozen before out-of-sample evaluation.

## Current status
Framework architecture: defined.
14-company universe: defined.
Raw point-in-time dataset: not yet complete.
Sector transmission matrices: must be populated and validated.
Company exposure coefficients: must be sourced and calibrated.
Historical evals: not yet passed.

Therefore current company scores are research-grade, not deterministic production rankings.
