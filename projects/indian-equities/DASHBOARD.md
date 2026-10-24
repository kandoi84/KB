# Your Indian Equities KB — dashboard

**Snapshot prepared 24 October 2026.** Coverage/source observations date from
23 October 2026. This page is a read-only project snapshot, not live market data.
It can be shown in GPT as a chat overview; it does not refresh automatically.

## What you actually have

| Measure | Current state | What it means |
|---|---:|---|
| Companies organized | 50 | Symbols matched the observed official Nifty download; historical effective dates remain open |
| Research sectors | 13 | Shared sector desks link to canonical company folders |
| Companies with existing research | 4 | Dated pilots/preliminary work, not four validated current recommendations |
| Intake-only companies | 46 | Company-specific questions and source routes; financial analysis unfinished |
| Registered source versions | 0 | No reviewed evidence chain can be inferred from the folder count |
| Reachable company homepages | 28 / 50 | Access observations, not verified financial documents |
| Investor links identified | 21 | Discovery links; not proof their reports were acquired/reviewed |

**Decision readiness: not ready for defensible portfolio recommendations.**
There is no current buy/sell engine, validated ranking or recommended portfolio.

## Open the research you already have

| Company | Existing material | Main unresolved issue |
|---|---|---|
| [SBI](Companies/SBI/COMPANY.md) | Thesis, earnings note, source ledger and reproducible dated equity model | Book-value definition bridge, current sources, shares and price |
| [Reliance](Companies/Reliance/COMPANY.md) | Thesis, preview, SOTP workbook and ten recovered source references | Retrieve/reconcile evidence and refresh segment inputs |
| [HDFC Bank](Companies/HDFCBank/COMPANY.md) | Consolidated historical working report and preliminary comparison | Primary filings and reproducible valuation model missing |
| [ICICI Bank](Companies/ICICIBank/COMPANY.md) | Consolidated historical working report and preliminary comparison | Primary filings and reproducible valuation model missing |

The other 46 folders are research intake profiles. A complete folder layout
is not a completed company analysis. Existing September prices/fair values
are historical work, not current values or trade signals.

## Browse by sector

| Sector | Companies | Existing dated research | Intake-only |
|---|---:|---:|---:|
| [Automobiles](kb/sectors/automobiles/README.md) | 5 | 0 | 5 |
| [Consumer durables](kb/sectors/consumer-durables/README.md) | 2 | 0 | 2 |
| [Consumer services](kb/sectors/consumer-services/README.md) | 2 | 0 | 2 |
| [Consumer staples](kb/sectors/consumer-staples/README.md) | 4 | 0 | 4 |
| [Energy](kb/sectors/energy/README.md) | 3 | 1 | 2 |
| [Financial services](kb/sectors/financial-services/README.md) | 12 | 3 | 9 |
| [Healthcare](kb/sectors/healthcare/README.md) | 5 | 0 | 5 |
| [Industrials](kb/sectors/industrials/README.md) | 3 | 0 | 3 |
| [Information technology](kb/sectors/information-technology/README.md) | 4 | 0 | 4 |
| [Materials](kb/sectors/materials/README.md) | 5 | 0 | 5 |
| [Telecommunications](kb/sectors/telecommunications/README.md) | 1 | 0 | 1 |
| [Transport and logistics](kb/sectors/transport-logistics/README.md) | 2 | 0 | 2 |
| [Utilities](kb/sectors/utilities/README.md) | 2 | 0 | 2 |

[Open all 50 company entries](research/NIFTY50_COVERAGE.md) ·
[Open source-route observations](research/PRIMARY_SOURCE_ROUTES_2026-10-23.csv)

## Capability status

| Capability | Status | What exists / what is missing |
|---|---|---|
| Coverage organization | Available | 50-company register, sector desks and source routes |
| Fundamental research | Partial | Four dated research folders; most financial inputs/models still missing |
| Source integrity/evidence workflow | Code exists; real research not promoted | CLI and tests exist; this snapshot has zero registered source versions |
| Technical analysis | Proposed | Trend, relative-strength, volatility and volume design; no implemented signals |
| Buy/add/hold/reduce/exit decisions | Proposed | Decision policy draft; no active recommendation engine |
| Portfolio construction | Proposed | Constraints and paper-portfolio design; no holdings or weights recommended |
| Nifty-relative performance | Unproven | Evaluation requirements exist; no demonstrated strategy outperformance |
| Older web app | Unhosted, unvalidated prototype | `app.py` reads experimental stores and uses mock search; it does not power this dashboard |

## What makes the next version useful

1. Complete and source the existing bank models plus a non-bank pilot.
2. Acquire permitted price/benchmark history and validate corporate actions.
3. Implement/test the approved technical and decision rules on that evidence.
4. Run a constrained paper portfolio and compare against Nifty 50 TRI after costs.
5. Expand proven workflows across all sectors, retaining only incremental changes.

Your confirmed objective is a **1–3 year horizon with monthly reviews**.
The [fundamental/technical/portfolio design](../../docs/superpowers/specs/2026-10-24-fundamental-technical-portfolio-design.md)
is proposed and independently reviewed, not implemented or user-approved.

## Navigate the project

- [Progress and known gaps](PROGRESS.md)
- [Public source catalog: company filings, Value Research, ET and Screener](research/PUBLIC_SOURCE_CATALOG.md)
- [How incremental updates should work](research/INCREMENTAL_RESEARCH.md)
- [Official index observation and its limits](research/NIFTY50_OFFICIAL_OBSERVATION_2026-10-23.json)
- [Existing runtime validation results and failures](../../docs/cloud/VALIDATION_2026-10-23.md)

To refresh this dashboard, inspect the registers, source state and implementation
before updating it. Do not increment readiness simply because more files exist.
No raw credentials, account information or invented market values belong here.
