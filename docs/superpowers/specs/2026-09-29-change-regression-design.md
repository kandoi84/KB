# Change proposals and regression design (mini spec 11)

## Purpose and boundary

Turn a reproducible mini-spec 10 process failure into a reviewable, versioned
proposal. Compare candidate and baseline on the same frozen regression set,
record what ran, and require explicit human approval for structural changes.
No proposal or regression receipt edits active production configuration.
Mini-spec 12 owns investment-quality evaluation and any later promotion gate.
The runtime still has no validated live publication or scoring engine, so
mini-spec 11 must not pretend that a passing synthetic test promotes one.

Prompt, weight, schema, and rule proposals can all be registered. A proposal
is *testable* only when a named, pinned adapter executes that exact artifact
against the exact baseline on the same cases. Unsupported change types remain
`BLOCKED_NO_EXECUTOR`; they do not receive an invented passing result.

## Reuse check and selected design

Reuse the repository's immutable JSON SHA-256 and link-once report pattern,
the 10 `eval_candidates/<postmortem_id>.json` contract, and
`retrieval_eval.evaluate_retrieval`'s dataset kind, rubric version, case
count, exact gold/corpus digests, and explicit `promotion_allowed: false`.
The latter is a useful *evidence format*, not an executor for prompt or
weight changes. The installed Python is 3.14.6; its maintained
[`hashlib`](https://docs.python.org/3.14/library/hashlib.html),
[`tempfile`](https://docs.python.org/3.14/library/tempfile.html), and
[`os.link`](https://docs.python.org/3.14/library/os.html#os.link) implement
content binding and immutable writes under the [PSF License Version
2](https://docs.python.org/3.14/license.html). Existing pytest 9.1.1
([official docs](https://docs.pytest.org/en/stable/), [MIT
license](https://github.com/pytest-dev/pytest/blob/main/LICENSE)) supplies
parametrized regression checks. No new package or copied upstream code is
needed. A generic experiment framework would expand the trusted surface
before any production scorer or real gold set exists.

Store a strict proposal at `state_dir/change_proposals/<proposal_id>.json`.
It pins `proposal_id`, author, created time, `change_type` (`PROMPT`,
`WEIGHT`, `SCHEMA`, `RULE`), `baseline_version`, `candidate_version`,
their content SHA-256 digests, the exact changed artifact bytes in a
content-addressed artifact store, rationale, affected contract IDs, and
zero or more 10 eval candidate IDs/digests. Versions are opaque safe IDs,
never floating names such as `latest`. A candidate ID must differ from the
baseline; same ID with changed bytes fails. Paths are resolved beneath the
expected project/state roots. `baseline_version` is the supplied local
artifact identity, not proof of what is deployed. No active-version registry
exists yet, so a proposal cannot assert that it has changed production.

## Regression contract

The frozen regression manifest contains `regression_set_id`, rubric version,
dataset kind (`SYNTHETIC_FIXTURE` or `REVIEWED_REAL`), at least 20 unique
cases for the initial prompt/config guard, case IDs, inception cutoffs,
expected invariants, and exact file/content hashes. Each candidate derived
from 10 must withhold its later outcome from decision inputs. An independent
reviewer must mark real gold and timestamps reviewed; synthetic cases can
test plumbing only. All cases must share the same rubric and dataset version.
Do not turn the current 04E retrieval gold into an investment regression
set: its 30–50 questions assess retrieval and citation, not ranking or
returns.

`run_change_regression` accepts a proposal, frozen manifest, and a registered
adapter ID. It must execute baseline and candidate in isolated, read-only
working state on *each same case*, in a fixed order or paired random order
recorded in the receipt. It binds runner source/version/hash, input digests,
candidate and baseline outputs, per-case pass/fail, explicit guardrail
violations, and counts. Arbitrary command strings, imports, network calls,
and generated Python from proposal data are forbidden. A runner must expose
the artifact injection point and prove it consumed the pinned bytes; otherwise
status is `BLOCKED_NO_EXECUTOR`. A run failure, changed input, missing case,
look-ahead, or invalid provenance yields `FAILED`/`BLOCKED`, never `PASSED`.
Replaying the same run ID with identical inputs returns the immutable receipt;
changed inputs fail. A baseline failure is reported separately and prevents
a candidate pass claim.

The minimum initial gate is 20/20 runnable cases, zero source/cutoff,
publication, and active-version guardrail violations, zero newly failed
hard cases, and no reduction in the named baseline metric or invariant.
Thresholds are pinned in the manifest and cannot be relaxed by the
candidate. A synthetic fixture may yield `MECHANICS_PASS`, never
`REGRESSION_PASS_FOR_REVIEW`. A reviewed real set may yield
`REGRESSION_PASS_FOR_REVIEW` only through a genuine registered adapter and
all gates; this still is not investment promotion. Missing reviewed real
gold, a working adapter, or active version proof remains explicit in the
receipt. The current retrieval evaluator has no candidate injection point,
so it cannot be presented as a genuine prompt/weight regression runner.

## Human approval and no activation

`WEIGHT` and `SCHEMA` changes are structural. Any rule that changes scoring,
source acceptance, rights, cutoff, publication, or safety is structural too.
When classification is uncertain, require structural approval. A `PROMPT`
change can also be structural when it changes decision instructions or an
output contract. Classification is determined from an allowlisted changed
contract path and reviewed diff, never just the proposer's claimed label.

An immutable approval receipt pins proposal and regression digests, exact
baseline/candidate hashes, reviewer identity, timezone-aware decision time,
`APPROVED|REJECTED`, scope, and rationale. The reviewer cannot be the
proposal author for structural changes. An approval before the regression
receipt, for a stale candidate, or for `MECHANICS_PASS` is invalid.
Approval means *eligible for later promotion review* only. This slice has
no activate command and never writes a production pointer, code file,
score weights, prompt, schema, or rule. Missing/failing regression or missing
approval keeps `approval_status: PENDING|BLOCKED` and the baseline in use.
Luck, `UNAVOIDABLE_SURPRISE`, and 10 candidates lacking reproducible process
failure cannot be used as a change trigger.

## Failure and acceptance

Unknown fields, unsafe IDs, path traversal, damaged or swapped artifacts,
forged 10 candidate/postmortem link, duplicate/mixed cases, later outcome in
decision input, and self-approved structural changes fail closed. Compare
the active configuration tree/hash before and after each operation in tests;
it must be byte-identical. Test exact retry, conflicting retry, missing
executor, baseline failure, changed runner code, synthetic-only mechanics,
real reviewed gate, stale approval, structural reviewer separation, and
luck no-proposal control. All receipts say `publication_allowed: false`,
`live_decision_allowed: false`, and `promotion_status: NOT_EVALUATED`.

The present blockers are substantive: 09/10 must land first; no executable
prompt/weight/scoring adapter or independently reviewed real regression set
exists. Implement the registry and fail-closed runner contract, but do not
claim a real passing regression or production learning until those inputs
exist. The 50-to-5 gate and empirical investment tests remain in 12.
