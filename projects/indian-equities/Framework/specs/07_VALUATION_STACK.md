# Valuation Stack Spec

## Purpose
Create a comparable valuation gauge without forcing every sector into one method.

## Required valuation lenses

### A. Intrinsic value
Use the appropriate primary method:
- DCF / FCFF / FCFE
- SOTP for multi-business companies
- residual income / P-B/ROE framework for banks where appropriate

Output:
- central fair value
- sensitivity range
- terminal-value share
- model confidence

### B. Historical multiple
Use sector-appropriate metric such as P/E, EV/EBITDA, P/B, EV/sales, or FCF yield.
Calculate current percentile vs 5y/10y history, current z-score, and normalized multiple.

### C. Peer-relative multiple
Compare with a pre-defined peer set.
Adjust only through explicit quality/growth variables, not analyst discretion.

### D. Growth-adjusted valuation
Examples:
- P/E vs sustainable EPS growth
- EV/EBITDA vs EBITDA growth
- P/B vs normalized ROE
- FCF yield vs growth / cost of equity

Do not use PEG mechanically across all sectors.

### E. Reverse valuation / market-implied expectations
Solve for operating assumptions required to justify current price:
- growth
- margins
- ROIC
- terminal value
- sector-specific KPIs

### F. Probability-weighted fair value
Combine independently assessed debates and catalyst probabilities.
Do not create correlated all-good/all-bad cases as the primary method.

## Valuation gauge
Final valuation attractiveness depends on:
1. discount/premium to probability-weighted fair value
2. valuation percentile vs own history
3. peer-relative valuation
4. growth/quality-adjusted valuation
5. market-implied expectation gap
6. valuation-method disagreement / confidence

## Error bar
Widen the valuation error bar when terminal value is high, forecast duration is long, business cyclicality is high, valuation lenses disagree materially, consensus dispersion is high, or event/catalyst value is large.
