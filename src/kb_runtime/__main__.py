import argparse
import json
import sys
from pathlib import Path

from .claim_lineage import evaluate_claims
from .evidence_refresh import refresh_evidence
from .filtered_retrieval import search_chunks
from .identity_store import register_identity, resolve_symbol
from .metric_store import query_metrics, register_filing, register_filing_metrics
from .passage_evidence import evaluate_passages
from .pdf_chunks import extract_pdf_filing, query_pdf_chunks, review_pdf_role
from .source_refresh import evaluate_sources
from .source_store import record_source
from .text_chunks import extract_text_filing, query_text_chunks
from .workflow import run_company_research


def main():
    parser = argparse.ArgumentParser(description="Run a supplied company research snapshot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    company = subparsers.add_parser("company-research")
    company.add_argument("--entity", required=True)
    company.add_argument("--input", type=Path, required=True, help="Structured, sourced research JSON")
    company.add_argument("--state-dir", type=Path, default=Path("projects/indian-equities/state"))
    company.add_argument("--run-id", required=True)
    company.add_argument("--fail-once", choices=["CASE_OPENED"], help="Exercise recovery after a case-write failure")
    source = subparsers.add_parser("record-source", help="Store one immutable source observation")
    source.add_argument("--metadata", type=Path, required=True)
    source.add_argument("--raw-file", type=Path, required=True)
    source.add_argument(
        "--project-dir", type=Path,
        default=Path(__file__).resolve().parents[2] / "projects/indian-equities",
    )
    refresh = subparsers.add_parser("evaluate-sources", help="Freeze source readiness at a cutoff")
    refresh.add_argument("--request", type=Path, required=True)
    refresh.add_argument("--run-id", required=True)
    refresh.add_argument(
        "--project-dir", type=Path,
        default=Path(__file__).resolve().parents[2] / "projects/indian-equities",
    )
    refresh.add_argument("--state-dir", type=Path, default=Path("projects/indian-equities/state"))
    claims = subparsers.add_parser("evaluate-claims", help="Freeze claim lineage and open gaps")
    claims.add_argument("--claims", type=Path, required=True)
    claims.add_argument("--source-report", type=Path, required=True)
    claims.add_argument("--run-id", required=True)
    claims.add_argument(
        "--project-dir", type=Path,
        default=Path(__file__).resolve().parents[2] / "projects/indian-equities",
    )
    claims.add_argument("--state-dir", type=Path, default=Path("projects/indian-equities/state"))
    passages = subparsers.add_parser("evaluate-passages", help="Freeze exact quote presence for claims")
    passages.add_argument("--packet", type=Path, required=True)
    passages.add_argument("--claim-report", type=Path, required=True)
    passages.add_argument("--run-id", required=True)
    passages.add_argument(
        "--project-dir", type=Path,
        default=Path(__file__).resolve().parents[2] / "projects/indian-equities",
    )
    passages.add_argument("--state-dir", type=Path, default=Path("projects/indian-equities/state"))
    identity = subparsers.add_parser("register-identity", help="Register a sourced ISIN and symbol")
    identity.add_argument("--request", type=Path, required=True)
    identity.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    identity.add_argument("--catalog", type=Path,
                          default=Path("projects/indian-equities/data/registry/identity.sqlite"))
    symbol = subparsers.add_parser("resolve-symbol", help="Resolve a dated exchange symbol")
    symbol.add_argument("--catalog", type=Path,
                        default=Path("projects/indian-equities/data/registry/identity.sqlite"))
    symbol.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    symbol.add_argument("--exchange", required=True)
    symbol.add_argument("--symbol", required=True)
    symbol.add_argument("--effective-date", required=True)
    symbol.add_argument("--cutoff", required=True)
    filing = subparsers.add_parser("register-filing-metrics", help="Register reviewed filing metrics")
    filing.add_argument("--request", type=Path, required=True)
    filing.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    filing.add_argument("--catalog", type=Path,
                        default=Path("projects/indian-equities/data/registry/identity.sqlite"))
    filing_only = subparsers.add_parser("register-filing", help="Register a reviewed filing without metrics")
    filing_only.add_argument("--request", type=Path, required=True)
    filing_only.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    filing_only.add_argument("--catalog", type=Path,
                             default=Path("projects/indian-equities/data/registry/identity.sqlite"))
    metric_query = subparsers.add_parser("query-metrics", help="Read metrics at a strict live cutoff")
    metric_query.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    metric_query.add_argument("--catalog", type=Path,
                              default=Path("projects/indian-equities/data/registry/identity.sqlite"))
    metric_query.add_argument("--isin", required=True)
    metric_query.add_argument("--metric-name", required=True)
    metric_query.add_argument("--period-end", required=True)
    metric_query.add_argument("--cutoff", required=True)
    extract = subparsers.add_parser("extract-text-filing", help="Chunk a reviewed plain UTF-8 filing")
    extract.add_argument("--filing-id", required=True)
    extract.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    extract.add_argument("--catalog", type=Path,
                         default=Path("projects/indian-equities/data/registry/identity.sqlite"))
    chunk_query = subparsers.add_parser("query-text-chunks", help="Read cited text chunks at a strict cutoff")
    chunk_query.add_argument("--filing-id", required=True)
    chunk_query.add_argument("--cutoff", required=True)
    chunk_query.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    chunk_query.add_argument("--catalog", type=Path,
                             default=Path("projects/indian-equities/data/registry/identity.sqlite"))
    pdf_extract = subparsers.add_parser("extract-pdf-filing", help="Extract cited PDF pages and chunks")
    pdf_extract.add_argument("--filing-id", required=True)
    pdf_extract.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    pdf_extract.add_argument("--catalog", type=Path,
                             default=Path("projects/indian-equities/data/registry/identity.sqlite"))
    pdf_query = subparsers.add_parser("query-pdf-chunks", help="Read cited PDF chunks at a strict cutoff")
    pdf_query.add_argument("--filing-id", required=True)
    pdf_query.add_argument("--cutoff", required=True)
    pdf_query.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    pdf_query.add_argument("--catalog", type=Path,
                           default=Path("projects/indian-equities/data/registry/identity.sqlite"))
    pdf_role = subparsers.add_parser("review-pdf-role", help="Review one exact PDF speaker chunk")
    pdf_role.add_argument("--request", type=Path, required=True)
    pdf_role.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    pdf_role.add_argument("--catalog", type=Path,
                          default=Path("projects/indian-equities/data/registry/identity.sqlite"))
    search = subparsers.add_parser("search-chunks", help="Search verified filing chunks at a strict cutoff")
    search.add_argument("--issuer-id", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--cutoff", required=True)
    search.add_argument("--isin")
    search.add_argument("--document-type", action="append", dest="document_types")
    search.add_argument("--speaker-role")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--include-superseded", action="store_true")
    search.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    search.add_argument("--catalog", type=Path,
                        default=Path("projects/indian-equities/data/registry/identity.sqlite"))
    evidence = subparsers.add_parser("refresh-evidence", help="Run source and claim checks together")
    evidence.add_argument("--source-request", type=Path, required=True)
    evidence.add_argument("--claims", type=Path, required=True)
    evidence.add_argument("--run-id", required=True)
    evidence.add_argument("--previous-run-id")
    evidence.add_argument(
        "--project-dir", type=Path,
        default=Path(__file__).resolve().parents[2] / "projects/indian-equities",
    )
    evidence.add_argument("--state-dir", type=Path, default=Path("projects/indian-equities/state"))
    args = parser.parse_args()
    try:
        if args.command == "record-source":
            result = record_source(args.metadata, args.raw_file, args.project_dir)
        elif args.command == "evaluate-sources":
            result = evaluate_sources(args.request, args.project_dir, args.state_dir, args.run_id)
        elif args.command == "evaluate-claims":
            result = evaluate_claims(
                args.claims, args.source_report, args.project_dir, args.state_dir, args.run_id
            )
        elif args.command == "evaluate-passages":
            result = evaluate_passages(
                args.packet, args.claim_report, args.project_dir, args.state_dir, args.run_id
            )
        elif args.command == "register-identity":
            result = register_identity(args.request, args.project_dir, args.catalog)
        elif args.command == "resolve-symbol":
            result = {"isin": resolve_symbol(
                args.catalog, args.project_dir, args.exchange, args.symbol,
                args.effective_date, args.cutoff
            )}
        elif args.command == "register-filing-metrics":
            result = register_filing_metrics(args.request, args.project_dir, args.catalog)
        elif args.command == "register-filing":
            result = register_filing(args.request, args.project_dir, args.catalog)
        elif args.command == "query-metrics":
            result = {"metrics": query_metrics(args.catalog, args.project_dir, args.isin,
                                                args.metric_name, args.period_end, args.cutoff)}
        elif args.command == "extract-text-filing":
            result = extract_text_filing(args.catalog, args.project_dir, args.filing_id)
        elif args.command == "query-text-chunks":
            result = {"chunks": query_text_chunks(args.catalog, args.project_dir,
                                                   args.filing_id, args.cutoff)}
        elif args.command == "extract-pdf-filing":
            result = extract_pdf_filing(args.catalog, args.project_dir, args.filing_id)
        elif args.command == "query-pdf-chunks":
            result = {"chunks": query_pdf_chunks(args.catalog, args.project_dir,
                                                  args.filing_id, args.cutoff)}
        elif args.command == "review-pdf-role":
            result = review_pdf_role(args.request, args.catalog, args.project_dir)
        elif args.command == "search-chunks":
            result = {"chunks": search_chunks(
                args.catalog, args.project_dir, args.issuer_id, args.query, args.cutoff,
                isin=args.isin, document_types=args.document_types,
                speaker_role=args.speaker_role, limit=args.limit,
                include_superseded=args.include_superseded)}
        elif args.command == "refresh-evidence":
            result = refresh_evidence(
                args.source_request, args.claims, args.project_dir, args.state_dir,
                args.run_id, args.previous_run_id,
            )
        else:
            state = run_company_research(args.entity, args.input, args.state_dir, args.run_id, args.fail_once)
            result = {"run_id": args.run_id, "status": state["status"]}
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Run failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
