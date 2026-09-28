import argparse
import json
import sys
from pathlib import Path

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
    args = parser.parse_args()
    try:
        state = run_company_research(args.entity, args.input, args.state_dir, args.run_id, args.fail_once)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Run failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"run_id": args.run_id, "status": state["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
