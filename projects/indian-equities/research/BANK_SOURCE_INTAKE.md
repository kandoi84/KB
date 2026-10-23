# Bank source intake queue

Prepared 23 October 2026 from existing repository work. All entries below are
pending; this document does not attest that a filing was acquired or reviewed.

## First batch

| Company | Starting point | Primary documents to collect | Acceptance checks |
|---|---|---|---|
| SBI | `Companies/SBI/Sources/LEDGER.md`, existing model and thesis | Latest available standalone results and notes, presentation, annual-report book-value definition, share-capital reconciliation | Verify issuer identity; reconcile reserves and published BVPS; distinguish quarterly, annualised and period-end ratios |
| HDFC Bank | `derived/comparison/BANKS_FINAL_COMPARISON.md` | Latest available results, presentation, annual report and share-capital/corporate-action disclosures | Confirm standalone versus consolidated basis, share adjustments, NIM denominator and ROA annualisation |
| ICICI Bank | Same preliminary comparison | Latest available results, presentation, annual report and share-capital disclosures | Confirm reporting scope, average versus period-end balances and annualisation conventions |

Use company investor-relations materials first. Exchange data requires the
collection and storage rights checks in `GOVERNANCE/SOURCE_POLICY.md`; a public
URL or wrapper library is not proof of permission. Obtain a permitted local
copy if a primary link blocks access. Do not bypass an access restriction.

## Evidence record for each document

Record the issuer, document title, reporting scope, period end, publication
date, exact source URL, observed/retrieved timestamps, local path, SHA-256,
rights basis and physical PDF page references. Preserve raw bytes separately
from extracted text. A missing publication timestamp stays unknown rather
than being replaced with the financial period end.

The `record-source` command expects the metadata fields documented in the
project README. Use it only after obtaining the actual document. Registration
is an integrity trail, not claim approval. Identity and metric registration
require their own source-backed review packets.

## Comparable bank metrics

Collect reported NII, net profit, advances, deposits, NIM, GNPA, NNPA, credit
cost, CET1/capital adequacy, ROA, ROE, equity and diluted shares. For each number,
retain its source page, unit, period, reporting scope and definition. Keep
reported, derived and analyst-assumption fields separate. Do not compare NIM
or book value across banks until the denominators and definitions reconcile.

## Completion gate

- Each bank has the required company-folder sections and a source ledger.
- Load-bearing numbers link to retrieved evidence with dates and definitions.
- Typed metrics and cited text pass the guarded source/identity checks.
- Meaning and rights reviews are performed by the named reviewer.
- Missing consensus, prices, history or score inputs remain explicit gaps.
- No investment ranking, trading band or refreshed fair value is claimed merely
  because the ingestion command exited successfully.

SBI's immediate unresolved items remain its published BVPS bridge, current
shares and official price evidence. HDFC/ICICI comparison values remain dated
preliminary research until this intake and the framework's evaluation gates pass.
