# Retrieval and answer evaluation: 04E

**Goal:** Make retrieval changes measurable against reviewed, point-in-time evidence without treating synthetic fixture scores as research quality.

**Gold contract:** A versioned JSONL set has 30–50 unique cases. Each case pins a question, issuer, optional ISIN and document filters, UTC-normalized cutoff, expected state (`ANSWERABLE`, `ABSENT`, or `CONFLICT`), category, and reviewer. Answerable and conflict cases pin source-version IDs plus exact evidence quotes, with optional physical PDF page numbers. At least five cases must be absent and five must cover revision or future-cutoff behavior. No real case may claim review without source anchors. Numeric questions belong to typed-metric evaluation, not this text search slice.

**Runner:** Validate the whole set before search. Score quote-and-version recall at five against the current source-checked retrieval path. Record individual failures, cutoff and issuer violations, distinct query/evidence counts, and input hashes. A supplied answer file is scored separately: answerable cases need an exact normalized gold answer and citations to all required evidence; absent cases abstain and conflict cases cite both sides with an explicit conflict status. If no answer file is supplied, answer quality is `NOT_RUN`. The catalog file hash is a partial receipt; it is not a frozen source corpus. A score cannot promote a real index from synthetic fixtures.

**Gate:** Real reviewed set only: recall@5 >= 0.90, citation precision >= 0.95, abstention accuracy >= 0.90, zero wrong-issuer or cutoff violations, and no hard-case regression versus a frozen baseline. Report numerator, denominator, dataset type, and failures. Missing baseline or fewer than 30 reviewed real cases blocks promotion.

## Execution

1. Write failing tests for malformed gold, missing citations, abstention, cutoffs, and score denominators.
2. Implement a small JSONL evaluator and CLI over `search_chunks`; keep raw source validation in the existing reader.
3. Add a clearly synthetic 30-case contract fixture. Leave real gold collection as analyst review work.
4. Run focused/full checks, independent review, staged diff check, commit task files, and push.
