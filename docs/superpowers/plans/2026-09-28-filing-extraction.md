# Filing and transcript extraction implementation plan

**Goal:** Store cited text chunks from reviewed filing versions without losing raw-source provenance.

**Scope:** First add filing-only registration for documents with no typed metrics. Then extract UTF-8 text with exact byte spans and explicit `UNKNOWN` speaker role unless a reviewer supplies verified spans. PDF input stays blocked until a tested, page-aware parser adapter exists. Preserve the real-publication gate.

**Contract:** One filing version points to one immutable raw source. A parser run names its implemented version; each chunk ID binds the source version, parser version, text span, and metadata. Replays must match exactly. A read rechecks raw bytes, text spans, issuer identity, and strict live cutoff. Source text and derived context stay separate.

## Task 1: Filing-only registration

- Add failing tests for a transcript filing with zero metrics, exact replay, and a results filing that still requires metrics.
- Reuse the existing source, identity, rights, timestamp, revision, and transaction checks.
- Add a CLI entry point and document the request.

## Task 2: Verifiable text chunks

- Add failing tests for UTF-8 offsets, exact replay, damaged raw text, unimplemented parser versions, and cutoff exclusion.
- Add an append-only extraction/chunk contract with deterministic IDs, bounded chunk size, and explicit role metadata.
- Reject binary/PDF, empty text, malformed stored offsets, and unchecked attribution with clear errors.

## Task 3: Review and delivery

- Run focused tests and the project suite; inspect the diff and staged files.
- Commit and push only the completed extraction files on the feature branch.
