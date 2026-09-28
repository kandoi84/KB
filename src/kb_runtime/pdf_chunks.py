"""Immutable, page-cited PDF text and separately reviewed speaker roles."""

import hashlib
import io
import json
import re
import unicodedata
from contextlib import closing
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from pypdf import PdfReader

from .identity_store import _connect, _source, _timestamp
from .metric_store import _filing_source, _id, _label
from .text_chunks import _filing, _tables as _text_tables


PARSER_VERSION = "pypdf_6_19_0_plain_v1"
MAX_RAW_BYTES = 8 * 1024 * 1024
MAX_PAGES = 200
MAX_PAGE_BYTES = 1024 * 1024
MAX_CHUNK_BYTES = 2048


def _tables(db):
    _text_tables(db)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS pdf_extractions (
            filing_id TEXT NOT NULL REFERENCES filings(filing_id),
            parser_version TEXT NOT NULL, source_id TEXT NOT NULL,
            version_id TEXT NOT NULL, raw_sha256 TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            page_count INTEGER NOT NULL CHECK (page_count > 0),
            chunk_count INTEGER NOT NULL CHECK (chunk_count > 0),
            PRIMARY KEY (filing_id, parser_version)
        );
        CREATE TABLE IF NOT EXISTS pdf_pages (
            filing_id TEXT NOT NULL, parser_version TEXT NOT NULL,
            page_number INTEGER NOT NULL CHECK (page_number > 0),
            text_sha256 TEXT NOT NULL, text TEXT NOT NULL,
            PRIMARY KEY (filing_id, parser_version, page_number),
            FOREIGN KEY (filing_id, parser_version)
                REFERENCES pdf_extractions(filing_id, parser_version)
        );
        CREATE TABLE IF NOT EXISTS pdf_chunks (
            chunk_id TEXT PRIMARY KEY, filing_id TEXT NOT NULL,
            parser_version TEXT NOT NULL, page_number INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
            byte_start INTEGER NOT NULL CHECK (byte_start >= 0),
            byte_end INTEGER NOT NULL CHECK (byte_end > byte_start),
            text_sha256 TEXT NOT NULL, text TEXT NOT NULL,
            FOREIGN KEY (filing_id, parser_version, page_number)
                REFERENCES pdf_pages(filing_id, parser_version, page_number),
            UNIQUE (filing_id, parser_version, page_number, chunk_index)
        );
        CREATE TABLE IF NOT EXISTS pdf_role_reviews (
            review_id TEXT PRIMARY KEY, filing_id TEXT NOT NULL,
            parser_version TEXT NOT NULL, chunk_id TEXT NOT NULL REFERENCES pdf_chunks(chunk_id),
            page_number INTEGER NOT NULL, byte_start INTEGER NOT NULL,
            byte_end INTEGER NOT NULL, quote TEXT NOT NULL,
            speaker_role TEXT NOT NULL CHECK (speaker_role IN ('MANAGEMENT', 'ANALYST', 'MODERATOR', 'UNKNOWN')),
            reviewer_id TEXT NOT NULL, reviewed_at TEXT NOT NULL,
            recorded_at TEXT NOT NULL, evidence_locator TEXT NOT NULL,
            supersedes_review_id TEXT UNIQUE REFERENCES pdf_role_reviews(review_id)
        );
    """)
    for table in ("pdf_extractions", "pdf_pages", "pdf_chunks", "pdf_role_reviews"):
        db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_update BEFORE UPDATE ON {table} "
                   f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END")
        db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_delete BEFORE DELETE ON {table} "
                   f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END")


def _parser(parser_version):
    if parser_version != PARSER_VERSION or version("pypdf") != "6.19.0":
        raise ValueError("PDF parser_version or installed pypdf version is invalid")


def _now():
    return _timestamp(datetime.now(timezone.utc).isoformat(), "recorded_at")


def _raw(filing, project_dir):
    digest = _filing_source(filing, project_dir)
    if digest != filing["raw_sha256"]:
        raise ValueError("PDF filing source digest differs from catalog")
    path = Path(project_dir) / "data/raw/sha256" / digest
    try:
        if not 0 < path.stat().st_size <= MAX_RAW_BYTES:
            raise ValueError("PDF raw size is invalid")
        data = path.read_bytes()
    except OSError as exc:
        raise ValueError("PDF raw source is unavailable") from exc
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("PDF raw source changed while reading")
    if b"%PDF-" not in data[:1024]:
        raise ValueError("raw source is not a PDF")
    return data


def _chunks(filing, page_number, text):
    raw = text.encode("utf-8")
    spans = []
    start = 0
    for line in text.splitlines(keepends=True):
        part = bytearray()
        for char in line:
            encoded = char.encode("utf-8")
            if part and len(part) + len(encoded) > MAX_CHUNK_BYTES:
                spans.append((start, start + len(part), bytes(part)))
                start += len(part)
                part.clear()
            part.extend(encoded)
        if part:
            spans.append((start, start + len(part), bytes(part)))
            start += len(part)
    if start != len(raw):
        raise ValueError("PDF page text chunk coverage differs")
    rows = []
    for index, (byte_start, byte_end, part) in enumerate(spans):
        digest = hashlib.sha256(part).hexdigest()
        binding = {"filing_id": filing["filing_id"], "raw_sha256": filing["raw_sha256"],
                   "source_id": filing["source_id"], "version_id": filing["version_id"],
                   "parser_version": PARSER_VERSION, "page_number": page_number,
                   "byte_start": byte_start, "byte_end": byte_end, "text_sha256": digest}
        chunk_id = hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        rows.append({"chunk_id": chunk_id, "filing_id": filing["filing_id"],
                     "parser_version": PARSER_VERSION, "page_number": page_number,
                     "chunk_index": index, "byte_start": byte_start, "byte_end": byte_end,
                     "text_sha256": digest, "text": part.decode("utf-8")})
    return rows


def _expected(filing, raw):
    try:
        reader = PdfReader(io.BytesIO(raw), strict=True)
        if reader.is_encrypted:
            raise ValueError("encrypted PDF is blocked")
        count = len(reader.pages)
        if not 0 < count <= MAX_PAGES:
            raise ValueError("PDF page count is invalid")
        pages, chunks = [], []
        for number, page in enumerate(reader.pages, 1):
            text = page.extract_text(extraction_mode="plain")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"PDF page {number} has no extractable text")
            encoded = text.encode("utf-8")
            if len(encoded) > MAX_PAGE_BYTES or any(
                unicodedata.category(char) == "Cc" and char not in "\n\r\t" for char in text
            ):
                raise ValueError(f"PDF page {number} text is invalid")
            pages.append({"filing_id": filing["filing_id"], "parser_version": PARSER_VERSION,
                          "page_number": number, "text_sha256": hashlib.sha256(encoded).hexdigest(),
                          "text": text})
            chunks.extend(_chunks(filing, number, text))
        return pages, chunks
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PDF parser failed") from exc


def _receipt(filing, pages, chunks, recorded_at):
    return {"filing_id": filing["filing_id"], "parser_version": PARSER_VERSION,
            "source_id": filing["source_id"], "version_id": filing["version_id"],
            "raw_sha256": filing["raw_sha256"], "recorded_at": recorded_at,
            "page_count": len(pages),
            "chunk_count": len(chunks)}


def _compare(db, filing, pages, chunks):
    receipt = db.execute("SELECT * FROM pdf_extractions WHERE filing_id=? AND parser_version=?",
                         (filing["filing_id"], PARSER_VERSION)).fetchone()
    if receipt is None:
        return False
    stored_pages = db.execute("SELECT * FROM pdf_pages WHERE filing_id=? AND parser_version=? ORDER BY page_number",
                              (filing["filing_id"], PARSER_VERSION)).fetchall()
    stored_chunks = db.execute("SELECT * FROM pdf_chunks WHERE filing_id=? AND parser_version=? ORDER BY page_number, chunk_index",
                               (filing["filing_id"], PARSER_VERSION)).fetchall()
    if dict(receipt) != _receipt(filing, pages, chunks, receipt["recorded_at"]) or [dict(p) for p in stored_pages] != pages or [dict(c) for c in stored_chunks] != chunks:
        raise ValueError("stored PDF extraction, page, or chunk differs from source")
    return receipt


def extract_pdf_filing(catalog_path: Path, project_dir: Path, filing_id: str,
                       parser_version: str = PARSER_VERSION) -> dict:
    _parser(parser_version)
    with closing(_connect(catalog_path)) as db:
        _tables(db)
        filing = _filing(db, filing_id)
        pages, chunks = _expected(filing, _raw(filing, project_dir))
        with db:
            db.execute("BEGIN IMMEDIATE")
            if not _compare(db, filing, pages, chunks):
                db.execute("INSERT INTO pdf_extractions VALUES (?,?,?,?,?,?,?,?)", tuple(_receipt(filing, pages, chunks, _now()).values()))
                db.executemany("INSERT INTO pdf_pages VALUES (?,?,?,?,?)", [tuple(p.values()) for p in pages])
                db.executemany("INSERT INTO pdf_chunks VALUES (?,?,?,?,?,?,?,?,?)", [tuple(c.values()) for c in chunks])
    return {"filing_id": filing_id, "parser_version": parser_version,
            "page_count": len(pages), "chunk_ids": [c["chunk_id"] for c in chunks],
            "publication_allowed": False}


def _visible(db, filing, project_dir, cutoff):
    if any(filing[key] > cutoff for key in ("published_at", "first_seen_at", "reviewed_at")):
        return False
    if filing["rights_status"] != "REVIEWED" or filing["review_decision"] != "CONFIRMED":
        raise ValueError("filing review is invalid")
    identity = db.execute("""SELECT s.*, c.source_id company_source_id,
        c.version_id company_version_id, c.first_seen_at company_first_seen_at,
        c.reviewed_at company_reviewed_at, c.review_decision company_review_decision
        FROM securities s JOIN companies c ON c.issuer_id=s.issuer_id WHERE s.isin=?""",
        (filing["isin"],)).fetchone()
    if identity is None or identity["issuer_id"] != filing["issuer_id"]:
        raise ValueError("filing issuer identity differs")
    if any(identity[key] > cutoff for key in ("announced_at", "first_seen_at", "reviewed_at",
                                              "company_first_seen_at", "company_reviewed_at")):
        return False
    if identity["review_decision"] != "CONFIRMED" or identity["company_review_decision"] != "CONFIRMED":
        raise ValueError("filing issuer identity is not confirmed")
    for source_id, version_id, first_seen in (
        (identity["source_id"], identity["version_id"], identity["first_seen_at"]),
        (identity["company_source_id"], identity["company_version_id"], identity["company_first_seen_at"])):
        _source({"source_id": source_id, "version_id": version_id,
                 "first_seen_at": first_seen}, project_dir)
    return True


def query_pdf_chunks(catalog_path: Path, project_dir: Path, filing_id: str,
                     cutoff_timestamp: str, parser_version: str = PARSER_VERSION) -> list[dict]:
    cutoff = _timestamp(cutoff_timestamp, "cutoff_timestamp")
    _parser(parser_version)
    if not Path(catalog_path).is_file():
        return []
    with closing(_connect(catalog_path)) as db:
        _tables(db)
        filing = db.execute("SELECT * FROM filings WHERE filing_id=?", (filing_id,)).fetchone()
        if filing is None or not _visible(db, filing, project_dir, cutoff):
            return []
        pages, chunks = _expected(filing, _raw(filing, project_dir))
        receipt = _compare(db, filing, pages, chunks)
        if not receipt or receipt["recorded_at"] > cutoff:
            return []
        reviews = db.execute("SELECT * FROM pdf_role_reviews WHERE filing_id=? AND parser_version=?",
                             (filing_id, PARSER_VERSION)).fetchall()
        by_chunk = {}
        expected_ids = {c["chunk_id"]: c for c in chunks}
        review_ids = {r["review_id"]: r for r in reviews}
        children = {}
        roots = {}
        for review in reviews:
            row = dict(review)
            chunk = expected_ids.get(row["chunk_id"])
            if chunk is None or any(row[key] != chunk[key] for key in ("filing_id", "parser_version", "page_number", "byte_start", "byte_end")) or row["quote"] != chunk["text"]:
                raise ValueError("stored PDF role review differs from chunk")
            prior_id = row["supersedes_review_id"]
            prior = review_ids.get(prior_id) if prior_id else None
            if row["recorded_at"] < receipt["recorded_at"] or (prior_id and (prior is None or prior["chunk_id"] != row["chunk_id"]
                              or prior["recorded_at"] > row["recorded_at"]
                              or prior["reviewed_at"] > row["reviewed_at"])):
                raise ValueError("stored PDF role revision is invalid")
            if prior_id:
                if prior_id in children:
                    raise ValueError("stored PDF role revision branches")
                children[prior_id] = row
            elif row["chunk_id"] in roots:
                raise ValueError("stored PDF role revision has two roots")
            else:
                roots[row["chunk_id"]] = row
        visited = set()
        for chunk_id, root in roots.items():
            current = root
            while current is not None:
                if current["review_id"] in visited:
                    raise ValueError("stored PDF role revision cycles")
                visited.add(current["review_id"])
                if current["recorded_at"] <= cutoff and current["reviewed_at"] <= cutoff:
                    by_chunk[chunk_id] = current
                current = children.get(current["review_id"])
        if len(visited) != len(reviews):
            raise ValueError("stored PDF role revision is disconnected")
        return [{**chunk, "source_id": filing["source_id"], "version_id": filing["version_id"],
                 "raw_sha256": filing["raw_sha256"], "isin": filing["isin"],
                 "document_type": filing["document_type"], "period_end": filing["period_end"],
                 "published_at": filing["published_at"], "first_seen_at": filing["first_seen_at"],
                 "extraction_recorded_at": receipt["recorded_at"],
                 "offset_basis": "DERIVED_PAGE_UTF8", "speaker_role": by_chunk.get(chunk["chunk_id"], {}).get("speaker_role", "UNKNOWN"),
                 "role_review_id": by_chunk.get(chunk["chunk_id"], {}).get("review_id"),
                 "availability_mode": "LIVE_STRICT", "publication_allowed": False}
                for chunk in chunks]


def review_pdf_role(request_path: Path, catalog_path: Path, project_dir: Path) -> dict:
    try:
        request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("PDF role request is invalid JSON") from exc
    keys = {"review_id", "supersedes_review_id", "filing_id", "chunk_id", "page_number", "byte_start", "byte_end", "quote",
            "speaker_role", "reviewer_id", "reviewed_at", "evidence_locator"}
    if not isinstance(request, dict) or set(request) != keys:
        raise ValueError("PDF role request fields are invalid")
    for key in ("review_id", "filing_id", "reviewer_id"):
        _id(request[key], key)
    if not isinstance(request["chunk_id"], str) or not re.fullmatch(r"[0-9a-f]{64}", request["chunk_id"]):
        raise ValueError("chunk_id is invalid")
    if not isinstance(request["speaker_role"], str) or request["speaker_role"] not in {"MANAGEMENT", "ANALYST", "MODERATOR", "UNKNOWN"}:
        raise ValueError("speaker_role is invalid")
    if request["supersedes_review_id"] is not None:
        _id(request["supersedes_review_id"], "supersedes_review_id")
    elif request["speaker_role"] == "UNKNOWN":
        raise ValueError("UNKNOWN role requires a prior review to revoke")
    if any(type(request[key]) is not int or request[key] < (1 if key == "page_number" else 0)
           for key in ("page_number", "byte_start", "byte_end")):
        raise ValueError("PDF role span is invalid")
    _label(request["evidence_locator"], "evidence_locator")
    request["reviewed_at"] = _timestamp(request["reviewed_at"], "reviewed_at")
    recorded_at = _now()
    if request["reviewed_at"] > recorded_at:
        raise ValueError("reviewed_at cannot be in the future")
    if not isinstance(request["quote"], str) or not request["quote"].strip():
        raise ValueError("quote is invalid")
    chunks = query_pdf_chunks(catalog_path, project_dir, request["filing_id"], recorded_at)
    match = next((c for c in chunks if c["chunk_id"] == request["chunk_id"]), None)
    if match is None or any(request[key] != match[key] for key in ("page_number", "byte_start", "byte_end")) or request["quote"] != match["text"]:
        raise ValueError("PDF role span or quote differs from chunk")
    row = {"review_id": request["review_id"], "filing_id": request["filing_id"],
           "parser_version": PARSER_VERSION, **{key: request[key] for key in
           ("chunk_id", "page_number", "byte_start", "byte_end", "quote", "speaker_role",
            "reviewer_id", "reviewed_at")}, "recorded_at": recorded_at,
           "evidence_locator": request["evidence_locator"],
           "supersedes_review_id": request["supersedes_review_id"]}
    with closing(_connect(catalog_path)) as db:
        _tables(db)
        with db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM pdf_role_reviews WHERE review_id=?", (row["review_id"],)).fetchone()
            prior = db.execute("SELECT * FROM pdf_role_reviews WHERE review_id=?",
                               (row["supersedes_review_id"],)).fetchone() if row["supersedes_review_id"] else None
            other = db.execute("""SELECT * FROM pdf_role_reviews WHERE chunk_id=? AND review_id NOT IN
                (SELECT supersedes_review_id FROM pdf_role_reviews WHERE supersedes_review_id IS NOT NULL)""",
                               (row["chunk_id"],)).fetchone()
            if old is not None:
                if {k: old[k] for k in row if k != "recorded_at"} != {k: row[k] for k in row if k != "recorded_at"}:
                    raise ValueError("PDF role review ID has conflicting content")
            elif (other is None and row["supersedes_review_id"] is not None) or (other is not None and
                  (prior is None or prior["review_id"] != other["review_id"] or
                   prior["recorded_at"] > row["recorded_at"] or prior["reviewed_at"] > row["reviewed_at"])):
                raise ValueError("PDF role conflict or invalid revision")
            else:
                db.execute("INSERT INTO pdf_role_reviews VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", tuple(row.values()))
    return {"review_id": row["review_id"], "chunk_id": row["chunk_id"], "publication_allowed": False}
