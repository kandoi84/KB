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

## Connectivity observations

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

Once network settings are applied, first inspect the selected site's terms
and a single relevant page. Record whether permitted manual reading, an export,
RSS or a documented API is the suitable route. Prefer an official export or
feed when supported; automated harvesting is not the default.
