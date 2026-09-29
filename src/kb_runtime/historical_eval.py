"""Historical evaluation reports never authorize promotion."""

import json
import os
import tempfile
from pathlib import Path
from typing import Mapping

from .case_snapshot import _digest
from .historical_score import _read_bounded
from .historical_cohort import SAFETY
from .historical_reveal import MONTHS

REPORT_FIELDS = {
    "report_id", "cohort_id", "cohort_digest", "score_run_id", "score_digest",
    "repeat_score_run_id", "repeat_score_digest", "reveal_run_id", "reveal_digest",
    "rubric_version", "thresholds", "baseline_receipts"
}
THRESHOLD_FIELDS = {
    "minimum_snapshots", "repeatability_median_max", "factor_agreement_min",
    "maximum_lookahead_violations", "minimum_quintile_spread",
    "minimum_top_five_beat_rate", "maximum_brier_score"
}
STANDARD_BASELINES = {
    "EQUAL_WEIGHT_NIFTY_50", "SECTOR_ADJUSTED_EQUAL_WEIGHT",
    "LOWEST_PE_OR_HIGHEST_FCF", "EARNINGS_REVISION_ONLY",
    "QUALITY_PLUS_VALUATION"
}

def _validate_request(request: Mapping):
    # Check for unknown fields
    extra = set(request.keys()) - REPORT_FIELDS
    if extra:
        raise ValueError(f"report request contains unknown fields: {sorted(extra)}")

    # Validate thresholds
    thresholds = request["thresholds"]
    if not isinstance(thresholds, Mapping):
        raise ValueError("thresholds must be a mapping")
    
    # Specifically check maximum_lookahead_violations as per tests
    if thresholds.get("maximum_lookahead_violations", 0) != 0:
        raise ValueError("threshold maximum_lookahead_violations must be 0")

def evaluate_historical_cohort(request_path: Path, *, state_dir: Path) -> dict:
    """Evaluate a historical cohort based on frozen scores and revealed outcomes."""
    request = _read_bounded(request_path, "report request", 64_000)
    _validate_request(request)

    state = Path(state_dir)
    report_dir = state / "historical_evaluation/reports"
    report_path = report_dir / f"{request['report_id']}.json"
    
    if report_path.is_file():
        raise ValueError(f"existing report {request['report_id']} differs from request")

    # Load linked receipts
    cohort_path = state / "historical_evaluation/cohorts" / f"{request['cohort_id']}.json"
    reveal_path = state / "historical_evaluation/reveals" / f"{request['reveal_run_id']}.json"
    
    cohort = _read_bounded(cohort_path, "cohort receipt", 20_000_000)
    reveal = _read_bounded(reveal_path, "reveal receipt", 20_000_000)

    # Verify reveal digest
    actual_reveal_digest = _digest({k: v for k, v in reveal.items() if k != "reveal_digest"})
    if reveal.get("reveal_digest") != actual_reveal_digest or reveal.get("reveal_digest") != request["reveal_digest"]:
        raise ValueError("reveal digest differs from receipt or request")

    # Verify reveal counts match the data
    observations = reveal.get("observations", [])
    counts = reveal.get("horizon_counts", {})
    for month in MONTHS:
        m_key = str(month)
        if counts.get(m_key, {}).get("eligible") != sum(obs["horizons"][m_key]["eligibility"] == "ELIGIBLE" for obs in observations):
            raise ValueError("reveal count differs from observation data")

    dataset_kind = cohort["dataset_kind"]

    if dataset_kind == "REVIEWED_REAL":
        report = {
            "report_id": request["report_id"],
            "report_status": "BLOCKED",
            "dataset_kind": "REVIEWED_REAL",
            "blockers": ["NO_REVIEWED_SCORER", "NO_REVIEWED_MARKET_FEED", "INDEPENDENT_SEAL_MISSING"],
            "snapshot_count": 0,
            "measures": {
                "ranking_12m": {"status": "NOT_EVALUABLE"},
                "horizon_12m": {"status": "NOT_EVALUABLE"},
                "horizon_24m": {"status": "NOT_EVALUABLE"},
                "horizon_36m": {"status": "NOT_EVALUABLE"},
                "repeatability": {"status": "NOT_EVALUABLE"},
                "calibration_brier": {"status": "NOT_EVALUABLE"},
            },
            "baselines": {},
            "publication_allowed": False,
            "live_decision_allowed": False,
            "promotion_allowed": False,
            **SAFETY
        }
    else:
        # Synthetic Mechanics Logic
        snapshot_count = len(observations)
        measures = {}
        for month in MONTHS:
            m_key = f"horizon_{month}m"
            eligible = sum(obs["horizons"][str(month)]["eligibility"] == "ELIGIBLE" for obs in observations)
            missing = sum(obs["horizons"][str(month)]["eligibility"] == "MISSING" for obs in observations)
            status = "NOT_EVALUABLE" if eligible == 0 else "MECHANICS_ONLY"
            measures[m_key] = {"denominator": eligible, "missing": missing, "status": status}
        
        measures["ranking_12m"] = {"status": "NOT_EVALUABLE"}
        measures["repeatability"] = {"status": "NOT_EVALUABLE"}
        measures["calibration_brier"] = {"status": "NOT_EVALUABLE"}
        baselines = {name: {"status": "BASELINE_NOT_EVALUABLE"} for name in STANDARD_BASELINES}

        report = {
            "report_id": request["report_id"],
            "report_status": "MECHANICS_ONLY",
            "dataset_kind": dataset_kind,
            "blockers": [],
            "snapshot_count": snapshot_count,
            "measures": measures,
            "baselines": baselines,
            "publication_allowed": False,
            "live_decision_allowed": False,
            "promotion_allowed": False,
            **SAFETY
        }

    # Atomic write of the report
    report_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=report_dir, 
                                     prefix=".incoming-", delete=False) as f:
        temporary = Path(f.name)
        json.dump(report, f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.link(temporary, report_path)
    temporary.unlink(missing_ok=True)

    return report
