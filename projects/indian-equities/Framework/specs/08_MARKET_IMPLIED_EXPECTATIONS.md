# Market-Implied Expectations Spec

## Core question
What must the market believe for today's share price to be fair, and how does that compare with the most likely operating path?

## Required outputs
- current price and date
- reverse-DCF / reverse-valuation assumptions
- current consensus assumptions
- historical normalized assumptions
- analyst most-likely path
- expectation gap
- confidence

## Examples by sector
Banks: loan growth, NIM, credit cost, ROE, terminal P/B/ROE.
NBFC: AUM growth, NIM/spread, credit cost, leverage, ROA/ROE.
IT: revenue growth, margin, FCF conversion, terminal growth.
Cement: volume, EBITDA/tonne, utilization, capacity additions.
Pharma: US/domestic growth, margins, R&D, regulatory outcomes.
Staples: volume growth, pricing, gross margin, reinvestment.
Industrials: order growth, execution, margin, working capital, ROIC.

## Guardrail
Do not call a stock cheap simply because its multiple is low.
A low multiple can be fair if the market-implied path is close to the most likely deteriorating path.
