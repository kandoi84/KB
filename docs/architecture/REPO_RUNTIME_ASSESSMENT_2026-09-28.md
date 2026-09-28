# Indian Equities runtime assessment — 2026-09-28

## Repository reality before this slice

- **Research already in Git:** India macro and financials-lending sector
  current-state reports, source/claim maps, manifests and gaps. The hierarchy
  has placeholders for industries and companies, but no HDFC company folder.
- **Specification only in Git:**
  `projects/indian-equities/Framework/specs/architecture-review-handoff.md`
  describes the six runtime responsibilities, state machine, Case Book and
  acceptance tests. It had no executable implementation.
- **Outside Git:** the ChatGPT Library ZIPs in Downloads contain additional
  framework, governance, agent, schema, eval and company documents. They were
  inspected for overlap but are not yet the Git master. The downloaded HDFC
  bank comparison, probability and premortem files are preliminary research;
  they do not contain a complete validated company snapshot.
- **Existing executable code:** `ttl_cache.py` and its tests are unrelated to
  orchestration. Before this slice there was no runtime entrypoint, durable
  run state, run manifest, executable dependency gate or automatic Case Book.

## First executable slice

`src/kb_runtime/` now provides a CLI over a supplied research JSON input.
The states are persisted in order. A run manifest records the source cutoff,
source IDs, input hash, completed steps and snapshot ID. A failed Case Book
write leaves publication pending and can resume without repeating completed
steps. The frozen inception record is never overwritten with different data.
The HDFC tests use explicitly synthetic research data to exercise these
control-plane behaviors; they are not a published HDFC recommendation.

## Still missing executable behavior

Evidence retrieval and gap resolution; analysis and judgment calculations;
source-level and epistemic validation; a real HDFC company input with full
lineage; scheduled outcome observation and postmortems; eval generation;
regression-gated methodology changes. The current structural validator must
be strengthened before using this CLI for production investment publication.
The existing ontology, weights and legacy specifications remain intact.
