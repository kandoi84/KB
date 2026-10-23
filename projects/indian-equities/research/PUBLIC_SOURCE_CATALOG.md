# Reuse public research before collecting it again

Prepared 23 October 2026. This is a source-routing catalog, not an assertion
that every service, page or field is currently accessible or licensed for automation.

The KB's job is to retain evidence, reconcile definitions and track changes.
Use existing financial tables, document indexes and news coverage to find
answers quickly; build proprietary analysis only for the questions those
sources do not answer. Reuse does not require copying their full databases.

## Where to look first

| Source | Proposed use | What the KB should retain | Important limit |
|---|---|---|---|
| Company investor relations: [SBI](https://sbi.bank.in/), [HDFC Bank](https://www.hdfcbank.com/personal/about-us/investor-relations), [ICICI Bank](https://www.icicibank.com/about-us/invest-relations), [Reliance](https://www.ril.com/) | Reported results, annual reports, presentations, transcripts, management guidance | Permitted original filing, exact URL/date/hash and cited pages | Confirm document scope and date; a homepage is not a filing citation |
| [Value Research](https://www.valueresearchonline.com/stocks/) | Candidate starting point for company background, financial history and valuation context | Links, permitted observations, dates and definitions; our own short interpretation | Current stock coverage, field availability, free/paid boundary and reuse terms need verification; ratings are provider opinions |
| [Economic Times Markets](https://economictimes.indiatimes.com/markets/stocks/stock-quotes) | Candidate stock-page summaries, results/news discovery and event context | Article/stock-page URL, publication and observation dates, brief relevant observations | News may be syndicated; publication time differs from filing time. Paywalled content needs access; no assumed bulk-data rights |
| [Screener](https://www.screener.in/) | Candidate financial-table and filing-link discovery; user-authorized exports where available | Permitted export or observed table plus units, scope, adjustment notes and underlying filing link | Export availability and permissions need checking; consolidated/standalone and restatement treatment may differ |
| [BSE](https://www.bseindia.com/) / [NSE](https://www.nseindia.com/) | Issuer/security identity, announcements and official market data | Specific permitted filing/security record and dated observation | No automated website collection without reviewed endpoint rights; public availability is not permission |
| [RBI](https://www.rbi.org.in/) | Shared banking and macro inputs: credit, deposits, liquidity, asset quality and capital | One shared dated evidence series, reused by all bank reports | Reference period, release date and observation date must remain distinct |

These are routing choices, not vendor endorsements or a claim that a supported
public API exists. Do not install another wrapper merely to bypass a denied
site. The existing `bfinance` experiment is not an approved data contract:
its fallback identities and inferred filing dates are unsuitable for reviewed research.

## Suggested order for a question

1. Search the existing company ledger, shared sector notes and registered sources.
2. Check a public aggregator for the already-prepared table or filing link.
3. Verify each material new number against the company/exchange document when
   available. If only a secondary source exists, keep that label and the gap.
4. Store only permitted evidence needed for this question; link to the full
   article or provider page rather than reproducing it unnecessarily.
5. Write the incremental implication: what changed, why it matters, which
   assumption or thesis is affected, and what remains uncertain.

Two websites displaying the same upstream feed are not independent confirmation.
Do not mix bank standalone profit with consolidated equity, different NIM
denominators, split-adjusted prices or different share counts without a bridge.
Do not treat an aggregator's rating or news headline as a reported company fact.

## Connectivity and reuse observations

On 23 October, direct checks to Value Research, ET's stock-quotes landing page,
HDFC Bank IR and ICICI Bank IR failed at the configured proxy. Curl confirmed
`CONNECT tunnel failed, response 403` for Value Research. This does not establish
that the publishers themselves rejected requests or that their pages are gone.
The research-domain additions were saved to the cloud configuration draft;
the running instance has not been shown to receive those changes.

Screener, RBI, exchange sites, Reliance and individual company pages beyond
the listed checks are candidate routes, not successfully retrieved sources.
Rights, login requirements, exact document URLs and field coverage remain
unverified. No fresh financial claim was created from these access checks.

In the subsequent Nifty coverage task on the same date, Screener, Value Research
and ET returned successful pages. This supersedes their earlier connectivity
failures, but does not prove that every endpoint or issuer source is reachable.
The official Nifty constituent CSV still failed at the proxy. See the
[dated discovery register](NIFTY50_COVERAGE.md); no official membership approval
or bulk financial-data acquisition was inferred from that secondary observation.

[Screener's terms](https://www.screener.in/guides/terms/), read on 23 October,
limit the service license to personal, non-commercial transitory viewing and
restrict copying/mirroring. Its robots file is not a replacement license.
Use it for permitted viewing and document discovery; do not import its tables
or assume a supported export is licensed for KB storage.

[ET's terms](https://economictimes.indiatimes.com/terms-conditions), also read
on 23 October, restrict aggregation/scraping/recreation/redistribution and
systematic database building. Use links and permitted personal reading; no
full-page archive, price feed, financial-table mirror or article corpus is
introduced by this task. The one-time constituent observation routes research
and still needs an official source; it is not an ET data-licensing agreement.
Value Research's landing page was reachable, but its data/export reuse terms
have not been confirmed. Do not activate a collection adapter on that basis.

An ICICI Bank request without following redirects confirmed HTTP 301 from
`www.icicibank.com` to `www.icici.bank.in`. Following it failed at the proxy;
the destination hostname was added to the draft. Candidate company homepage
domains for the Nifty coverage queue were also saved. Those are routing seeds,
not confirmation of page accessibility, ownership or retention rights.

After the cloud reconnected, the official Nifty CSV and terms page both
returned HTTP 200. Its 50 symbols match the coverage register; see the
[observation receipt](NIFTY50_OFFICIAL_OBSERVATION_2026-10-23.json).
The source does not supply a membership-effective date. Its terms restrict
copying and automated collection; no recurring index collector or redistributed
raw constituent/ISIN file was created.

The [50-company route check](PRIMARY_SOURCE_ROUTES_2026-10-23.csv) subsequently
found 28 reachable homepages and selected investor links on 21 of them. Other
responses included redirects, 403/406/503 and one proxy error. These are access
observations, not retained financial datasets, reviewed ownership or permission
to scrape. Read each ledger's dated status before retrying; old access failures
must not be treated as permanent and an HTTP 200 is not a data-quality check.

For each route, record whether manual reading, an authorized export, RSS or a
documented API is suitable. Prefer an official export/feed when supported;
automated harvesting is not the default. Obtain provider permission where
retention or systematic reuse requires it, rather than rebuilding the provider.
