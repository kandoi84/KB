# Indian Equities KB

Three-layer storage model:

- Local Mac: working copy
- GitHub: version history after this branch is pushed and merged
- ChatGPT Library: agent-readable mirror

Do not store secrets or large licensed raw datasets in Git.

## Project map

- `MASTER.md`: research and valuation rules.
- `Framework/`, `GOVERNANCE/`, `Agents/`, `config/`, `schemas/`, `trust/`:
  specifications, policies, agent contracts, and evaluation definitions.
- `kb/`: shared macro and sector research, source maps, and KB architecture.
- `Companies/Reliance/`: company thesis, earnings preview, and valuation model.
- `derived/`: preliminary HDFC Bank and ICICI Bank comparisons, probabilities,
  and premortems. These are research outputs, not validated company snapshots.
- `docs/sources/`: the imported Library package manifest.
- `data/`: reserved input and normalized-data structure; `outputs/` and
  `state/`: generated local files.

This directory is the single Indian Equities project within `~/code/kb`.
The older generic KB shell now lives in `../research-journal/` as a separate
project within this repository. Connector experiments in `~/code/codex-work/`
remain separate because they are a distinct model-router design. The imported
Library documents have not been changed to match the newer runtime code.

## First runtime slice

The repository-root CLI accepts a structured test research JSON file and records
each workflow step under `projects/indian-equities/state/`. Generated state,
snapshots and Case Book files stay on this Mac and are ignored by Git.

```sh
python3 -m src.kb_runtime company-research \
  --entity "HDFC Bank" --input path/to/research.json --run-id hdfc-001
```

Use the same `run-id` and unchanged input to resume a failed run. The CLI
does not gather evidence, calculate valuation or write an investment opinion.
It validates a supplied test snapshot and opens a frozen case only after the
snapshot passes its current structural checks. Real research publication is
blocked until source and integrity validation are implemented. See
`docs/architecture/REPO_RUNTIME_ASSESSMENT_2026-09-28.md` at the repository root.

## Record a source update

Create a JSON metadata file with these exact fields: `source_id`, `entity`,
`source_kind`, `url`, `source_date` (YYYY-MM-DD), `observed_at`, and
`retrieved_at` (ISO timestamps with timezone offsets). Then run:

```sh
python3 -m src.kb_runtime record-source \
  --metadata path/to/source.json --raw-file path/to/downloaded-file
```

The command writes the raw bytes under ignored `data/raw/sha256/` and one
version record under tracked `data/registry/sources/`. It returns the source
ID, version ID, and raw SHA-256 hash. Repeating the same input returns the
same version. The source register is an update trail, not approval of the
source or its claims. See `GOVERNANCE/INGESTION_POLICY.md` for the rules.

## Check source readiness

Create a JSON request with a research `entity`, a timezone-aware
`cutoff_timestamp`, and a nonempty `required_sources` list. Each entry names a
registered `source_id` and its allowed `max_age_days`. Shared macro and sector
sources may support another entity. For example:

```json
{
  "entity": "SBI",
  "cutoff_timestamp": "2026-09-28T18:00:00+05:30",
  "required_sources": [{"source_id": "SBI_Q1FY27", "max_age_days": 60}]
}
```

Run the check from the repository root:

```sh
python3 -m src.kb_runtime evaluate-sources \
  --request path/to/refresh-request.json --run-id sbi-refresh-001
```

The command checks source dates, registered versions, raw file hashes, and age
at the cutoff. It writes a frozen report under ignored `state/refresh_runs/`.
`SOURCE_READY` means all requested source files passed these checks.
`SOURCE_BLOCKED` names each missing, late, stale, or damaged source. Use a new
run ID after a source update. This check does not validate claims or permit
real research publication.

## Check claim links and gaps

After a source readiness run, prepare a JSON claim request with `entity`, the
same `cutoff_timestamp`, and a nonempty `claims` list. Each claim needs
`claim_id`, `claim_type`, `statement`, `as_of` (YYYY-MM-DD), `source_id`, the
exact `version_id` from the source report, and `passage_locator`. For example:

