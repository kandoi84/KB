# Indian Equities — MASTER.md

## Purpose
This project is a persistent fundamental-research system for Indian listed equities. The objective is to maintain a slowly moving intrinsic-value anchor while allowing market prices to fluctuate around that anchor, creating disciplined research and trading opportunities.

## Core valuation philosophy
- Value businesses on their underlying economics, not on short-term market price action.
- Use SOTP when conglomerate or multi-business structures make a single consolidated multiple misleading.
- Prefer DCF / FCFF by business where cash-flow economics can be modeled.
- Use multiples only as cross-checks unless the business is better suited to relative valuation.
- Fair value should change because fundamentals, capital structure, cost of capital, or long-run economics change — not because the stock price moved.

## Fair-value and trading-band framework
- Maintain a central fair-value anchor for every covered company.
- Track market-price deviation from fair value.
- Calculate rolling dispersion of price versus fair value.
- Use ±1 standard deviation as the first investigation/action band and ±2 standard deviations as an extreme band.
- Price below -1σ is a re-underwrite / potential buy zone if the thesis remains intact.
- Price above +1σ is a re-underwrite / potential trim zone if fundamentals have not improved enough to justify the premium.
- Never mechanically trade a band without checking whether fair value itself should change first.

## Model rules
- Zoho Sheet is the preferred master spreadsheet environment.
- Models should use formulas and structures compatible with Zoho Sheet.
- Blue cells = hardcoded assumptions / editable inputs.
- Black cells = formulas.
- Green cells = links to other cells / sheets.
- Do not bury hardcoded assumptions inside formulas.
- Every major valuation output should have visible checks.
- Keep a source ledger for reported facts, market data, and analyst assumptions.

## Source hierarchy
Use, in order of preference:
1. Company filings and investor relations materials.
2. Earnings releases, presentations and transcripts.
3. Exchange filings.
4. Credible market-data providers.
5. High-quality news sources.
6. Analyst estimates / explicit assumptions.

Always label whether a number is Reported, Management guidance, Consensus, Market data, Derived calculation, Analyst estimate, or User assumption.

Never invent consensus, guidance, financial metrics, dates, ownership stakes, or market data.

## Earnings workflow
For every covered company:
1. Pre-earnings preview.
2. Results / transcript analysis.
3. Model update.
4. Fair-value update.
5. Trading-band update.
6. Thesis tracker update.

## Company folder standard
Each covered company should contain:
- `COMPANY.md`
- `Thesis.md`
- `Earnings/`
- `Valuation/`
- `Model/`
- `Sources/`

## Analytical style
- Be skeptical and test assumptions.
- Do not simply agree with the user.
- Focus on what the market is pricing versus what the evidence supports.
- Identify variant perception explicitly.
- Separate operating performance from valuation / sentiment.
- State what would prove or disprove the thesis.
- Distinguish cyclical from structural changes.

## Fair-value discipline
Do not change WACC, terminal growth, target multiples or discount rates simply to fit the current stock price. A change in fair value must have an explicit economic reason such as revenue growth, margin/unit economics, capex/reinvestment, balance sheet, cost of capital, structural mix, or ownership/corporate action.

## Most-likely-path framework
Do not use correlated bull/base/bear worlds as the primary decision framework.

For every company:
1. Define the current state.
2. Underwrite one most-likely operating path.
3. Identify the independent debates that can make that path wrong.
4. Assign explicit probabilities to those debates.
5. Convert those probabilities into a probability-weighted fair value.
6. Ask what the market likely believes differently.
7. Compare expected value and downside with alternative companies in the universe.

Bull/bear cases can still be used as stress tests, but not as the primary investment decision tool.

## Mandatory three-leg thesis
Every stock thesis must explicitly assess:
1. **Macro / sector cycle and valuation** — trough, mid-cycle or peak, plus direction.
2. **Company multiple / valuation** — cheap, fair or expensive versus its own history and versus probability-weighted fair value.
3. **Earnings expectations** — falling, stable or rising; easy, fair or demanding.

## Poker framework for 50-company comparison
Every company receives a standardized poker setup.

### Five scored factors
Score each factor from 0 to 5 using current information.

| Factor | Weight | What it captures |
|---|---:|---|
| Macro factor | 15% | Rates, liquidity, commodities, currency, demand backdrop |
| Sector attractiveness | 20% | Cycle position, industry structure, capacity, competition, sector valuation |
| Multiple attractiveness / % to fair value | 25% | Current price versus probability-weighted fair value and own-history multiple |
| Long-term fair-value durability | 25% | ROIC, moat, reinvestment runway, FCF quality, balance sheet, terminal-value confidence |
| Upcoming catalyst probability | 15% | Probability, timing and magnitude of identifiable catalysts / estimate revisions |

