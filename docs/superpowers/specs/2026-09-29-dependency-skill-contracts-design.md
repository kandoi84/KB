# Dependency and skill contracts design (mini spec 06, first slice)

## Goal and scope

Make one evidence review workflow executable. A selected, versioned contract
must be loaded and validated before its named handler runs. The workflow
records what actually ran and blocks dependents when an artifact is missing or
invalid. This slice stops at the internal claim review from 05. It cannot
generate investment analysis, publish real research, or open a real Case Book
case.

The existing `config/workflow.yaml` lists a desired pipeline but no runtime
reads it. `src/kb_runtime/workflow.py` is a separate synthetic-fixture state
machine. The 21 `Agents/*/contract.yaml` files describe permissions and checks;
they do not identify a callable handler or typed artifact. Reading an `AGENT.md`
or listing a stage in YAML is not evidence that a skill executed.

## Executable contract

Add one workflow JSON contract at
`projects/indian-equities/config/runtime_contracts/evidence_review.v1.json`
and three separate versioned skill contracts in the same directory:
`evidence_refresh.v1.json`, `passage_presence.v1.json`, and
`claim_integrity_review.v1.json`. Use the Python standard library for parsing.
The workflow's top-level fields are exactly
`contract_id`, `version`, `workflow_id`, `stages`, and `publication_allowed`.
`contract_id` and `workflow_id` are nonempty strings, `version` is the integer
`1`, `stages` is a nonempty list, and `publication_allowed` is exactly `false`.
Version 1 admits only
`contract_id=indian_equities_evidence_review`, `version=1`, and
`workflow_id=evidence_review_v1`. Reject unknown fields and versions. Every
workflow stage has exactly these fields:

| Field | Meaning |
| --- | --- |
| `stage_id` | Stable unique name: `refresh`, `passages`, or `review`. |
| `skill_contract_path` | Path relative to `runtime_contracts/`, limited to the three fixed skill filenames above. |
| `skill_contract_sha256` | Lowercase SHA-256 of the exact skill file bytes. A changed or missing skill file blocks the workflow before any handler runs. |
| `depends_on` | Stage IDs that must have valid frozen output first. |

Each skill file has exactly `skill_id`, `version`, `handler`,
`required_inputs`, `output_type`, `entity_policy`, `cutoff_policy`,
`retry_policy`, and `publication_allowed`. The fixed policies are
`version=1`, `entity_policy=EXACT_RUN_ENTITY`,
`cutoff_policy=EXACT_RUN_CUTOFF`, `retry_policy=REPLAY_IDEMPOTENT`, and
`publication_allowed=false`. Its handler must be one of the three hardcoded
Python callables, never a dynamic import, shell command, or model-selected
code. The runner loads each referenced skill file, checks the exact byte
digest against the workflow, validates every field and the fixed stage to
skill/handler/input/output mapping, and only then may execute that handler.
Unknown fields, missing files, path traversal, symlinks outside the contract
directory, and duplicate skill identities fail before stage one.

The only valid first-slice graph is `refresh -> passages -> review`; `review`
also depends on `refresh` because it consumes the claim report directly.
The exact stage bindings are:

| `stage_id` | `skill_id` | `handler` | `depends_on` | `required_inputs` | `output_type` |
| --- | --- | --- | --- | --- | --- |
| `refresh` | `evidence_refresh` | `refresh_evidence` | `[]` | `source_request`, `claim_request` | `evidence_manifest` |
| `passages` | `passage_presence` | `evaluate_passages` | `refresh` | `passage_packet`, `claim_report` | `passage_report` |
| `review` | `claim_integrity_review` | `review_claims` | `refresh`, `passages` | `review_packet`, `claim_report`, `passage_report` | `claim_review_report` |

`claim_report` is a verified child of `evidence_manifest`, not a free caller
supplied substitute. Lists are JSON arrays of these exact string names.
Bind these nodes to existing operations:

| Stage | External input | Frozen output and child binding |
| --- | --- | --- |
| `refresh` | Source request and claim request | `evidence_runs/<run_id>.json` manifest ID; its source and claim report IDs must verify against their frozen reports. |
| `passages` | Verbatim quote packet | `passage_runs/<run_id>.json` report ID; its claim report ID must equal the refresh claim report ID. |
| `review` | Human review packet | `claim_review_runs/<run_id>.json` report ID from 05; its claim and passage report IDs must match both parents. Adapt the directory/name to 05's shipped contract before implementation. |