```json
{
  "entity": "SBI",
  "cutoff_timestamp": "2026-09-28T18:00:00+05:30",
  "claims": [{
    "claim_id": "sbi-deposit-growth",
    "claim_type": "REPORTED_FACT",
    "statement": "Deposits grew.",
    "as_of": "2026-06-30",
    "source_id": "SBI_Q1FY27",
    "version_id": "<64-character version ID from source report>",
    "passage_locator": "page 12, deposits table"
  }]
}
```

```sh
python3 -m src.kb_runtime evaluate-claims \
  --claims path/to/claims.json \
  --source-report projects/indian-equities/state/refresh_runs/sbi-refresh-001.json \
  --run-id sbi-claims-001
```

The report under ignored `state/claim_runs/` checks source version and raw
bytes and lists an open gap for every claim. A linked source still has
`passage_status: UNVERIFIED`: the command cannot decide whether the passage
supports the statement. Derived and inferred claims need later calculation
or judgment checks. `CLAIMS_BLOCKED` is expected; this command does not
authorize real research publication.

## Run a repeatable evidence refresh

Use matching entity and cutoff values in the source and claim requests:

```sh
python3 -m src.kb_runtime refresh-evidence \
  --source-request path/to/refresh-request.json \
  --claims path/to/claims.json --run-id sbi-evidence-001
```

After new source data arrives, use a new run ID and name the earlier run:

```sh
python3 -m src.kb_runtime refresh-evidence \
  --source-request path/to/new-refresh-request.json \
  --claims path/to/claims.json --run-id sbi-evidence-002 \
  --previous-run-id sbi-evidence-001
```

The command runs both checks, saves their frozen reports, and writes an
evidence manifest under ignored `state/evidence_runs/`. It lists source
version changes, claims to recheck, and open gaps. Repeating an unchanged
run ID resumes the same result. `publication_allowed` stays false because
passage, conflict, calculation, and rights checks are not yet complete.

## Check supplied passage text

Create a packet with the same entity and cutoff as a frozen claim report:

```json
{
  "entity": "SBI",
  "cutoff_timestamp": "2026-09-28T18:00:00+05:30",
  "quotes": [{
    "claim_id": "sbi-deposit-growth",
    "verbatim_quote": "Deposits grew"
  }]
}
```

```sh
python3 -m src.kb_runtime evaluate-passages \
  --packet path/to/passage-packet.json \
  --claim-report projects/indian-equities/state/claim_runs/sbi-claims-001.json \
  --run-id sbi-passages-001
```

The frozen report under ignored `state/passage_runs/` checks exact UTF-8
quote bytes in the pinned raw source. Plain text up to 16 MiB is supported;
PDF and binary files stay `UNSUPPORTED_FORMAT`. `QUOTE_PRESENT` proves byte
presence only. Claim meaning stays `UNVERIFIED`, gaps remain open, and real
publication stays blocked.

## Review direct filing claims

After `evaluate-passages`, prepare a review packet with `entity`, the same
`cutoff_timestamp`, exact `claim_report_id` and `passage_report_id`, and a
`decisions` list. Each decision names a claim and reviewer, review time,
local-analysis rights evidence and decision, semantic decision, review note,
contradiction status and related claim IDs. Copy the exact `source_id`,
`version_id`, `raw_sha256`, `verbatim_quote`, and `byte_offset` from that
claim's frozen passage result. See the 05 design spec for the allowed values.

```sh
python3 -m src.kb_runtime review-claims \
  --packet path/to/review-packet.json \
  --claim-report projects/indian-equities/state/claim_runs/sbi-claims-001.json \
  --passage-report projects/indian-equities/state/passage_runs/sbi-passages-001.json \
  --run-id sbi-review-001
```

The frozen report under ignored `state/claim_review_runs/` can mark a direct
reported fact or management guidance `INTERNAL_REVIEWED` only when the exact
quote, reviewed filing and identity, strict cutoff, local-analysis rights,
human meaning review, and known-conflict decision all pass. Other claim types
stay blocked until their own contracts exist. The original gap report stays
unchanged; only this review report records a closed receipt. Human review does
not prove meaning, license scope, or that every contradiction was found.
Local hashes are integrity checks, not signed proof against someone who can
rewrite the whole local report chain.
`publication_allowed` remains false for real companies.

