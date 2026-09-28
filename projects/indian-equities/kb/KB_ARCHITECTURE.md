# Indian Equities KB Architecture

## Principle
The scoring system consumes structured, versioned knowledge-base snapshots. It must not recreate macro, sector, valuation, earnings, or event data ad hoc for each company.

## Knowledge hierarchy

### 1. Macro KB
Shared across all companies.
Stores India and global rates, inflation, growth, liquidity, credit, FX, commodities, fiscal/capex, PMI/trade and other universal variables, each with source, timestamp, data vintage, confidence, z-score/percentile.

### 2. Sector KB
One folder per sector.
Stores cycle position, sector valuation history, supply/capacity, demand drivers, industry structure, key cost inputs, regulation, sector KPI definitions, and the macro-to-sector transmission map.

### 3. Company KB
One folder per company.
Stores reported financial history, KPI history, management guidance, consensus, company-specific exposures, capital allocation, balance sheet, ownership/corporate actions, events/catalysts, thesis and falsifiers.

### 4. Valuation KB
For each company store separate valuation objects:
- DCF / SOTP / residual income as appropriate
- historical multiples
- peer multiples
- growth-adjusted multiples
- reverse DCF / market-implied expectations
- probability-weighted fair value
- valuation error band

### 5. Market Expectations KB
Stores what is already priced in:
- implied revenue CAGR
- implied margin
- implied ROIC
- implied terminal growth
- sector-specific implied KPIs
- current consensus vs history
- estimate revision breadth
- valuation percentile

Key output:
`Expectation Gap = Most-likely fundamental path - Market-implied path`

### 6. Events & Catalysts KB
Stores company-specific and sector events with date/window, probability, value impact, downside if delayed/failed, source, dependencies, and priced-in assessment.

### 7. Snapshot Layer
Each ranking run references a frozen snapshot:
- snapshot_id
- cutoff timestamp
- macro version
- sector version
- company version
- market-data version
- consensus version
- valuation-model version

No ranking may mix vintages silently.

## Scoring flow
Raw data -> normalized KB objects -> deterministic parameter calculations -> confidence/error bars -> final comparable score.

## Refresh cadence
- Market price / multiples: daily or on-demand
- Macro market data: daily/weekly depending on variable
- Official macro releases: on release
- Sector indicators: weekly/monthly/quarterly by series
- Company results/KPIs: quarterly
- Consensus estimates: weekly and after results/material events
- Company events/catalysts: event-driven
- Full valuation model: after results/material events; otherwise roll-forward only

## Guardrails
1. Source once, reference many times.
2. Never duplicate the same macro datapoint into company files.
3. Separate reported, consensus, derived, and analyst-estimate fields.
4. Store raw inputs before transformations.
5. Preserve old snapshots.
6. Never overwrite historical consensus with current consensus.
7. Market-implied expectations should be derived mechanically where possible.
8. Event probabilities require an evidence note and calibration bucket.
9. DCF and multiples are independent lenses; do not force one to match the other.
10. Fair-value confidence must reflect disagreement between valuation methods.
