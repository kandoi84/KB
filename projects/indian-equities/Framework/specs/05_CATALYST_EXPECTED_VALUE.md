# Catalyst Expected Value Specification

## Question
What identifiable events can move estimates or valuation over the next 3-24 months, and what is their probability-weighted impact?

## Required fields per catalyst
- Description
- Expected date/window
- Probability of occurrence
- Estimated impact on fair value (%)
- Estimated impact on earnings (%) if applicable
- Independence from other catalysts
- Source / evidence

## Formula
Catalyst EV contribution = probability × fair-value impact × timing discount.

Timing discount defaults:
- <=6 months: 1.00
- 6-12 months: 0.90
- 12-24 months: 0.75
- >24 months: 0.50 unless strategically critical

## Score anchors
5.0 = multiple high-probability, independent, material catalysts with near-term timing
4.0 = one strong or several moderate catalysts
3.0 = balanced / modest catalysts
2.0 = weak or distant catalysts
1.0 = catalysts mostly speculative
0.0 = identifiable negative catalysts dominate

## Guardrails
- Do not count an event twice through both earnings and valuation impact.
- Corporate announcements are not catalysts unless they alter cash flow, probability or valuation.
- Correlated catalysts must be clustered and probability-adjusted together.
