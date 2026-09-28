# Source refresh and evaluation design

## Intent

Turn the source register into a repeatable update loop. A refresh request lists
the source IDs needed for a research task, how old each may be, and one
timezone-aware cutoff. The runtime checks registered versions and writes a
frozen source-readiness evaluation. The result is evidence status, not an
investment conclusion or permission to publish.

## Input and result

The request is JSON with entity, cutoff_timestamp, and required_sources. Each
required source has source_id and max_age_days. The request may name shared
macro or sector sources, so source entity need not equal the research entity.
The evaluation selects the latest source version retrieved by the cutoff.
It checks version hashes, raw availability and raw SHA-256, source date,
retrieval cutoff, and age in calendar days. It reports per-source status:
CURRENT, MISSING, AFTER_CUTOFF, MISSING_RAW, CORRUPT_RAW, STALE, or
INVALID_REGISTRY. The overall result is SOURCE_READY only when every source
is CURRENT; otherwise it is SOURCE_BLOCKED. It never fetches or guesses data.

The CLI accepts a request path, run ID, project directory, and state directory.
It stores the report under ignored state/refresh_runs/<run_id>.json. Existing
run IDs are immutable: the same request returns the original report; a changed
request is rejected. After recording a new source, use a new run ID to get a
new evaluation. Reports include exact version IDs and reasons for every gap.

## Boundaries

Source readiness does not validate individual claims, permissions, conflicts,
analysis, or model scores. Real research publication remains blocked. Later
slices connect explicit evidence gaps, claim lineage, research refreshes, and
outcome-based evals to this report.
