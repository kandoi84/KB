# Outcome and postmortem design (mini spec 10)

## Purpose and boundary

Append later, source-backed operating observations to a frozen mini-spec 09
case. When its evaluation is due, record a human process review and derive
the target result without editing the case. This is a sandbox learning loop,
not a return study, a ranking result, an autonomous framework change, or a
research publication. Mini specs 11 and 12 own change promotion and historical
evaluation. Every receipt retains `publication_allowed: false`,
`live_decision_allowed: false`, and `promotion_status: NOT_EVALUATED`.

The first outcome is the case's named operating metric. Stock/benchmark
returns, quality trajectory, multiple changes, catalyst probability
calibration, and portfolio decisions require separate sourced contracts.
`RESULT_MET` means only that this case's falsifiable metric target was met;
it does not mean the investment made money or that the thesis was sound.

## Reuse and chosen storage

Reuse mini-spec 09's immutable `state_dir/cases/<case_id>.json` case and
digest, `metric_store.query_metrics` with its strict live cutoff and source
rights checks, source version/raw hash validation, and the repository's
temporary-file, fsync, link-once JSON pattern. Python 3.14's maintained
[`hashlib`](https://docs.python.org/3.14/library/hashlib.html),
[`tempfile`](https://docs.python.org/3.14/library/tempfile.html), and
[`os.link`](https://docs.python.org/3.14/library/os.html#os.link) are
sufficient; they carry the [PSF License Version
2](https://docs.python.org/3.14/license.html). We also checked the
maintained [`sqlite3` module](https://docs.python.org/3.14/library/sqlite3.html)
for transactional event storage. Its single-file database would add an
unneeded second authority beside the existing immutable case/report files.
No third-party code or new dependency is needed. New code handles only the
case-to-outcome join and postmortem contract missing from those components.

Use one immutable JSON file per event at
`state_dir/case_events/<case_id>/<event_id>.json`, and one immutable
postmortem at `state_dir/postmortems/<postmortem_id>.json`. An event ID is a
caller-supplied safe ID and its canonical digest covers the full payload.
The same ID and identical bytes replay as a no-op after revalidation;
different content fails. A revision or correction gets a new event ID with
`supersedes_event_id`; the old event remains readable. Do not silently select
the newest event. A postmortem pins one observation event, or explicitly
records that observation is pending.

## Observation contract

The input packet is strict JSON with `event_id`, `case_id`,
`case_digest`, `event_type: OUTCOME_OBSERVED`, `metric_id`,
`observed_at`, `recorded_at`, and optional `supersedes_event_id`. Timestamps
are timezone-aware analyst declarations; `recorded_at >= observed_at`.
The case must exist, have a valid digest, and be `SANDBOX_OPEN`. It must
still say all three safety fields above. Read it from the expected case path;
do not accept arbitrary parent paths or a rehashed replacement of a case
whose 09 inputs no longer replay. The 09 parent validator must recheck its
exact input bindings, raw source, review, model, and cutoff before an outcome
is appended. If 09 cannot expose this replay verification, add it there as a
prerequisite rather than trusting the case digest alone.

`query_metrics(catalog, project_dir, isin, metric_name, period_end,
observed_at)` must return the exact selected `metric_id` as one unambiguous
live-strict leaf. Match case ISIN, metric name, unit, and period end exactly;
accept `value_kind: REPORTED` only for an actual outcome. Guidance cannot
stand in for an actual. The selected metric carries `filing_id`,
`source_id`, `version_id`, evidence locator, published/first-seen/reviewed
times, and typed decimal. Freeze that full citation, source raw SHA-256,
`value_decimal`, `period_kind`, and `reporting_scope` in the event. Validate
source and identity through the existing store. All source, filing, review,
and metric availability must be at or before `observed_at`; the case cutoff
must be earlier than `observed_at`, and the outcome period must be after the
case cutoff. A later revision cannot change this event: strict replay uses
the event's original observation cutoff and metric ID. A new metric revision
creates a new observation event.

These rules prove only local consistency of reviewed source bytes and
declared times. They do not authenticate when the analyst first saw the
source. An outcome observed after its due date remains valid and is marked
`LATE_OBSERVATION`; it must not be backdated to create apparent timeliness.
An observation on a `HISTORICAL_RECONSTRUCTION` case retains that label and
cannot count as a prospective forecast in 12.

## Due evaluation and human process review

The due command receives a strict packet with `postmortem_id`, `case_id`,
`case_digest`, `due_event_id`, `evaluated_at`, optional
`observation_event_id`, and an optional process review object. It requires
`evaluated_at >= case.outcome.due_at`; before then it fails. The due event
and postmortem are idempotent immutable receipts, not a scheduler promise.
If no qualifying observed metric exists, the postmortem is
`AWAITING_OBSERVATION`; no result or process/result quadrant is invented.
If an observation exists but no completed human review exists, it is
`AWAITING_PROCESS_REVIEW`. A pending receipt can be followed by a new
postmortem ID; its prior state is never overwritten.

The human review names `reviewer_id`, `reviewed_at`,
`process_assessment: GOOD_PROCESS|BAD_PROCESS`, a concise reasoning note,
and cited frozen case/claim/metric/gap IDs. It assesses decision method at
the *inception cutoff*, not whether the later metric was favorable. The
reviewer selects one `error_class` from `THESIS_ERROR`,
`PROBABILITY_ERROR`, `VALUATION_ERROR`, `TIMING_ERROR`, `DATA_ERROR`,
`SOURCE_ERROR`, `MACRO_REGIME_ERROR`, `CATALYST_ERROR`,
`MISSING_INFORMATION`, `PROCESS_VIOLATION`, `MODEL_ERROR`,
`UNAVOIDABLE_SURPRISE`, or `NONE`, with a short explanation. The packet
also records `reproducible_process_failure: true|false` and a concrete
`failure_invariant` only when true. `BAD_PROCESS` requires an error class
other than `NONE` or `UNAVOIDABLE_SURPRISE`. `GOOD_PROCESS` permits only
`NONE` or `UNAVOIDABLE_SURPRISE` and cannot have a reproducible process
failure. `UNAVOIDABLE_SURPRISE` requires `RESULT_MISSED`. Human disagreement creates a new
review/postmortem ID; it cannot rewrite an earlier judgment.

Result is mechanical: compare the sourced `Decimal(value_decimal)` with the
case's frozen `target_decimal` using `AT_LEAST` or `AT_MOST`, producing
`RESULT_MET` or `RESULT_MISSED`. No float conversion. A completed review
and observed result produce exactly one of the four required quadrants:
`GOOD_PROCESS_GOOD_RESULT`, `GOOD_PROCESS_BAD_RESULT`,
`BAD_PROCESS_GOOD_RESULT`, or `BAD_PROCESS_BAD_RESULT`. Here “good result”
means target met only. The selected observation, comparison, source
citation, human reviewer, rationale, error class, and receipt digest are
frozen together. The system must not infer process quality or error class
from a target hit/miss.

## Reproducible error to eval candidate

A completed postmortem with `BAD_PROCESS`, a named error other than
`NONE`/`UNAVOIDABLE_SURPRISE`, `reproducible_process_failure: true`, and a
specific `failure_invariant` writes a companion immutable
`state_dir/eval_candidates/<postmortem_id>.json`. It binds the frozen
case/postmortem digests, inception cutoff, cited decision inputs, error
class, and the expected invariant. It excludes the later outcome from the
candidate's decision input and marks `candidate_status: UNREVIEWED`.
No prompt, schema, score, active version, or production rule changes here.
Good-process misses, luck, and unavoidable surprises record the outcome
without a forced eval or framework change. Mini spec 11 may review a
candidate; 12 may test it. This candidate is not a passing benchmark.

## Failure and acceptance

Fail closed on unknown fields, unsafe IDs or paths, damaged case/parent,
changed same-ID payload, missing/ambiguous metric, mismatch in metric
identity/series, guidance masquerading as reported outcome, absent rights,
source bytes changed, look-ahead, due-before-deadline, and a fabricated
process label. No failed operation may leave a success receipt. Atomic
create handles two concurrent writers, including the postmortem/candidate
pair through an explicit retry-safe two-phase state: never report a
completed postmortem until its required candidate exists and matches.

Synthetic tests prove valid observation, exact retry, conflicting retry,
later source revision preserving old observation, late observation label,
wrong ISIN/period/unit/value-kind rejection, damaged raw/case rejection,
due timing, pending states, all four quadrants, taxonomy constraints,
candidate creation/retry, and permanent safety flags. Real source samples
are needed before any empirical quality claim. A local digest is not an
independent timestamp or authorship proof.
