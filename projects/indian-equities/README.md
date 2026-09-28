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
The older generic KB shell now lives in `../research-journal/` as a separate
project within this repository. Connector experiments in `~/code/codex-work/`
remain separate because they are a distinct model-router design. The imported
Library documents have not been changed to match the newer runtime code.

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

## Record a source update

Create a JSON metadata file with these exact fields: `source_id`, `entity`,
`source_kind`, `url`, `source_date` (YYYY-MM-DD), `observed_at`, and
`retrieved_at` (ISO timestamps with timezone offsets). Then run:

```sh
python3 -m src.kb_runtime record-source \
  --metadata path/to/source.json --raw-file path/to/downloaded-file
```

The command writes the raw bytes under ignored `data/raw/sha256/` and one
version record under tracked `data/registry/sources/`. It returns the source
ID, version ID, and raw SHA-256 hash. Repeating the same input returns the
same version. The source register is an update trail, not approval of the
source or its claims. See `GOVERNANCE/INGESTION_POLICY.md` for the rules.

## Check source readiness

Create a JSON request with a research `entity`, a timezone-aware
`cutoff_timestamp`, and a nonempty `required_sources` list. Each entry names a
registered `source_id` and its allowed `max_age_days`. Shared macro and sector
sources may support another entity. For example:

```json
{
  "entity": "SBI",
  "cutoff_timestamp": "2026-09-28T18:00:00+05:30",
  "required_sources": [{"source_id": "SBI_Q1FY27", "max_age_days": 60}]
}
```

Run the check from the repository root:

```sh
python3 -m src.kb_runtime evaluate-sources \
  --request path/to/refresh-request.json --run-id sbi-refresh-001
```

The command checks source dates, registered versions, raw file hashes, and age
at the cutoff. It writes a frozen report under ignored `state/refresh_runs/`.
`SOURCE_READY` means all requested source files passed these checks.
`SOURCE_BLOCKED` names each missing, late, stale, or damaged source. Use a new
run ID after a source update. This check does not validate claims or permit
real research publication.

## Check claim links and gaps

After a source readiness run, prepare a JSON claim request with `entity`, the
same `cutoff_timestamp`, and a nonempty `claims` list. Each claim needs
`claim_id`, `claim_type`, `statement`, `as_of` (YYYY-MM-DD), `source_id`, the
exact `version_id` from the source report, and `passage_locator`. For example:

```json
{
  "entity": "SBI",
  "cutoff_timestamp": "2026-09-28T18:00:00+05:30",
  "claims": [{
    "claim_id": "sbi-deposit-growth",
    "claim_type": "REPORTED_FACT",
    "statement": "Deposits grew.",
    "as_of": "2026-06-30",
    "source_id": "SBI_Q1FY27",
    "version_id": "<64-character version ID from source report>",
    "passage_locator": "page 12, deposits table"
  }]
}
```

```sh
python3 -m src.kb_runtime evaluate-claims \
  --claims path/to/claims.json \
  --source-report projects/indian-equities/state/refresh_runs/sbi-refresh-001.json \
  --run-id sbi-claims-001
```

The report under ignored `state/claim_runs/` checks source version and raw
bytes and lists an open gap for every claim. A linked source still has
`passage_status: UNVERIFIED`: the command cannot decide whether the passage
supports the statement. Derived and inferred claims need later calculation
or judgment checks. `CLAIMS_BLOCKED` is expected; this command does not
authorize real research publication.

## Run a repeatable evidence refresh

Use matching entity and cutoff values in the source and claim requests:

```sh
python3 -m src.kb_runtime refresh-evidence \
  --source-request path/to/refresh-request.json \
  --claims path/to/claims.json --run-id sbi-evidence-001
```

After new source data arrives, use a new run ID and name the earlier run:

```sh
python3 -m src.kb_runtime refresh-evidence \
  --source-request path/to/new-refresh-request.json \
  --claims path/to/claims.json --run-id sbi-evidence-002 \
  --previous-run-id sbi-evidence-001
```

The command runs both checks, saves their frozen reports, and writes an
evidence manifest under ignored `state/evidence_runs/`. It lists source
version changes, claims to recheck, and open gaps. Repeating an unchanged
run ID resumes the same result. `publication_allowed` stays false because
passage, conflict, calculation, and rights checks are not yet complete.

## Check supplied passage text

Create a packet with the same entity and cutoff as a frozen claim report:

```json
{
  "entity": "SBI",
  "cutoff_timestamp": "2026-09-28T18:00:00+05:30",
  "quotes": [{
    "claim_id": "sbi-deposit-growth",
    "verbatim_quote": "Deposits grew"
  }]
}
```

```sh
python3 -m src.kb_runtime evaluate-passages \
  --packet path/to/passage-packet.json \
  --claim-report projects/indian-equities/state/claim_runs/sbi-claims-001.json \
  --run-id sbi-passages-001
```

The frozen report under ignored `state/passage_runs/` checks exact UTF-8
quote bytes in the pinned raw source. Plain text up to 16 MiB is supported;
PDF and binary files stay `UNSUPPORTED_FORMAT`. `QUOTE_PRESENT` proves byte
presence only. Claim meaning stays `UNVERIFIED`, gaps remain open, and real
publication stays blocked.
