# Evaluation Plan

## Objective
Determine whether the framework ranks future excess-return opportunities better than simple baselines.

## Minimum eval set
### 1. Repeatability
Same snapshot scored twice independently. Target absolute score difference <=3 points.

### 2. Inter-rater / model consistency
Independent scoring agents using identical data/spec. Target factor score disagreement <=0.5 on 80%+ of factors.

### 3. Look-ahead audit
100% of backtest observations must pass timestamp/provenance checks.

### 4. Historical ranking backtest
At each quarterly snapshot, rank 30-50 names. Measure 6m, 12m, 24m, 36m excess return versus Nifty and sector benchmarks.

### 5. Quintile monotonicity
Top quintile should outperform bottom quintile over sufficient samples. Test monotonic relationship between score bucket and forward excess return.

### 6. Hit rate
Measure proportion of top-5 names outperforming benchmark by >5% over 12 and 24 months.

### 7. Drawdown
Track max adverse excursion and downside capture for top-ranked names.

### 8. Factor attribution
Regress / bucket forward returns against each factor. Reweight only after adequate sample size.

### 9. Probability calibration
Events assigned 60%, 70%, 80% etc. should resolve near those frequencies over a sufficient sample.

### 10. Fair-value stability
Track quarterly FV revisions. Flag models where normal new information moves FV >15% too often.

## Baselines to beat
- Equal-weight Nifty 50
- Sector-adjusted equal weight
- Lowest P/E / highest FCF yield screen
- Earnings-revision-only screen
- Simple quality + valuation composite

## Promotion gate
Do not use the framework as a high-conviction 50-to-5 selector until:
- >=100 historical company-snapshot observations
- no material look-ahead violations
- top quintile beats bottom quintile on 12m and 24m median excess returns
- score repeatability <=3 points median
- catalyst probability calibration is directionally acceptable
