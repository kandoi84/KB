# Evidence refresh run design

## Goal

Execute source readiness and claim lineage as one resumable evidence refresh.
The run exposes source version changes and claim recheck needs. It does not
publish research or resolve gaps.

## Contract

`refresh-evidence` accepts a source request, a claim request, project and
state directories, one run ID, and optionally a previous evidence run ID.
The two requests must have the same entity and exact cutoff timestamp.
Use the existing `evaluate_sources` and `evaluate_claims` operations with the
same run ID; each already freezes its result and rejects changed inputs.
Write one immutable manifest under ignored `state/evidence_runs/<run_id>.json`
after both succeed. If interrupted between steps, rerunning the same ID
resumes through the frozen source result. A changed request cannot silently
reuse the ID.

The manifest records both report IDs and statuses, a source change list, a
claim impact list, open gap IDs, and `publication_allowed: false`. With a previous run,
validate its manifest and reports, require the same entity and a nondecreasing
cutoff, and compare selected versions and statuses. On the first run, a source
is `INITIAL` or `BLOCKED` and a claim is `INITIAL`. On later runs, a source is
`UNCHANGED`, `UPDATED`, `NEW`, `REMOVED`, or `BLOCKED`. A claim is
`UNCHANGED`, `RECHECK_SOURCE`, `BLOCKED_GAP`, or `REMOVED`. Any claim with a nonlinked
lineage result or a changed source needs review. All passage gaps remain
open; no status here can promote a claim.

## Guardrails

- Preserve exact frozen reports and previous manifests. Never mutate them.
- Reject missing, tampered, mismatched, or future previous runs.
- A removed required source is a blocked change, not evidence that it became
  irrelevant.
- Compare the recorded selected version, not just dates or file names.
- Keep the real company publication gate unchanged.
- No automatic fetch, passage approval, investment analysis, or methodology
  change is part of this run.
