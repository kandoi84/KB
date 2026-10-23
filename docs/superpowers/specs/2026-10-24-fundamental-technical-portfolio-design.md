# Fundamental anchors, technical timing and a Nifty-relative portfolio

Status: proposed design for review, not an implemented strategy or recommendation.
Date: 24 October 2026. No claim of demonstrated outperformance.

## Goal and current gap

Build a source-backed investment process across the Nifty 50 that produces
explainable buy/add/hold/reduce/exit decisions and a constrained model portfolio.
The objective is positive excess total return against Nifty 50 TRI after
realistic implementation costs, with explicit drawdown and concentration limits.
Technical analysis must earn its place through testing; more indicators do not
constitute a research advantage.

The current KB has 50 official-list-observed symbols, 13 research sectors,
four dated research folders and 46 intake-only profiles. Existing fundamental
scoring and historical receipts are useful foundations, not validated strategy
performance. Real publication remains blocked. Historical evaluation has known
defects and no trusted production scorer/market-feed executor; those need
separately tested implementation work before performance claims.

## Choices and assumptions

The user requested fundamental anchors, technical analysis and an eventual
Nifty-beating recommendation portfolio. Recommended interpretation:

- Fundamental underwriting determines eligibility, value and expected payoff.
- Technical evidence informs timing, entry staging and risk review.
- Portfolio construction determines size and combined exposure.

An equal-weight fundamental/technical score is a weaker starting point: it can
double count momentum/earnings expectations and hide why a trade is proposed.
A trading-led system would require different data, turnover and execution
assumptions from the fundamental-anchor goal. Neither alternative is selected.

User-confirmed: 1–3 year fundamental horizon with monthly scheduled reviews.
Proposed defaults: long-only, unlevered, with event-driven risk reviews.
Technical observations use daily end-of-day data. No intraday strategy, shorting,
derivatives or broker execution is part of the initial scope. Portfolio size,
drawdown tolerance, investment capital and tax treatment need confirmation
before a personalized portfolio can be recommended. Proposals below are research
defaults, not agreed investment limits or fitted parameters.

## 1. Evidence and valuation foundation

Finish sector cohorts using permitted primary filings and authorized exports.
Reuse existing provider tables/document discovery, shared macro evidence and
sector definitions rather than recreating them. Keep source rights, issuer/ISIN,
reporting scope, filing publication, actual first-seen time and review status.
Retain revised observations rather than overwriting prior inputs.

Every eligible company needs:

- Comparable financial history, cash-flow/earnings normalization, shares and
  corporate-action reconciliation, and sector-specific operating KPIs.
- A reproducible DCF/SOTP/bank-equity/insurance valuation appropriate to its
  economics, with sources separated from forecast assumptions.
- One most-likely operating path, independent debates and explicitly labelled
  probabilities; no invented consensus or precision from missing data.
- A fair-value uncertainty range, expected return over a stated horizon,
  downside assumptions, three-leg thesis and falsifiers.
- Valuation fragility and market-implied assumptions: what the price requires
  versus what the evidence supports, not simply a low multiple.

Price action cannot change terminal growth, required return or fair value.
Only new economic evidence or an explicitly justified assumption revision can.
Uncertainty belongs beside the estimate; it is not silently subtracted from a
score. Existing fundamental weights remain unchanged pending evidence.

## 2. Technical overlay to test

Start with a small, transparent candidate set. These are test hypotheses, not
proven profitable signals or approved buy thresholds:

| Dimension | Candidate observation | Purpose |
|---|---|---|
| Trend | Price versus 200-day moving average; 50-day average direction | Distinguish persistent strength/weakness from valuation alone |
| Relative strength | Trailing 12-month total return excluding the latest month, relative to Nifty and sector | Measure leadership with a precisely frozen window |
| Risk | 20-session ATR/price, realized volatility and drawdown | Inform entry staging, risk budgets and adverse-price review |
| Participation | Volume versus a documented trailing baseline | Describe whether a move has unusual participation |

Use vetted implementations where suitable; test them against known calculations.
Do not rebuild charting platforms, start with dozens of overlapping oscillators,
or assume a crossover/RSI level is an investment edge. Record exact formulas,
window endpoints, missing-data treatment and version for each candidate.

