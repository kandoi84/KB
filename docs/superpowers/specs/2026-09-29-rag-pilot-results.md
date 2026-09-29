# RAG pilot comparison result

Date: 2026-09-29. Status: synthetic contract probe; `NOT_PROMOTED`.

## Measured local probe

Task 4 ran the same 32-case synthetic 04E gold set through the frozen lexical
path (`TOKEN_OVERLAP_V1`) and the optional Haystack BM25 pilot
(`HAYSTACK_BM25_PILOT`). The set had 21 answerable, 10 absent, and one conflict
case. It contained nine distinct query/filter combinations and three distinct
source anchors. Haystack AI was `3.2.0` in the isolated pilot environment.

| Measure | Lexical baseline | Haystack pilot |
| --- | ---: | ---: |
| Answerable source-anchor recall@5 | 21/21 (1.00) | 21/21 (1.00) |
| Absent cases with empty retrieval | 10/10 | 10/10 |
| Conflict groups covered | 1/1 | 1/1 |
| Haystack multi-group anchor recall | 1.00 | 1.00 |
| Retrieved chunks matching a gold anchor | 23/43 (0.535) | 23/64 (0.359) |
| Wrong issuer, cutoff, citation, parse failures | 0 | 0 |
| Search wall time across 32 cases | 0.076 s | 0.822 s |

The last precision-like row measures retrieved chunks against this small gold
set. It is **not** the 04E citation precision of submitted answers. Both paths
found the synthetic anchors, but Haystack returned more non-anchor chunks and
was slower in this tiny disposable-index probe. These numbers are diagnostic,
not a production performance or research-quality estimate.

The one-run receipt recorded gold SHA-256
`f17f73a6cb2d93310796e1b2bc69ad98df6c04d5bc4027bec587b1ab6fbb4e73`,
catalog SHA-256
`f084c3aa65c627d176cd00177acf3c8011291479367d09a142b39e4b083ab979`,
and local evidence-file manifest SHA-256
`67bfdce45e9b6e07f68655e8f05f4e1d0113eb69a3921a976a009ba0034d2668`
over 12 synthetic registry/raw files. The test fixture was temporary and has
been removed; these hashes identify that run but do not constitute a durable
frozen corpus. Every comparison report also records the current baseline and
candidate module hashes and package versions. A mid-run change to gold,
catalog, or local evidence files fails the comparison.

## Promotion decision and open gates

`promotion_allowed` is false. No reviewed real 30–50 question set, externally
frozen licensed corpus, independently frozen baseline, submitted answer
citations, or real PDF page/table visual review exists in this run. The current
pilot indexes the existing source-verified text and PDF chunks; Docling's
separate derived chunks have not yet been compared head to head. The 04E gate
requires answerable recall@5 ≥ 0.90, submitted citation precision ≥ 0.95,
abstention accuracy ≥ 0.90, no hard-case regression, full cutoff provenance,
and zero wrong-issuer citations on reviewed real gold. Synthetic passing scores
cannot satisfy that gate.

## Checks

- Focused Task 4 tests in `/tmp/kb-rag-pilot-venv`: 6 passed. The combined
  paired-evaluation and retrieval set: 37 passed.
- Full pilot environment suite at delivery: 457 passed.
- Full core interpreter suite: 433 passed, 3 skipped. The optional pilot test
  modules skip without Haystack.
