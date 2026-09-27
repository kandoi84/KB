---
kb_id: macro_india_current
layer: macro
entity: India Macro
schema_version: 1.0
as_of: 2026-09-27
source_cutoff: 2026-09-27T14:00:00+05:30
freshness_status: mixed
confidence: 0.90
status: research_v1
---

# India Macro — Current State

## Executive state

The currently verified first-hand data point to a strong real-growth backdrop, inflation that has moved back up toward the upper half of the RBI target band, a policy rate of 5.25%, continued central-government capex execution, and strong reported credit growth in industry/services. Several market-sensitive inputs (current INR, G-sec curve, Brent, global rates and liquidity) are deliberately left unresolved pending a Market Data Agent refresh.

## Growth and activity

- **Real GDP growth, Q1 FY2026-27:** 7.8% YoY. `REPORTED_FACT` — Tier 1 government release; confidence A.
- **Nominal GDP growth, Q1 FY2026-27:** 10.3% YoY. `REPORTED_FACT` — Tier 1; confidence A.
- **Real GVA growth, Q1 FY2026-27:** 8.2% YoY. `REPORTED_FACT` — Tier 1; confidence A.
- **Industrial production, July 2026:** +6.7% YoY, as reported in the Government's GDP backgrounder. `REPORTED_FACT` — Tier 1 government source; confidence A-/B+ pending direct IIP table ingestion.

**Interpretation:** domestic activity is currently strong enough that the macro regime should not be described as a growth slowdown. This is an `INFERENCE`, not a reported fact.

## Inflation

- **CPI inflation, August 2026:** 4.82% YoY, up from 4.45% in July. `REPORTED_FACT` — Tier 1 MoSPI/PIB; confidence A.
- **Food inflation, August 2026:** 5.95% YoY. `REPORTED_FACT` — Tier 1; confidence A.
- **WPI inflation, August 2026:** 9.92% YoY, versus 9.78% in July. `REPORTED_FACT` — Tier 1 Ministry of Commerce/PIB; confidence A.

**Interpretation:** inflation pressure has re-accelerated at both retail and wholesale levels. Sector impact should be handled downstream because food, fuel and manufactured-price transmission differ materially by industry.

## Monetary policy

- **RBI policy repo rate:** 5.25% as of the August 2026 MPC period. `REPORTED_FACT` — Tier 1 RBI; confidence A.
- **Standing Deposit Facility:** 5.00%.
- **Marginal Standing Facility / Bank Rate:** 5.50%.
- **CRR:** 3.00%.
- **SLR:** 18.00%.

**Interpretation:** policy is not currently highly restrictive by recent-cycle standards, but the Macro KB will not label the stance as easing/neutral/tight until the full MPC statement and forward guidance are ingested directly.

## Fiscal and public capex

As of end-July 2026:
- **Fiscal deficit YTD:** ₹4,55,144 crore, or **26.8% of FY2026-27 Budget Estimate**.
- **Central capital expenditure YTD:** ₹4,50,635 crore, or **36.9% of Budget Estimate**, versus 30.9% in the corresponding prior-year period.

`REPORTED_FACT` — Tier 1 Controller General of Accounts; confidence A.

**Interpretation:** central capex execution is running ahead of the comparable budget-utilisation pace from the prior year, which is directionally supportive for capex-sensitive industries. This does not automatically imply strong private capex or company-specific order conversion.

## Credit conditions

The Government's Q1 GDP backgrounder reports for July 2026:
- credit to **industry:** +20.0% YoY;
- credit to **services:** +22.9% YoY.

`REPORTED_FACT` from a Tier 1 government summary, confidence A-/B+ pending direct RBI series ingestion.

## Current macro regime — provisional

| Dimension | State | Confidence |
|---|---|---|
| Growth | Strong | A- |
| Inflation | Re-accelerating | A |
| Monetary policy | Repo 5.25%; stance not yet classified | A / gap on stance |
| Public capex | Strong execution | A |
| Credit | Strong | B+ pending direct RBI series |
| FX | Unresolved | GAP |
| Commodities | Unresolved | GAP |
| Global rates | Unresolved | GAP |
| Liquidity | Unresolved | GAP |

## Important discipline

This file is a macro observation layer. It must not directly convert "strong GDP" or "higher inflation" into company-level conclusions. Sector and Industry KBs own transmission, while Company KBs own exposure intensity.
