"""Append-only, sourced filings and typed metrics for strict live replay."""

import json
import re
import sqlite3
from contextlib import closing
from decimal import Decimal
from pathlib import Path

from .identity_store import DIGEST, SAFE_ID, _connect, _date, _source, _timestamp, _valid_isin
from .source_store import _hash_file, _read_existing


FILING_FIELDS = {
    "filing_id", "issuer_id", "isin", "source_id", "version_id",
    "document_type", "period_end", "published_at", "first_seen_at",
    "rights_status", "reviewer_id", "reviewed_at", "review_decision",
    "evidence_locator", "supersedes_filing_id", "metrics",
}
METRIC_FIELDS = {
    "metric_id", "metric_name", "value_decimal", "unit", "period_end",
    "period_kind", "reporting_scope", "value_kind", "evidence_locator",
    "supersedes_metric_id",
}
SERIES = ("isin", "metric_name", "period_end", "period_kind", "reporting_scope", "unit", "value_kind")
UNITS = {"INR", "INR_LAKH", "INR_CRORE", "PERCENT", "SHARES", "COUNT", "RATIO"}
DOCUMENTS = {"RESULTS", "ANNUAL_REPORT", "CONCALL_TRANSCRIPT", "PRESENTATION", "ANNOUNCEMENT"}
DECIMAL_TEXT = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")


def _id(value, name):
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise ValueError(f"{name} is invalid")
    return value


def _label(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise ValueError(f"{name} is invalid")
    return value


def _choice(value, choices, name):
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f"{name} is invalid")
    return value


def _decimal(value):
    if not isinstance(value, str) or len(value) > 40 or not DECIMAL_TEXT.fullmatch(value):
        raise ValueError("value_decimal must be a finite plain decimal")
    number = Decimal(value)
    if not number.is_finite() or number.copy_abs() > Decimal("1e20"):
        raise ValueError("value_decimal is out of range")
    if not number:
        return "0"
    return value.rstrip("0").rstrip(".") if "." in value else value


