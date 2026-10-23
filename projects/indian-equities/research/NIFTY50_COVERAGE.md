# Nifty 50 — sector-organized coverage

Discovery: **2026-10-23T14:53:29+05:30**. Official-list observation: **2026-10-23T15:05:41+05:30**.

**50 official-list-observed symbols across 13 research sectors.** Four companies
have existing dated research; 46 have intake profiles, not completed research.
No new company financials, market prices, forecasts or scores were imported.

## Universe status

The initial [ET discovery observation](https://economictimes.indiatimes.com/markets/indices/nifty-50)
was cross-checked after the cloud reconnected against the
[official constituent download](https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv).
All **50 of 50 symbols match**, with no additions or omissions. The
[dated observation receipt](NIFTY50_OFFICIAL_OBSERVATION_2026-10-23.json)
records the actual retrieval/observation time and content hash.

The file does not state its publication or membership-effective date. This
establishes the set observed at retrieval, not a historical backtest universe.
The source includes identity fields, but no ISINs were imported into the
reviewed identity catalog. BSE and Tata Motors Passenger Vehicles are in the
observed official set; confirm the latter's corporate-action/reporting perimeter
before reusing former Tata Motors history.

Canonical register:
[nifty50_2026-10-23.csv](../config/universes/nifty50_2026-10-23.csv).
Every row has `membership_status: OFFICIAL_SYMBOL_SET_OBSERVED`, the official
URL and observation time, and an empty `membership_effective_date`. The earlier
secondary discovery source/time are retained separately. `symbol_candidate`
is a routing-column name; its values now match the observed official symbols,
while catalog identity remains unregistered. Sector/subsector assignments are
our research organization, not official index classifications.

The official [terms](https://www.niftyindices.com/terms-of-use) restrict copying
and automated collection. No recurring collector, redistributed official CSV,
ISIN dataset or raw page archive is introduced. The receipt is our one-time
comparison result, not permission for a data feed. Financial evidence and
source rights remain separate review gates.

## Sector desks

The [primary-route register](PRIMARY_SOURCE_ROUTES_2026-10-23.csv) records one
homepage request per company: 28 returned HTTP 200, eight redirected without
being followed, five returned 403, five returned 406, three returned 503 and
one failed at the proxy. Twenty-one homepages yielded selected investor links.
Those links were observed, not fetched or approved; no financial values were
extracted. Each company source ledger records its own observation and next route.

| Research sector | Companies | Desk |
|---|---:|---|
| Automobiles | 5 | [Open sector](../kb/sectors/automobiles/README.md) |
| Consumer durables | 2 | [Open sector](../kb/sectors/consumer-durables/README.md) |
| Consumer services | 2 | [Open sector](../kb/sectors/consumer-services/README.md) |
| Consumer staples | 4 | [Open sector](../kb/sectors/consumer-staples/README.md) |
| Energy | 3 | [Open sector](../kb/sectors/energy/README.md) |
| Financial services | 12 | [Open sector](../kb/sectors/financial-services/README.md) |
| Healthcare | 5 | [Open sector](../kb/sectors/healthcare/README.md) |
| Industrials | 3 | [Open sector](../kb/sectors/industrials/README.md) |
| Information technology | 4 | [Open sector](../kb/sectors/information-technology/README.md) |
| Materials | 5 | [Open sector](../kb/sectors/materials/README.md) |
| Telecommunications | 1 | [Open sector](../kb/sectors/telecommunications/README.md) |
| Transport and logistics | 2 | [Open sector](../kb/sectors/transport-logistics/README.md) |
| Utilities | 2 | [Open sector](../kb/sectors/utilities/README.md) |

## Company register

| Sector | Company | Routing alias | Work status |
|---|---|---|---|
| Automobiles | [Bajaj Auto](../Companies/BAJAJ-AUTO/COMPANY.md) | BAJAJ-AUTO | INTAKE_ONLY |
| Automobiles | [Eicher Motors](../Companies/EICHERMOT/COMPANY.md) | EICHERMOT | INTAKE_ONLY |
| Automobiles | [Mahindra & Mahindra](../Companies/M&M/COMPANY.md) | M&M | INTAKE_ONLY |
| Automobiles | [Maruti Suzuki India](../Companies/MARUTI/COMPANY.md) | MARUTI | INTAKE_ONLY |
| Automobiles | [Tata Motors Passenger Vehicles](../Companies/TMPV/COMPANY.md) | TMPV | INTAKE_ONLY |
| Consumer durables | [Asian Paints](../Companies/ASIANPAINT/COMPANY.md) | ASIANPAINT | INTAKE_ONLY |
| Consumer durables | [Titan Company](../Companies/TITAN/COMPANY.md) | TITAN | INTAKE_ONLY |
| Consumer services | [Eternal](../Companies/ETERNAL/COMPANY.md) | ETERNAL | INTAKE_ONLY |
| Consumer services | [Trent](../Companies/TRENT/COMPANY.md) | TRENT | INTAKE_ONLY |
| Consumer staples | [Hindustan Unilever](../Companies/HINDUNILVR/COMPANY.md) | HINDUNILVR | INTAKE_ONLY |
| Consumer staples | [ITC](../Companies/ITC/COMPANY.md) | ITC | INTAKE_ONLY |
| Consumer staples | [Nestle India](../Companies/NESTLEIND/COMPANY.md) | NESTLEIND | INTAKE_ONLY |
| Consumer staples | [Tata Consumer Products](../Companies/TATACONSUM/COMPANY.md) | TATACONSUM | INTAKE_ONLY |
| Energy | [Coal India](../Companies/COALINDIA/COMPANY.md) | COALINDIA | INTAKE_ONLY |
| Energy | [Oil and Natural Gas Corporation](../Companies/ONGC/COMPANY.md) | ONGC | INTAKE_ONLY |
| Energy | [Reliance Industries](../Companies/Reliance/COMPANY.md) | RELIANCE | EXISTING_RESEARCH_UNREVALIDATED |
| Financial services | [Axis Bank](../Companies/AXISBANK/COMPANY.md) | AXISBANK | INTAKE_ONLY |
| Financial services | [BSE](../Companies/BSE/COMPANY.md) | BSE | INTAKE_ONLY |
| Financial services | [Bajaj Finance](../Companies/BAJFINANCE/COMPANY.md) | BAJFINANCE | INTAKE_ONLY |
| Financial services | [Bajaj Finserv](../Companies/BAJAJFINSV/COMPANY.md) | BAJAJFINSV | INTAKE_ONLY |
| Financial services | [HDFC Bank](../Companies/HDFCBank/COMPANY.md) | HDFCBANK | EXISTING_RESEARCH_UNREVALIDATED |
| Financial services | [HDFC Life Insurance](../Companies/HDFCLIFE/COMPANY.md) | HDFCLIFE | INTAKE_ONLY |
| Financial services | [ICICI Bank](../Companies/ICICIBank/COMPANY.md) | ICICIBANK | EXISTING_RESEARCH_UNREVALIDATED |
| Financial services | [Jio Financial Services](../Companies/JIOFIN/COMPANY.md) | JIOFIN | INTAKE_ONLY |
| Financial services | [Kotak Mahindra Bank](../Companies/KOTAKBANK/COMPANY.md) | KOTAKBANK | INTAKE_ONLY |
| Financial services | [SBI Life Insurance](../Companies/SBILIFE/COMPANY.md) | SBILIFE | INTAKE_ONLY |
| Financial services | [Shriram Finance](../Companies/SHRIRAMFIN/COMPANY.md) | SHRIRAMFIN | INTAKE_ONLY |
| Financial services | [State Bank of India](../Companies/SBI/COMPANY.md) | SBIN | EXISTING_RESEARCH_UNREVALIDATED |
| Healthcare | [Apollo Hospitals](../Companies/APOLLOHOSP/COMPANY.md) | APOLLOHOSP | INTAKE_ONLY |
| Healthcare | [Cipla](../Companies/CIPLA/COMPANY.md) | CIPLA | INTAKE_ONLY |
| Healthcare | [Dr Reddy's Laboratories](../Companies/DRREDDY/COMPANY.md) | DRREDDY | INTAKE_ONLY |
| Healthcare | [Max Healthcare Institute](../Companies/MAXHEALTH/COMPANY.md) | MAXHEALTH | INTAKE_ONLY |
| Healthcare | [Sun Pharmaceutical Industries](../Companies/SUNPHARMA/COMPANY.md) | SUNPHARMA | INTAKE_ONLY |
| Industrials | [Adani Enterprises](../Companies/ADANIENT/COMPANY.md) | ADANIENT | INTAKE_ONLY |
| Industrials | [Bharat Electronics](../Companies/BEL/COMPANY.md) | BEL | INTAKE_ONLY |
| Industrials | [Larsen & Toubro](../Companies/LT/COMPANY.md) | LT | INTAKE_ONLY |
| Information technology | [HCL Technologies](../Companies/HCLTECH/COMPANY.md) | HCLTECH | INTAKE_ONLY |
| Information technology | [Infosys](../Companies/INFY/COMPANY.md) | INFY | INTAKE_ONLY |
| Information technology | [Tata Consultancy Services](../Companies/TCS/COMPANY.md) | TCS | INTAKE_ONLY |
| Information technology | [Tech Mahindra](../Companies/TECHM/COMPANY.md) | TECHM | INTAKE_ONLY |
| Materials | [Grasim Industries](../Companies/GRASIM/COMPANY.md) | GRASIM | INTAKE_ONLY |
| Materials | [Hindalco Industries](../Companies/HINDALCO/COMPANY.md) | HINDALCO | INTAKE_ONLY |
| Materials | [JSW Steel](../Companies/JSWSTEEL/COMPANY.md) | JSWSTEEL | INTAKE_ONLY |
| Materials | [Tata Steel](../Companies/TATASTEEL/COMPANY.md) | TATASTEEL | INTAKE_ONLY |
| Materials | [UltraTech Cement](../Companies/ULTRACEMCO/COMPANY.md) | ULTRACEMCO | INTAKE_ONLY |
| Telecommunications | [Bharti Airtel](../Companies/BHARTIARTL/COMPANY.md) | BHARTIARTL | INTAKE_ONLY |
| Transport and logistics | [Adani Ports and Special Economic Zone](../Companies/ADANIPORTS/COMPANY.md) | ADANIPORTS | INTAKE_ONLY |
| Transport and logistics | [InterGlobe Aviation](../Companies/INDIGO/COMPANY.md) | INDIGO | INTAKE_ONLY |
| Utilities | [NTPC](../Companies/NTPC/COMPANY.md) | NTPC | INTAKE_ONLY |
| Utilities | [Power Grid Corporation of India](../Companies/POWERGRID/COMPANY.md) | POWERGRID | INTAKE_ONLY |

## Update order and acceptance

1. Resolve reviewed issuer/ISIN mappings and historical effective dates from
   permitted evidence. Preserve the observed snapshot and record future
   membership differences, additions or exits; do not overwrite history.
2. Reuse the existing four company pilots, then work sector by sector. Shared
   definitions and macro/sector evidence are collected once, not per company.
3. Acquire each issuer's latest and comparable primary filings. Use public
   aggregators to locate prepared tables and documents, within actual terms;
   prefer a supported export or feed to rebuilding the provider's database.
4. Register actual bytes/dates, review identity and material claims, and write
   only the incremental financial/thesis/model changes.
5. Complete the most-likely path, independent debates, three-leg thesis,
   reproducible valuation and review gates before assigning ranking or bands.

All company folders have the required sections. A populated folder is not a
completed analysis: `INTAKE_ONLY` means financial data and underwriting are
still missing. Existing four-company research is preserved, not revalidated.

The earlier [14-company validation cohort](../Framework/UNIVERSE_14.md) stays
separate. Its Divi's Laboratories, ABB India and Ambuja Cements are absent
from the observed official set; this does not establish historical exit dates. Preserve the validation design and research rather than silently
turning those names into Nifty constituents or deleting them.

## Checkpoint validation

The register has 50 distinct aliases, company paths and observed discovery
links, assigned to 13 research sectors. All 50 folders contain company, thesis,
earnings, valuation, model and source sections. The four prior canonical paths
were preserved. Local-link checks cover this task's Markdown files; sector totals reconcile to 50. No runtime, test, workbook,
database or existing company thesis was changed. These checks validate coverage
organization and the observed symbol-set match, not financial evidence or
historical index membership.

The cloud draft now includes the official index destinations, candidate issuer
homepage domains and ICICI Bank's observed redirect destination, plus startup
instructions pointing to this queue. Review/save the changes in environment
settings and publish the environment. Draft persistence is confirmed; the
machine reconnected during the task. The official CSV and TCS homepage became
reachable on retry. A separate one-request-per-homepage discovery pass checked
all 50 primary-route candidates; see the source-route observation register.
No current company financial filing was acquired as part of that route check.
Publication or a successful fresh-task restore has not been established.