## Run the pinned evidence workflow

The versioned contract at `config/runtime_contracts/evidence_review.v1.json`
loads three pinned skill contracts and runs source refresh, passage presence,
and claim review in dependency order. First run without a review packet:

```sh
python3 -m src.kb_runtime run-evidence-workflow \
  --source-request path/to/source-request.json \
  --claims path/to/claims.json \
  --passage-packet path/to/passages.json \
  --contract projects/indian-equities/config/runtime_contracts/evidence_review.v1.json \
  --run-id evidence-001
```

The trace pauses at `AWAITING_REVIEW`. Read its frozen claim and passage
reports, then prepare the human review packet described above with their exact
IDs. Resume with the same arguments and run ID plus
`--review-packet path/to/review.json`. The runner binds the packet to this run,
checks each parent and source again, and records the selected skill path,
digest, handler, and output ID. A changed input or contract under that run ID
fails. The old `Agents/*/contract.yaml` files remain design references; they
are not callable skills. This workflow grants no publication permission and
does not execute analysis, case opening, or learning stages.

## Record a classified source gap attempt

Use `attempt-gap` only after reviewing a frozen open gap and the exact source
permission. Give it the source and claim requests that produced the two frozen
reports, plus a classification packet. For an eligible public primary source,
provide a local raw file and matching source metadata:

```sh
python3 -m src.kb_runtime attempt-gap \
  --packet path/to/gap-classification.json \
  --claim-report path/to/claim-report.json \
  --source-report path/to/source-report.json \
  --source-request path/to/source-request.json \
  --claims path/to/claims.json \
  --raw-file path/to/downloaded-filing.pdf \
  --metadata path/to/source-metadata.json \
  --project-dir projects/indian-equities \
  --state-dir projects/indian-equities/state \
  --attempt-id gap-attempt-001
```

The packet fields and allowed classifications are in the [07 design spec](../../docs/superpowers/specs/2026-09-29-gap-adapter-design.md).
For internal, restricted, or unclassified gaps, omit `--raw-file` and
`--metadata`; the command writes a blocked receipt without importing a source.
The local adapter makes no network request. Rights are attested by a human;
the runtime does not verify an agreement or grant NSE/BSE collection rights.
Each receipt stays under ignored `state/gap_attempts/<attempt-id>/`, leaves the
old gap `OPEN`, and has `publication_allowed: false`. A recorded source needs
a new cutoff refresh, passage check, and 05 claim review before it can support
research.

## Freeze an internal analyst worksheet

`analyze-judgment` checks a strict analyst packet against one frozen claim
review and the typed metric catalog at its cutoff. It records four research
layers, a most-likely path, independent debates, catalysts, valuation
assumptions, and judgment checks. The packet schema and a synthetic example
are in `tests/test_analysis_judgment.py`. Run it with:

```sh
python3 -m src.kb_runtime analyze-judgment \
  --packet path/to/analysis.json \
  --claim-review-report path/to/claim-review.json \
  --project-dir projects/indian-equities \
  --catalog projects/indian-equities/data/registry/identity.sqlite \
  --state-dir projects/indian-equities/state \
  --run-id analysis-001
```

The fair value is an **analyst estimate**: base value plus declared
probability-weighted incremental impacts, rounded to two decimal places.
The command checks the model file's hash but does not verify its formulas,
assumptions, causal explanations, or the analyst's independence claims.
Market price, consensus, score, and trading stance remain `NOT_ASSESSED`;
judgment stays `HUMAN_REVIEW_REQUIRED`, and `publication_allowed` stays false.
Use a new run ID and `previous_report_id` for a later worksheet revision.

## Register issuer and traded-security identity

After storing a reviewed exchange security file with `record-source`, make an
identity request with issuer ID, ISIN, listing and symbol dates, announcement
and first-seen times, and that source's ID and version ID. For example:

