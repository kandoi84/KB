---
kb_id: sector_financials_lending_macro_transmission
layer: sector
entity: Financials - Lending
schema_version: 1.0
last_updated: 2026-09-27
---

# Financials — Macro Transmission

| Macro variable | First-order sector channel | Typical lag | Direction is conditional on | Downstream industry differentiation |
|---|---|---:|---|---|
| Real / nominal GDP growth | Credit demand, fee pools, borrower cash flows | 1–4 qtrs | leverage, capacity utilisation | Banks usually capture broad system credit; NBFC effect depends on product mix |
| Inflation | Nominal loan demand, policy response, borrower affordability | 1–4 qtrs | income growth, policy reaction | Retail lenders can face affordability stress; secured lenders may differ |
| RBI repo rate | Asset and liability repricing | immediate–4 qtrs | reset structure, deposit beta | Banks depend on loan/deposit reset; NBFCs on borrowing mix and asset yields |
| System liquidity | Marginal funding conditions and deposit competition | immediate | RBI operations, government cash, FX flows | Banks: deposit/liquidity conditions; NBFCs: wholesale spreads/refinancing |
| CRR / reserve requirements | Balance-sheet liquidity and lendable resources | immediate | offsetting RBI liquidity measures | Primarily banks; indirect funding impact on NBFCs |
| G-Sec / money-market yields | Funding costs, treasury valuations, benchmark pricing | immediate–2 qtrs | duration, funding mix | Banks carry treasury books; NBFCs more sensitive to market borrowing spreads |
| INR | Corporate borrower stress, imported inflation, offshore funding | 1–4 qtrs | hedging / sector exposure | Company-specific more than sector-wide |
| Government capex / fiscal impulse | Corporate/MSME credit demand and asset quality | 2–6 qtrs | execution and crowding out | Corporate banks benefit differently from retail lenders |
| Employment / wages | Retail credit demand and delinquencies | 1–4 qtrs | household leverage | High relevance to unsecured / consumer lenders |
| Property cycle | Mortgage demand, collateral values, developer stress | 1–6 qtrs | region/product | High relevance to HFCs and mortgage-heavy banks |

## Interpretation rule

No macro input receives a fixed positive/negative sign at sector level.

Transmission must be resolved using:
`macro state × sector sensitivity × industry model × company exposure`.
