"""Sourced, append-only issuer and security identity catalog."""

import hashlib
import json
import re
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

from .source_store import _hash_file, _read_existing


FIELDS = {
    "issuer_id", "legal_name", "isin", "security_type", "listed_from", "listed_to",
    "exchange", "symbol", "valid_from", "valid_to", "announced_at", "first_seen_at",
    "source_id", "version_id",
    "reviewer_id", "reviewed_at", "review_decision", "evidence_locator",
}
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]\Z")


def _date(value, name):
    try:
        if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
            raise ValueError
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO date") from exc
    return value


def _timestamp(value, name):
    try:
        stamp = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError as exc:
        raise ValueError(f"{name} must be timezone-aware") from exc
    if stamp is None or stamp.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return stamp.astimezone(timezone.utc).isoformat()


def _valid_isin(value):
    if not isinstance(value, str) or not ISIN.fullmatch(value):
        return False
    digits = "".join(str(ord(char) - 55) if char.isalpha() else char for char in value)
    total = 0
    for index, character in enumerate(reversed(digits)):
        number = int(character) * (2 if index % 2 else 1)
        total += number // 10 + number % 10
    return total % 10 == 0


def _request(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("identity request must be valid JSON") from exc
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError("identity request fields are invalid")
    for key in ("issuer_id", "source_id"):
        if not isinstance(value[key], str) or not SAFE_ID.fullmatch(value[key]):
            raise ValueError(f"{key} is invalid")
    for key in ("legal_name", "security_type", "exchange", "symbol", "evidence_locator"):
        if not isinstance(value[key], str) or not value[key].strip() or len(value[key]) > 160:
            raise ValueError(f"{key} is invalid")
    if not _valid_isin(value["isin"]):
        raise ValueError("ISIN check digit or format is invalid")
    if value["exchange"] not in {"NSE", "BSE"}:
        raise ValueError("exchange must be NSE or BSE")
    if value["security_type"] not in {"EQUITY", "PREFERENCE", "DEBT"}:
        raise ValueError("security_type is unsupported")
    if not isinstance(value["reviewer_id"], str) or not SAFE_ID.fullmatch(value["reviewer_id"]):
        raise ValueError("reviewer_id is invalid")
    if value["review_decision"] != "CONFIRMED":
        raise ValueError("review_decision must be CONFIRMED")
    if not isinstance(value["version_id"], str) or not DIGEST.fullmatch(value["version_id"]):
        raise ValueError("version_id is invalid")
    for key in ("listed_from", "valid_from"):
        _date(value[key], key)
    for key, start in (("listed_to", "listed_from"), ("valid_to", "valid_from")):
        if value[key] is not None and _date(value[key], key) <= value[start]:
            raise ValueError(f"{key} must follow {start}")
    if value["valid_from"] < value["listed_from"]:
        raise ValueError("symbol starts before security listing")
    if value["listed_to"] is not None and (value["valid_to"] is None or value["valid_to"] > value["listed_to"]):
        raise ValueError("symbol extends beyond security listing")
    for key in ("announced_at", "first_seen_at", "reviewed_at"):
        value[key] = _timestamp(value[key], key)
    if value["first_seen_at"] < value["announced_at"]:
        raise ValueError("first_seen_at precedes announced_at")
    if value["reviewed_at"] < value["first_seen_at"]:
        raise ValueError("reviewed_at precedes first_seen_at")
    return value


def _source(request, project_dir):
    version_path = (Path(project_dir) / "data/registry/sources" / request["source_id"]
                    / f"{request['version_id']}.json")
    try:
        version = _read_existing(version_path)
        digest = version["raw_sha256"]
        if (version["source_id"] != request["source_id"]
                or version["version_id"] != request["version_id"]
                or not isinstance(digest, str) or not DIGEST.fullmatch(digest)
                or _hash_file(Path(project_dir) / "data/raw/sha256" / digest) != digest):
            raise ValueError("source version is inconsistent")
        if request["first_seen_at"] < _timestamp(version["retrieved_at"], "retrieved_at"):
            raise ValueError("first_seen_at precedes source retrieval")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("identity source version is missing or invalid") from exc


def _connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            issuer_id TEXT PRIMARY KEY, legal_name TEXT NOT NULL,
            source_id TEXT NOT NULL, version_id TEXT NOT NULL,
            first_seen_at TEXT NOT NULL, reviewer_id TEXT NOT NULL,
            reviewed_at TEXT NOT NULL, review_decision TEXT NOT NULL,
            evidence_locator TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS securities (
            isin TEXT PRIMARY KEY, issuer_id TEXT NOT NULL REFERENCES companies(issuer_id),
            security_type TEXT NOT NULL, listed_from TEXT NOT NULL, listed_to TEXT,
            announced_at TEXT NOT NULL, first_seen_at TEXT NOT NULL,
            source_id TEXT NOT NULL, version_id TEXT NOT NULL,
            reviewer_id TEXT NOT NULL, reviewed_at TEXT NOT NULL,
            review_decision TEXT NOT NULL,
            evidence_locator TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS symbol_history (
            exchange TEXT NOT NULL, symbol TEXT NOT NULL,
            isin TEXT NOT NULL REFERENCES securities(isin),
            valid_from TEXT NOT NULL, valid_to TEXT,
            announced_at TEXT NOT NULL, first_seen_at TEXT NOT NULL,
            source_id TEXT NOT NULL, version_id TEXT NOT NULL,
            reviewer_id TEXT NOT NULL, reviewed_at TEXT NOT NULL,
            review_decision TEXT NOT NULL,
            evidence_locator TEXT NOT NULL,
            PRIMARY KEY(exchange, symbol, valid_from)
        );
        CREATE TRIGGER IF NOT EXISTS companies_no_update BEFORE UPDATE ON companies
            BEGIN SELECT RAISE(ABORT, 'identity rows are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS companies_no_delete BEFORE DELETE ON companies
            BEGIN SELECT RAISE(ABORT, 'identity rows are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS securities_no_update BEFORE UPDATE ON securities
            BEGIN SELECT RAISE(ABORT, 'identity rows are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS securities_no_delete BEFORE DELETE ON securities
            BEGIN SELECT RAISE(ABORT, 'identity rows are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS symbols_no_update BEFORE UPDATE ON symbol_history
            BEGIN SELECT RAISE(ABORT, 'identity rows are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS symbols_no_delete BEFORE DELETE ON symbol_history
            BEGIN SELECT RAISE(ABORT, 'identity rows are append-only'); END;
    """)
    return db


def _match_or_insert(db, table, key, row, message):
    existing = db.execute(
        f"SELECT * FROM {table} WHERE " + " AND ".join(f"{field}=?" for field in key),
        tuple(row[field] for field in key),
    ).fetchone()
    if existing is not None:
        if dict(existing) != row:
            raise ValueError(message)
        return
    db.execute(
        f"INSERT INTO {table} (" + ",".join(row) + ") VALUES ("
        + ",".join("?" for _ in row) + ")", tuple(row.values()),
    )


def register_identity(request_path: Path, project_dir: Path, catalog_path: Path) -> dict:
    """Register one sourced identity observation, or replay it unchanged."""
    value = _request(request_path)
    _source(value, project_dir)
    with closing(_connect(catalog_path)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        company = {key: value[key] for key in (
            "issuer_id", "legal_name", "source_id", "version_id", "first_seen_at",
            "reviewer_id", "reviewed_at", "review_decision", "evidence_locator",
        )}
        prior_company = db.execute("SELECT * FROM companies WHERE issuer_id=?", (value["issuer_id"],)).fetchone()
        if prior_company is None:
            _match_or_insert(db, "companies", ("issuer_id",), company, "issuer identity conflicts")
        elif prior_company["legal_name"] != value["legal_name"]:
            raise ValueError("issuer identity conflicts")
        security = {key: value[key] for key in (
            "isin", "issuer_id", "security_type", "listed_from", "listed_to",
            "announced_at", "first_seen_at", "source_id", "version_id",
            "reviewer_id", "reviewed_at", "review_decision", "evidence_locator",
        )}
        prior = db.execute("SELECT * FROM securities WHERE isin=?", (value["isin"],)).fetchone()
        if prior is None:
            _match_or_insert(db, "securities", ("isin",), security, "security identity conflicts")
        elif any(prior[key] != value[key] for key in (
            "issuer_id", "security_type", "listed_from", "listed_to",
        )):
            raise ValueError("security identity conflicts")
        symbol = {key: value[key] for key in (
            "exchange", "symbol", "isin", "valid_from", "valid_to", "announced_at",
            "first_seen_at", "source_id", "version_id",
            "reviewer_id", "reviewed_at", "review_decision", "evidence_locator",
        )}
        for old in db.execute(
            "SELECT * FROM symbol_history WHERE exchange=? AND symbol=?",
            (value["exchange"], value["symbol"]),
        ):
            if dict(old) == symbol:
                break
            if (old["valid_to"] is None or value["valid_from"] < old["valid_to"]) and (
                value["valid_to"] is None or old["valid_from"] < value["valid_to"]
            ):
                raise ValueError("symbol validity overlaps an existing mapping")
        _match_or_insert(db, "symbol_history", ("exchange", "symbol", "valid_from"),
                         symbol, "symbol identity conflicts")
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {"identity_id": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "issuer_id": value["issuer_id"], "isin": value["isin"], "symbol": value["symbol"]}


def resolve_symbol(catalog_path: Path, project_dir: Path, exchange: str, symbol: str,
                   effective_date: str, cutoff_timestamp: str) -> str | None:
    """Resolve one symbol without using a mapping learned after the cutoff."""
    effective_date = _date(effective_date, "effective_date")
    cutoff = _timestamp(cutoff_timestamp, "cutoff_timestamp")
    if effective_date > datetime.fromisoformat(cutoff_timestamp).date().isoformat():
        raise ValueError("effective_date after cutoff")
    if not Path(catalog_path).is_file():
        return None
    with closing(_connect(catalog_path)) as db:
        rows = db.execute("""
            SELECT sh.*, s.source_id AS security_source_id,
                   s.version_id AS security_version_id,
                   s.first_seen_at AS security_first_seen_at,
                   s.reviewed_at AS security_reviewed_at,
                   s.review_decision AS security_review_decision,
                   c.source_id AS company_source_id,
                   c.version_id AS company_version_id,
                   c.first_seen_at AS company_first_seen_at,
                   c.reviewed_at AS company_reviewed_at,
                   c.review_decision AS company_review_decision
            FROM symbol_history sh JOIN securities s ON s.isin=sh.isin
            JOIN companies c ON c.issuer_id=s.issuer_id
            WHERE sh.exchange=? AND sh.symbol=?
              AND sh.valid_from<=? AND (sh.valid_to IS NULL OR sh.valid_to>?)
              AND s.listed_from<=? AND (s.listed_to IS NULL OR s.listed_to>?)
              AND sh.announced_at<=? AND sh.first_seen_at<=?
              AND s.announced_at<=? AND s.first_seen_at<=?
              AND sh.reviewed_at<=? AND s.reviewed_at<=? AND c.reviewed_at<=?
              AND sh.review_decision='CONFIRMED'
              AND s.review_decision='CONFIRMED'
              AND c.review_decision='CONFIRMED'
        """, (exchange, symbol, effective_date, effective_date, effective_date,
              effective_date, cutoff, cutoff, cutoff, cutoff, cutoff, cutoff, cutoff)).fetchall()
    if len(rows) > 1:
        raise ValueError("symbol resolves ambiguously")
    if not rows:
        return None
    row = rows[0]
    for prefix in ("", "security_", "company_"):
        _source({
            "source_id": row[f"{prefix}source_id"],
            "version_id": row[f"{prefix}version_id"],
            "first_seen_at": row[f"{prefix}first_seen_at"],
        }, project_dir)
    return row["isin"]
