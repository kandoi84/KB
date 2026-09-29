# Structured Indian equities KB extension

Date: 2026-09-28. Status: 04A–04C2 controlled local paths active; later adapters planned.

## Decision

Keep the immutable raw store as the evidence base. Add a local SQLite catalog
for ten companies first: it is included with Python, supports fixed screening
queries, and avoids operating Postgres, a vector server, and an orchestration
framework before retrieval quality is measured. Add a replaceable retrieval
index only after the gold questions show keyword search is insufficient.
Company research uses an issuer ID; a traded security uses ISIN. An issuer can
have several securities. Symbols are dated aliases, never primary keys.

`period_end` describes the accounts. `published_at` describes when the exchange
made the filing public. `first_seen_at` describes when this KB acquired it.
Live replay requires both timestamps at or before the cutoff. A later
historical reconstruction slice may use a backfill only when reviewed,
version-specific exchange archive and identity receipts prove that the exact
filing and ISIN relationship were public by the cutoff; the result is labelled
`BACKFILLED` and evaluated separately. Unknown
publication time blocks both modes. Revisions append new records and point to
the prior version. A later restatement never replaces an earlier observation.

The 04F typed-metric implementation uses a separate `query_backfilled_metrics`
path. Separate reviewed filing and identity archive attestations bind issuer,
ISIN, company/security source versions, filing source version, exact filing
SHA-256, publication time, and identity announcement time to raw archive bytes
recorded by the requested cutoff. Every eligible revision needs its own filing
proof and a matching identity proof. Outputs retain both proof/reconstruction times, the
`BACKFILLED` label, and `publication_allowed: false`. This is a **manual
research attestation**: `record_source` metadata times are caller supplied,
and the local runtime cannot authenticate an exchange archive or its historic
timestamp independently. Its primary-exchange hostname and digest checks
catch internal mismatch and tampering, but a reviewer must check the actual
source, rights, and timestamp evidence. Do not treat synthetic fixtures or a
current archive URL as historical availability proof. An automated trusted
backfill needs a verifiable timestamped digest or signed primary artifact.

## Core schema proposal (SQLite)

This sketches the active catalog; the runtime schema in `identity_store.py`,
`metric_store.py`, and `text_chunks.py` is authoritative.
All timestamps use timezone-aware ISO 8601 text normalized to UTC before insert. Decimal values
are canonical strings and are parsed with Python `Decimal` for calculations.

