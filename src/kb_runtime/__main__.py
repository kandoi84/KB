import argparse
import json
import sys
from pathlib import Path

from .analysis_judgment import analyze_judgment
from .case_snapshot import open_sandbox_case
from .claim_lineage import evaluate_claims
from .claim_review import review_claims
from .evidence_refresh import refresh_evidence
from .evidence_workflow import run_evidence_workflow
from .filtered_retrieval import search_chunks
from .gap_attempt import attempt_gap
from .identity_store import register_identity, resolve_symbol
from .metric_store import query_metrics, register_filing, register_filing_metrics
from .outcome_postmortem import append_outcome_observation, evaluate_due_case
from .passage_evidence import evaluate_passages
from .pdf_chunks import extract_pdf_filing, query_pdf_chunks, review_pdf_role
from .retrieval_eval import evaluate_retrieval
from .source_refresh import evaluate_sources
from .source_route import select_gap_route
from .source_store import record_source
from .text_chunks import extract_text_filing, query_text_chunks
from .trust_observation import record_trust_observation
from .trust_report import build_trust_report
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
    review = subparsers.add_parser("review-claims", help="Freeze internal claim review decisions")
    review.add_argument("--packet", type=Path, required=True)
    review.add_argument("--claim-report", type=Path, required=True)
    review.add_argument("--passage-report", type=Path, required=True)
    review.add_argument("--run-id", required=True)
    review.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    review.add_argument("--catalog", type=Path,
                        default=Path("projects/indian-equities/data/registry/identity.sqlite"))
    review.add_argument("--state-dir", type=Path, default=Path("projects/indian-equities/state"))
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
    retrieval_eval = subparsers.add_parser("eval-retrieval", help="Score a reviewed text retrieval gold set")
    retrieval_eval.add_argument("--gold", type=Path, required=True)
    retrieval_eval.add_argument("--answers", type=Path)
    retrieval_eval.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    retrieval_eval.add_argument("--catalog", type=Path,
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
    workflow = subparsers.add_parser("run-evidence-workflow", help="Run pinned evidence skills, then resume after human review")
    workflow.add_argument("--source-request", type=Path, required=True)
    workflow.add_argument("--claims", type=Path, required=True)
    workflow.add_argument("--passage-packet", type=Path, required=True)
    workflow.add_argument("--review-packet", type=Path)
    workflow.add_argument("--contract", type=Path, required=True)
    workflow.add_argument("--run-id", required=True)
    workflow.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    workflow.add_argument("--catalog", type=Path,
                          default=Path("projects/indian-equities/data/registry/identity.sqlite"))
    workflow.add_argument("--state-dir", type=Path, default=Path("projects/indian-equities/state"))
    judgment = subparsers.add_parser("analyze-judgment", help="Freeze an internal analyst worksheet")
    judgment.add_argument("--packet", type=Path, required=True)
    judgment.add_argument("--claim-review-report", type=Path, required=True)
    judgment.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    judgment.add_argument("--catalog", type=Path,
                          default=Path("projects/indian-equities/data/registry/identity.sqlite"))
    judgment.add_argument("--state-dir", type=Path, default=Path("projects/indian-equities/state"))
    judgment.add_argument("--run-id", required=True)
    gap = subparsers.add_parser("attempt-gap", help="Freeze one reviewed local source attempt")
    gap.add_argument("--packet", type=Path, required=True)
    gap.add_argument("--claim-report", type=Path, required=True)
    gap.add_argument("--source-report", type=Path, required=True)
    gap.add_argument("--source-request", type=Path, required=True)
    gap.add_argument("--claims", type=Path, required=True)
    gap.add_argument("--raw-file", type=Path)
    gap.add_argument("--metadata", type=Path)
    gap.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    gap.add_argument("--state-dir", type=Path, default=Path("projects/indian-equities/state"))
    gap.add_argument("--attempt-id", required=True)
    route = subparsers.add_parser("plan-gap-route", help="Freeze a non-fetching source route decision")
    route.add_argument("--packet", type=Path, required=True)
    route.add_argument("--claim-report", type=Path, required=True)
    route.add_argument("--source-report", type=Path, required=True)
    route.add_argument("--source-request", type=Path, required=True)
    route.add_argument("--claims", type=Path, required=True)
    route.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    route.add_argument("--state-dir", type=Path, default=Path("projects/indian-equities/state"))
    route.add_argument("--route-id", required=True)
    observation = subparsers.add_parser("record-trust-observation", help="Freeze an independent attempt label")
    observation.add_argument("--observation", type=Path, required=True)
    observation.add_argument("--classification-packet", type=Path, required=True)
    observation.add_argument("--attempt-intent", type=Path, required=True)
    observation.add_argument("--attempt-result", type=Path, required=True)
    observation.add_argument("--state-dir", type=Path, default=Path("projects/indian-equities/state"))
    trust = subparsers.add_parser("build-trust-report", help="Summarize diagnostic trust labels")
    trust.add_argument("--observation-id", action="append", required=True)
    trust.add_argument("--cohort-filter", type=Path, help="JSON object of exact cohort filters")
    trust.add_argument("--state-dir", type=Path, default=Path("projects/indian-equities/state"))
    trust.add_argument("--report-id", required=True)
    case = subparsers.add_parser("open-sandbox-case", help="Freeze a replay-verified internal case")
    for name in ("packet", "source-request", "claim-request", "passage-packet",
                 "review-packet", "workflow-contract", "claim-review-report",
                 "analysis-packet", "analysis-report"):
        case.add_argument(f"--{name}", type=Path, required=True)
    case.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
    case.add_argument("--catalog", type=Path,
                      default=Path("projects/indian-equities/data/registry/identity.sqlite"))
    case.add_argument("--state-dir", type=Path, default=Path("projects/indian-equities/state"))
    for command, description in (("append-case-outcome", "Append a sourced sandbox outcome"),
                                 ("evaluate-due-case", "Freeze a due sandbox review")):
        outcome = subparsers.add_parser(command, help=description)
        outcome.add_argument("--packet", type=Path, required=True)
        outcome.add_argument("--case-packet", type=Path, required=True)
        for name in ("source-request", "claim-request", "passage-packet", "review-packet",
                     "workflow-contract", "claim-review-report", "analysis-packet", "analysis-report"):
            outcome.add_argument(f"--{name}", type=Path, required=True)
        outcome.add_argument("--project-dir", type=Path, default=Path("projects/indian-equities"))
        outcome.add_argument("--catalog", type=Path,
                             default=Path("projects/indian-equities/data/registry/identity.sqlite"))
        outcome.add_argument("--state-dir", type=Path, default=Path("projects/indian-equities/state"))
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
        elif args.command == "review-claims":
            result = review_claims(
                args.packet, args.claim_report, args.passage_report, args.project_dir,
                args.catalog, args.state_dir, args.run_id,
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
        elif args.command == "eval-retrieval":
            result = evaluate_retrieval(args.gold, args.catalog, args.project_dir, args.answers)
        elif args.command == "refresh-evidence":
            result = refresh_evidence(
                args.source_request, args.claims, args.project_dir, args.state_dir,
                args.run_id, args.previous_run_id,
            )
        elif args.command == "run-evidence-workflow":
            result = run_evidence_workflow(
                args.source_request, args.claims, args.passage_packet, args.review_packet,
                args.contract, args.project_dir, args.catalog, args.state_dir, args.run_id,
            )
        elif args.command == "analyze-judgment":
            result = analyze_judgment(args.packet, args.claim_review_report, args.project_dir,
                                      args.catalog, args.state_dir, args.run_id)
        elif args.command == "attempt-gap":
            result = attempt_gap(
                args.packet, args.claim_report, args.source_report,
                args.source_request, args.claims, args.raw_file, args.metadata,
                args.project_dir, args.state_dir, args.attempt_id,
            )
        elif args.command == "plan-gap-route":
            result = select_gap_route(
                args.packet, args.claim_report, args.source_report,
                args.source_request, args.claims, args.project_dir, args.state_dir,
                args.route_id,
            )
        elif args.command == "record-trust-observation":
            result = record_trust_observation(
                args.observation, args.classification_packet, args.attempt_intent,
                args.attempt_result, args.state_dir,
            )
        elif args.command == "build-trust-report":
            cohort_filter = (json.loads(args.cohort_filter.read_text(encoding="utf-8"))
                             if args.cohort_filter else {})
            result = build_trust_report(args.observation_id, cohort_filter,
                                        args.state_dir, args.report_id)
        elif args.command == "open-sandbox-case":
            result = open_sandbox_case(
                args.packet, source_request=args.source_request,
                claim_request=args.claim_request, passage_packet=args.passage_packet,
                review_packet=args.review_packet, workflow_contract=args.workflow_contract,
                claim_review_report=args.claim_review_report,
                analysis_packet=args.analysis_packet, analysis_report=args.analysis_report,
                project_dir=args.project_dir, catalog=args.catalog, state_dir=args.state_dir,
            )
        elif args.command in {"append-case-outcome", "evaluate-due-case"}:
            replay_inputs = {name: getattr(args, name) for name in (
                "source_request", "claim_request", "passage_packet", "review_packet",
                "workflow_contract", "claim_review_report", "analysis_packet", "analysis_report")}
            operation = (append_outcome_observation if args.command == "append-case-outcome"
                         else evaluate_due_case)
            result = operation(args.packet, case_packet_path=args.case_packet,
                               case_replay_inputs=replay_inputs, project_dir=args.project_dir,
                               catalog=args.catalog, state_dir=args.state_dir)
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