Use consistently adjusted OHLCV for signal calculations and corporate-action
checks; execute and mark actual holdings using tradable prices and separate
cash/share events. Returns/relative strength must account for distributions.
Warm-up periods, missing sessions, suspensions and partial history yield explicit
unavailable signals, not zeros. Technical confirmation never fixes missing
fundamental evidence.

## 3. Explainable decision policy

Each recommendation records evidence cutoff, price timestamp, valuation/model
version, signal version, confidence, reason, invalidation conditions, risk and
next review trigger. The state machine is a research hypothesis until evaluated:

| Fundamental evidence and value | Technical/risk condition | Candidate decision |
|---|---|---|
| Missing, stale, conflicted or invalid | Any | No new recommendation; investigate |
| Eligible; attractive payoff outside value uncertainty | Supportive | Buy/add candidate, subject to portfolio constraints |
| Eligible and attractive | Weak or deteriorating | Watch/defer, or explicitly test a smaller staged entry |
| Eligible, near fair value | Stable | Hold/reassess; do not buy merely because momentum is strong |
| Value/payoff no longer adequate | Any | Reduce/exit candidate, considering risk and implementation |
| Thesis broken or evidence materially invalidated | Any | Immediate review; technical strength cannot rescue the thesis |

Define mutually exclusive, deterministic thresholds and precedence before
backtesting; this table alone is not executable policy. Distinguish valuation
exits, thesis exits and risk-driven reductions. A price alert triggers review;
any mandatory exposure/stop rule must be declared separately. Do not pretend a
stop guarantees its trigger price through gaps or illiquidity.

## 4. Portfolio construction

Begin with an auditable model portfolio and shadow orders, not live trading.
Every weight must trace to an eligible recommendation and the same dated
portfolio snapshot. Missing evidence means exclusion, not a fabricated low score.

Proposed starting constraints for testing:

- Target 12–15 holdings, maximum 10% per issuer; include look-through group and
  related-company exposure in concentration review.
- Sector overweight capped at 10 percentage points above the benchmark,
  using one reconciled sector map and actual dated benchmark weights.
- Review common exposures: rates, credit, currency, commodities, regulation
  and correlated earnings drivers. Historical correlation alone is insufficient.
- Size within limits using conservative payoff/downside estimates, liquidity
  and portfolio fit; volatility scaling is a candidate, not a validated rule.
- Cash target 0–20%, but never force weak stocks into the portfolio. If eligible
  names or constraints prevent deployment, retain cash and flag the shortfall.
- Prefer turnover buffers/minimum actionable changes to constant rebalancing;
  test these against costs rather than choosing thresholds after seeing results.

Resolve infeasible constraints explicitly. Do not normalize weights in a way
that violates issuer/sector/risk caps. A defensive cash allocation is an active
benchmark decision whose drag and benefit must be measured. Personalized limits
and a portfolio-level drawdown response remain open user decisions.

## 5. Prove incremental benefit

Use Nifty 50 TRI as the primary total-return benchmark, on matching valuation
dates and currency. Retain equal-weight Nifty, simple quality/value and
technical-only baselines. Compare four frozen variants on the same eligible
data and cost assumptions:

1. Fundamental selection with simple portfolio rules.
2. Fundamental selection plus technical entry/exit timing.
3. Fundamental selection plus portfolio risk constraints.
4. The combined system.

This isolates whether timing and construction add value. Report net return,
annualized excess return with its definition, volatility, maximum drawdown,
turnover, information ratio, tracking error, downside capture, rolling excess
returns, invested exposure and sector/style attribution. Show gross and net
results; separate cash, selection, timing and sizing effects.

### Proposed adoption criteria to freeze before seeing results

The primary metric is the annualized portfolio net total-return CAGR minus
Nifty 50 TRI CAGR over the identical window. It is not whichever return/risk
statistic looks best afterward. For technical timing, compare that same metric
against the fundamental-only variant as well as the index.

Proposed research hurdles, subject to design approval:

- Positive held-out net excess return against both baselines, with a predeclared
  paired block-resampling analysis whose uncertainty excludes zero after the
  declared multiple-comparison adjustment. An interval spanning zero means
  inconclusive, not successful adoption.
- Held-out maximum drawdown no worse than the fundamental-only variant, and
  within the user's separately agreed risk mandate. A return increase cannot
  silently authorize a higher loss budget.
- Higher turnover is acceptable only if the incremental net-return result
  survives a predeclared doubling of assumed spreads/slippage, with verified
  statutory costs unchanged. Disclose the turnover increase rather than hide it.
