# Integrity, snapshot, and sandbox case design (mini spec 09)

## Purpose and boundary

Freeze a testable research decision only after the evidence workflow and the
internal analysis worksheet agree on one issuer, ISIN, and information cutoff.
The resulting case is a sandbox artifact for later outcome and postmortem work.
It is neither a published recommendation nor a validated fair value. Every
result has `publication_allowed: false`, `live_decision_allowed: false`, and
`promotion_status: NOT_EVALUATED`. Mini spec 12 owns historical evaluation and
separate promotion; this command cannot enable publication.

## Chosen design

Use a strict case packet and a deterministic validator. The validator replays
the existing 06 evidence workflow and 08 analysis against their exact inputs,
then freezes a small case receipt. Replaying the parents is necessary: their
JSON digests alone are local checksums, and rehashing a forged parent must not
turn unsupported material into a case. A direct free-form snapshot or a scoring
engine would create conclusions the current sources and models do not support.

### Reuse check

The installed Python is 3.14.6. Its maintained standard library supplies
[`hashlib`](https://docs.python.org/3.14/library/hashlib.html),
[`tempfile`](https://docs.python.org/3.14/library/tempfile.html), and
[`os.link`](https://docs.python.org/3.14/library/os.html#os.link) for digests and
link-once storage; Python carries the [PSF License Version
2](https://docs.python.org/3.14/license.html). Reuse the repository's existing
`run_evidence_workflow`, `analyze_judgment`, strict timestamp/ID helpers, and
atomic JSON report pattern. New code is limited to the cross-artifact join and
case contract that those upstream and internal components do not provide. No
new package or copied third-party code is needed.

The command receives paths for the 06 source request, claim request, passage
packet, review packet, pinned workflow contract, 05 review report, 08 analyst
packet, and 08 analysis report. The case packet binds their exact file-byte
SHA-256 hashes, plus `workflow_run_id`,
`analysis_run_id`, `issuer_id`, `isin`, `cutoff_timestamp`, `case_id`,
`mode: SANDBOX`, and a timezone-aware `opened_at`. All referenced report paths must
be under their expected `state_dir` subfolders and their basenames must match
safe run IDs. CLI input paths are trusted caller choices; the packet binds
their exact file-byte hashes, so a path substitution fails unless it supplies
the identical bytes.

The existing 06 workflow and 08 analysis files must exist before validation;
case opening may only replay them, never initiate an unfinished parent. The
06 workflow must be `COMPLETE` and have all three stages complete, with
the review stage's exact child ID equal to the 05 report ID used by 08. The
review report, 08 packet, 08 report, and workflow state must have identical
issuer/entity and cutoff. The 08 worksheet must be
`CALCULATED_MODEL_UNVERIFIED`, have no evidence gaps, and retain its explicit
`MODEL_UNVERIFIED` and `HUMAN_REVIEW_REQUIRED` labels. A blocked worksheet
cannot open a case. The validator requires the supplied 08 packet to equal
the report's frozen `worksheet`, then replays `analyze_judgment` with that
packet under its existing run ID and compares the entire report. This rechecks
the model file, current raw bytes,
reviewed claims, typed metric leaves, strict cutoff, and arithmetic. A changed
parent, later metric revision, stale source, or mixed cutoff blocks before a
case file is written.

## Case content

The analyst supplies one concise, falsifiable hypothesis, a named outcome metric, unit, comparison
(`AT_LEAST` or `AT_MOST`), plain-decimal target, future `period_end`, and
timezone-aware `due_at` after the cutoff. The target is explicitly
`ANALYST_HYPOTHESIS`; it is not a reported metric. The due date must be on or
after the outcome period end. A case may list existing 08
claim and metric IDs as its rationale, but no new numeric evidence or claims.
Free text cannot contain digits, matching the 08 syntactic guard. At least one
08 citation is required. The case stores no price, order, position size,
portfolio action, score, evidence grade, conviction, or stance. An optional
`poker` field is accepted only as `{status: NOT_ASSESSED, hand: null, draw:
null}`; any label or implied score is rejected. This makes the invalid-label
guard explicit while no scoring engine exists.

The frozen case contains parent IDs and hashes, the exact cutoff, the
prediction contract, the analysis fair value as a labelled *unverified analyst
estimate*, the range from `analysis_report.worksheet.valuation_range`,
`opened_at`, a canonical case digest, and the safety
fields above. It lives at `state_dir/cases/<case_id>.json`. Creating a second
case with the same ID and different inputs fails. Exact replay rechecks all
parents and returns the same bytes. A revised decision uses a new case ID and
an optional previous-case ID; it never edits an old case. An earlier case does
not inherit a later source or metric revision.

The receipt uses `case_status: SANDBOX_OPEN` for a valid case and a separate
`timing_class: HISTORICAL_RECONSTRUCTION|ANALYST_DECLARED_PROSPECTIVE` field.
The latter is a clock disclosure, not an evidence grade or permission to trade.

## Time and trust rules

The analysis cutoff equals the workflow cutoff and the case cutoff. The
model's as-of time, reviewer time, metric filing availability, source
publication/arrival, and packet preparation must all have passed their
upstream strict checks at that cutoff. `opened_at` is the analyst-declared
opening time and cannot precede cutoff. A historical cutoff opened later is
marked `HISTORICAL_RECONSTRUCTION` when the calendar dates differ; it cannot
count as a prospective prediction in
mini spec 12 without an independent pre-outcome timestamp receipt. A local
clock and SHA-256 do not prove authorship or when the analyst first formed a
view. The case does not resolve model-formula correctness, analyst bias,
licensing beyond the 05 local-use decision, full-corpus contradiction search,
or valuation calibration. A same-day cutoff remains only an analyst-declared
prospective case until an independent time receipt is available.

## Failure and acceptance

Malformed packet, wrong root/path, changed input binding, corrupt parent,
mixed identity/cutoff, missing workflow stage, blocked evidence or analysis,
invalid prediction, a poker label, and changed case replay fail closed before
writing a success case. An internal validation receipt may list machine-readable
reasons, but cannot contain a fair value or set publication true on failure.
Atomic create plus link-once preserves old cases under concurrent calls.

Tests use synthetic inputs to prove valid opening, replays, tamper rejection,
look-ahead prevention, unsupported-claim rejection, duplicate-ID behavior,
and permanently false publication. The tests prove contract mechanics only.
