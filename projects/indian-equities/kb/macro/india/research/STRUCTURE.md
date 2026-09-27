# Macro KB Structure

## Purpose
The Macro KB is the single reusable source of macroeconomic state for all downstream Sector, Industry and Company KBs.

It should answer:
- what is happening in the economy;
- how fast conditions are changing;
- which variables are leading vs lagging;
- which observations are structural vs cyclical;
- which data are fresh, stale or missing.

The Macro KB does **not** make company recommendations. Downstream Sector and Industry KBs translate macro state into economic impact.

## Core domains
1. Growth and activity
2. Inflation and pricing
3. Monetary policy and liquidity
4. Credit and financial conditions
5. Fiscal policy and public capex
6. Labour / consumption
7. External sector and FX
8. Commodities and energy
9. Global growth / trade
10. Global rates and risk conditions

## Storage rules
- Store universal observations once.
- Preserve source date, observation period, release date and vintage.
- Prefer first-hand sources: RBI, MoSPI, Ministry of Finance/CGA, Ministry of Commerce, official global institutions.
- Do not duplicate market-price data already owned by the Market Data Agent; reference it instead.
- Separate reported observation from interpretation.
- Missing data stays missing and is logged in `GAPS.md`.

## State output
The Macro Agent should publish a concise `CURRENT_STATE.md` plus structured normalized data. Every state conclusion must point to source-backed observations and include confidence/freshness.