The packet headers, reports, and run must agree on entity and exact
timezone-aware cutoff. A report's `publication_allowed` must be `false`.
Blocked evidence statuses may still feed the next diagnostic stage so it can
record a precise blocked reason. A missing, corrupt, mismatched, or unsafe
artifact cannot. A stage is complete only after its output loader verifies the
digest, typed safety fields, parent IDs, entity, cutoff, and raw-source checks
that the existing loader requires. Merely finding a file is not completion.

Validate all four contracts and the full graph before any handler runs: exact
schemas and digests, unique stage and skill identities, known handlers and
artifact types, matching handler to stage, all dependencies present, no
self-reference or cycle, and all required inputs satisfiable from external
inputs or parents. Enforce each skill's exact entity and cutoff policy on its
inputs and output. For this first slice, reject extra stages. Future contracts
need a new explicit allowlist and tests.

## Run and recovery

Expose `run-evidence-workflow` with source and claim requests, a passage
packet, an optional review packet, project/catalog/state directories, an
explicit contract path, and a safe run ID. The first call runs refresh and
passages, then returns `AWAITING_REVIEW`. A human can read those frozen reports
and prepare a review packet with their exact IDs. A later call with the same
run ID and that packet runs review. A changed review packet after it is bound
fails; a missing packet cannot turn the waiting trace into `COMPLETE`.
Before invoking a handler, hash the exact workflow and three skill contract
bytes and canonical available external input contents. Bind all four contract
hashes, entity, cutoff, and run ID in
`state/workflow_runs/<run_id>/state.json`. Reusing a run ID with a changed
workflow, skill, external input, entity, or cutoff fails before any stage.

For each stage, record stage/skill/handler/version, exact skill path and
digest, workflow digest, parent artifact IDs, input hashes, output
path/type/ID, start/end timestamps, status,
attempt number, and a machine-readable blocked or failure reason. Write state
atomically. On resume, re-verify every completed output and its parent links.
If a handler created a frozen output just before a crash but its run state was
not updated, call the same idempotent handler again and adopt its verified
output. Never rerun a completed valid node or silently replace a changed
output. A validation failure stops dependent execution; a safe retry repeats
only the failed node under the same inputs. Cap automatic retries at one
additional attempt per invocation and record both attempts. The final trace
has `publication_allowed: false` and no status named `PUBLISHED`.

The contract and trace establish **execution**, not the correctness of a
reviewer's judgment or rights to redistribute source material. The 05 report
remains an internal evidence decision. Existing `company-research` keeps its
fixture-only guard. All analysis, judgment, publication, Case Book, postmortem,
and learning stages are unavailable here and must not be marked active.

## Migration map

Keep the legacy agent documents as design references during migration:

| Runtime responsibility | Existing agent documents |
| --- | --- |
| Orchestrator | `orchestrator` |
| Evidence | `evidence`, `market_data`, `web_sentiment`, `earnings` |
| Analysis | `macro`, `sector`, `industry`, `company_fundamentals`, `expectations`, `valuation`, `probability` |
| Judgment | `premortem` |
| Integrity and validation | `workflow_compliance`, `research_integrity`, `snapshot_audit` |
| Learning | `historical_case`, `postmortem`, `casebook`, `learning`, `self_healing` |

This map grants no runtime authority. Later slices may add handlers after
their typed inputs, outputs, and evaluation gates exist. Do not delete or
rewrite the old documents in 06.

## Acceptance

- A synthetic run loads the workflow and each of its three selected skill
  contracts, executes in dependency order, and records the exact skill paths,
  digests, handler versions, and verified artifact IDs.
- Missing contract, bad version, unknown handler, duplicate stage, cycle,
  wrong dependency/type, wrong skill digest or cutoff policy, and missing input
  fail before downstream execution.
- Damaged output, wrong entity/cutoff/parent ID, and a self-consistent unsafe
  report cannot count as a completed stage.
- Replaying unchanged inputs is idempotent. A crash between output creation
  and trace update resumes without duplicate output. Changed inputs or
  contract under the same run ID fail.
- Blocked evidence yields an explicit diagnostic result or blocks its
  dependent as specified; it never becomes publication permission.
- Real publication and learning remain disabled even when all three stages
  complete in synthetic tests.
