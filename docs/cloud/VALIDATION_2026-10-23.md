# Cloud development checkpoint — 23 October 2026

Repository baseline: `232d0380848aec7553d61721ebfcb97cf2d9e6c3`.
Python: 3.12.14. Virtual environment: `/workspace/venvs/kb`.

## Reproduce the working environment

The environment draft saves a complete installation script and startup
instructions. The installation script is also preserved in `install.sh` here.
It leaves application source, tests, dependency manifests and lockfiles intact.
No persistent server is required for the guarded local evidence workflow.

Before using the environment, from `/workspace/KB`:

```sh
export PATH="/workspace/venvs/kb/bin:$PATH"
export PYTHONPATH=/workspace/KB
export HAYSTACK_TELEMETRY_ENABLED=false
python -m src.kb_runtime --help
python -m pytest -q tests/test_live_storage.py tests/test_source_store.py tests/test_source_refresh.py
```

These 25 tests passed. `pip check` found no broken requirements. Fatal lint
selection `E9,F63,F7,F82` passed for `src/` and `tests/`.

The environment is already isolated. Use the existing checkout; do not create
a Git worktree unless explicitly requested. Package downloads use verified
HTTPS; CPU PyTorch avoids unnecessary GPU dependencies. Keep `mcp==1.30.0`:
MCP 2 removed the `FastMCP` import required by this repository. Haystack
telemetry is disabled to avoid its attempted write to the read-only home.
Set `PYTHONPATH` and use the environment's `python3` on PATH for tests that
invoke the CLI as a direct script. These overrides resolved the initial CLI
import failures without editing application code.

## Full suite

```sh
HF_HUB_OFFLINE=1 python -m pytest -q
```

Result after setup: **635 passed, 4 failed, 18 warnings, no skips**, in 54.72s.
This is not a green full-suite result. The failures are repository defects:

| Test | Diagnosis |
|---|---|
| `test_ingestion_engine_blocks_on_low_recall` | Fixture writes `b"content"` to a `.pdf`; real Docling rejects it before the recall gate |
| `test_full_ingestion_pipeline` | Fixture writes `b"Simulated PDF Content"`; it is not a valid PDF |
| `test_ingestion_temporal_isolation` | Fixture writes `b"Content One"` and `b"Content Two"`; neither is a valid PDF |
| `test_synthetic_mechanics_reports_all_horizon_denominators_and_missing` | Historical evaluation unconditionally raises when the report file exists, including an unchanged retry |

The repeat-run failure was also reproduced alone. No assertion was disabled,
no fake parser was substituted, and no runtime or test code was changed.
Passing checks cover source integrity, dated evidence, PDF extraction,
retrieval pilots, storage and the valid-text live CLI. They do not establish
licensed real-company PDF acquisition or real embedding quality. Warnings
include deprecated LanceDB `table_names()` calls.

## Research state and limits

See `projects/indian-equities/PROGRESS.md` and its bank-source intake queue.
The tracked DuckDB was inspected read-only: one placeholder company, zero
filings, zero metrics. SBI's unchanged model reproduces its dated INR 840.03
probability-weighted value. No current valuation or price was established.
The SBI primary presentation URL in the saved ledger returned HTTP 403;
no access restriction was bypassed or claim marked reviewed.

The old tracked company configuration contained an OpenRouter key. Its current
value was cleared. Provider revocation/rotation is still required because past
Git commits retain it. No key is needed for the verified local workflow.

## Persistence

The cloud `install_script` and `start_skill` draft fields were confirmed saved.
Review and save them in environment settings, then publish the environment to
retain the prepared snapshot. Draft saving does not itself publish, and a
fresh task restore has not been tested. No network policy or credential binding
was changed. Live processes are not assumed to survive publication.
