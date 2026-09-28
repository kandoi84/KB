# KB executable research program

Date: 2026-09-28

## Intent and boundary

Turn the Indian Equities KB into a repeatable research and learning system.
The useful result is a point-in-time decision with traceable evidence, a
frozen case, later outcomes, and measured improvement over simple baselines.
This program uses the current KB folder and feature branch. It preserves raw
evidence, prior snapshots, and the real-research publication block until the
integrity and promotion gates are implemented and demonstrated.

The architecture handoff is a target and review brief. The live runtime is
the source of truth for implementation status. No synthetic input or test
fixture becomes a real company result.

## Approach

Three sequences were considered:

1. **Evidence first (selected):** finish claim and source contracts, then
   activate analysis, publication, and learning. This minimizes the chance
   of polished output from unsupported inputs.
2. **Orchestrator first:** wire every stage before evidence checks. This
   would make more of the handoff executable quickly, but the stages would
   still have weak inputs.
3. **Learning first:** build cases and backtests around the synthetic
   workflow. This is easy to demonstrate but risks treating fixture behavior
   as research quality.

Each mini spec below is a vertical slice with its own input contract,
frozen output, blocked path, checks, and task-only commit. A later slice can
consume an earlier output but cannot silently mutate it.

## Working loop

For each pending mini spec: inspect the live code and prior handoff, write the
focused design and plan, implement test-first, run affected and full checks,
review the diff and guardrails, then commit only owned files and push the
feature branch. Record the commit, check result, remaining risk, and next
action in the current handoff. A separate reviewer checks completed slices
when the work can be reviewed independently. A rejected review is fixed
before the slice is marked active.

Keep the context handoff short and refresh it before automatic compaction.
The global `codex.md` rule targets compaction near 40% of the configured
window; the runtime's fixed `model_auto_compact_token_limit` is authoritative.
Do not claim a measured percentage unless the runtime exposes it. Resume from
the handoff after compaction; do not repeat completed work. Commit and push
verified slices automatically under the KB Git rules. Never include files
owned by another session.

## Mini specs

| ID | Mini spec | Status | Acceptance contract |
| --- | --- | --- | --- |
| 00 | Immutable local source versions | Active | Raw hash and metadata version are immutable; conflicting identities fail. |
| 01 | Cutoff source readiness | Active | Selected version and freshness are frozen; missing, late, stale, or corrupt sources block. |
| 02 | Claim lineage and gap ledger | Active, meaning open | Typed claims pin source version and raw hash; every claim has an open gap. |
| 03 | Repeatable evidence refresh | Active | A run compares prior frozen reports, identifies affected claims, and cannot reuse an ID with changed inputs. |
| 04 | Passage evidence packet | Active, meaning open | A supplied verbatim quote is checked against the exact raw version when text is supported. Unsupported or absent text stays open. Presence never means semantic approval. |
| 04A | Issuer and security identity | Active, caller-reviewed mapping | Company research uses issuer ID; listed security uses ISIN. Exchange symbols are dated aliases and ambiguous matches block. Existing source versions remain readable. |
| 04B | Point-in-time typed metrics | Active, strict live replay | Reviewed reported and guidance revisions bind ISIN, full metric series, source version, and filing availability. Cutoff queries never see later revisions; publication remains blocked. |
| 04C | Filing and transcript extraction | Active, plain UTF-8 slice | Filing-only registration and versioned plain-text parser produce immutable chunks with exact raw byte offsets and `UNKNOWN` role. Binary/PDF input stays blocked. |
| 04C2 | PDF pages and reviewed speaker roles | Active, controlled PDF slice | Pinned parser stores page-mapped derived text separately from raw PDF; extraction arrival and exact whole-chunk role revisions are append-only and cutoff-aware. Failed or ambiguous extraction stays blocked. Licensed real-sample visual validation remains an adapter gate. |
| 04D | Filtered retrieval | Active, lexical baseline | Retrieval filters by issuer/security, document type, speaker role, and strict cutoff; it returns immutable chunk IDs and citation metadata. Typed metrics are the authority for numeric answers. Quality remains unmeasured pending 04E. |
| 04E | Retrieval and answer evals | Active, contract harness | A 30–50 case JSONL runner scores source-anchor recall and optional submitted answers. Synthetic cases test mechanics; real reviewed gold and a frozen baseline are still needed for quality or promotion claims. |
| 04F | Historical backfill reconstruction | Active, manual attestation | Separate reviewed filing and identity archive receipts bind exact source versions. Research-only backfilled results are labelled and queried separately from live replay; historical timestamps remain reviewer-attested, not independently authenticated. |
| 05 | Claim integrity review | Active, direct filing claims | Frozen human decisions bind claim, exact quote, source version, reviewer, and strict cutoff. Local rights and known conflicts have explicit blocked results; derived claims and assumptions await their own contracts. Gap closure is a review receipt only, and publication remains blocked. |
| 06 | Dependency and skill contracts | Active, evidence review slice | A pinned three-stage DAG loads and runs refresh, passages, and human claim review with frozen parent checks, two-phase resume, and an execution trace. Later analysis/publication skills remain unavailable. |
| 07 | Gap resolution | Active, reviewed local source slice | A classified missing or stale public primary gap can record one manually supplied source version with a human rights attestation and frozen attempt receipt. No network adapter, gap closure, or publication is enabled. Internal, restricted, and damaged gaps remain blocked. |
| 08 | Analysis and judgment | Active, internal worksheet slice | Four sourced layers, a most-likely path, independent debates, Decimal fair-value arithmetic, catalysts, diagnostics, and bias/mechanism/inversion checks are frozen with revision links. Model formulas, analyst judgment, market price, scores, and calibration remain unverified; publication stays blocked. |
| 09 | Integrity, snapshot, and case opening | Active, sandbox only | Replay-verified parents and one cutoff open an immutable sandbox case with a falsifiable metric target. No score, price, trade, or publication permission. Prior-case links check local structure and digests; historical quality and the live gate remain pending. |
| 10 | Outcome and postmortem loop | Sandbox active | Dated source-backed observations append idempotently to replayed cases. A due review records process/result classification and error taxonomy; reproducible bad process yields an unreviewed eval candidate. Real publication stays blocked. |
| 11 | Change proposals and regressions | Planned | Proposed prompts, weights, schemas, and rules are versioned. Production stays on the old version until regression passes, and structural changes have explicit human approval. |
| 12 | Historical evaluation and promotion | Planned | Point-in-time cases reveal outcomes only after frozen decisions; repeatability, look-ahead, ranking, calibration, drawdown, and simple baselines run with sample counts. The 50-to-5 gate follows `Framework/evals/EVAL_PLAN.md`. |
| 13 | Source adapter expansion and trust calibration | Active, route and diagnostic slice only | Frozen plans and independently labeled local attempts expose rights scope, failures, denominators, and uncertainty. Observed real gaps: 0 on 2026-09-29. No HTTP connector, calibrated trust claim, investment-score input, or publication permission. |

