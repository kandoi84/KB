"""Diagnostic, write-once summaries of frozen trust observations."""

import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from .claim_lineage import SAFE_ID
from .gap_attempt import _read_sealed, _sealed, _time, _write_once
from .trust_observation import FAILURE_CLASSES, LABEL_FIELDS, LABEL_VALUES, PERIOD, STATUS_FAILURE


OBSERVATION_FIELDS = {
    "observation_id", "attempt_id", "attempt_intent_id", "attempt_result_id",
    "attempt_status", "classification_packet_hash", "observation_hash", "origin",
    "declared_origin", "adjudicator_id", "adjudicated_at", "rubric_version",
    "entity", "source_id", "adapter_id", "adapter_version",
    "rights_reference_hash", "rights_policy_hash", "attempted_at", "source_authority",
    "document_type", "reporting_period", "raw_sha256", "labels",
    "failure_class", "publication_allowed", "observation_digest",
}
FILTER_FIELDS = {"adapter_id", "adapter_version", "rights_policy_hash",
                 "source_authority", "document_type", "reporting_period",
                 "rubric_version", "attempt_status"}
STRATUM_FIELDS = ("adapter_id", "adapter_version", "rights_policy_hash",
                  "source_authority", "document_type", "rubric_version")
Z95 = 1.959963984540054


def _observation(state: Path, observation_id: str) -> dict:
    if not isinstance(observation_id, str) or not SAFE_ID.fullmatch(observation_id):
        raise ValueError("observation ID is unsafe")
    path = state / "trust_observations" / f"{observation_id}.json"
    try:
        row = _read_sealed(path, "observation_digest")
    except OSError as exc:
        raise ValueError("trust observation is unavailable") from exc
    if set(row) != OBSERVATION_FIELDS or row["observation_id"] != observation_id:
        raise ValueError("trust observation schema is invalid")
    for field in ("attempt_id", "attempt_intent_id", "attempt_result_id",
                  "adjudicator_id", "entity", "source_id", "adapter_id",
                  "source_authority", "document_type"):
        if not isinstance(row[field], str) or not row[field]:
            raise ValueError("trust observation identity is invalid")
    if not isinstance(row["adapter_version"], int) or isinstance(row["adapter_version"], bool) or row["adapter_version"] <= 0:
        raise ValueError("trust observation adapter version is invalid")
    for field in ("classification_packet_hash", "observation_hash",
                  "rights_reference_hash", "rights_policy_hash"):
        value = row[field]
        if not isinstance(value, str) or len(value) != 64 or any(
                char not in "0123456789abcdef" for char in value):
            raise ValueError("trust observation hash is invalid")
    raw = row["raw_sha256"]
    if row["attempt_status"] == "RECORDED":
        if not isinstance(raw, str) or len(raw) != 64 or any(
                char not in "0123456789abcdef" for char in raw):
            raise ValueError("recorded attempt raw hash is invalid")
    elif raw is not None:
        raise ValueError("blocked attempt cannot claim raw bytes")
    if (row["declared_origin"] == "SYNTHETIC_FIXTURE"
            and row["origin"] != "SYNTHETIC_FIXTURE") or (
            row["declared_origin"] == "REAL_OBSERVED"
            and row["origin"] != "UNVERIFIED"):
        raise ValueError("trust observation origin is unsupported")
    if (row["declared_origin"] not in {"SYNTHETIC_FIXTURE", "REAL_OBSERVED"}
            or row["publication_allowed"] is not False
            or row["rubric_version"] != "trust-v1"
            or row["document_type"] != "EXCHANGE_FILING"
            or row["source_authority"] not in {"NSE", "BSE"}
            or not isinstance(row["reporting_period"], str)
            or not PERIOD.fullmatch(row["reporting_period"])
            or row["failure_class"] not in FAILURE_CLASSES
            or row["failure_class"] != STATUS_FAILURE.get(row["attempt_status"])):
        raise ValueError("trust observation classification is invalid")
    labels = row["labels"]
    if (not isinstance(labels, dict) or set(labels) != LABEL_FIELDS
            or any(not isinstance(label, str) or label not in LABEL_VALUES
                   for label in labels.values())
            or labels["raw_replay"] != ("UNVERIFIED" if row["attempt_status"] == "RECORDED"
                                         else "NOT_APPLICABLE")):
        raise ValueError("trust observation labels are invalid")
    if _time(row["adjudicated_at"], "adjudicated_at") < _time(
            row["attempted_at"], "attempted_at"):
        raise ValueError("trust observation time is invalid")
    return row


def _metric(rows: list[dict], name: str) -> dict:
    counts = Counter(row["labels"][name] for row in rows)
    denominator = counts["PASS"] + counts["FAIL"]
    result = {"pass": counts["PASS"], "fail": counts["FAIL"],
              "unresolved": counts["UNRESOLVED"],
              "unverified": counts["UNVERIFIED"],
              "not_applicable": counts["NOT_APPLICABLE"],
              "denominator": denominator}
    if denominator == 0:
        return {**result, "status": "NO_ESTIMATE", "rate": None, "ci95": None}
    rate = counts["PASS"] / denominator
    z2 = Z95 * Z95
    center = (rate + z2 / (2 * denominator)) / (1 + z2 / denominator)
    half = Z95 * math.sqrt(rate * (1 - rate) / denominator + z2 / (4 * denominator ** 2)) / (1 + z2 / denominator)
    return {**result, "status": "DIAGNOSTIC_ONLY", "rate": rate,
            "ci95": [max(0.0, center - half), min(1.0, center + half)]}


