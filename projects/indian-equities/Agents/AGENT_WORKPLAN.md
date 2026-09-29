# Indian Equities — 14 Company Agent Workplan

## Objective
Run seven parallel sector workstreams over the 14-company validation universe and produce comparable, point-in-time, deterministic research inputs for the 50-to-5 stock-selection framework.

## Common instructions for every sector agent
1. Read `MASTER.md`, `Framework/SCORING_ENGINE.md`, all relevant `Framework/specs/*.md`, `Framework/data/*`, and `Framework/evals/*` before scoring.
2. Use current public information only, with explicit `as_of_date` and source provenance.
3. Do not infer missing numeric inputs silently. Mark `MISSING` and reduce confidence/evidence grade.
4. Separate raw facts, derived calculations, analyst assumptions, and judgment.
5. Score the common factors using the same definitions and thresholds.
6. Produce: raw data snapshot, factor scores, uncertainty/error bars, evidence grade, probability-weighted FV range, <=100-word stance, exact poker hand + draw, first rejection condition.
7. Highlight where a sector-specific adapter is required.
8. Do not call inclusion in the universe a Buy recommendation.

## Sector workstreams
- Pharma Agent: Sun Pharma, Divi's Labs
- Banks Agent: HDFC Bank, ICICI Bank
- Financials ex-Banks Agent: Bajaj Finance, Bajaj Finserv
- Industrials Agent: Larsen & Toubro, ABB India
- Cement Agent: UltraTech Cement, Ambuja Cements
- IT Services Agent: TCS, Infosys
- Consumer Staples Agent: Hindustan Unilever, ITC

## Deliverables per agent
- `raw_snapshot.md`
- `scorecard.md`
- `open_questions.md`
- `source_ledger.md`

## Promotion gate
No company can be included in a cross-company ranking until:
- required data coverage >= 80%;
- no critical source conflict remains unresolved;
- evidence grade >= B;
- score uncertainty <= +/-10 points;
- fair-value range and earnings-expectation inputs have current-date support.
