# Filtered chunk retrieval: 04D

**Goal:** Answer a text search with source-checked, point-in-time chunks from one issuer, optionally narrowed by ISIN and document type. Keep numeric facts in the typed metric path and real publication blocked.

**Contract:** Require issuer ID, nonempty text query, timezone-aware cutoff, and bounded result count. Reject an ISIN that is not a reviewed security of the issuer. Consider only matching reviewed filings eligible at the strict cutoff. Use the registered plain-text or PDF extraction reader, which rechecks raw evidence, identity, rights, chunk spans, and arrival times. A missing extraction is skipped; a damaged registered extraction blocks the search. Rank case-folded word overlap deterministically, return only matching chunks with IDs, source hashes, page/offset basis, and score. No LLM answer or numeric inference is made here.

## Execution

1. Add failing tests for issuer and document filters, cutoff, stable rank, PDF and text, wrong-issuer distractors, tampering, missing extraction, and bad input.
2. Align plain-text extraction with a system-recorded arrival receipt, including safe migration of older rows on verified replay. Earlier strict-live cutoffs cannot see newly derived text.
3. Implement the filtered reader and CLI. Keep the candidate set bounded for the ten-company pilot.
4. Run focused and full checks, independent review, staged diff check, task-only commit, and push.

**Limit:** Lexical ranking is a baseline for the reviewed 04E gold set. Do not claim retrieval quality until recall, citation, and abstention gates are measured.
