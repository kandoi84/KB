"""Immutable byte-exact chunks from reviewed plain UTF-8 filings."""

import hashlib
import json
import unicodedata
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .identity_store import _connect, _source, _timestamp
from .metric_store import _filing_source, _tables as _filing_tables


MAX_RAW_BYTES = 8 * 1024 * 1024
MAX_CHUNK_BYTES = 2048
PARSER_VERSION = "plain_utf8_v1"


def _parser(value):
    if value != PARSER_VERSION:
        raise ValueError("parser_version is invalid")
    return value


def _tables(db):
    _filing_tables(db)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS text_extractions (
            filing_id TEXT NOT NULL REFERENCES filings(filing_id),
            parser_version TEXT NOT NULL, source_id TEXT NOT NULL,
            version_id TEXT NOT NULL, raw_sha256 TEXT NOT NULL,
            chunk_count INTEGER NOT NULL CHECK (chunk_count > 0),
            PRIMARY KEY (filing_id, parser_version)
        );
        CREATE TABLE IF NOT EXISTS text_chunks (
            chunk_id TEXT PRIMARY KEY,
            filing_id TEXT NOT NULL,
            parser_version TEXT NOT NULL,
            chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
            byte_start INTEGER NOT NULL CHECK (byte_start >= 0),
            byte_end INTEGER NOT NULL CHECK (byte_end > byte_start),
            text_sha256 TEXT NOT NULL,
            text TEXT NOT NULL,
            speaker_role TEXT NOT NULL CHECK (speaker_role = 'UNKNOWN'),
            page_number INTEGER CHECK (page_number IS NULL),
            FOREIGN KEY (filing_id, parser_version)
                REFERENCES text_extractions(filing_id, parser_version),
            UNIQUE (filing_id, parser_version, chunk_index)
        );
        CREATE TABLE IF NOT EXISTS text_extraction_arrivals (
            filing_id TEXT NOT NULL, parser_version TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            PRIMARY KEY (filing_id, parser_version),
            FOREIGN KEY (filing_id, parser_version)
                REFERENCES text_extractions(filing_id, parser_version)
        );
        CREATE TRIGGER IF NOT EXISTS text_extractions_no_update BEFORE UPDATE ON text_extractions
            BEGIN SELECT RAISE(ABORT, 'text extractions are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS text_extractions_no_delete BEFORE DELETE ON text_extractions
            BEGIN SELECT RAISE(ABORT, 'text extractions are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS text_chunks_no_update BEFORE UPDATE ON text_chunks
            BEGIN SELECT RAISE(ABORT, 'text chunks are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS text_chunks_no_delete BEFORE DELETE ON text_chunks
            BEGIN SELECT RAISE(ABORT, 'text chunks are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS text_extraction_arrivals_no_update BEFORE UPDATE ON text_extraction_arrivals
            BEGIN SELECT RAISE(ABORT, 'text extraction arrivals are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS text_extraction_arrivals_no_delete BEFORE DELETE ON text_extraction_arrivals
            BEGIN SELECT RAISE(ABORT, 'text extraction arrivals are append-only'); END;
    """)


def _raw(filing, project_dir):
    digest = _filing_source(filing, project_dir)
    if digest != filing["raw_sha256"]:
        raise ValueError("filing source digest differs from catalog")
    path = Path(project_dir) / "data/raw/sha256" / digest
    try:
        size = path.stat().st_size
        if size == 0 or size > MAX_RAW_BYTES:
            raise ValueError("raw text size is invalid")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("raw source changed while reading")
        text = data.decode("utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        raise ValueError("raw text is not valid UTF-8") from exc
    if not text.strip():
        raise ValueError("raw text is empty")
    if b"%PDF-" in data[:1024] or any(
        unicodedata.category(char) == "Cc" and char not in "\n\r\t" for char in text
    ):
        raise ValueError("PDF or binary data is not plain text")
    return data


def _rows(filing, raw, parser_version):
    text = raw.decode("utf-8")
    spans = []
    start = 0
    current = bytearray()
    for char in text:
        encoded = char.encode("utf-8")
        if current and len(current) + len(encoded) > MAX_CHUNK_BYTES:
            spans.append((start, start + len(current), bytes(current)))
            start += len(current)
            current.clear()
        current.extend(encoded)
    if current:
        spans.append((start, start + len(current), bytes(current)))
    rows = []
    for index, (byte_start, byte_end, part) in enumerate(spans):
        text_sha256 = hashlib.sha256(part).hexdigest()
        binding = {
            "filing_id": filing["filing_id"], "source_id": filing["source_id"],
            "version_id": filing["version_id"], "raw_sha256": filing["raw_sha256"],
            "parser_version": parser_version, "byte_start": byte_start,
            "byte_end": byte_end, "text_sha256": text_sha256,
        }
        canonical = json.dumps(binding, sort_keys=True, separators=(",", ":"))
        rows.append({"chunk_id": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                     "filing_id": filing["filing_id"], "parser_version": parser_version,
                     "chunk_index": index, "byte_start": byte_start, "byte_end": byte_end,
                     "text_sha256": text_sha256, "text": part.decode("utf-8"),
                     "speaker_role": "UNKNOWN", "page_number": None})
    return rows


def _filing(db, filing_id):
    row = db.execute("SELECT * FROM filings WHERE filing_id=?", (filing_id,)).fetchone()
    if row is None:
        raise ValueError("filing is not registered")
    if row["rights_status"] != "REVIEWED" or row["review_decision"] != "CONFIRMED":
        raise ValueError("filing review is invalid")
    return row


def extract_text_filing(catalog_path: Path, project_dir: Path, filing_id: str,
                        parser_version: str = "plain_utf8_v1") -> dict:
    """Store deterministic plain-text chunks, or replay the exact extraction."""
    _parser(parser_version)
    with closing(_connect(catalog_path)) as db:
        _tables(db)
        filing = _filing(db, filing_id)
        raw = _raw(filing, project_dir)
        expected = _rows(filing, raw, parser_version)
        receipt = {"filing_id": filing_id, "parser_version": parser_version,
                   "source_id": filing["source_id"], "version_id": filing["version_id"],
                   "raw_sha256": filing["raw_sha256"], "chunk_count": len(expected)}
        with db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM text_extractions WHERE filing_id=? AND parser_version=?",
                             (filing_id, parser_version)).fetchone()
            if old is None:
                db.execute("INSERT INTO text_extractions VALUES (?,?,?,?,?,?)", tuple(receipt.values()))
                for row in expected:
                    db.execute("INSERT INTO text_chunks VALUES (?,?,?,?,?,?,?,?,?,?)", tuple(row.values()))
            else:
                stored = db.execute("SELECT * FROM text_chunks WHERE filing_id=? AND parser_version=? ORDER BY chunk_index",
                                    (filing_id, parser_version)).fetchall()
                if dict(old) != receipt or [dict(row) for row in stored] != expected:
                    raise ValueError("stored text extraction or chunks differ from source")
            arrival = db.execute("SELECT recorded_at FROM text_extraction_arrivals WHERE filing_id=? AND parser_version=?",
                                 (filing_id, parser_version)).fetchone()
            if arrival is None:
                recorded_at = _timestamp(datetime.now(timezone.utc).isoformat(), "recorded_at")
                db.execute("INSERT INTO text_extraction_arrivals VALUES (?,?,?)",
                           (filing_id, parser_version, recorded_at))
    return {"filing_id": filing_id, "parser_version": parser_version,
            "chunk_ids": [row["chunk_id"] for row in expected], "publication_allowed": False}


def query_text_chunks(catalog_path: Path, project_dir: Path, filing_id: str,
                      cutoff_timestamp: str, parser_version: str = "plain_utf8_v1") -> list[dict]:
    """Read source-checked text chunks known by the strict live cutoff."""
    cutoff = _timestamp(cutoff_timestamp, "cutoff_timestamp")
    _parser(parser_version)
    if not Path(catalog_path).is_file():
        return []
    with closing(_connect(catalog_path)) as db:
        _tables(db)
        filing = db.execute("SELECT * FROM filings WHERE filing_id=?", (filing_id,)).fetchone()
        if filing is None:
            return []
        if any(filing[key] > cutoff for key in ("published_at", "first_seen_at", "reviewed_at")):
            return []
        if filing["rights_status"] != "REVIEWED" or filing["review_decision"] != "CONFIRMED":
            raise ValueError("filing review is invalid")
        identity = db.execute("""SELECT s.*, c.source_id company_source_id,
            c.version_id company_version_id, c.first_seen_at company_first_seen_at,
            c.reviewed_at company_reviewed_at, c.review_decision company_review_decision
            FROM securities s JOIN companies c ON c.issuer_id=s.issuer_id
            WHERE s.isin=?""", (filing["isin"],)).fetchone()
        if identity is None or identity["issuer_id"] != filing["issuer_id"]:
            raise ValueError("filing issuer identity differs")
        if any(identity[key] > cutoff for key in ("announced_at", "first_seen_at", "reviewed_at",
                                                  "company_first_seen_at", "company_reviewed_at")):
            return []
        if identity["review_decision"] != "CONFIRMED" or identity["company_review_decision"] != "CONFIRMED":
            raise ValueError("filing issuer identity is not confirmed")
        for source_id, version_id, first_seen in (
            (identity["source_id"], identity["version_id"], identity["first_seen_at"]),
            (identity["company_source_id"], identity["company_version_id"], identity["company_first_seen_at"]),
        ):
            _source({"source_id": source_id, "version_id": version_id,
                     "first_seen_at": first_seen}, project_dir)
        raw = _raw(filing, project_dir)
        receipt = db.execute("SELECT * FROM text_extractions WHERE filing_id=? AND parser_version=?",
                             (filing_id, parser_version)).fetchone()
        if receipt is None:
            return []
        expected = _rows(filing, raw, parser_version)
        stored = db.execute("SELECT * FROM text_chunks WHERE filing_id=? AND parser_version=? ORDER BY chunk_index",
                            (filing_id, parser_version)).fetchall()
        canonical_receipt = {"filing_id": filing_id, "parser_version": parser_version,
                             "source_id": filing["source_id"], "version_id": filing["version_id"],
                             "raw_sha256": filing["raw_sha256"], "chunk_count": len(expected)}
        if dict(receipt) != canonical_receipt or [dict(row) for row in stored] != expected:
            raise ValueError("stored text extraction or chunks differ from source")
        arrival = db.execute("SELECT recorded_at FROM text_extraction_arrivals WHERE filing_id=? AND parser_version=?",
                             (filing_id, parser_version)).fetchone()
        if arrival is None:
            raise ValueError("text extraction arrival is unknown; verified replay required")
        if arrival["recorded_at"] > cutoff:
            return []
        return [{**row, "source_id": filing["source_id"], "version_id": filing["version_id"],
                 "raw_sha256": filing["raw_sha256"], "isin": filing["isin"],
                 "document_type": filing["document_type"], "period_end": filing["period_end"],
                 "published_at": filing["published_at"],
                 "first_seen_at": filing["first_seen_at"], "reviewed_at": filing["reviewed_at"],
                 "extraction_recorded_at": arrival["recorded_at"],
                 "availability_mode": "LIVE_STRICT", "publication_allowed": False}
                for row in expected]
