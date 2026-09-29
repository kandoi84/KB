# RAG reuse assessment for the Indian equities KB

Date: 2026-09-29. Status: design checkpoint; no dependency migration or quality claim.

## Intent

Use maintained RAG components for ordinary document processing, retrieval, and
evaluation. Keep local code only where the research contract needs immutable
source versions, dated issuer and ISIN identity, strict availability cutoffs,
rights decisions, and human claim review. The existing SQLite catalog remains
the evidence authority. Raw filings and prior derived versions are never
overwritten. Real research publication remains blocked.

## Upstream review

Checked the official repositories and documentation on 2026-09-29. Commit IDs
identify the upstream state reviewed; they are not dependency pins. No source
code was copied in this assessment.

| Project | Reviewed commit and license | Proven pattern | Fit and limit |
| --- | --- | --- | --- |
| [Docling](https://github.com/docling-project/docling) | [`98d78ef`](https://github.com/docling-project/docling/commit/98d78ef87bbe4eb88b3212e3ef2a5cbe4dd4729c), [MIT](https://github.com/docling-project/docling/blob/main/LICENSE) | `DocumentConverter` produces a structured document; [hierarchical and hybrid chunkers](https://docling-project.github.io/docling/concepts/chunking/) preserve headings, captions, and document items. | Preferred replacement for bespoke PDF parsing and line chunks. Its chunk metadata must be mapped and checked against our raw hash, page, extraction time, and citation rules. OCR output needs separate visual review. |
| [Haystack](https://github.com/deepset-ai/haystack) | [`11a0dd2`](https://github.com/deepset-ai/haystack/commit/11a0dd260a43250ff7c9b121aaad9b89ae2e0ef4), [Apache-2.0](https://github.com/deepset-ai/haystack/blob/main/LICENSE) | [Document stores](https://docs.haystack.deepset.ai/docs/document-store), [query-time metadata filters](https://docs.haystack.deepset.ai/docs/metadata-filtering), and [document recall evaluation](https://docs.haystack.deepset.ai/docs/documentrecallevaluator). | Preferred retrieval and evaluation candidate. Its index is derived and rebuildable. The KB must select eligible source versions before indexing or querying; framework filters alone do not prove point-in-time correctness. |
| [LlamaIndex](https://github.com/run-llama/llama_index) | [`9ca9664`](https://github.com/run-llama/llama_index/commit/9ca9664a7c3ddb8216edc5df0941be40aa63af2e), [MIT](https://github.com/run-llama/llama_index/blob/main/LICENSE) | [Ingestion pipeline](https://github.com/run-llama/llama_index/blob/main/docs/src/content/docs/framework/module_guides/loading/ingestion_pipeline/index.md) chains transforms and caches work by document identity and hash. | Good alternative if Haystack cannot meet the pilot. Its changed-document upsert semantics cannot replace append-only evidence; use it only for derived nodes if selected. |
| [Ragas](https://github.com/vibrantlabsai/ragas) | [`298b682`](https://github.com/vibrantlabsai/ragas/commit/298b68274234c060deacab3cf5fb52aa3a20e885), license not assessed | Model-judged answer metrics. | Defer. The current gate needs deterministic source-anchor recall, cutoff, citation, and abstention checks before an LLM judge adds value. Its reviewed repository commit is older than the other candidates. |

## Decision and rollout

Use **Docling plus Haystack as a measured pilot**, not a wholesale framework
rewrite. Keep current `pypdf` extraction, token-overlap retrieval, and JSONL
runner as frozen baselines until a replacement passes the same reviewed gold
set. Do not install or run a package merely because its upstream is active.

1. Freeze a small licensed corpus and 30–50 reviewed, source-anchored questions.
   Include missing answers, late filings, revisions, wrong issuers, conflicting
   documents, transcript roles, and tables. Record exact package versions and
   transitive license checks when creating the pilot environment.
2. Parse raw local PDF files with Docling, store its structured output as a new
   derived version, and map chunks to immutable source and page identities.
   Reject missing, ambiguous, or changed citation anchors. Keep the raw PDF and
   existing extraction readable. Human review checks page and table fidelity.
3. Build a disposable Haystack document store from cutoff-eligible chunks.
   Index source version, raw hash, issuer ID, ISIN, document type, publication
   and first-seen times, extraction arrival, page, and reviewed speaker role.
   Apply filters before ranking. Refuse mixed issuers or any timestamp beyond
   cutoff in returned results. Numeric answers continue to use typed metrics.
4. Score both retrievers on the same frozen cases. Reuse Haystack document
   recall and rank metrics where their labels fit. Keep local checks for exact
   quote and raw-hash citation, abstention, issuer, revision, and cutoff
   violations. Report per-case results, sample counts, parser failure rate,
   runtime, and dependency size. Do not infer real quality from synthetic tests.
5. Promote one replacement at a time only when it meets the existing 04E
   thresholds, does not regress hard cases, and preserves 100% provenance and
   zero wrong-issuer citations. Failed or unlicensed samples stay blocked. If
   Haystack cannot meet these gates, trial LlamaIndex against the same frozen
   cases rather than add another custom retriever.

The adapters still needed are small: source-version to framework document
mapping, cutoff eligibility, immutable derivative receipts, and exact citation
validation. These are domain contracts that the upstream libraries do not
provide. Do not copy upstream source; use pinned packages and their public
interfaces. Record the version and license before any runtime dependency lands.

## Effect on the mini-spec program

Run this pilot before expanding 09–13 or replacing existing 04C2/04D/04E.
Existing 07 and 08 work may be finished and verified because it does not
depend on a retrieval-framework choice. Do not call the RAG path production
ready while real reviewed gold and the parser visual gate are missing.
