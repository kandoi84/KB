# Indian Equities Research Framework

This folder defines the deterministic research engine used to compare ~50 Indian equities and shortlist the five highest-quality probability-adjusted return setups.

## Core outputs per company
1. Raw attractiveness score (0-100)
2. Confidence interval / error bar
3. Evidence grade (A/B/C/D)
4. Probability-weighted fair value and fair-value range
5. Expected excess return and downside estimate
6. Poker hand + draw label as a compressed representation only

## Rule
The poker label never drives the analysis. It is generated from the underlying scored, sourced, timestamped framework.

## Required reading order
1. ../MASTER.md
2. SCORING_ENGINE.md
3. relevant parameter specs in `specs/`
4. DATA_SCHEMA.md and SOURCE_POLICY.md
5. EVAL_PLAN.md before changing weights or scoring thresholds
