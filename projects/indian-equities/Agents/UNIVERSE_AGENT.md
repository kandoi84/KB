# Indian Equities — 14-Company Universe Agent

## Purpose
Maintain a comparable starter universe of 14 Indian listed equities: the top two liquid, sector-defining market leaders across seven deliberately diverse sectors.

This agent is a research-universe constructor, not a recommendation engine.

## Public Equity Investing workflow
Use the Public Equity Investing `idea-generation` workflow for universe triage and research prioritization. The agent must not treat inclusion as a Buy recommendation.

## Fixed sectors
1. Pharma
2. Banks
3. Financials ex-banks
4. Industrials
5. Cement
6. IT Services
7. Consumer Staples

## Selection rule
For each sector:
1. Start with India-listed, liquid large-cap companies.
2. Rank primarily by current equity market capitalization.
3. Confirm the company is a genuine economic leader in the intended sector.
4. Use category purity / sector relevance as a tie-breaker.
5. Exclude companies whose classification would duplicate another sector or whose value is mainly driven by unrelated businesses.
6. Record selection date, market cap, ticker, and source.
7. Re-check the universe quarterly or after a major corporate action.

## Current 14-company universe — 26 Sep 2026
| Sector | Company | NSE ticker | Rationale |
|---|---|---|---|
| Pharma | Sun Pharmaceutical Industries | SUNPHARMA | Largest Indian pharma market-cap leader |
| Pharma | Divi's Laboratories | DIVISLAB | Large-cap pharma/API leader and #2 in selected pharma universe |
| Banks | HDFC Bank | HDFCBANK | Largest private-sector bank by market cap |
| Banks | ICICI Bank | ICICIBANK | #2 private-sector bank by market cap |
| Financials ex-banks | Bajaj Finance | BAJFINANCE | Largest pure-play diversified retail NBFC / financial-services leader |
| Financials ex-banks | Bajaj Finserv | BAJAJFINSV | Large listed non-bank financial conglomerate across lending/insurance/AMC |
| Industrials | Larsen & Toubro | LT | Dominant listed Indian engineering/construction leader |
| Industrials | ABB India | ABB | Large listed automation/electrification industrial leader; current market cap above Siemens India |
| Cement | UltraTech Cement | ULTRACEMCO | Largest Indian cement company by market cap/capacity leadership |
| Cement | Ambuja Cements | AMBUJACEM | #2 selected Indian cement leader by market cap |
| IT Services | Tata Consultancy Services | TCS | Largest Indian IT-services company by market cap |
| IT Services | Infosys | INFY | #2 Indian IT-services leader by market cap |
| Consumer Staples | Hindustan Unilever | HINDUNILVR | Largest broad FMCG / consumer-staples leader |
| Consumer Staples | ITC | ITC | Major consumer-staples/cigarettes leader with very large listed market cap |

## Required output for every company
Before the 50-to-5 framework can be trusted, each company must eventually have:
- current information timestamp;
- raw-data snapshot with provenance;
- macro score + uncertainty;
- sector-attractiveness score + uncertainty;
- valuation-attractiveness score + uncertainty;
- earnings-expectations score + uncertainty;
- fair-value-durability score + uncertainty;
- catalyst expected value + probability;
- probability-weighted fair value;
- fair-value error band;
- evidence-quality grade;
- ≤100-word stance;
- exact poker made-hand + draw classification;
- first rejection / thesis-break condition.

## Determinism guardrails
- No score without the required raw fields for that parameter spec.
- Missing data must remain missing; do not infer a numeric substitute silently.
- Every input must carry `as_of_date`, `source`, and `source_posture`.
- Use the same snapshot date across companies wherever possible.
- Store raw data separately from derived scores.
- Sector-specific adapters are allowed only where specified in Framework/specs.
- Any manual override must record old value, new value, reason, author, and date.
- Company name should not influence mechanical factor calculations.
- Inclusion in this universe is not a Buy/Sell call.

## Refresh protocol
Quarterly:
1. Re-check top-two sector leadership.
2. Preserve prior universe snapshot.
3. Flag entrants/exits rather than silently replacing names.
4. Re-run parameter scores only after fresh point-in-time inputs are stored.
5. Compare rank movement into fundamental change, valuation change, and data-change components.

## Next workflow
Use these 14 names as the first validation cohort for the deterministic framework before expanding toward 50 companies.
