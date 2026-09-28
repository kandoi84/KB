import argparse
import json
import sys
from pathlib import Path

from .claim_lineage import evaluate_claims
from .evidence_refresh import refresh_evidence
from .identity_store import register_identity, resolve_symbol
from .metric_store import query_metrics, register_filing_metrics
from .passage_evidence import evaluate_passages
from .source_refresh import evaluate_sources
from .source_store import record_source
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
    metric_query = subparsers.add_parser("query-metrics", help="Read metrics at a strict live cutoff")
    metric_query.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    metric_query.add_argument("--catalog", type=Path,
                              default=Path("projects/indian-equities/data/registry/identity.sqlite"))
    metric_query.add_argument("--isin", required=True)
    metric_query.add_argument("--metric-name", required=True)
    metric_query.add_argument("--period-end", required=True)
    metric_query.add_argument("--cutoff", required=True)
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
        elif args.command == "query-metrics":
            result = {"metrics": query_metrics(args.catalog, args.project_dir, args.isin,
                                                args.metric_name, args.period_end, args.cutoff)}
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