def _request(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("filing request must be valid JSON") from exc
    if not isinstance(value, dict) or set(value) != FILING_FIELDS:
        raise ValueError("filing request fields are invalid")
    for key in ("filing_id", "issuer_id", "source_id", "reviewer_id"):
        _id(value[key], key)
    if not isinstance(value["version_id"], str) or not DIGEST.fullmatch(value["version_id"]):
        raise ValueError("version_id is invalid")
    if not _valid_isin(value["isin"]):
        raise ValueError("ISIN is invalid")
    _choice(value["document_type"], DOCUMENTS, "document_type")
    if value["period_end"] is not None:
        _date(value["period_end"], "period_end")
    for key in ("published_at", "first_seen_at", "reviewed_at"):
        value[key] = _timestamp(value[key], key)
    if not value["published_at"] <= value["first_seen_at"] <= value["reviewed_at"]:
        raise ValueError("filing availability times are inconsistent")
    if value["rights_status"] != "REVIEWED" or value["review_decision"] != "CONFIRMED":
        raise ValueError("filing rights and review must be confirmed")
    _label(value["evidence_locator"], "evidence_locator")
    if value["supersedes_filing_id"] is not None:
        _id(value["supersedes_filing_id"], "supersedes_filing_id")
    if not isinstance(value["metrics"], list) or not value["metrics"]:
        raise ValueError("metrics must be nonempty")
    ids = set()
    series = set()
    for metric in value["metrics"]:
        if not isinstance(metric, dict) or set(metric) != METRIC_FIELDS:
            raise ValueError("metric fields are invalid")
        _id(metric["metric_id"], "metric_id")
        if metric["metric_id"] in ids:
            raise ValueError("metric_id repeats")
        ids.add(metric["metric_id"])
        _id(metric["metric_name"], "metric_name")
        metric["value_decimal"] = _decimal(metric["value_decimal"])
        _choice(metric["unit"], UNITS, "unit")
        _date(metric["period_end"], "metric period_end")
        _choice(metric["period_kind"], {"FY", "QUARTER", "YTD"}, "period_kind")
        _choice(metric["reporting_scope"], {"CONSOLIDATED", "STANDALONE"}, "reporting_scope")
        _choice(metric["value_kind"], {"REPORTED", "GUIDANCE"}, "value_kind")
        _label(metric["evidence_locator"], "metric evidence_locator")
        if metric["supersedes_metric_id"] is not None:
            _id(metric["supersedes_metric_id"], "supersedes_metric_id")
        key = (metric["metric_name"], metric["period_end"], metric["period_kind"],
               metric["reporting_scope"], metric["unit"], metric["value_kind"])
        if key in series:
            raise ValueError("metric series repeats in filing")
        series.add(key)
    return value


def _filing_source(request, project_dir):
    version_path = Path(project_dir) / "data/registry/sources" / request["source_id"] / f"{request['version_id']}.json"
    try:
        version = _read_existing(version_path)
        digest = version["raw_sha256"]
        if (version["source_id"] != request["source_id"] or version["version_id"] != request["version_id"]
                or not isinstance(digest, str) or not DIGEST.fullmatch(digest)
                or _hash_file(Path(project_dir) / "data/raw/sha256" / digest) != digest):
            raise ValueError("source version differs")
        if request["first_seen_at"] < _timestamp(version["retrieved_at"], "retrieved_at"):
            raise ValueError("first_seen_at precedes source retrieval")
        observed = _timestamp(version["observed_at"], "observed_at")
        retrieved = _timestamp(version["retrieved_at"], "retrieved_at")
        if not request["published_at"] <= observed <= retrieved <= request["first_seen_at"]:
            raise ValueError("source availability times are inconsistent")
        if version["entity"] != request["issuer_id"]:
            raise ValueError("source issuer differs")
        if version["source_kind"] != "EXCHANGE_FILING":
            raise ValueError("source kind is not an exchange filing")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("filing source version is missing or invalid") from exc
    return digest


def _tables(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS filings (
            filing_id TEXT PRIMARY KEY, issuer_id TEXT NOT NULL REFERENCES companies(issuer_id),
            isin TEXT NOT NULL REFERENCES securities(isin),
            source_id TEXT NOT NULL, version_id TEXT NOT NULL UNIQUE,
            raw_sha256 TEXT NOT NULL, document_type TEXT NOT NULL,
            period_end TEXT, published_at TEXT NOT NULL, first_seen_at TEXT NOT NULL,
            rights_status TEXT NOT NULL, reviewer_id TEXT NOT NULL,
            reviewed_at TEXT NOT NULL, review_decision TEXT NOT NULL,
            evidence_locator TEXT NOT NULL,
            supersedes_filing_id TEXT UNIQUE REFERENCES filings(filing_id),
            CHECK (rights_status='REVIEWED' AND review_decision='CONFIRMED')
        );
        CREATE TABLE IF NOT EXISTS metrics (
            metric_id TEXT PRIMARY KEY, filing_id TEXT NOT NULL REFERENCES filings(filing_id),
            isin TEXT NOT NULL REFERENCES securities(isin), metric_name TEXT NOT NULL,
            value_decimal TEXT NOT NULL, unit TEXT NOT NULL, period_end TEXT NOT NULL,
            period_kind TEXT NOT NULL, reporting_scope TEXT NOT NULL,
            value_kind TEXT NOT NULL, evidence_locator TEXT NOT NULL,
            supersedes_metric_id TEXT UNIQUE REFERENCES metrics(metric_id),
            CHECK (value_kind IN ('REPORTED', 'GUIDANCE')),
            CHECK (reporting_scope IN ('CONSOLIDATED', 'STANDALONE')),
            CHECK (period_kind IN ('FY', 'QUARTER', 'YTD')),
            CHECK (unit IN ('INR', 'INR_LAKH', 'INR_CRORE', 'PERCENT', 'SHARES', 'COUNT', 'RATIO'))
        );
        CREATE INDEX IF NOT EXISTS metrics_series ON metrics(isin, metric_name, period_end);
        CREATE INDEX IF NOT EXISTS filings_cutoff ON filings(issuer_id, published_at, first_seen_at);
        CREATE TRIGGER IF NOT EXISTS filings_no_update BEFORE UPDATE ON filings
            BEGIN SELECT RAISE(ABORT, 'filings are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS filings_no_delete BEFORE DELETE ON filings
            BEGIN SELECT RAISE(ABORT, 'filings are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS metrics_no_update BEFORE UPDATE ON metrics
            BEGIN SELECT RAISE(ABORT, 'metrics are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS metrics_no_delete BEFORE DELETE ON metrics
            BEGIN SELECT RAISE(ABORT, 'metrics are append-only'); END;
    """)


def _insert_or_match(db, table, key, row):
    old = db.execute(f"SELECT * FROM {table} WHERE {key}=?", (row[key],)).fetchone()
    if old is not None:
        if dict(old) != row:
            raise ValueError(f"{table} ID conflicts with an existing row")
        return False
    db.execute(f"INSERT INTO {table} ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))
    return True


def register_filing_metrics(request_path: Path, project_dir: Path, catalog_path: Path) -> dict:
    """Atomically add a reviewed filing and its reported or guidance metrics."""
    request = _request(request_path)
    digest = _filing_source(request, project_dir)
    with closing(_connect(catalog_path)) as db:
        _tables(db)
        with db:
            db.execute("BEGIN IMMEDIATE")
            security = db.execute("SELECT * FROM securities WHERE isin=?", (request["isin"],)).fetchone()
            company = db.execute("SELECT * FROM companies WHERE issuer_id=?", (request["issuer_id"],)).fetchone()
            if security is None or company is None or security["issuer_id"] != request["issuer_id"]:
                raise ValueError("filing issuer and ISIN do not match reviewed identity")
            for identity in (security, company):
                if identity["review_decision"] != "CONFIRMED" or identity["reviewed_at"] > request["reviewed_at"]:
                    raise ValueError("issuer identity was not reviewed at filing review time")
                _source({"source_id": identity["source_id"], "version_id": identity["version_id"],
                         "first_seen_at": identity["first_seen_at"]}, project_dir)
            filing = {key: request[key] for key in (
                "filing_id", "issuer_id", "isin", "source_id", "version_id", "document_type",
                "period_end", "published_at", "first_seen_at", "rights_status", "reviewer_id",
                "reviewed_at", "review_decision", "evidence_locator", "supersedes_filing_id",
            )}
            filing["raw_sha256"] = digest
            if request["supersedes_filing_id"] is not None:
                prior = db.execute("SELECT * FROM filings WHERE filing_id=?", (request["supersedes_filing_id"],)).fetchone()
                if prior is None or any(prior[k] != filing[k] for k in ("issuer_id", "isin", "document_type", "period_end")) or prior["published_at"] >= filing["published_at"]:
                    raise ValueError("filing revision is invalid")
            new_filing = _insert_or_match(db, "filings", "filing_id", filing)
            if not new_filing:
                current = {row[0] for row in db.execute("SELECT metric_id FROM metrics WHERE filing_id=?", (filing["filing_id"],))}
                if current != {metric["metric_id"] for metric in request["metrics"]}:
                    raise ValueError("filing replay has different metrics")
            for metric in request["metrics"]:
                row = {"metric_id": metric["metric_id"], "filing_id": filing["filing_id"],
                       "isin": filing["isin"], **{key: metric[key] for key in (
                           "metric_name", "value_decimal", "unit", "period_end", "period_kind",
                           "reporting_scope", "value_kind", "evidence_locator", "supersedes_metric_id",
                       )}}
                if metric["supersedes_metric_id"] is not None:
                    prior = db.execute("""SELECT m.*, f.published_at FROM metrics m
                        JOIN filings f ON f.filing_id=m.filing_id WHERE m.metric_id=?""",
                        (metric["supersedes_metric_id"],)).fetchone()
                    if prior is None or any(prior[key] != row[key] for key in SERIES) or prior["published_at"] >= filing["published_at"]:
                        raise ValueError("metric revision is invalid")
                else:
                    existing = db.execute("""SELECT metric_id FROM metrics WHERE isin=? AND metric_name=?
                        AND period_end=? AND period_kind=? AND reporting_scope=? AND unit=? AND value_kind=?""",
                        tuple(row[key] for key in SERIES)).fetchone()
                    if existing is not None and existing["metric_id"] != row["metric_id"]:
                        raise ValueError("metric series needs a revision link")
                _insert_or_match(db, "metrics", "metric_id", row)
    return {"filing_id": filing["filing_id"], "metric_ids": [m["metric_id"] for m in request["metrics"]],
            "publication_allowed": False}


def query_metrics(catalog_path: Path, project_dir: Path, isin: str, metric_name: str,
                  period_end: str, cutoff_timestamp: str) -> list[dict]:
    """Return reviewed metric leaves known at a strict live cutoff."""
    if not _valid_isin(isin):
        raise ValueError("ISIN is invalid")
    _id(metric_name, "metric_name")
    _date(period_end, "period_end")
    cutoff = _timestamp(cutoff_timestamp, "cutoff_timestamp")
    if not Path(catalog_path).is_file():
        return []
    with closing(_connect(catalog_path)) as db:
        _tables(db)
        security = db.execute("""SELECT s.*, c.source_id AS company_source_id,
            c.version_id AS company_version_id, c.first_seen_at AS company_first_seen_at,
            c.reviewed_at AS company_reviewed_at, c.review_decision AS company_review_decision
            FROM securities s JOIN companies c ON c.issuer_id=s.issuer_id WHERE s.isin=?""", (isin,)).fetchone()
        if security is None:
            return []
        if (security["announced_at"] > cutoff or security["first_seen_at"] > cutoff
                or security["reviewed_at"] > cutoff or security["company_first_seen_at"] > cutoff
                or security["company_reviewed_at"] > cutoff):
            return []
        if security["review_decision"] != "CONFIRMED" or security["company_review_decision"] != "CONFIRMED":
            raise ValueError("issuer identity is not confirmed")
        for source_id, version_id, first_seen in (
            (security["source_id"], security["version_id"], security["first_seen_at"]),
            (security["company_source_id"], security["company_version_id"], security["company_first_seen_at"]),
        ):
            _source({"source_id": source_id, "version_id": version_id,
                     "first_seen_at": first_seen}, project_dir)
        rows = db.execute("""SELECT m.*, f.issuer_id, f.isin AS filing_isin,
            f.source_id, f.version_id, f.raw_sha256,
            f.document_type, f.published_at, f.first_seen_at, f.reviewed_at,
            f.rights_status, f.review_decision
            FROM metrics m JOIN filings f ON f.filing_id=m.filing_id
            WHERE m.isin=? AND m.metric_name=? AND m.period_end=?
              AND f.published_at<=? AND f.first_seen_at<=? AND f.reviewed_at<=?""",
            (isin, metric_name, period_end, cutoff, cutoff, cutoff)).fetchall()
        if not rows:
            return []
        grouped = {}
        for row in rows:
            if (row["issuer_id"] != security["issuer_id"] or row["filing_isin"] != isin
                    or row["rights_status"] != "REVIEWED" or row["review_decision"] != "CONFIRMED"):
                raise ValueError("metric issuer, rights, or review is invalid")
            for key, choices in (("unit", UNITS), ("period_kind", {"FY", "QUARTER", "YTD"}),
                                 ("reporting_scope", {"CONSOLIDATED", "STANDALONE"}),
                                 ("value_kind", {"REPORTED", "GUIDANCE"})):
                _choice(row[key], choices, key)
            if _decimal(row["value_decimal"]) != row["value_decimal"]:
                raise ValueError("stored metric decimal is invalid")
            if row["supersedes_metric_id"] is not None:
                prior = db.execute("""SELECT m.*, f.published_at FROM metrics m
                    JOIN filings f ON f.filing_id=m.filing_id WHERE m.metric_id=?""",
                    (row["supersedes_metric_id"],)).fetchone()
                if (prior is None or any(prior[key] != row[key] for key in SERIES)
                        or prior["published_at"] >= row["published_at"]):
                    raise ValueError("stored metric revision is invalid")
            digest = _filing_source(row, project_dir)
            if digest != row["raw_sha256"]:
                raise ValueError("filing source digest differs from catalog")
            grouped.setdefault(tuple(row[key] for key in SERIES), []).append(row)
        results = []
        for rows_in_series in grouped.values():
            revised = {row["supersedes_metric_id"] for row in rows_in_series if row["supersedes_metric_id"]}
            leaves = [row for row in rows_in_series if row["metric_id"] not in revised]
            if len(leaves) != 1:
                raise ValueError("metric revisions resolve ambiguously")
            row = leaves[0]
            results.append({key: row[key] for key in (
                "metric_id", "filing_id", "isin", "metric_name", "value_decimal", "unit",
                "period_end", "period_kind", "reporting_scope", "value_kind",
                "evidence_locator", "source_id", "version_id", "document_type",
                "published_at", "first_seen_at", "reviewed_at",
            )} | {"availability_mode": "LIVE_STRICT", "publication_allowed": False})
        return sorted(results, key=lambda item: (item["period_kind"], item["reporting_scope"], item["unit"], item["value_kind"]))
