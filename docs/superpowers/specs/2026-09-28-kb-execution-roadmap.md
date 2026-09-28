# KB execution roadmap

Date: 2026-09-28

## Current status

The repository at `~/code/kb` is the master KB. Indian Equities lives under
`projects/indian-equities/`; older copies are provenance, not competing
working trees. The Claude architecture handoff is a review brief, not a
completed implementation or evaluation.

| Contract | Runtime state | Evidence |
| --- | --- | --- |
| Immutable source updates | Active for local files | `record-source` stores raw hashes and version records |
| Source freshness at a cutoff | Active for explicit requests | `evaluate-sources` freezes a report per run ID |
| Claim to passage lineage | Specification only | Claim maps are empty; no passage validator runs |
| Research workflow | Synthetic execution only | `company-research` persists steps and rejects real inputs |
| Case Book creation | Synthetic execution only | A test run opens a frozen inception case |
| Outcome observation and postmortems | Missing | No runtime trigger or outcome adapter |
| Historical and calibration evals | Specification only | `Framework/evals/EVAL_PLAN.md` defines targets |
| Research skill or agent activation | Specification only | Agent contracts exist without runtime dispatch |
| Git delivery hook | Advisory | The Stop hook requests review, commit and push; it never does Git writes |

## Scope and order

1. **Source storage and update rules — complete.** Register every raw
   observation under a stable source ID, keep its content hash and metadata
   version, and reject edits or identity conflicts.
2. **Source refresh and first evaluation — complete.** A request names its
   cutoff and maximum source ages. The report pins version IDs and says why
   any source is blocked. A new run ID is required after an update. This is
   source readiness only.
3. **Claim contract and gap ledger.** Define one typed claim record with exact
   source version, passage locator, date, and calculation or assumption
   lineage. Check links and mark unverified passages plainly. Turn missing,
   conflicting, or stale evidence into structured gaps with resolution type,
   preferred source, attempt time, and unresolved reason. Accept only when a
   test claim can be traced to immutable raw evidence and a gap cannot be
   silently filled with narrative.
4. **Refresh orchestration.** Compare two frozen source reports and determine
   which claims and derived views need rechecking. Run only the affected
   steps; persist a manifest and retry state. Accept when a source update
   triggers a new evaluation, preserves the old one, and blocks downstream
   publication on unresolved gaps. Fetch adapters come later and must obey
   source rights and the free first catalog.
5. **Research integrity gate.** Validate claim type, passage, cutoff, source
   rights, contradictions, calculations, score inputs, and provenance before
   any real research can publish. Keep the existing real publication block
   until these checks and the project promotion gate actually pass.
6. **Outcome and learning loop.** Append dated observations to frozen cases;
   trigger postmortems when due; classify process versus result; create eval
   cases only for reproducible errors. Keep methodology changes as proposals
   with regression results and human approval for structural changes.
7. **Historical evaluation and promotion.** Build point in time snapshots,
   compare with the baselines in `Framework/evals/EVAL_PLAN.md`, test
   repeatability, look ahead, ranking and calibration, then apply the stated
   sample and performance gates. A source readiness report is not a passing
   investment evaluation.

## Hook and skill boundary

Hooks can remind the agent to finish delivery; they cannot identify which
files belong to a task or safely commit them. Add hook behavior only for an
observed failure with a focused fixture and a real activation check. The
separate Codex efficiency design covers global hook setup. Research agent
YAML or a skill file counts as activated only when a runtime entry point
loads its contract, checks its required inputs and outputs, records execution
in a manifest, and blocks dependent work on failure.

## Delivery rule

Implement one bounded vertical slice at a time. For each slice, write the
input and output contract, exercise the blocked and successful paths, inspect
the changed files, commit only owned work, and push the feature branch. Report
the exact remaining gates after each slice. Do not label the overall learning
loop active until the handoff's case, outcome, postmortem, eval, and change
proposal acceptance tests pass end to end.
