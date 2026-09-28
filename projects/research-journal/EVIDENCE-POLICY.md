# Evidence grades and freshness

This small rubric can be revised as the KB grows. Record the reason for each grade; do not turn these labels into numerical scores.

## Separate three judgments

- **Source quality:** high = identifiable original evidence with clear method and scope; medium = attributable secondary report or partial original; low = unverifiable, ambiguous, or illustrative. High quality never means infallible. Fictional examples are low quality for real-world claims.
- **Source confidence:** high, medium, or low confidence that this item accurately represents what it purports to record. Explain gaps such as transcription or missing context. This does not establish that all claims in the source are true.
- **Conclusion confidence:** high = directly supported within stated scope, with material conflicts resolved; medium = useful support with consequential gaps; low = thin, indirect, conflicting, or hypothetical support. Use unknown when not assessed.

Freshness is a separate judgment: current, review-needed, stale, historical-only, or unknown. Always state the assessment date and intended use. A high-quality historical source can be unsuitable for a current-price claim. An expired source is not erased; retain it for historical claims.

## Source metadata

In each `raw/SOURCES.md`, preserve the original source links and add one `### Metadata: ID` block per registered item: source type, quality grade and reason, source confidence and reason, published date, observed/received date, data class, time-sensitive market/pricing flag, freshness policy, freshness status and as-of date. Use unknown for absent dates. A shared source keeps its stable ID; cross-topic registers may repeat its metadata but must cite the canonical source and remain synchronized.

## Default freshness rules by data class

| Data class | Suitable use and refresh rule |
| --- | --- |
| price-market | Record instrument, currency, venue, timestamp and timezone. Treat as historical snapshot; refresh for each current-price/market claim. Never describe an old quote as live. |
| consensus | Record provider, covered period, definition and snapshot date. Refresh before each current expectations comparison and after earnings or material estimate revisions. |
| guidance | Valid only as the latest known management statement as of the research cutoff. Check for replacement, withdrawal or new results before using as current. |
| historical-reported | Retain for the stated reporting period; recheck on restatement, correction or a newer filing affecting that period. It does not expire merely with age. |
| session-record | Historical record of a session; append corrections. Installation, blocker and task status must be rechecked before asserting present status. |
| research-other | Choose a use-specific review trigger or date; otherwise freshness is unknown. |

A source containing several classes lists each class and applies the relevant policy to each claim. The market/pricing flag is yes for price/market or consensus content, no where absent, and unknown if not inspected. Guidance can be time-sensitive even when that flag is no.

## Incremental evidence review

Each topic has `analysis/evidence-gaps.md`. For each question list supporting sources, conflicting evidence, missing data, conclusion confidence and rationale, freshness status/as-of date, and the next evidence most likely to improve confidence. Put the highest-value next source first; this is a judgment, not a score. New sources update the register and relevant journal entries; curated changes still require approval. Never silently promote a draft because its sources improved.

Automated checks verify field presence and allowed labels. They do not authenticate sources, detect new market events, enforce expiry automatically, or judge reasoning. Manually reassess freshness when answering a current question.