```json
{
  "issuer_id": "SBI", "legal_name": "State Bank of India",
  "isin": "INE062A01020", "security_type": "EQUITY",
  "listed_from": "1995-01-01", "listed_to": null,
  "exchange": "NSE", "symbol": "SBIN",
  "valid_from": "1995-01-01", "valid_to": null,
  "announced_at": "2026-09-28T09:00:00+05:30",
  "first_seen_at": "2026-09-28T09:05:00+05:30",
  "source_id": "SBI_IDENT", "version_id": "<64-character source version ID>",
  "reviewer_id": "analyst-1", "reviewed_at": "2026-09-28T09:06:00+05:30",
  "review_decision": "CONFIRMED", "evidence_locator": "security file row 1"
}
```

```sh
python3 -m src.kb_runtime register-identity --request path/to/identity.json
python3 -m src.kb_runtime resolve-symbol --exchange NSE --symbol SBIN \
  --effective-date 2026-09-28 --cutoff 2026-09-28T09:06:00+05:30
```

The local catalog under `data/registry/identity.sqlite` is ignored by Git.
Registration validates the source bytes and ISIN, rejects conflicting or
overlapping mappings, and is safe to retry. Resolution hides a mapping until
its announcement, KB first-seen, and manual review times pass the cutoff. It
rechecks source bytes before returning an ISIN. The reviewer must inspect the
named evidence row; the runtime cannot infer identity from the file alone.
The example dates are illustrative; enter verified dates from the actual
exchange source.

## Register and query filing metrics

After `record-source` and `register-identity`, create one JSON request per
reviewed filing. The recorded source must have `source_kind: EXCHANGE_FILING`,
`entity` equal to the issuer ID, and observation time no later than retrieval.
The request needs these exact filing fields: `filing_id`, `issuer_id`,
`isin`, `source_id`, `version_id`, `document_type`, `period_end`,
`published_at`, `first_seen_at`, `rights_status`, `reviewer_id`,
`reviewed_at`, `review_decision`, `evidence_locator`,
`supersedes_filing_id`, and a nonempty `metrics` list. Set `rights_status` to
`REVIEWED` and `review_decision` to `CONFIRMED` only after manual review.
Each metric needs `metric_id`, `metric_name`, `value_decimal` as a plain
decimal string, `unit`, `period_end`, `period_kind`, `reporting_scope`,
`value_kind`, `evidence_locator`, and `supersedes_metric_id`. Use `null` for
no predecessor. The supported value kinds are `REPORTED` and `GUIDANCE`;
units are `INR`, `INR_LAKH`, `INR_CRORE`, `PERCENT`, `SHARES`, `COUNT`, and
`RATIO`. Period kinds are `FY`, `QUARTER`, and `YTD`; reporting scope is
`CONSOLIDATED` or `STANDALONE`.

```sh
python3 -m src.kb_runtime register-filing-metrics --request path/to/filing.json
python3 -m src.kb_runtime query-metrics --isin INE062A01020 \
  --metric-name revenue --period-end 2026-06-30 \
  --cutoff 2026-09-28T18:00:00+05:30
```

The query uses strict live replay: filing publication, KB first-seen, and
review times must all pass the cutoff. It rechecks the raw source and identity
files. A later restatement appends a revision; an older cutoff still returns
the earlier metric. A metric's `period_end` can precede its filing's period
for a reported comparison, but the metric is never available before the
filing. Historical reconstruction of later backfills needs a separate
archive and identity proof contract. This command does not publish research.

For a reviewed transcript, presentation, annual report, or announcement with
no typed metrics, use the same filing request shape with `metrics: []` and run:

```sh
python3 -m src.kb_runtime register-filing --request path/to/filing.json
```

The filing-only command rejects a `RESULTS` document or a nonempty metrics
list. It applies the same source, ISIN, rights, review, and revision checks.

For a reviewed plain UTF-8 filing, extract cited text chunks and read them at
a cutoff:

```sh
python3 -m src.kb_runtime extract-text-filing --filing-id F1
python3 -m src.kb_runtime query-text-chunks --filing-id F1 \
  --cutoff 2026-09-28T18:00:00+05:30
```

