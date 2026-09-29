# Error Bar Specification

## Factor uncertainty
Each factor receives an uncertainty estimate in score points.

### Default bands
- ±0.25: mostly directly observed, current and stable
- ±0.50: some forecast/judgment
- ±0.75: meaningful cyclicality or forecast dependence
- ±1.00: sparse data / major structural uncertainty
- ±1.25+: experimental / unproven business model

## Fair-value uncertainty
Suggested starting ranges before company-specific sensitivity work:
- Stable compounder: ±8-10%
- Normal diversified company: ±12-15%
- Cyclical / leveraged / transition: ±15-25%
- Early-stage / turnaround / binary: ±25%+

## Score error aggregation
Weighted RSS of factor uncertainties, then add correlation penalty of 1-3 score points when several factors depend on the same underlying variable.

## Ranking rule
If two companies' score intervals materially overlap, treat them as statistically tied unless another decision metric (expected return, downside, catalyst timing, portfolio fit) separates them.
