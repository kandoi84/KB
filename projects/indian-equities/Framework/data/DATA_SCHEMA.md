# Data Schema

Each company snapshot must contain immutable as-of data.

## Required identifiers
- issuer_id for company-level research
- ISIN for each traded security
- ticker as a dated exchange alias resolved for `snapshot_date`, not identity
- company_name
- sector
- industry
- snapshot_date
- fiscal_year_end

## Market data
- price
- market_cap
- enterprise_value
- shares_outstanding
- net_debt
- benchmark

## Historical valuation
At least 5 years preferred, 3 years minimum, with metric appropriate to sector.

## Earnings / consensus
- FY1/FY2 revenue, EBITDA, EBIT, EPS / sector-specific equivalents
- estimate dispersion
- revision history

## Fundamental quality
- revenue growth
- margins
- ROIC/ROE
- FCF conversion
- leverage
- capex intensity

## Fair value
- method
- central_fv
- low_fv
- high_fv
- model_date
- assumptions_version

## Provenance fields
Every load-bearing datapoint must include:
- value
- unit
- period
- source
- source_date
- retrieved_at
- source_type
- confidence

For point-in-time use, keep `period_end`, exchange `published_at`, and KB
`first_seen_at` separately. Append restatements as new versions. At a cutoff,
exclude data that was published or first seen later. The proposed issuer,
security, filing, chunk, and metric contracts are in
`docs/superpowers/specs/2026-09-28-structured-kb-extension.md`; they are not
yet live storage.