Each chunk has an immutable ID, source version, exact raw byte span, and text
hash. The reader rechecks the raw file, identity, review time, and spans.
Speaker role is `UNKNOWN` and page number is empty for this plain-text parser.
It does not guess who spoke. PDF, binary, empty, or oversized input is blocked
on this plain-text path.
These chunks are evidence candidates, not approved research claims.

For a reviewed PDF filing, use the separate page-aware path:

```sh
python3 -m src.kb_runtime extract-pdf-filing --filing-id F1
python3 -m src.kb_runtime query-pdf-chunks --filing-id F1 \
  --cutoff 2026-09-28T18:00:00+05:30
python3 -m src.kb_runtime review-pdf-role --request path/to/role-review.json
```

The PDF parser is pinned to `pypdf==6.19.0`. It stores extracted UTF-8 page
text apart from the raw PDF. A PDF chunk's 1-based page number is its physical
PDF page. Its byte offsets refer to that derived page text, **not** the raw
PDF. Every page must have extractable text; corrupt, encrypted, image-only,
blank-page, or oversized documents block without partial extraction. The
reader reparses the raw PDF and compares every stored page and chunk. This
does not validate OCR or a printed page label. A licensed real sample and
visual page check are required before a source adapter uses this path.

Roles default to `UNKNOWN`. A role review JSON has exactly these fields:
`review_id`, `filing_id`, `chunk_id`, `page_number`, `byte_start`, `byte_end`,
`quote`, `speaker_role` (`MANAGEMENT`, `ANALYST`, or `MODERATOR`), `reviewer_id`,
`reviewed_at`, `evidence_locator`, and `supersedes_review_id` (`null` for the
first review). Copy the full exact chunk text into
`quote`. The page and offsets must match that chunk. A review is append-only,
and the role becomes visible only after both `reviewed_at` and the system
recorded arrival time. A later review can correct the role by naming the
previous review ID in `supersedes_review_id`; use `UNKNOWN` to revoke it.
The PDF extraction also has a system recorded arrival time. An earlier
strict-live cutoff cannot see chunks first parsed later. Mixed-speaker
chunks must stay `UNKNOWN`; this path does not infer a role. Neither PDF
extraction nor role review permits real research publication.

Search verified filing text within one issuer at a strict cutoff:

```sh
python3 -m src.kb_runtime search-chunks --issuer-id SBI --query 'capex guidance' \
  --cutoff 2026-09-28T18:00:00+05:30 --document-type CONCALL_TRANSCRIPT
```

Optional filters are `--isin`, repeated `--document-type`, `--speaker-role`,
`--limit` (1–20), and `--include-superseded`. The default excludes earlier
filing versions once a reviewed successor is visible at the cutoff. Each
result includes a stable chunk ID, source hash, citation offsets, and a simple
word-overlap score. Plain-text and PDF extraction must already exist; missing
extractions are skipped and damaged registered extractions block the search.
Plain-text extraction also records when it reached the KB. Old extraction rows
with unknown arrival require verified replay before a strict-live read.
This is a lexical baseline pending the reviewed retrieval evaluation set.
Search text is a citation candidate. Numeric answers and screens use typed
metrics, not the words or figures found in a chunk. The search cannot publish
research.

Score a 30–50 case reviewed text gold set with:

```sh
python3 -m src.kb_runtime eval-retrieval --gold path/to/gold.jsonl \
  --catalog projects/indian-equities/data/registry/identity.sqlite
```

Pass `--answers path/to/answers.jsonl` to score a separate answer generator.
The runner reports source-quote recall at five, empty results for reviewed
absence cases, exact submitted answer accuracy, citation precision, and
abstention accuracy with counts. Without answers, answer quality is `NOT_RUN`.
Gold cases pin source version, raw hash, and exact quote; PDF anchors may pin
a physical page. Real quality and promotion remain blocked until a reviewed
real gold set and frozen baseline exist. Synthetic fixture scores only check
the runner's behavior. The reported catalog hash is a partial receipt, not a
frozen source corpus. Numeric-answer evaluation belongs to typed metrics.