## Cross-cutting checks

- Every run has an entity, timezone-aware cutoff, immutable input identity,
  explicit state, and machine-readable reason for blocked work.
- Every material numeric input has source and observation dates plus a
  reported, guidance, consensus, derived, or assumption label.
- A later observation never rewrites an inception case or earlier report.
- Real research stays blocked while any required validator is missing.
- Tests exercise a successful path, a blocked path, retry or replay, damaged
  evidence, and cutoff or look-ahead behavior for each slice.
- Historical evaluations compare against the listed simple baselines and
  record sample sizes. No passing claim is inferred from a small fixture.

## Execution order

Build 04 and the 04A–04F storage and retrieval path, including 04C2, then 05. Activate
dependency and skill contracts in 06, then add audited gap adapters in 07.
Add 08 only after those inputs are controlled.
Wire 09 only after the evidence and analysis validators
exist. Then build 10–12. Add 13 only for observed data gaps and credible
calibration samples. Each mini spec gets a separate design and implementation
plan; the table records program scope, not a claim that future stages work.

## Acceptance details for later specs

- **06:** Inventory old agents and skills against the six runtime
  responsibilities. A selected contract must be loaded, checked, executed,
  and named in the run trace. A missing output blocks its dependents.
- **07:** A gap attempt receipt binds the gap ID, cutoff, allowed source,
  rights decision, adapter version, result, and time. Retry is idempotent.
  Proprietary and internal gaps never reach a web adapter.
- **09:** The decision manifest binds the evidence manifest ID, exact cutoff,
  source hashes, validator receipts, and derived score/poker inputs. A crash
  between sandbox decision and Case Book write resumes without false success
  or duplicate inception. Real publication stays blocked.
- **10:** Observations have a stable event ID and append-only payload.
  Replaying the same event is a no-op; changing its payload fails. A due event
  produces the four process/result combinations and a named error class.
- **11:** A proposal records candidate version, baseline version, regression
  set, result, and approval status. Failure or missing approval cannot change
  the active version. Luck or unavoidable surprise records an outcome only.
- **12:** The historical runner freezes a decision before revealing outcome.
  Report sample counts for quarterly 30–50 name snapshots and 6, 12, 24,
  and 36 month horizons. Check 100% timestamp provenance; median score
  repeatability at most 3 points; factor agreement within 0.5 for at least
  80% of factors; 12 and 24 month top-versus-bottom quintile excess returns;
  calibration, drawdown, and the five baselines in `EVAL_PLAN.md`. Promotion
  needs at least 100 historical company snapshots and the stated gates.
