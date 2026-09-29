# Snapshot / Look-Ahead Policy

Historical evaluation must use information available as of the snapshot timestamp only.

## Requirements
- Freeze prices at snapshot close.
- Freeze consensus using the version available on that date.
- Freeze filings/transcripts by publication timestamp.
- Do not backfill revised financials into historical snapshots unless explicitly labelled restated.
- Store model version and assumptions version.
- Record missing data instead of filling with future-known values.

Any violation invalidates the backtest observation.
