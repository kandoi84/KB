# Classified gap attempts (mini spec 07, first slice)

## Goal and boundary

Turn an open claim-lineage gap into a frozen attempt to obtain a **new source
version**, only when a reviewer classifies it as a missing public primary
source and records permission for local collection. An attempt never writes a
claim, answers a question, closes a gap, changes an old report, or grants
publication. The new source must pass a new cutoff refresh and the passage and
claim reviews before it can support research.

This first slice has one source adapter: `reviewed_local_primary_v1`. A person
supplies exact downloaded bytes and a metadata file. The adapter verifies the
reviewed source URL, rights receipt, dates, and content identity, then calls
the immutable `record_source` path. It performs **no network request**. There
is no open web fallback, search, scrape, NSE MCP, inferred URL, or browser
cookie reuse. An HTTP adapter needs a later version with endpoint-specific
rights and security review. `record_source` records caller-supplied dates;
neither it nor this attempt authenticates when an external document was first
published.

The live source registry has no rights field. The rights receipt in this slice
is therefore an attempt-level gate, not a retroactive license or a change to
the source version schema. A public URL alone is never permission. NSE's
[website terms](https://www.nseindia.com/static/nse-terms-of-use) prohibit
systematic automated collection; its [MCP terms](https://www.nseindia.com/nse-mcp)
limit that interface to informational, noncommercial use. Its
[data policy](https://www.nseindia.com/static/market-data/nse-data-policy)
describes agreement-based usage rights, and its
[corporate data feed](https://www.nseindia.com/static/market-data/corporate-data-subscription)
is a separate product. This design grants no NSE access right.

## Input and classification

`attempt-gap` consumes an intact frozen claim report, its intact source
readiness report, their original source and claim requests, a reviewer
classification packet, a local raw file, a source
metadata file, project directory, state directory, and safe `attempt_id`.
The packet contains exactly: `gap_id`, `claim_report_id`, `source_report_id`,
`entity`, `cutoff_timestamp`, `classification`, `operator_id`,
`reviewer_id`, `reviewed_at`,
`classification_reason`, `adapter_id`, `source_id`, `source_url`,
`rights_use`, `rights_evidence_ref`, `rights_scope_actor`,
`rights_scope_method`, `rights_scope_storage`, `rights_scope_purpose`,
`rights_reviewed_by`, and `rights_reviewed_at`. `adapter_id` must be
`reviewed_local_primary_v1`.
`rights_use` must be `LOCAL_RESEARCH_COLLECTION_ALLOWED` for execution.
The rights reference must identify a concrete agreement or permission and its
scope; an unexplained website URL, `PUBLIC`, or `N/A` is invalid. This is a
human attestation, not machine proof of license. The actual permission must
cover `operator_id`, source, local manual acquisition method, storage, and
research purpose. The four scope fields must be explicit, nonempty attestations
that match the actual operator and local-use mode. The reviewer must have
reviewed rights no later than the attempt time.
No permission for redistribution is inferred.

Classification is one of:

| Class | Adapter result |
| --- | --- |
| `PUBLIC_PRIMARY_MISSING` | Eligible only when the referenced readiness source is `MISSING` and the gap's `preferred_source` equals `source_id`. |
| `PUBLIC_PRIMARY_STALE` | Eligible only when readiness says `STALE` for that exact source. New bytes can serve a later run, never the frozen cutoff. |
| `INTERNAL_RESEARCH` | `HUMAN_WORK_REQUIRED`; no adapter call. |
| `PROPRIETARY_OR_RESTRICTED` | `RIGHTS_BLOCKED`; no adapter call. |
| `UNCLASSIFIED` | `CLASSIFICATION_REQUIRED`; no adapter call. |

The runner checks request hashes, recomputes the source and claim states at
the old cutoff, and rejects self-consistently rehashed parent reports that
change those states. A later source observation cannot rewrite an old
`MISSING` result. All classes require a real `OPEN` gap from the frozen report. The reviewer
cannot set `web_resolvable` or edit the frozen gap; the attempt records its
own classification and reason. Reject a fake gap, mismatched claim or source
report, wrong entity or exact cutoff, duplicate decision, unsafe ID, or
claim status that already has a reviewed support receipt. `AFTER_CUTOFF`,
`MISSING_RAW`, `CORRUPT_RAW`, and `INVALID_REGISTRY` are integrity or
point-in-time problems; they cannot become an acquisition attempt by changing
the classification. Linked claims needing semantic review remain human work.

For blocked classifications, raw and metadata inputs are optional and never
opened. For eligible attempts, the source metadata must have the existing
exact `record_source` schema and match `source_id`, `entity`, and `source_url`
from the packet. The adapter builds the registration metadata itself with
`retrieved_at` set to actual attempt time, ignoring any earlier caller value;
it rejects a caller value that claims a later retrieval. `observed_at` and
`source_date` remain reviewer-attested and are not historical availability
proof. The raw file must
be a regular file with nonzero length and a bounded maximum size (25 MiB in
v1); record SHA-256 and byte count before import. The URL must use HTTPS,
contain no credentials, fragment, query, localhost, IP literal, or private
host, and be the *exact reviewed URL* in the rights receipt. This validation
does not make the URL safe for future network access. Source kind must be
`EXCHANGE_FILING` for this first slice. The hostname must be `nseindia.com`,
`bseindia.com`, or a direct subdomain of one of those two domains; a lookalike
suffix fails. This identifies the publication authority, but still does not
grant usage rights. Company IR domains need a reviewed issuer-domain mapping
and are deferred. The operator must attest the issuer or security identity
separately where the filing catalog requires it; a URL or ticker alone cannot
establish ISIN. A new retrieval after the frozen cutoff
stays a new observation and cannot be backdated into the old run. Neither a
source date nor an operator-supplied observation time changes this rule.

## Frozen attempt and recovery

Write `state/gap_attempts/<attempt_id>/intent.json` and, after execution,
`result.json` as canonical, digest-bound, atomic, write-once records. The
result binds the intent ID, claim/source report IDs, gap and claim
IDs, original gap reason, classification packet hash, adapter ID and version,
reviewer and rights decision, exact source URL, metadata hash, raw SHA-256 and
byte count, attempt time, status and reason, and the resulting source/version
ID and raw hash when recorded. Every result has `gap_status: OPEN` and
`publication_allowed: false`.

For eligible local attempts, write the intent with all input hashes and the
actual attempt/retrieval time before
calling `record_source`, then write the result after verifying the exact
version. On retry, an unchanged `attempt_id` and unchanged inputs returns the
same final result. If interrupted after source registration, re-read the
intact existing version and write the missing result without adding a second
source version. Resume regenerates registration metadata from the frozen
intent time, never a new wall-clock time. Changed packet, source report,
metadata, raw bytes, adapter
version, or rights decision under the same ID fails. Tampered intent, result,
or source version fails closed. An attempt that cannot execute writes a frozen
blocked result with machine-readable status and no source version.
No automatic retries of a denied or damaged input.

One attempt is one classified gap and one exact candidate document. It may
record a new version even though the gap stays open. Another document or
later rights decision uses a new attempt ID. A later `refresh-evidence` run
uses a new run ID and cutoff and may select the version; 04/05 checks still
decide presence and semantic support. The 06 workflow does not gain a new
node in this slice. This CLI is a controlled side path that can feed a future
refresh.

## Acceptance

- A synthetic missing primary gap plus reviewed local rights and exact bytes
  records one immutable source version and frozen attempt; replay is stable.
- A stale primary gap can record a later version but cannot alter the old
  readiness report or make it current at an earlier cutoff.
- Internal, restricted, unclassified, linked, damaged, and late gaps never
  call the adapter; they get explicit blocked receipts.
- Missing rights scope, URL/metadata mismatch, wrong source or entity,
  malformed or altered parent reports, raw change, and attempt ID collision
  fail closed. A crash after registration resumes to one version.
- The receipt has no claim answer or closed-gap status, and always says
  `publication_allowed: false`. A later refresh and 05 review are required.