**Poker Setup Score = weighted score × 20**, producing 0–100.

### Made-hand mapping
- 95–100: AA
- 90–94: KK
- 85–89: QQ
- 80–84: JJ
- 75–79: TT
- 70–74: 99
- 65–69: 88
- 60–64: 77
- 55–59: 66
- 50–54: 55
- 45–49: 44
- 40–44: 33
- 35–39: 22
- Below 35: high-card / speculative setup

The rank is a comparative research label, not a literal probability of investment success.

### Draw classification
The draw describes forward optionality beyond what is already reflected in the made hand.

- **No draw:** little identifiable positive optionality; thesis depends mostly on current valuation.
- **Gutshot draw:** one narrow or low-probability path to material upside.
- **Open-ended straight draw:** two or more credible independent paths to upside, but meaningful execution / macro risk remains.
- **Flush draw:** one dominant, relatively high-probability catalyst can materially re-rate value.
- **Combo draw:** multiple independent high-quality catalysts plus valuation support; rare and reserved for the strongest setups.

Do not call a setup a combo draw simply because many good things could happen. The positive paths must be independently supportable and not all depend on the same macro variable.

## Standard ≤100-word stance
At every substantive update, provide a Buy/Sell/Valuation summary in no more than 100 words. It must include current price, probability-weighted fair value, most-likely path, why the market may disagree, and current research posture.

## Versioning and model-change log
For every material valuation change, record the date, catalyst/new information, old fair value, new fair value, key assumption changes, and why the change was justified.

## Standard investment output
Every substantive company update should state current market price and as-of date, current fair value, upside/downside, ±1σ / ±2σ bands when available, segment value contributions, key estimate revisions, catalysts, risks, thesis-break conditions, and what to monitor next.

## Hallucination control
- Never fill missing market-sensitive data with invented numbers.
- If consensus is unavailable, say so and use clearly labeled analyst scenarios.
- If a number is inferred, label it.
- If a source is stale, label the date.
- Prefer no number to a fabricated number.

## Model refresh cadence
- Monthly: smooth fair-value roll-forward only.
- Quarterly: update actuals, forecast KPIs, capex, net debt and segment DCFs.
- Event-driven: update only affected businesses for material events.
- Annually: full re-underwrite of long-run growth, margins, reinvestment, WACC and terminal assumptions.

## GPT operating instruction
Before substantive work in this project:
1. Read this file.
2. Read the relevant company `COMPANY.md`.
3. Read the latest `Thesis.md`.
4. Use the latest model / valuation source as the baseline.
5. Preserve prior work unless new evidence justifies a change.
6. Explain material changes instead of silently overwriting assumptions.
7. Apply the mandatory three-leg thesis, most-likely-path probabilities, ≤100-word stance, and poker framework.

## Deterministic scoring framework
All cross-company ranking work must use the specifications under `Framework/`.

Required files:
- `Framework/SCORING_ENGINE.md`
- `Framework/specs/01_MACRO_FACTOR.md`
- `Framework/specs/02_SECTOR_ATTRACTIVENESS.md`
- `Framework/specs/03_VALUATION_ATTRACTIVENESS.md`
- `Framework/specs/04_FAIR_VALUE_DURABILITY.md`
- `Framework/specs/05_CATALYST_EXPECTED_VALUE.md`
- `Framework/specs/06_EARNINGS_EXPECTATIONS.md`
- `Framework/data/DATA_SCHEMA.md`
- `Framework/data/SOURCE_POLICY.md`
- `Framework/data/SNAPSHOT_POLICY.md`
- `Framework/evals/EVAL_PLAN.md`
- `Framework/evals/GUARDRAILS.md`
- `Framework/evals/CALIBRATION.md`
- `Framework/evals/ERROR_BARS.md`

### Mandatory output for every ranked company
- Raw score /100
- Factor-level scores
- Error band in score points
- Evidence grade A-D
- Probability-weighted fair value and valuation uncertainty range
- Earnings-expectations overlay
- Most-likely operating path and independent debate probabilities
- Poker hand/draw label generated from, never substituted for, the underlying score

### Promotion gate
Until the framework passes the historical, repeatability, look-ahead and calibration tests in `Framework/evals/EVAL_PLAN.md`, all rankings are research-grade only. Do not represent small score differences as meaningful when error bands overlap.
