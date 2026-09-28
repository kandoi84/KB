# Historical evaluation and promotion design (mini spec 12)

## Purpose and present boundary

Test whether frozen Indian-equity decisions rank later excess returns better
than simple baselines, using the ten checks in
`projects/indian-equities/Framework/evals/EVAL_PLAN.md`. The present runtime
cannot run that investment test: 08 has unverified analyst fair value but no
0–100 score, 09 cases have no score or price, 10 concerns operating outcomes,
and 04E scores retrieval rather than stocks. There is no reviewed price,
corporate-action, sector, or benchmark feed. Mini spec 12 therefore delivers
a strict readiness and sealed-evaluation contract first. It reports blocked
dependencies explicitly. It must never manufacture scores, returns, sample
sizes, baseline wins, or promotion from synthetic fixtures.

The final output is an immutable evaluation receipt for human review, never
an activated 50-to-5 selector. Every receipt has `publication_allowed: false`,
`live_decision_allowed: false`, and `promotion_allowed: false`. A complete,
reviewed real evaluation can say `GATE_ELIGIBLE_FOR_HUMAN_REVIEW`; it cannot
turn those booleans true or change any production pointer.

## Reuse and scope

Reuse 09's case ID, digest, cutoff, parent input hashes, timing class and
publication block; revalidate the whole frozen case against its parents,
including exact bytes and the reconstructed case body, before counting it.
The needed `verify_frozen_case` helper belongs in 09's case module; a matching
`case_digest` alone is not authentication. Reuse 10's observation/postmortem
link only as a qualitative diagnostic. Reuse 04E's strict JSONL, dataset kind,
rubric version, file digests and explicit nonpromotion receipt conventions;
04E's retrieval score is never an investment score. Reuse 04F's reviewed
archive provenance as a *declared* historical source class, not independent
proof of when a past decision was made. Reuse Python's maintained
[`hashlib`](https://docs.python.org/3.14/library/hashlib.html),
[`decimal`](https://docs.python.org/3.14/library/decimal.html),
[`statistics`](https://docs.python.org/3.14/library/statistics.html), and
[`os.link`](https://docs.python.org/3.14/library/os.html#os.link) under the
[PSF license](https://docs.python.org/3.14/license.html). Existing pytest
([official docs](https://docs.pytest.org/en/stable/),
[MIT license](https://github.com/pytest-dev/pytest/blob/main/LICENSE)) covers
the contracts. No new package or copied upstream code is needed. Custom code
is limited to this repository's case provenance and EVAL_PLAN gates; a generic
backtest package cannot supply missing reviewed prices or a scoring model.

Upstream check on 2026-09-29: [QuantStats v0.0.86, commit
`9ef4c6d`](https://github.com/ranaroussi/quantstats/releases/tag/v0.0.86) is
active and [Apache-2.0](https://github.com/ranaroussi/quantstats/blob/main/pyproject.toml).
Its [documented stats and reports](https://github.com/ranaroussi/quantstats)
could later calculate drawdowns and portfolio return summaries from an already
validated daily-return series. It does not certify pre-outcome case seals,
point-in-time constituents, feed rights, or the five EVAL_PLAN baselines. Its
package declares pandas, NumPy, SciPy, plotting and yfinance dependencies;
the present slice has no reviewed daily-return series and no reason to expand
that trust surface. Keep exact contract arithmetic in stdlib for the initial
runner. Reconsider QuantStats only after a reviewed feed exists and its
outputs are cross-checked against pinned synthetic examples.

## Data contract and two-phase reveal

`register_evaluation_cohort` accepts a strict JSON manifest and exact case
paths. It creates a content-bound, immutable receipt under
`state_dir/historical_evaluation/cohorts/<cohort_id>.json`. The manifest pins
`cohort_id`, `dataset_kind` (`SYNTHETIC_FIXTURE` or `REVIEWED_REAL`), rubric
version, quarter-end decision cutoffs, case IDs/digests, ISINs, scorer ID and
source hash if one exists, independent reviewer, and the declared timestamp
proof for each decision. One observation is one distinct `(ISIN, cutoff)`;
repeated cases or revised decisions at the same pair do not inflate counts.
Every quarter intended for ranking has 30–50 distinct issuers and a fixed
universe selection rule recorded before scoring. An incomplete quarter is
reported, never silently dropped. The cohort receipt contains no future
outcome, price, benchmark, or corporate-action input path or value.

09's `ANALYST_DECLARED_PROSPECTIVE` label is not independent time proof.
Historical reconstructions and manual archive attestations remain
`REPLAY_ONLY` unless an independent, reviewed contemporaneous decision record
binds the exact case digest and predates the earliest price/outcome reveal.
A local clock, a newly created file, or a rehashed JSON receipt is not such
proof. The current project has no independently authenticated seal service,
so its existing cases cannot yet satisfy the promotion cohort gate. The
readiness report distinguishes `REPLAY_ONLY`, `SEALED_PROSPECTIVE`, and
`SYNTHETIC_FIXTURE`, with the evidence and reviewer for any seal.

`freeze_historical_scores` is a separate phase. A registered, reviewed scorer
must consume only the pinned case and evidence available at or before its
cutoff, in an isolated input view with no future-outcome mount or network
access. The scorer is supplied by an allowlisted runtime adapter registry,
never an import path, shell command, or code string in a manifest. Its receipt
pins source/version/hash, exact input digests, 0–100 score, five factor scores,
score error band, catalyst probabilities and due dates, fair value and unit,
and independent repeat runs. It records output and execution timestamps. A
test-only scorer can validate mechanics but cannot create reviewed real
scores or promotion evidence. No production scoring adapter exists now:
`BLOCKED_NO_SCORER` is the required real-data result.

`reveal_historical_outcomes` is callable only after an immutable score receipt
exists and passes replay. It accepts independently reviewed, versioned market
and benchmark observations. It pins raw hashes, provider rights, reviewer,
observation/publication time, ISIN, currency, exchange, corporate-action
adjustment, delisting treatment, sector membership at cutoff, and benchmark
composition/return methodology. The entry convention is the first eligible
close strictly after the frozen decision and score seal, with a declared
execution lag;
forward total-return windows end at 6, 12, 24 and 36 calendar months under a
pinned trading-calendar rule. Use the same window and currency for Nifty,
sector and each baseline. Missing prices, rights, corporate actions,
delistings, or benchmark data produce per-horizon missing status and cannot
be forward filled into a win. No market adapter/feed exists now:
`BLOCKED_NO_MARKET_FEED` is required for real returns.

The runner checks all sources visible to the scorer have availability times
at or before the case cutoff, including publication, first seen, extraction,
filing availability, and any metric revision. Later restatements can be
outcomes or retrospective commentary, never inputs to the frozen decision.
All decision, score, seal, reveal, and feed hashes are compared twice before
write; same ID/same bytes returns the original receipt, changed same-ID bytes
fail. Writes are link-once beneath the state root, and partial crashes yield
an explicit recoverable blocked state rather than a misleading complete run.

## Measurements and gates

The report always shows denominators, missing counts, quarter coverage,
cohort class, and per-horizon eligibility. A missing or zero denominator is
`NOT_EVALUABLE`, never zero performance or pass. At least 100 distinct
reviewed company snapshots are needed for a promotion review. For every
backtest observation, the look-ahead audit must pass; one unknown/violation
blocks the gate. Median absolute independent 0–100 score difference must be
at most 3. At least 80% of paired factor scores must differ by at most 0.5.
The repeated and inter-rater runs must use the same frozen input and pinned
rubric, with independently identified runs/reviewers.

For each 30–50-name quarter, assign deterministic quintiles by score, with
ties broken by ISIN only for stable reporting and overlapping score error
bands disclosed as tied confidence. Report 6/12/24/36 month total and excess
returns against Nifty and sector, sample and missing counts, top-to-bottom
median excess-return spread, monotonicity by all five buckets, top-five
`>5%` benchmark beat rate at 12/24 months, maximum adverse excursion and
downside capture. Report factor bucket attribution; regression requires a
declared sufficient sample and fit diagnostics, otherwise `NOT_EVALUABLE`.
Record Brier score and reliability bins for frozen catalyst probabilities,
with unresolved/ambiguous events excluded and counted. Show quarterly fair
value changes and flag absolute changes above 15% after normal new
information; explain changed models, currencies and corporate actions.
Pin all definitions in the rubric before any reveal.

Compare the same eligible universe and windows with all five EVAL_PLAN
baselines: equal-weight Nifty 50, sector-adjusted equal weight, lowest P/E or
highest FCF yield, earnings-revision-only, and quality-plus-valuation.
Fundamental/revision inputs need point-in-time reviewed source receipts;
missing inputs yield `BASELINE_NOT_EVALUABLE`, not a substituted strategy.
Use point-in-time constituents and include delisted firms. Each baseline's
formula, rebalance and transaction-cost assumption are pinned before the
reveal. The runner may display gross and declared-cost sensitivities, but
must not select the better result after seeing outcomes.

`GATE_ELIGIBLE_FOR_HUMAN_REVIEW` requires a reviewed real cohort, independent
pre-reveal seals for all counted decisions, at least 100 distinct snapshots,
30–50 issuers per ranked quarter, complete 12/24 month eligible windows,
100% provenance pass, median repeatability at most 3, at least 80% factor
agreement within 0.5, top quintile beating bottom on 12/24 month median
excess returns, directionally acceptable catalyst calibration under a
predeclared rubric, and complete five-baseline comparisons. Report the
remaining EVAL_PLAN checks even when they lack a numeric gate. Passing does
not authorize high-conviction use: a later independent human review and
explicit activation contract are outside this slice.

## Failure and acceptance

The initial implementation must accept a correctly formed synthetic cohort,
prove two-phase separation and arithmetic on deterministic fixture feeds,
and label it `MECHANICS_ONLY`. A real cohort with the current runtime must
produce precise blockers for independent seal, scorer, reviewed market feed,
or benchmark/baseline inputs. No synthetic or replay-only result can become
`GATE_ELIGIBLE_FOR_HUMAN_REVIEW`. Test malformed nested JSON, wrong issuer,
duplicate ISIN/cutoff, mixed rubric, forged/changed case digest, future
source, unreviewed rights, score input containing outcomes, same-ID changed
retry, crash recovery, missing/delisted prices, incomplete horizons, and
every publication/promotion flag. The expected current state is a rigorous
blocked evaluation contract, not an empirical claim of investment quality.
