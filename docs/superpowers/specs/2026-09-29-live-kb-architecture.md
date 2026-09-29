# Live KB Architecture Spec

## 1. Intent and Scope
Move the KB from a "Historical Lab" (where we test theories) to a "Live Factory" (where we maintain current truth). The goal is a system that supports both quantitative screening (SQL) and qualitative research (RAG) while maintaining the "point-in-time" rigor implemented in the historical runtime.

## 2. Core Storage Design (The Truth System)
We adopt an **ISIN-centric temporal store**. Every record is versioned to prevent lookahead bias and support "as-of" queries.

### Layer A: Structured Store (The "Quant" Side)
- **Tool**: DuckDB (local, fast, SQL-compliant).
- **Entities**:
    - `companies`: ISIN (PK), symbol_history, sector, industry, country.
    - `metrics`: ISIN, metric_name, value, period_end, filing_date, version_id.
    - `filings`: ISIN, doc_type, filing_date, period_end, source_url, version_id.
- **Update Rule**: Append-only. No `UPDATE` statements. New data creates a new version with a later `filing_date`.

### Layer B: Vector Store (The "Qual" Side)
- **Tool**: LanceDB (local, serverless, integrated with DuckDB).
- **Content**:
    - `chunks`: text, embedding, isin, doc_id, page_num, section, metadata.
- **Metadata Contract**: Every chunk must carry:
    - `isin`: For hard filtering.
    - `doc_id`: Link back to the `filings` table.
    - `temporal_window`: `[filing_date, period_end]` to enable "as-of" retrieval.

### Layer C: Thesis Wiki (The "Analyst" Side)
- **Format**: Markdown files (one per ISIN).
- **Structure**:
    - `companies/{ISIN}/thesis.md`: The evolving narrative.
    - `companies/{ISIN}/notes/`: Dated research fragments.
- **Sync**: The Wiki can link to specific `version_id`s in the Structured Store for evidence.

## 3. The Refresh & Eval Loop (The Factory Line)
The "Loop" is a series of guarded stages. Failure at any stage blocks the update.

1. **Ingestion**: Fetch PDF/XBRL $\to$ Store Raw Blob $\to$ Record in `filings`.
2. **Parsing**: Docling $\to$ Clean Text $\to$ Sectioning.
3. **Indexing**: Chunking $\to$ Embedding $\to$ Store in `chunks`.
4. **Verification (The Guardrail)**:
    - **Retrieval Eval**: Run a "Golden Set" of 20 questions for that company. If recall drops, block the index update.
    - **Numeric Sanity**: Check if new metrics are within reasonable bounds (e.g., Revenue cannot be negative).
5. **Activation**: Update the "Current Version" pointer for the company.

## 4. Skill Activation Contracts
We define the "glue" as a set of CLI tools for the agent:
- `kb update --isin <ISIN>`: Triggers the full refresh loop.
- `kb query --isin <ISIN> --as-of <DATE> --q <QUERY>`: Performs a temporal RAG query.
- `kb audit --isin <ISIN>`: Reports on data freshness and eval scores.

## 5. Implementation Roadmap (Mini-Specs)
- **Mini-Spec 1**: Storage Layer Setup (DuckDB + LanceDB schemas).
- **Mini-Spec 2**: The Ingestion Pipeline (Docling $\to$ Chunks).
- **Mini-Spec 3**: The Verification Guardrails (Retrieval Eval).
- **Mini-Spec 4**: Tooling & CLI Wrapper.