def _summary(rows: list[dict]) -> dict:
    counts = {"attempts": len(rows), "issuers": len({row["entity"] for row in rows}),
              "reporting_periods": len({row["reporting_period"] for row in rows}),
              "verified_real_attempts": 0}
    volume_met = (counts["attempts"] >= 30 and counts["issuers"] >= 5
                  and counts["reporting_periods"] >= 2)
    reasons = []
    if counts["attempts"] < 30:
        reasons.append("FEWER_THAN_30_ATTEMPTS")
    if counts["issuers"] < 5:
        reasons.append("FEWER_THAN_5_ISSUERS")
    if counts["reporting_periods"] < 2:
        reasons.append("FEWER_THAN_2_PERIODS")
    if rows and not all(row["origin"] == "REAL_OBSERVED" for row in rows):
        reasons.append("UNVERIFIED_REAL_ORIGIN")
    reasons.append("SELECTION_NOT_RANDOMIZED")
    lags = [(datetime.fromisoformat(row["adjudicated_at"])
             - datetime.fromisoformat(row["attempted_at"])).total_seconds()
            for row in rows]
    lag = ({"status": "DIAGNOSTIC_ONLY", "count": len(lags), "min": min(lags),
            "median": median(lags), "max": max(lags)} if lags
           else {"status": "NO_ESTIMATE", "count": 0, "min": None,
                 "median": None, "max": None})
    return {
        "count": len(rows), "sample_counts": counts, "volume_gate_met": volume_met,
        "sample_status": "INSUFFICIENT_SAMPLE", "sample_reasons": reasons,
        "metrics": {name: _metric(rows, name) for name in sorted(LABEL_FIELDS)} if rows else {},
        "failure_classes": dict(sorted(Counter(row["failure_class"] for row in rows).items())),
        "attempt_statuses": dict(sorted(Counter(row["attempt_status"] for row in rows).items())),
        "breakdowns": {
            "issuer": dict(sorted(Counter(row["entity"] for row in rows).items())),
            "reporting_period": dict(sorted(Counter(row["reporting_period"] for row in rows).items())),
            "failure_class": dict(sorted(Counter(row["failure_class"] for row in rows).items())),
        },
        "attempt_date_range": ([min(_time(row["attempted_at"], "attempted_at")
                                    for row in rows).astimezone(timezone.utc).isoformat(),
                                max(_time(row["attempted_at"], "attempted_at")
                                    for row in rows).astimezone(timezone.utc).isoformat()]
                               if rows else None),
        "adjudication_lag_seconds": lag,
    }


def build_trust_report(observation_ids: list[str], cohort_filter: dict,
                       state_dir: Path, report_id: str) -> dict:
    """Report operational labels only; local digest continuity is not source authentication."""
    if not isinstance(report_id, str) or not SAFE_ID.fullmatch(report_id):
        raise ValueError("report ID is unsafe")
    if (not isinstance(observation_ids, list)
            or any(not isinstance(item, str) for item in observation_ids)
            or len(set(observation_ids)) != len(observation_ids)):
        raise ValueError("observation IDs are invalid or repeated")
    if (not isinstance(cohort_filter, dict) or not set(cohort_filter) <= FILTER_FIELDS
            or any((not isinstance(value, int) or isinstance(value, bool) or value <= 0)
                   if field == "adapter_version" else
                   (not isinstance(value, str) or not value)
                   for field, value in cohort_filter.items())):
        raise ValueError("cohort filter is invalid")
    state = Path(state_dir)
    population = [_observation(state, item) for item in sorted(observation_ids)]
    attempts = [row["attempt_id"] for row in population]
    if len(set(attempts)) != len(attempts):
        raise ValueError("one attempt has duplicate trust observations")
    included = [row for row in population if all(row[field] == value
                for field, value in cohort_filter.items())]
    grouped = defaultdict(list)
    for row in included:
        grouped[tuple(row[field] for field in STRATUM_FIELDS)].append(row)
    strata = [{"cohort": dict(zip(STRATUM_FIELDS, key)), **_summary(rows)}
              for key, rows in sorted(grouped.items())]
    common = _summary(included) if len(strata) == 1 else _summary([])
    overall = _summary(included)
    value = {
        "report_id": report_id,
        "observation_ids": sorted(observation_ids),
        "cohort_filter": dict(sorted(cohort_filter.items())),
        "included_count": len(included),
        "excluded_count": len(population) - len(included),
        "selection": {"method": "EXPLICIT_IDS", "seed": None,
                      "population_count": len(population),
                      "population_scope": "PROVIDED_IDS_ONLY",
                      "excluded_ids": sorted(row["observation_id"] for row in population
                                             if row not in included)},
        "sample_counts": overall["sample_counts"],
        "volume_gate_met": overall["volume_gate_met"] and len(strata) == 1,
        "sample_status": "INSUFFICIENT_SAMPLE",
        "sample_reasons": overall["sample_reasons"] + (["MIXED_COHORT"] if len(strata) > 1 else []),
        "metrics": common["metrics"],
        "failure_classes": overall["failure_classes"],
        "attempt_statuses": overall["attempt_statuses"],
        "adjudication_lag_seconds": overall["adjudication_lag_seconds"],
        "acquisition_lag": {"status": "NO_ESTIMATE", "reason": "SOURCE_DATE_NOT_IN_OBSERVATION"},
        "probability_calibration": "NOT_CALIBRATABLE",
        "strata": strata,
        "integrity_scope": "LOCAL_DIGEST_AND_STRUCTURE_ONLY",
    }
    report = _sealed(value, "report_digest")
    _write_once(state / "trust_reports" / f"{report_id}.json", report, "report_digest")
    return report
