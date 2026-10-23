# Indian company KB progress

Checkpoint: 23 October 2026. This is an inventory of the checked-out repository,
not a refresh of company financials or investment recommendations.

## What is saved

| Coverage | Existing work | Remaining work |
|---|---|---|
| SBI | Company note, thesis, Q1FY27 earnings, source ledger, Python equity model and valuation note | Refresh primary evidence; reconcile published BVPS with model equity/share; verify official price and share count |
| Reliance | Company framework, thesis, earnings preview, SOTP workbook and [recovered source index](Companies/Reliance/Sources/LEDGER.md) | Retrieve the indexed documents and validate dated segment inputs before refreshing valuation |
| HDFC Bank | [Company folder](Companies/HDFCBank/COMPANY.md) consolidating the preliminary comparison, probability and risk work | Retrieve primary evidence and reconstruct the valuation model; inherited values and scores are not validated |
| ICICI Bank | [Company folder](Companies/ICICIBank/COMPANY.md) consolidating the preliminary comparison, probability and risk work | Retrieve primary evidence and reconstruct the valuation model; inherited values and scores are not validated |
| Nifty 50 | [50 official-list-observed symbols and 13 sector desks](research/NIFTY50_COVERAGE.md); four existing research folders and 46 intake profiles | Resolve historical membership/security identity, then acquire financial evidence and underwrite the intake profiles |
| Legacy validation universe | Fourteen-company selection in `Framework/UNIVERSE_14.md` preserved separately | Its Divi's, ABB India and Ambuja entries are not in the observed Nifty set; preserve them as validation-cohort entries |

SBI and Reliance are additional pilots outside the fourteen-company validation
cohort. All four existing company pilots appear in the official-list-observed
Nifty set. Shared India macro and lending-sector notes exist, with open RBI
data gaps. Their existence does not establish current source readiness.

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

On 24 October, the user expanded the goal to fundamental anchors, technical
buy/sell support and a recommendation portfolio seeking to outperform Nifty.
The confirmed horizon is 1–3 years with monthly reviews. The
[proposed system design](../../docs/superpowers/specs/2026-10-24-fundamental-technical-portfolio-design.md)
defines separate valuation, timing and portfolio decisions, proposed risk limits,
and cost-aware benchmark/ablation tests. It is independently reviewed but awaits
user design/mandate approval. No technical engine or portfolio is implemented,
and no outperformance or new stock recommendation is claimed.

The [public-source catalog](research/PUBLIC_SOURCE_CATALOG.md) routes company
filings, Value Research, ET and Screener to different research needs. The
[incremental workflow](research/INCREMENTAL_RESEARCH.md) reuses existing
evidence and updates only affected data/analysis. HDFC/ICICI folders contain
clearly labelled inherited inputs; no new external financial evidence was
acquired. Screener, Value Research and ET became reachable in the next task;
the machine then reconnected and the official index download became accessible.
Its 50 symbols match the register. Candidate issuer routes were checked separately;
not all sites or documents are reachable. Saved domain changes do not themselves
establish licensed collection rights or successful publication.
OpenRouter key revocation remains pending account-owner action; see
[the incident status](../../docs/cloud/OPENROUTER_REVOCATION_STATUS.md).

1. Use the [sector-organized Nifty coverage queue](research/NIFTY50_COVERAGE.md).
   Resolve effective-date/identity gaps, then work sector by sector,
   reusing the four existing pilots and the [bank intake](research/BANK_SOURCE_INTAKE.md).
2. Obtain permitted primary documents; preserve URL, actual retrieval time,
   source date and content hash. Do not backdate first-seen evidence.
3. Resolve real identities and register source evidence through the guarded
   runtime. Human review fields require actual review; never manufacture receipts.
4. Reconcile SBI's book-value basis before changing its fair-value anchor.
5. Populate reviewed metrics and cited text, then build a reviewed retrieval
   gold set. Fifty folder entries do not establish fifty completed reports.

Code defects and experiment hardening need a separately scoped coding change;
this checkpoint preserves application source, tests and research assumptions.
