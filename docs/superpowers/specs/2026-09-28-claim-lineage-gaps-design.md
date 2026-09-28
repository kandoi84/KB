# Claim lineage and gap evaluation design

## Goal

Make every supplied research claim point to an exact source version and expose
missing or unverified support as a frozen, structured gap. This is an evidence
control, not a truth judgment or publication approval.

## Input and output

`evaluate-claims` takes a claim request, a frozen source-readiness report,
project directory, state directory, and run ID. The request contains one
`entity`, the same timezone-aware `cutoff_timestamp` as the source report,
and a nonempty `claims` list. Each claim has `claim_id`, `claim_type`,
`statement`, `as_of` date, `source_id`, `version_id`, and a nonempty
`passage_locator` (for example a page and table name). Claim IDs are unique
within a request. A source may belong to a shared macro or sector entity.

For every claim, check that the source report is intact and current, that its
selected version matches the claim, that the register record and raw hash are
intact, and that `as_of` is no later than the information cutoff. The result
records `LINEAGE_LINKED`, `SOURCE_NOT_READY`, `VERSION_MISMATCH`,
`INVALID_SOURCE`, `AFTER_CUTOFF`, or `NEEDS_DERIVATION`. Direct source types
are `REPORTED_FACT`, `MANAGEMENT_GUIDANCE`, `CONSENSUS`, `MARKET_DATA`, and
`SENTIMENT`. `DERIVED`, `ANALYST_ASSUMPTION`, `INFERENCE`, and `UNKNOWN`
always need a later calculation or judgment contract; they cannot pass as a
direct source quote.

A linked claim remains `passage_status: UNVERIFIED`. A locator is only a
pointer; the runtime does not extract or compare the passage or decide whether
it supports the statement. Every non-approved claim produces an `OPEN` gap
with claim ID, reason, resolution type, web resolvability, preferred and
fallback source, last attempt, and unresolved reason. Use `INTERNAL_RESEARCH`
for a linked claim needing passage review; use `UNCLASSIFIED` for missing or
damaged lineage. No automatic web fetch occurs from this classification.
The overall status is `CLAIMS_BLOCKED`; this slice has no approval path.

Freeze the report, including its gaps, under ignored
`state/claim_runs/<run_id>.json`. Reusing a run ID with the same claim request
and same source report returns the frozen result. Changed inputs require a new
run ID. Include hashes of both inputs and of the report. Tampered reports
fail closed.

## Guardrails and limits

- Reject malformed requests, duplicate claim IDs, unsafe IDs, invalid dates,
  and mismatched entity or cutoff before writing a report.
- Never treat a source report as proof of a claim. `LINEAGE_LINKED` means only
  that exact evidence bytes can be found.
- A source report with missing or stale files cannot support a claim.
- A new source version does not silently rewrite an old claim evaluation.
- Do not alter `company-research` or weaken its real publication block.
- Passage verification, contradiction handling, calculations, rights checks,
  and gap resolution are later contracts. Until then no real claim is approved.
