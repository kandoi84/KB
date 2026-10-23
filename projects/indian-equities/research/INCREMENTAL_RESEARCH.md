# Incremental company research

Use the existing source register and evidence workflow. Do not rebuild tables,
download every historical document or rewrite the thesis at each refresh.

The [Nifty 50 coverage register](NIFTY50_COVERAGE.md) now links all 50 observed
companies, now matched to the observed official list, through 13 sector desks. Keep one canonical company folder
and shared sector definitions; do not duplicate reports into sector folders.
The observation is not proof of historical effective membership; resolve those
dates and reviewed security identity before strict replay or backtests.

## Start with the saved state

Read `COMPANY.md`, `Thesis.md`, the latest earnings/valuation note and the
source ledger. The HDFC Bank and ICICI Bank folders now consolidate the
existing preliminary work; their linked legacy artifacts remain intact.
Shared RBI and sector data belong in the shared KB and should be referenced
by every affected bank rather than collected separately for each company.

Look for the answer in the [source catalog](PUBLIC_SOURCE_CATALOG.md) before
creating a new data pipeline. Use provider-prepared tables to locate changes;
retain source labels and verify definitions before adopting the numbers.

## Collect only the missing change

| Trigger | Refresh | Preserve |
|---|---|---|
| New quarterly result | New filing, changed KPIs, guidance and affected model periods | Historical raw files, prior values and earlier valuation assumptions |
| Restatement or corporate action | Revision link, affected periods/shares and adjustment bridge | Original observations and their availability dates |
| RBI/sector release | Shared source and affected bank assumptions | Unaffected company-specific evidence |
| Material news | Named event, primary confirmation and thesis implication | Unaffected financial forecasts; do not mechanically change fair value |
| No new material information | Record the check and next trigger | Existing evidence and analysis; old observations retain their original dates |

For a retrieved document, retain its URL, source date, actual observation and
retrieval timestamps, rights basis and SHA-256. Use the same source ID only
for the same entity, source kind and canonical URL. A new quarterly URL needs
its own source identity. Do not force unrelated documents under one ID.

`record-source` stores raw bytes by content hash. Exact metadata/bytes retries
return the same version. A new timestamp or changed content creates another
observation/version; unchanged content can reuse its raw blob. This is the
existing behavior, not a newly implemented polling or change-detection service.

From the repository root, register acquired evidence with the documented CLI:

```sh
python -m src.kb_runtime record-source \
  --metadata path/to/actual-source-metadata.json \
  --raw-file path/to/permitted-document.pdf
```

Then update source and claim requests with the same entity and cutoff, using
the exact returned source/version IDs. A new refresh gets a new run ID:

```sh
python -m src.kb_runtime refresh-evidence \
  --source-request path/to/source-request.json \
  --claims path/to/claims.json --run-id bank-refresh-002 \
  --previous-run-id bank-refresh-001
```

These are command shapes, not acquired sources or executed real-company runs.
The register cannot represent an unknown source date: leave an undated candidate
in the ledger until its date is established rather than inventing one.
Registration and refresh do not approve claim meaning, rights or publication.

## The update to write

Each dated update should answer: **what changed since the previous observation,
which evidence supports it, and what does it change in our view?** Include:

- New versus previous value with the same unit, period basis and reporting scope.
- Source/version and page locator; reported fact versus derived calculation,
  provider opinion or analyst assumption.
- Operating implication and which independent debate it affects.
- Model/fair-value impact, or an explicit statement that evidence is insufficient
  to change it. Preserve the old valuation and explain every material revision.
- Open conflict or missing evidence, owner/next source, and next review trigger.

Start with SBI's book-value reconciliation and HDFC/ICICI's missing filing
evidence. Consensus and historical-price access are gaps, not reasons to
manufacture a score. Until checked, inherited September values are historical
work in progress, never a live market view.