```sql
CREATE TABLE companies (
  issuer_id TEXT PRIMARY KEY,
  legal_name TEXT NOT NULL,
  source_id TEXT NOT NULL,
  version_id TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  reviewer_id TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  review_decision TEXT NOT NULL,
  evidence_locator TEXT NOT NULL
);
CREATE TABLE securities (
  isin TEXT PRIMARY KEY,
  issuer_id TEXT NOT NULL REFERENCES companies(issuer_id),
  security_type TEXT NOT NULL,
  listed_from TEXT NOT NULL,
  listed_to TEXT,
  announced_at TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  source_id TEXT NOT NULL,
  version_id TEXT NOT NULL,
  reviewer_id TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  review_decision TEXT NOT NULL,
  evidence_locator TEXT NOT NULL
);
CREATE TABLE symbol_history (
  exchange TEXT NOT NULL,
  symbol TEXT NOT NULL,
  isin TEXT NOT NULL REFERENCES securities(isin),
  valid_from TEXT NOT NULL,
  valid_to TEXT,
  announced_at TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  source_id TEXT NOT NULL,
  version_id TEXT NOT NULL,
  reviewer_id TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  review_decision TEXT NOT NULL,
  evidence_locator TEXT NOT NULL,
  PRIMARY KEY (exchange, symbol, valid_from)
);
CREATE TABLE filings (
  filing_id TEXT PRIMARY KEY,
  issuer_id TEXT NOT NULL REFERENCES companies(issuer_id),
  isin TEXT NOT NULL REFERENCES securities(isin),
  source_id TEXT NOT NULL,
  version_id TEXT NOT NULL UNIQUE,
  raw_sha256 TEXT NOT NULL,
  document_type TEXT NOT NULL,
  period_end TEXT,
  published_at TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  supersedes_filing_id TEXT UNIQUE REFERENCES filings(filing_id),
  rights_status TEXT NOT NULL,
  reviewer_id TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  review_decision TEXT NOT NULL,
  evidence_locator TEXT NOT NULL
);
CREATE TABLE text_extractions (
  filing_id TEXT NOT NULL REFERENCES filings(filing_id),
  parser_version TEXT NOT NULL,
  source_id TEXT NOT NULL,
  version_id TEXT NOT NULL,
  raw_sha256 TEXT NOT NULL,
  chunk_count INTEGER NOT NULL,
  PRIMARY KEY (filing_id, parser_version)
);
CREATE TABLE text_chunks (
  chunk_id TEXT PRIMARY KEY,
  filing_id TEXT NOT NULL,
  parser_version TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  byte_start INTEGER NOT NULL,
  byte_end INTEGER NOT NULL,
  text_sha256 TEXT NOT NULL,
  text TEXT NOT NULL,
  page_number INTEGER,
  speaker_role TEXT NOT NULL,
  FOREIGN KEY (filing_id, parser_version)
    REFERENCES text_extractions(filing_id, parser_version)
);
CREATE TABLE metrics (
  metric_id TEXT PRIMARY KEY,
  isin TEXT NOT NULL REFERENCES securities(isin),
  metric_name TEXT NOT NULL,
  value_decimal TEXT NOT NULL,
  unit TEXT NOT NULL,
  period_end TEXT NOT NULL,
  filing_id TEXT NOT NULL REFERENCES filings(filing_id),
  value_kind TEXT NOT NULL,
  reporting_scope TEXT NOT NULL,
  period_kind TEXT NOT NULL,
  evidence_locator TEXT NOT NULL,
  supersedes_metric_id TEXT UNIQUE REFERENCES metrics(metric_id),
  CHECK (value_kind IN ('REPORTED', 'GUIDANCE'))
);
CREATE INDEX metrics_series ON metrics(isin, metric_name, period_end);
CREATE INDEX filings_cutoff ON filings(issuer_id, published_at, first_seen_at);
```

The first typed-metric slice covers reported facts and issuer guidance from
filings. Consensus, assumptions, derived values, and prices need their own
typed origin contracts; they must not masquerade as exchange filings. One
`filings` row represents one raw document version. A bundle or attachment set
is split into distinct stored documents before registration.
Metrics inherit availability timestamps from their filing. Their own period
may be a prior comparative period. Plain UTF-8 chunks use exact raw byte
spans, a fixed 2048-byte maximum, and `UNKNOWN` speaker role. This parser
does not infer transcript speaker roles or PDF page numbers. PDF and binary
input are blocked on the plain-text path. The PDF path stores extracted page
text separately from raw bytes, with physical PDF page numbers and offsets
into derived UTF-8 page text. Reviewed speaker roles bind exact chunks and
become visible only after review and system-recorded arrival. Plain-text
extraction has a separate arrival receipt; old rows with unknown arrival
require verified replay. A real-sample visual gate remains. Derived
context is not part of source text or chunk identity.
04B accepts only a source version recorded as `EXCHANGE_FILING`, with matching
issuer and observation no later than retrieval or first-seen time. Manual
review asserts the exchange publication timestamp and named evidence locator.

The write API validates ISIN check digits, UTC timestamps, source hashes,
nonoverlapping symbol ranges, foreign keys, and revision links. Database
triggers reject `UPDATE` and `DELETE` on evidence rows. A revised metric must
match ISIN, metric, period, and unit of its predecessor; cycles and ambiguous
revision branches fail. The live cutoff reader selects only rows with both
`published_at <= cutoff` and `first_seen_at <= cutoff`. Historical
reconstruction requires a separate reviewed archive and identity receipt
contract before it can select later-ingested rows. Each mode chooses the
latest eligible revision within one metric series. Backfilled results carry
a distinct label and never appear in strict live replay. A
filing with only a calendar date needs a conservative availability timestamp
or remains ineligible intraday.
Security and symbol resolution also requires `announced_at` and
`first_seen_at` at or before cutoff; mergers and demergers with ambiguous
identity block until reviewed. Legacy records without availability time
remain readable but cannot enter historical decisions.

