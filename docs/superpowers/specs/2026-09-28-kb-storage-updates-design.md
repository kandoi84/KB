# KB source storage and update design

## Intent and scope

Make source updates executable in the current Indian Equities KB. This first slice records immutable raw content and versioned source metadata. It does not promote claims, refresh company analysis, or publish research. The existing macro, sector, company, and derived folders remain the research views.

## Existing boundary

The data/raw directory is ignored by Git. The macro and sector source manifests are empty while their SOURCES.md files contain human descriptions. A source ID alone in the current runtime is insufficient to prove lineage. The real publication gate stays closed.

## Storage contract

One source ID identifies one entity, source kind, and canonical URL. A source update requires JSON metadata and a local raw file. Metadata includes source_id, entity, source_kind, url, source_date, observed_at, and retrieved_at. The dates are ISO 8601: source_date may be a date; observation and retrieval times require timezone offsets. Raw content is stored under its SHA-256 digest in ignored data/raw/sha256/. The register stores one immutable JSON record per source version in tracked data/registry/sources/.

The version ID is the SHA-256 digest of canonical metadata plus the raw hash. Recording the same version again is idempotent. Changed raw content or a later observation creates another version. A reused source ID with changed identity is rejected. Existing records are never overwritten. New metadata is written atomically after the raw content is safely stored. A register write failure leaves an unreferenced raw blob, which a later retry may reuse.

## Interface and checks

The record-source CLI command accepts --metadata PATH and --raw-file PATH. It uses the Indian Equities project directory by default; tests may pass --project-dir. It prints source ID, version ID, and raw hash as JSON. Malformed metadata, missing raw files, conflicting IDs, and changed existing records fail without a successful version record. Tests cover those cases and idempotent retry. No network retrieval or source truth claim occurs here.

## Later slices

The refresh loop will resolve explicit gaps, create source versions, validate claim links and freshness, then update research views with a frozen cutoff. Eval generation and regression gates follow. Hooks will report check, commit, and push status without staging or committing arbitrary files.
