# Issuer and security identity implementation plan

**Mini spec:** 04A. **Design:** `../specs/2026-09-28-structured-kb-extension.md`.

## Contract

Register one sourced issuer/security/symbol observation per request in a
local SQLite catalog. A request binds issuer ID, legal name, ISIN, security
type, listing dates, exchange symbol and validity dates, announcement and
first-seen timestamps, and an immutable source version. Existing source
versions and synthetic research workflow stay unchanged. Exact retries are
idempotent; conflicting issuer/security facts and overlapping symbol aliases
fail. Resolve a symbol only when both its effective interval and its
announcement/first-seen times permit the requested cutoff. Ambiguity blocks.

## Tasks

1. Write failing tests for ISIN validation, registration/replay, conflicting
   identity, overlapping aliases, and future-known symbol suppression.
2. Implement an append-only SQLite catalog and sourced request validation.
   Validate the pinned version and raw digest before insert.
3. Add `register-identity` and `resolve-symbol` CLI commands and a short
   README example. Keep the real-publication gate unchanged.
4. Run focused and full checks, get independent review, inspect staged diff,
   commit only owned files, and push the feature branch.

The broader four-table filing/chunk/metric DDL remains proposed. This slice
activates only issuer, security, and symbol identity.
