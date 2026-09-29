"""CLI wrapper for the Live KB system.

Provides a simple interface for updating, querying, and auditing the KB.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

# Absolute imports for CLI execution
from src.kb_runtime.live_storage import LiveKBStorage, Company, Metric
from src.kb_runtime.live_ingestion import LiveIngestionEngine, IngestionConfig
from src.kb_runtime.live_query import LiveQueryEngine
from src.kb_runtime.thesis_wiki import ThesisWiki

def cmd_update(args, storage: LiveKBStorage, engine: LiveIngestionEngine):
    """Updates a company's KB."""
    
    # Case 1: Automated update from Symbol
    if args.symbol:
        print(f"Starting automated ingestion for {args.symbol}...")
        success, logs = engine.ingest_from_symbol(args.symbol)
        if not success:
            print(f"Automated update FAILED for {args.symbol}")
            for log in logs: print(f"  - {log}")
            sys.exit(1)
        print(f"Automated update SUCCESSFUL for {args.symbol}")
        for log in logs: print(f"  - {log}")
        return

    # Case 2: Manual update from File
    if not args.isin:
        print("Error: Either --symbol or --isin must be provided")
        sys.exit(1)
        
    storage.upsert_company(Company(args.isin, "UNKNOWN", "UNKNOWN", "UNKNOWN"))

    metrics_to_record = []
    if args.metrics:
        try:
            m_data = json.loads(args.metrics)
            for m in m_data:
                metrics_to_record.append(Metric(
                    isin=args.isin,
                    metric_name=m["name"],
                    value=float(m["value"]),
                    period_end=m["period_end"],
                    filing_date=m["filing_date"],
                    version_id=f"m_{m['name']}_{m['filing_date']}"
                ))
        except Exception as e:
            print(f"Error parsing metrics JSON: {e}")
            sys.exit(1)

    file_path = Path(args.file)
    if not file_path or not file_path.exists():
        print("Error: --file is required for manual updates and must exist")
        sys.exit(1)

    version_id, success, logs = engine.ingest_document(
        isin=args.isin,
        doc_type=args.doc_type,
        filing_date=args.filing_date,
        period_end=args.period_end,
        source_url=args.url,
        file_path=file_path,
        metrics_to_record=metrics_to_record
    )

    if not success:
        print(f"Update FAILED for {args.isin}")
        for log in logs:
            print(f"  - {log}")
        sys.exit(1)

    print(f"Update SUCCESSFUL. Version: {version_id}")
    for log in logs:
        print(f"  - {log}")

def cmd_query(args, storage: LiveKBStorage, query_engine: LiveQueryEngine):
    """Queries the KB for a company as-of a specific date."""
    import hashlib
    hash_val = int(hashlib.md5(args.query.encode()).hexdigest(), 16)
    mock_vector = [((hash_val >> (i * 8)) & 0xFF) / 255.0 for i in range(1536)]

    print(f"--- Snapshot for {args.isin} as of {args.as_of} ---")
    snapshot = query_engine.get_company_snapshot(args.isin, args.as_of)
    print("\nMetrics:")
    for name, data in snapshot["metrics"].items():
        print(f"  {name}: {data['value']} (Filed: {data['filing_date']})")

    print("\nContext Retrieval:")
    context = query_engine.query_context(args.isin, args.as_of, mock_vector)
    if not context:
        print("  No relevant chunks found.")
    for i, res in enumerate(context):
        print(f"  [{i}] {res['text'][:100]}... (Doc: {res['doc_id']}, Date: {res['filing_date']})")

def cmd_audit(args, storage: LiveKBStorage, engine: LiveIngestionEngine):
    """Audits the state of a company's KB."""
    filings = storage.conn.execute(
        "SELECT count(*) as count, max(filing_date) as last_date FROM filings WHERE isin = ?", 
        (args.isin,)
    ).fetchone()
    
    print(f"Audit for {args.isin}:")
    if not filings or filings[0] == 0:
        print("  No data found in KB.")
    else:
        print(f"  Total filings: {filings[0]}")
        print(f"  Most recent filing: {filings[1]}")

def cmd_wiki(args, wiki: ThesisWiki):
    """Manages the analyst's thesis wiki."""
    if args.wiki_action == "thesis":
        wiki.update_thesis(args.isin, args.content)
        print(f"Thesis updated for {args.isin}")
    elif args.wiki_action == "note":
        wiki.add_note(
            isin=args.isin,
            note_id=args.note_id,
            content=args.content,
            links=json.loads(args.links) if args.links else []
        )
        print(f"Note {args.note_id} added for {args.isin}")
    elif args.wiki_action == "list":
        notes = wiki.list_notes(args.isin)
        print(f"Notes for {args.isin}:")
        for n in notes:
            print(f"  - {n.name}")

def main():
    parser = argparse.ArgumentParser(description="Live KB Management CLI")
    parser.add_argument("--project-dir", default=".", help="Project root directory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    upd = subparsers.add_parser("update")
    upd.add_argument("--symbol", help="Update automatically using company symbol (e.g. RELIANCE)")
    upd.add_argument("--isin", help="Update manually using ISIN")
    upd.add_argument("--file", help="Path to document file (Required if --isin used)")
    upd.add_argument("--doc-type", default="ANNUAL")
    upd.add_argument("--filing-date", help="Filing date YYYY-MM-DD")
    upd.add_argument("--period-end", help="Period end date YYYY-MM-DD")
    upd.add_argument("--url", default="unknown")
    upd.add_argument("--metrics", help="JSON list of metrics")

    qry = subparsers.add_parser("query")
    qry.add_argument("--isin", required=True)
    qry.add_argument("--as-of", required=True)
    qry.add_argument("--query", required=True)

    aud = subparsers.add_parser("audit")
    aud.add_argument("--isin", required=True)

    wiki = subparsers.add_parser("wiki")
    wiki.add_argument("--isin", required=True)
    wiki.add_argument("--wiki-action", choices=["thesis", "note", "list"], required=True)
    wiki.add_argument("--content", help="Content for thesis or note")
    wiki.add_argument("--note-id", help="ID for the note")
    wiki.add_argument("--links", help="JSON list of version IDs for the note")

    args = parser.parse_args()
    
    root_dir = Path(args.project_dir)
    storage = LiveKBStorage(root_dir)
    engine = LiveIngestionEngine(storage)
    query_engine = LiveQueryEngine(storage)
    wiki = ThesisWiki(root_dir)

    try:
        if args.command == "update":
            cmd_update(args, storage, engine)
        elif args.command == "query":
            cmd_query(args, storage, query_engine)
        elif args.command == "audit":
            cmd_audit(args, storage, engine)
        elif args.command == "wiki":
            cmd_wiki(args, wiki)
    finally:
        storage.close()

if __name__ == "__main__":
    main()
