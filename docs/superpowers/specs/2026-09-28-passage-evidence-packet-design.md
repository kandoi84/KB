# Passage evidence packet design

## Goal

For each frozen claim, check whether a supplied verbatim quote occurs in the
exact raw source version. This is a reproducible byte-presence check. It
cannot judge whether the quote supports the claim, close a gap, or publish
research.

## Inputs and output

`evaluate-passages` accepts a JSON packet, frozen claim report path,
project directory, state directory, and safe run ID. The packet has exactly
`entity`, `cutoff_timestamp`, and `quotes`. Each quote entry has exactly
`claim_id` and `verbatim_quote`. Entries are unique and may cover only
claims in the report. A missing entry produces `MISSING_QUOTE`. A present
quote is nonempty UTF-8 text of at most 4096 bytes with no NUL.

The report binds the claim report digest, packet digest, entity, cutoff, and
run ID. It includes every claim, its source ID, version ID, raw SHA-256,
locator, quote text when supplied, byte offset when found, presence status,
and `semantic_status: UNVERIFIED`. The overall status is always
`PASSAGES_UNVERIFIED`. It is frozen under ignored
`state/passage_runs/<run_id>.json`; a repeated ID with changed packet or
claim report fails.

## Presence rules

- `LINEAGE_BLOCKED`: the frozen claim was not `LINEAGE_LINKED`.
- `MISSING_QUOTE`: no quote entry was supplied for a linked claim.
- `INVALID_SOURCE`: pinned version or raw blob is absent, altered, or
  inconsistent with the claim.
- `UNSUPPORTED_FORMAT`: raw bytes are PDF, contain NUL or invalid UTF-8,
  contain disallowed controls, or exceed the 16 MiB plain-text limit.
- `QUOTE_ABSENT`: supported raw text does not contain the quote's exact
  UTF-8 bytes.
- `QUOTE_PRESENT`: exact bytes occur; record the first byte offset.

Check source validity before scanning text. Treat PDF as unsupported even if
literal quote bytes appear in its structure. Exact byte matching is
deliberately conservative; normalized text, OCR, and PDF extraction need
their own versioned provenance contract later. No status here closes the
claim report's open gaps or changes the real publication block.

## Checks

Exercise presence, absence, missing quote, PDF/binary/oversized input,
damaged raw, blocked lineage, duplicate or unknown claim IDs, entity/cutoff
mismatch, same-ID replay and changed input, tampered frozen report, CLI, and
the unchanged real-publication gate. Every successful packet still says
`semantic_status: UNVERIFIED`.
