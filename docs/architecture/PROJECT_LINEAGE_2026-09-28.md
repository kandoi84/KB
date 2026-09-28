# KB project lineage — 2026-09-28

This is a map of existing work, not a new architecture. `~/code/kb` is the
local master repository. GitHub `kandoi84/KB` reflects these changes only after
this branch is pushed and merged. The ChatGPT conversation and Library are
historical sources, not a second editable repository.

## How the work evolved

| Stage | Preserved location | What it contributed | Current role |
| --- | --- | --- | --- |
| General KB shell and research journal | [`projects/research-journal/`](../../projects/research-journal/README.md) | Raw source register, notes, analysis, draft/curated wiki, evidence rubric, dated thesis journal, templates and link checker | Reusable journal and historical origin; its approval rules govern this project only |
| Indian Equities use case | [`projects/indian-equities/`](../../projects/indian-equities/README.md) | Macro → Sector → Industry → Company ontology; company research, source policy, valuation, scoring, GAPS, agents and eval specifications | Investment research project and authoritative equity rules in `MASTER.md` |
| Pocket Analyst / PAT ideas from the `Earnings Note` ChatGPT discussion | [runtime handoff](CHATGPT_RUNTIME_HANDOFF_2026-09-28.md) and [architecture review](../../projects/indian-equities/Framework/specs/architecture-review-handoff.md) | Narrow runtime responsibilities, persisted workflow, Case Book, outcome observation and a benchmark-first Teach loop | Design influence; only the behavior described in the committed handoff is approved for this repository |
| First executable runtime | [`src/kb_runtime/`](../../src/kb_runtime/) and [assessment](REPO_RUNTIME_ASSESSMENT_2026-09-28.md) | Resumable control flow, run manifest, structural validation and automatic frozen case for synthetic input | Tested control-plane slice; real research publication remains blocked |

The generic shell was copied from
`~/code/codex-work/2026-09-25/kb/outputs/KB/` on 2026-09-28, excluding its
independent `.git` directory. The source copy was left in place. Its fictional
company example is explicitly illustrative; it is not Indian Equities evidence.
The shell's `AGENTS.md` and `KB-GUIDE.md` apply inside `projects/research-journal/`.
The repository root and Indian Equities instructions govern the other paths.

## Existing versus still to build

**Already present:** the shell and source discipline; Indian Equities research
ontology and policy; imported ChatGPT Library specifications and preliminary
derived research; the runtime handoff; a small executable state machine,
manifest and synthetic Case Book path. The [runtime assessment](REPO_RUNTIME_ASSESSMENT_2026-09-28.md)
records the exact first-slice boundary.

**Specified but not running:** evidence retrieval and explicit gap resolution,
analysis and judgment modules, source-level and epistemic validators, outcome
observation, postmortems, eval generation and regression-gated method changes.
The Teach loop is therefore an intended workflow, not an active self-improving
system. No silent changes to research rules or models are authorized.

**Missing for real company publication:** source-linked validated company
snapshots, full lineage through claims and evidence, and production integrity
checks. Preliminary HDFC Bank and ICICI Bank files do not satisfy this gate.

## Separate design work

The `~/code/codex-work/2026-09-25/equity-kb-connector/` folder contains a
design-only model-router and Netflix SEC evidence proof. It has no executable
ingestion or router to merge. It is related background, not a dependency of
the approved Indian Equities runtime. Its plans should be reviewed separately
before any code or policy is reused here.

## Next decision

Keep the six-responsibility runtime and current equity ontology. The next
implementation choice is which production gate to build first: source-linked
evidence and gap resolution, or validation of a supplied real company snapshot.
Either route must keep real publication blocked until the full promotion gate
passes. The older shell can inform evidence metadata and review practice
without replacing the equity-specific policies or its runtime schemas.