## Ingestion and refresh

1. Register issuer, ISIN, and dated NSE/BSE symbols from reviewed source data.
2. Poll permitted official announcement/results listings with a saved cursor.
   Store request URL, retrieval time, response hash, source rights decision,
   and raw bytes through `record-source`. A repeated hash is idempotent; a
   revised filing creates a new source version and filing row.
3. Parse PDF/transcript in an isolated, versioned job. Keep raw and extracted
   text separate. Review page mapping and speaker labels; if extraction or
   attribution fails, mark blocked or use explicit `UNKNOWN` speaker role.
   Chunk by section/speaker with bounded
   overlap. Each chunk has a stable hash and filing/page/offset citation.
4. Generate optional context lines as derived, versioned text. Index only
   chunks eligible at the requested cutoff. Search first with metadata filters
   and SQLite FTS; trial embeddings only against the gold set.
5. Parse financial numbers into typed metrics with units and availability
   dates. Numeric answers and screens use these rows, not vector similarity.
   Source chunks may still contain numbers for direct citation.
6. A refresh compares source versions, rebuilds only affected derived chunks
   and indexes, runs retrieval regressions, and leaves prior snapshots intact.

## Retrieval evaluation contract

Store 30–50 reviewed questions as JSONL with `case_id`, `question`,
`issuer_id`, optional `isin`, `cutoff`, filters, expected state, gold answer,
source-version/raw-hash/quote evidence groups, and reviewer/version. Stable
source anchors survive parser changes better than chunk IDs. Include reported
facts, guidance, management versus analyst statements, revision history,
wrong-issuer distractors, future filings, contradictions, and no-answer cases.
Each index/parser change reports recall@5 and citation precision separately
from answer exactness or numeric tolerance and abstention accuracy. Fix the
baseline and rubric before a candidate run. Require at least five no-answer
and five revision/future-cutoff cases in the 30–50 question set. First
promotion gate: recall@5 >= 0.9 on answerable cases, citation precision >=
0.95, abstention accuracy >= 0.9, no regression against baseline on any hard
case, 100% cutoff provenance, and zero wrong-issuer citations. The 04E
runner scores text retrieval and optional submitted answers separately.
Synthetic contract fixtures are not measured research quality; real reviewed
gold, corpus freeze, and a frozen baseline remain promotion gates. Numeric
questions use typed metrics and need a separate scored path. The investment
ranking eval remains separate.

## Source and tool choice

NSE's [All Reports](https://www.nseindia.com/all-reports) names UDiFF as the
current cash-market bhavcopy and marks legacy CSV discontinued. Its
[data policy](https://www.nseindia.com/static/market-data/nse-data-policy)
requires a rights review before commercial collection. Official
[financial results](https://www.nseindia.com/companies-listing/corporate-filings-financial-results)
and [annual reports](https://www.nseindia.com/companies-listing/corporate-filings-annual-reports)
are candidate sources, but their web endpoints are not promised scraper APIs.
BSE's [corporate results](https://www.bseindia.com/corporates/comp_results.aspx?Code=500389)
and [announcements](https://m.bseindia.com/corporates.aspx) are separate
candidate primary sources; availability on a page is not a bulk-access grant.
`jugaad-data` has a recent [changelog](https://github.com/jugaad-py/jugaad-data/blob/master/CHANGELOG.md)
that records endpoint breakage; maintenance is not proof of reliable access.
The same caveat applies to `nselib`, `nsepython`, `nsetools`, `yfinance`, and
OpenBB. Official NSE/BSE filing pages are candidate primary documents, but
automated access reliability and commercial rights need adapter-specific
checks. Mini spec 13 records official URL, format/version, license decision,
sample fetch result, retries, and observed failure rate before activation.
Trial Docling on licensed sample PDFs before selecting a parser. FinanceBench
is a [format reference](https://github.com/patronus-ai/financebench), not an
Indian equity quality gate. Defer GraphRAG and a hosted parser until a measured
question or data-handling need justifies them.
