# Indian company KB progress

Checkpoint: 23 October 2026. This is an inventory of the checked-out repository,
not a refresh of company financials or investment recommendations.

## What is saved

| Coverage | Existing work | Remaining work |
|---|---|---|
| SBI | Company note, thesis, Q1FY27 earnings, source ledger, Python equity model and valuation note | Refresh primary evidence; reconcile published BVPS with model equity/share; verify official price and share count |
| Reliance | Company framework, thesis, earnings preview and SOTP workbook | Capture a source ledger and dated, sourced segment actuals before refreshing valuation |
| HDFC Bank | Preliminary comparison, probabilities and premortem under `derived/` | Build a complete company folder and pinned source evidence; preliminary values and scores are not validated |
| ICICI Bank | Preliminary comparison, probabilities and premortem under `derived/` | Build a complete company folder and pinned source evidence; preliminary values and scores are not validated |
| Remaining validation universe | Fourteen-company selection in `Framework/UNIVERSE_14.md` | Twelve of those fourteen have no dedicated company folder or company comparison in this checkout |

SBI and Reliance are additional pilots outside the fourteen-company validation
cohort. Shared India macro and lending-sector notes exist, with open RBI data
gaps. Their existence does not establish current source readiness.

## Runtime versus research readiness

- The guarded evidence runtime is `python -m src.kb_runtime`. It records sources,
  validates dated evidence and preserves publication restrictions.
- A separate experimental live pipeline is `python -m src.kb_runtime.cli`.
  Storage, ingestion, search, wiki and MCP code exist. It is not evidence that
  the company universe has been populated or that research passed review.
- Read-only inspection of tracked `kb_structured.duckdb` found **one company,
  zero filings and zero metrics**. Its only identity is `ISIN_RELIANCE`, a
  placeholder rather than a verified ISIN. The database was left unchanged.
- No registered source records or identity catalog were recovered under the
  project's `data/` directory. Raw evidence absent from this checkout must not
  be described as recovered from another machine or session.
- Live ingestion can fall back to hash-based mock embeddings and treats an
  absent golden set as a skipped evaluation with a perfect numeric result.
  Do not treat that result as verified retrieval quality or publish research
  from this path. The guarded runtime's publication restrictions still apply.

## Checks at this checkpoint

- SBI's unchanged Python model reproduces its saved probability-weighted
  value of INR 840.03 and most-likely cell of INR 829.02. Its INR 983 price is
  dated 25 September 2026; these are historical model outputs, not current values.
- The guarded CLI help runs successfully. Storage tests: three passed.
- Initial core-suite run, excluding four live dependency modules: 600 passed,
  three failed, three skipped. Two failures were direct-script CLI import
  errors. The historical evaluation repeat-run test failed because
  `evaluate_historical_cohort` rejects every existing report unconditionally.
  See the cloud validation report for results after dependency installation.
- Fatal syntax/undefined-name lint selection (`E9,F63,F7,F82`) passed for
  `src/` and `tests/`. This is not a full style or application-quality claim.
- The existing SBI Q1FY27 presentation URL returned HTTP 403 on this machine.
  No new financial fact or source approval was inferred from that response.
- A committed OpenRouter credential was cleared from the current configuration
  file. Revoke or rotate it at the provider: clearing the file does not remove
  the credential from earlier Git history. No history rewrite was performed.

## Continue here

1. Follow [bank source intake](research/BANK_SOURCE_INTAKE.md), starting with
   SBI as the existing model and evidence pilot, then HDFC Bank and ICICI Bank.
2. Obtain permitted primary documents; preserve URL, actual retrieval time,
   source date and content hash. Do not backdate first-seen evidence.
3. Resolve real identities and register source evidence through the guarded
   runtime. Human review fields require actual review; never manufacture receipts.
4. Reconcile SBI's book-value basis before changing its fair-value anchor.
5. Populate reviewed metrics and cited text, then build a reviewed retrieval
   gold set before expanding the remaining company universe.

Code defects and experiment hardening need a separately scoped coding change;
this checkpoint preserves application source, tests and research assumptions.
