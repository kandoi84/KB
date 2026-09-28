# Ingestion Policy

Pipeline: discover -> retrieve -> fingerprint -> classify -> store raw -> normalize -> validate -> publish fact. Do not infer missing values during normalization. Source conflicts create explicit gaps.

## Source storage and updates

Use one stable source ID for one entity, source kind, and canonical URL. Each
retrieval has a source date, observation timestamp, retrieval timestamp, and
raw content hash. Observation and retrieval timestamps include timezone
offsets. Store each raw content version in ignored `data/raw/sha256/`; keep a
version record in `data/registry/sources/<source_id>/`. Never edit or replace
an existing raw blob or version record. A new observation or changed content
creates a new version. Correct mistaken metadata by recording a new version
and linking the correction in the research view; do not rewrite history.

Registering a source does not make its claims valid. Before a fact is promoted
to research, check the source type, date, rights, relevant passage, conflicts,
and claim lineage. Until those checks run, real research publication remains
blocked.
