# Indian Equities KB

Three-layer storage model:

- Local Mac: working copy
- GitHub: version history after this branch is pushed and merged
- ChatGPT Library: agent-readable mirror

Do not store secrets or large licensed raw datasets in Git.

## Project map

- `MASTER.md`: research and valuation rules.
- `Framework/`, `GOVERNANCE/`, `Agents/`, `config/`, `schemas/`, `trust/`:
  specifications, policies, agent contracts, and evaluation definitions.
- `kb/`: shared macro and sector research, source maps, and KB architecture.
- `Companies/Reliance/`: company thesis, earnings preview, and valuation model.
- `derived/`: preliminary HDFC Bank and ICICI Bank comparisons, probabilities,
  and premortems. These are research outputs, not validated company snapshots.
- `docs/sources/`: the imported Library package manifest.
- `data/`: reserved input and normalized-data structure; `outputs/` and
  `state/`: generated local files.

This directory is the single Indian Equities project within `~/code/kb`.
The older generic KB templates and connector experiments in `~/code/codex-work/`
remain separate because they are different projects. The imported Library
documents have not been changed to match the newer runtime code.

## First runtime slice

The repository-root CLI accepts a structured test research JSON file and records
each workflow step under `projects/indian-equities/state/`. Generated state,
snapshots and Case Book files stay on this Mac and are ignored by Git.

```sh
python3 -m src.kb_runtime company-research \
  --entity "HDFC Bank" --input path/to/research.json --run-id hdfc-001
```

Use the same `run-id` and unchanged input to resume a failed run. The CLI
does not gather evidence, calculate valuation or write an investment opinion.
It validates a supplied test snapshot and opens a frozen case only after the
snapshot passes its current structural checks. Real research publication is
blocked until source and integrity validation are implemented. See
`docs/architecture/REPO_RUNTIME_ASSESSMENT_2026-09-28.md` at the repository root.
