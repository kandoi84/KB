# Claim integrity review design (mini spec 05, first slice)

## Goal and boundary

Turn exact source and quote presence into a frozen, human-reviewed decision for
direct filing claims. A reviewer must judge whether the quote actually supports
the complete statement. The result is an internal evidence control, not a
real-company publication permission. `company-research` and every 05 report
keep `publication_allowed: false`.

This slice can support `REPORTED_FACT` and `MANAGEMENT_GUIDANCE` from a
reviewed filing. `CONSENSUS`, `MARKET_DATA`, and `SENTIMENT` need distinct
origin and rights rules. `DERIVED`, `ANALYST_ASSUMPTION`, `INFERENCE`, and
`UNKNOWN` need calculation or judgment contracts. All these types receive
explicit blocked reasons, even when source bytes contain their quoted words.

## Inputs and binding

`review-claims` takes an exact frozen claim report, frozen passage report,
review packet, project directory, identity/filing catalog, state directory,
and safe run ID. The packet
names entity and timezone-aware cutoff, both input report IDs, and one decision
per claim ID. Its content hash becomes part of the immutable review report.
Each decision names reviewer ID, review time, rights evidence reference,
`rights_use` (`LOCAL_ANALYSIS_ALLOWED` or `BLOCKED`), semantic decision
(`SUPPORTS`, `DOES_NOT_SUPPORT`, or `UNCERTAIN`), a substantive review note,
and a contradiction disposition (`NO_KNOWN_CONFLICT`, `CONFLICT_OPEN`, or
`CONFLICT_RESOLVED`) with related claim IDs and explanation where relevant.
The receipt repeats the exact source ID, version ID, raw SHA-256, verbatim
quote, and byte offset from the passage result. A mismatch fails closed.
Missing decisions are represented as `MISSING_REVIEW`; duplicate, unknown, or
extra fields fail before writing.

The reader verifies the frozen report digests and required safety fields,
entity/cutoff agreement, unique claim IDs, the passage-to-claim report ID,
source record and raw bytes. The catalog must have one confirmed reviewed
filing for the exact source version and matching entity; its publication,
first-seen, and review times must be no later than the cutoff. A missing or
ambiguous filing blocks. Only a `LINEAGE_LINKED` claim with
`QUOTE_PRESENT` may proceed. The exact quote and offset must still point into
the raw source. A missing, damaged, or PDF-only raw quote remains blocked;
derived PDF text requires a separate pinned extraction anchor contract.

The reader also loads the claim's pinned source-readiness report from local
state and checks that it selected the same current source version and raw
digest. A human decision cannot predate the filing's publication, first-seen,
or review time, or the matching identity's announcement, first-seen, or review
time. Such a decision is `REVIEW_BEFORE_EVIDENCE`.

The review time must be timezone aware and no later than the cutoff for this
strict live-review mode. A later review cannot be used to simulate an earlier
decision. Historical reconstruction may use later audit receipts only under
the separately labelled 04F backfill contract; it does not change this mode.

## Decision rules

For a direct filing claim to become `INTERNAL_REVIEWED`, all these conditions
must hold:

1. Input reports and exact raw quote are intact and cutoff eligible.
2. The filing has a reviewed identity and rights record for the exact source
   version. The packet separately records a reviewed permission for **local
   analysis** with a concrete evidence reference. `rights_status=REVIEWED`
   alone does not grant redistribution or publication rights.
3. A named reviewer marks `SUPPORTS` and explains period, entity, scope,
   numbers, units, attribution, and negation where material. Byte presence
   alone does not establish any of these.
4. The reviewer records a contradiction disposition. `CONFLICT_OPEN` blocks
   every related claim. `CONFLICT_RESOLVED` requires named related claims and
   a reason that identifies the controlling version or explains distinct
   periods/scopes. `NO_KNOWN_CONFLICT` is an attestation about checked known
   evidence, not proof that no contradiction exists anywhere.

An unsupported, uncertain, rights-blocked, late, inconsistent, or
unreviewed claim has a specific blocked code. The review report is immutable
and includes each gate outcome, decision receipt, and reason. Replaying an
identical run returns its frozen report; a changed packet or input report with
the same run ID is rejected. A newer review uses a new run ID and never
rewrites an old decision.

The original claim report and its `OPEN` gaps remain untouched. The 05 report
may record `CLOSED_BY_REVIEW` for a gap only when its matching direct claim is
`INTERNAL_REVIEWED`; it binds the original gap ID and belongs to the frozen
review report identified by its top-level report ID.
All other gaps stay `OPEN` with a reason. A later stage must consume this
receipt explicitly. No narrative can silently close a gap.

## Limits and later contracts

- Human review is an attestation, not a machine proof of meaning, completeness,
  license scope, or all contradictions. Do not treat `INTERNAL_REVIEWED` as
  research quality or publication approval.
- Local SHA-256 report IDs and cross-bindings detect mismatches and many
  self-consistent edits, but they are not signatures against a writer who can
  replace the entire source and report chain.
- Numeric derived claims need a separate formula/version, typed input IDs,
  units, deterministic recomputation, source dates, and cutoff checks.
  Assumptions need an explicit label, owner, rationale, as-of time, and
  dependencies. Neither may inherit `REPORTED_FACT` status. Both stay
  `TYPE_CONTRACT_MISSING` in this slice.
- Consensus, market data, and sentiment need source-specific rights and
  semantic contracts. A public URL does not imply scraping, storage, quoting,
  or redistribution permission.
- Contradiction discovery across the whole corpus is not automated here.
  Known related claims are checked together; an unresolved conflict blocks.
- The real publication gate remains blocked until later validators and the
  separate promotion gate pass.
