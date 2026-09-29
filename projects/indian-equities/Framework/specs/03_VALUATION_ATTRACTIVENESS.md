# Multiple / Valuation Attractiveness Specification

## Question
How much valuation support exists today relative to normalized fundamentals and probability-weighted fair value?

## Required inputs
- Current price and timestamp
- Probability-weighted fair value
- Fair-value uncertainty range
- Relevant company historical multiple percentile
- Sector-relative multiple percentile
- Normalized FCF yield / earnings yield where appropriate
- Cost of equity

## Core measurements
- Discount/premium to probability-weighted fair value
- Distance from fair-value error band
- Own-history valuation percentile
- Sector-relative valuation
- FCF yield minus cost-of-equity spread

## Score anchors
5.0 = price materially below lower bound of reasonable FV range and historically cheap
4.0 = >15% discount to central FV with supportive historical valuation
3.0 = within ~±10% of central FV / normal historical range
2.0 = 10-20% above FV or elevated historical percentile
1.0 = >20% above FV and expensive versus history
0.0 = extreme valuation unsupported by current economics

## Guardrails
- Never score cheapness from P/E alone for cyclicals.
- Normalize earnings before comparing multiples.
- For banks/financials use P/B, ROE, credit costs and normalized profitability adapters.
- Fair value must be timestamped and independent of current price.
