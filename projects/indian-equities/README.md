# Indian Equities KB

Three-layer storage model:

- Local Mac: working copy
- GitHub: canonical version history
- ChatGPT Library: agent-readable mirror

Do not store secrets or large licensed raw datasets in Git.

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