- At least 36 calendar months of genuinely out-of-sample monthly portfolio
  observations, plus predeclared regime and data-coverage checks. This is a
  proposed minimum, not a claim of statistical power; overlapping company
  outcomes do not multiply the independent sample size.
- Freeze the resampling/block method, confidence level (proposed 95%), comparison
  family, missing-data rules and all thresholds in an evaluation manifest before
  opening the holdout. If evidence is insufficient, retain the simpler baseline.

The reviewer must evaluate these joint conditions, not choose return, Sharpe,
drawdown or a favorable subperiod after the fact. A prospective paper portfolio
can establish operational reliability while long-horizon evidence accumulates;
paper operation alone does not satisfy the performance/adoption gate.

Required controls:

- Historical constituents, exits and corporate actions as actually effective;
  today's observed 50 are not a historical universe. Retain delistings and losses.
- Point-in-time filings, first-seen availability, revisions, estimates and model
  assumptions. Do not use today's retrospective analyst thesis in an old decision.
- Signals from completed sessions; earliest modeled fill is a later tradable
  session, with explicit handling of suspensions, gaps, liquidity and failed fills.
- Dividends, corporate actions, financing/cash treatment, fees, STT/other applicable
  charges, spreads and slippage. Verify current schedules; invent no fixed costs.
  Capital-gains tax is reported separately unless account-specific assumptions exist.
- Separate development, rolling validation and untouched holdout periods;
  freeze all thresholds and disclose all tried variants. Test multiple regimes,
  parameter sensitivity and worse costs, not only an attractive single period.
- Account for overlapping holding periods and correlated stock observations.
  The existing 100 company-snapshot minimum alone cannot establish strategy alpha.
- Use block-based uncertainty analysis where appropriate and report weak samples.
  Do not optimize on the holdout or infer significance from one winning backtest.

Historic fundamental models may be unavailable. In that case evaluate transparent
historical mechanics separately, and establish real recommendations prospectively
through a frozen paper portfolio. Do not relabel reconstructed judgments as
strict historical evidence or synthetic results as real outperformance.

## 6. Phases and acceptance

| Phase | Deliverable | Acceptance |
|---|---|---|
| Data | Reviewed company/price/benchmark vintages and source routes | Identity, rights, integrity, adjustment and timing checks pass |
| Fundamental pilot | Complete existing bank models, then a non-bank cohort | Reproducible source-to-value bridge, uncertainty and thesis changes |
| Technical pilot | Versioned indicators and rule hypotheses | Correct calculations, no leakage, explicit unavailable states |
| Evaluation | Frozen baselines, ablations and walk-forward reports | Real data/results distinguished from mechanics; costs and uncertainty shown |
| Paper portfolio | Dated recommendations, weights, shadow fills and journal | Constraints enforced, no future fills, attribution and failure handling |
| Adoption review | Evidence pack and user risk/mandate sign-off | Existing promotion gates plus independently reviewed incremental benefit |

Do not wait for all 50 full models before testing the end-to-end research workflow
on a small, representative cohort. Expand only after that path works. Equally,
do not claim a Nifty-relative investable portfolio from four preliminary pilots.
If technical timing fails to improve the held-out result, omit it from production.
If the combined strategy fails, report that result and preserve the benchmark.

## Boundaries and open decisions

This proposal changes no active score, valuation, recommendation, portfolio,
publication gate or broker connection. It is not a promise to beat Nifty.
The horizon and monthly cadence are agreed. Before implementation agree the
long-only mandate, cash flexibility,
holding-count/concentration limits and acceptable drawdown. Before a live
portfolio, confirm investable capital, existing holdings, liquidity needs and
tax constraints. Start with research/paper recommendations; order execution is
a separate scope requiring explicit authorization.

References: project `MASTER.md`, `Framework/SCORING_ENGINE.md`,
`Framework/specs/architecture-review-handoff.md`, `Framework/evals/EVAL_PLAN.md`,
`Framework/evals/GUARDRAILS.md`, and `Framework/data/SNAPSHOT_POLICY.md`.

## Design review

An independent read-only builder review found no material contradiction or
unsupported performance claim. It identified two prerequisites: user confirmation
of mandate/risk limits, and a frozen definition of incremental benefit. The
proposed adoption criteria above address the second; mandate confirmation remains
open. This review is not strategy validation or approval to implement.
