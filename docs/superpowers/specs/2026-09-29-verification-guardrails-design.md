# Verification Guardrails Design

## 1. Intent and Scope
Ensure that updates to the Live KB do not degrade retrieval quality or introduce data corruption. The guardrails act as a "Quality Gate" between the Ingestion Engine and the final activation of a data version.

## 2. Numeric Sanity Gates
Before a metric is recorded in the structured store, it must pass a set of sanity checks.

### Check Categories
- **Absolute Bounds**: e.g., Revenue $\ge 0$, Assets $\ge 0$.
- **Relative Bounds**: e.g., Current Assets $\ge 0$ (unless extreme distressed), Net Income within $\pm 1000\%$ of previous year (flag for review).
- **Consistency**: e.g., Total Assets = Total Liabilities + Equity.

### Execution
A `SanityGate` class will take a `Metric` and a company's current state. If it fails, the update is blocked, and a `SANITY_FAILURE` is logged.

## 3. Retrieval Evaluation (The Golden Set)
To prevent "embedding drift" or chunking regressions, we implement a Golden Set harness.

### The Golden Set
A JSON file per company containing a list of `(question, expected_chunk_id)` pairs.
- **Question**: A specific factual query (e.g., "What was the capex guidance for FY25?").
- **Expected Chunk ID**: The exact `version_id + chunk_id` that contains the answer.

### The Evaluation Loop
1. **Baseline**: Run the query against the *current* active version.
2. **Candidate**: Run the query against the *newly ingested* version.
3. **Comparison**: If the candidate fails to retrieve the expected chunk while the baseline succeeded, the update is blocked.
4. **Recall Metric**: Calculate the \% of the Golden Set retrieved correctly.

## 4. Integration into Ingestion Loop
The `LiveIngestionEngine` is modified to follow this sequence:
`Fetch` $\to$ `Parse` $\to$ `Embed` $\to$ `Sanity Check` $\to$ `Retrieval Eval` $\to$ `Commit`.

If any guardrail fails:
- The raw data is kept.
- The structured/vector records are marked as `PENDING_REVIEW`.
- The "Current Version" pointer is NOT updated.

## 5. CLI and Reporting
A new command `kb audit --isin <ISIN>` will report:
- Last sanity failure.
- Current Golden Set recall score.
- Date of last successful verification.
