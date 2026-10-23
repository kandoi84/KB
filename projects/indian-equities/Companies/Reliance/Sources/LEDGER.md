# Reliance — recovered workbook source references

Inventory date: 23 October 2026. The existing SOTP workbook was inspected
read-only; its financial inputs, formulas, thesis and fair values were unchanged.

[WORKBOOK_SOURCE_INDEX.csv](WORKBOOK_SOURCE_INDEX.csv) recovers the ten rows
already stored in the workbook's `Sources` sheet, including their exact URL
and cell. This avoids searching for the same baseline documents again.
`workbook_as_of_label` and `workbook_source_posture` are the workbook's labels,
not newly verified source dates or evidence approvals. Every row is marked
`URL_RECOVERED_UNFETCHED`; retrieval time and raw hash remain empty.

## Reuse first

- FY26 financial review and the analyst meeting deck: existing segment baseline.
- Annual-report consolidated PDF: existing shares/balance-sheet provenance.
- Retail disclosure and BRSR links: existing ownership references to recheck.
- Events/presentations pages: discovery indexes; replace an index citation with
  an exact document and page before relying on a number.
- Investing.com/Digrin: historical price references already in the workbook,
  not verified official exchange prices. Do not relabel them current.

The workbook also links its Retail sheet to the FY26 retail review and its
Media sheet to an events index. New Energy has no URL cell in the inspected
sheet. Review the provenance of its valuation assumptions before changing them.

## Acquire and reconcile next

Retrieve permitted copies of the linked primary documents, capture actual
source/retrieval dates and hashes, and verify each load-bearing input with
physical page references. Establish the fiscal-period meaning of the stored
`2Q26 preview` label before comparing it with later results. Capture new segment
actuals only once, then update the affected DCF inputs and record the valuation
bridge required by `MASTER.md`.

Use the [public-source catalog](../../../research/PUBLIC_SOURCE_CATALOG.md)
for prepared tables/news discovery and the
[incremental workflow](../../../research/INCREMENTAL_RESEARCH.md) for changes.
Recovered URLs are not registered source versions and do not close evidence,
rights, freshness or publication gaps. Network access to these documents has
not been established in this update.

## 23 October 2026 — homepage route observation

Request: [https://www.ril.com/](https://www.ril.com/); observed `2026-10-23T09:37:15+00:00`.
Outcome: `HOMEPAGE_REACHABLE`; HTTP status: `200`.
Selected discovery link: [Investor Relations](https://www.ril.com/investors/investor-relations); linked from the fetched homepage, not yet retrieved.
No financial values were extracted. Access is not rights approval or issuer-identity review.
See the [route register](../../../research/PRIMARY_SOURCE_ROUTES_2026-10-23.csv).
