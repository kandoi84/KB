# Indian equities desk rules

- Read `MASTER.md` before substantive company research. Read the relevant company `COMPANY.md`, latest `Thesis.md`, and model before changing a thesis or fair value.
- Use the source hierarchy and labels in `MASTER.md`. Every load bearing number needs a source URL or local document reference, source date, observation date, and calculation or assumption label. Mark missing or stale data plainly.
- Prefer company and exchange filings. Use `GOVERNANCE/SOURCE_POLICY.md`, `GOVERNANCE/FRESHNESS_POLICY.md`, and `Framework/data/SOURCE_POLICY.md` for ingestion and freshness decisions.
- Use the free first catalog in `../../../resources` (the sibling `~/code/resources` project). A public website is not automatically an API or a license to scrape.
- Treat a price as a time stamped observation. Do not invent live prices, consensus, guidance, financials, or probabilities.
- Preserve the most likely path, independent debates, valuation history, three leg thesis, and poker scoring required by `MASTER.md`. Explain any material change.
- Do not publish a real company result from the synthetic runtime. Require source validation and the project promotion gate first.
- For personal research, keep broker credentials, API keys, and account statements outside Git. Ask before publishing or sharing research externally.
