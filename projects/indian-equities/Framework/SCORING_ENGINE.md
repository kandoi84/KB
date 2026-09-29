# Scoring Engine Specification

## Objective
Rank companies on forward 12-36 month probability-adjusted excess-return potential while preserving comparability across sectors and time.

## Core factor set
- Macro factor: 15%
- Sector attractiveness: 20%
- Multiple / valuation attractiveness: 25%
- Long-term fair-value durability: 25%
- Catalyst expected value: 15%

Earnings expectations are separately scored and must be reported as a mandatory overlay. They feed valuation, catalysts and thesis risk but are not double-counted in the 100-point score until historical evals justify an explicit weight.

## Scoring scale
Each factor is scored 0.0-5.0 in 0.5 increments only. No arbitrary decimals.

## Deterministic requirements
Each factor must produce:
- raw data inputs
- timestamp / as-of date
- source IDs
- normalized metrics
- score according to explicit thresholds
- confidence grade
- missing-data flags
- sector adapter used

## Final score
Raw Score = sum(weight_i * factor_score_i / 5) * 100

## Confidence adjustment
Do NOT silently subtract confidence from attractiveness. Report:
- Raw Score: 0-100
- Error band: ± points
- Evidence grade: A-D
- Confidence-adjusted lower bound = Raw Score - error band

Ranking should use both Raw Score and lower-bound score.

## Error bar construction
Start with factor-level uncertainty:
- ±0.25 score points: hard market/reported data with stable relationship
- ±0.50: multiple inputs or modest judgment
- ±0.75: forecast-heavy / cyclical / weak consensus
- ±1.00+: sparse or structurally uncertain

Portfolio-level score error is computed from weighted factor uncertainties using root-sum-square, with an added correlation penalty when two factors share the same underlying driver.

## Poker mapping
Poker rank is derived from Raw Score only; draw classification comes from catalyst/optionality specs. Always display the numeric score and error band beside the poker label.
