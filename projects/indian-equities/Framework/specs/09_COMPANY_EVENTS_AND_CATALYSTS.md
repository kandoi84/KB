# Company Events & Catalyst Spec

## Event object
Each material event must store:
- event_id
- company
- event type
- description
- expected timing
- probability bucket
- estimated value impact
- downside if delayed/failed
- dependency map
- source
- evidence confidence
- priced-in assessment
- last updated

## Probability buckets
Use calibrated ranges rather than false precision:
- Very high: 85-95%
- High: 70-85%
- Medium: 50-70%
- Low: 30-50%
- Speculative: <30%

Exact probabilities are allowed only when supported by an explicit model.

## Catalyst expected value
`EV = probability × incremental value - failure probability × downside`

Avoid double counting a catalyst already embedded in the base DCF or market-implied expectations.

## Refresh
Update event objects after company filings, regulatory decisions, earnings calls, transaction milestones, guidance changes, or credible new evidence.
