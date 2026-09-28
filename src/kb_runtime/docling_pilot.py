"""Rebuildable, page-cited Docling pilot over reviewed PDF source versions."""

import hashlib
import io
import json
import re
import unicodedata
from contextlib import closing
from importlib.metadata import version
from pathlib import Path

from .identity_store import _connect, _timestamp
from .pdf_chunks import MAX_CHUNK_BYTES, MAX_PAGES, _now, _raw, _visible
from .text_chunks import _filing, _tables as _base_tables


def _parser_version():
    if version("docling") != "2.130.0":
        raise ValueError("Docling pilot requires docling 2.130.0")
    parts = [version(name) for name in ("docling", "docling-core", "docling-parse")]
    if any(not re.fullmatch(r"[0-9A-Za-z.]+", part) for part in parts):
        raise ValueError("Docling parser version is invalid")
    docling, core, parser = (part.replace(".", "_") for part in parts)
    return f"docling_{docling}_core_{core}_parse_{parser}_native_hierarchical_v1"


def _tables(db):
    _base_tables(db)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS docling_extractions (
            filing_id TEXT NOT NULL REFERENCES filings(filing_id),
            parser_version TEXT NOT NULL, source_id TEXT NOT NULL,
            version_id TEXT NOT NULL, raw_sha256 TEXT NOT NULL,
            recorded_at TEXT NOT NULL, page_count INTEGER NOT NULL CHECK(page_count > 0),
            chunk_count INTEGER NOT NULL CHECK(chunk_count > 0),
            structure_sha256 TEXT NOT NULL, structure_json TEXT NOT NULL,
            PRIMARY KEY (filing_id, parser_version)
        );
        CREATE TABLE IF NOT EXISTS docling_chunks (
            chunk_id TEXT PRIMARY KEY, filing_id TEXT NOT NULL,
            parser_version TEXT NOT NULL, chunk_index INTEGER NOT NULL,
            page_number INTEGER NOT NULL CHECK(page_number > 0),
            text_sha256 TEXT NOT NULL, text TEXT NOT NULL,
            item_refs_json TEXT NOT NULL,
            FOREIGN KEY (filing_id, parser_version)
                REFERENCES docling_extractions(filing_id, parser_version),
            UNIQUE (filing_id, parser_version, chunk_index)
        );
    """)
    for table in ("docling_extractions", "docling_chunks"):
        db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_update BEFORE UPDATE ON {table} "
                   f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END")
        db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_delete BEFORE DELETE ON {table} "
                   f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END")


def _chunk_page(chunk, page_count):
    items = getattr(getattr(chunk, "meta", None), "doc_items", None)
    if not items:
        raise ValueError("Docling chunk has no page anchor")
    pages = set()
    for item in items:
        provenance = getattr(item, "prov", None)
        if not provenance:
            raise ValueError("Docling chunk item has no page anchor")
        for entry in provenance:
            number = getattr(entry, "page_no", None)
            if type(number) is not int or not 1 <= number <= page_count:
                raise ValueError("Docling chunk page anchor is invalid")
            pages.add(number)
    if len(pages) != 1:
        raise ValueError("Docling chunk has ambiguous physical page anchors")
    return pages.pop()


def _expected(filing, project_dir, parser_version):
    # Reuse the existing source reader: it validates version, digest, size, and PDF bytes.
    raw = _raw(filing, project_dir)
    try:
        from docling.datamodel.base_models import ConversionStatus, DocumentStream, InputFormat
        from docling.document_converter import DocumentConverter, NativePdfFormatOption
        from docling_core.transforms.chunker import HierarchicalChunker

        source = DocumentStream(name=filing["raw_sha256"] + ".pdf", stream=io.BytesIO(raw))
        result = DocumentConverter(format_options={InputFormat.PDF: NativePdfFormatOption()}).convert(source)
        if result.status != ConversionStatus.SUCCESS or result.document is None:
            raise ValueError("Docling PDF conversion failed")
        document = result.document
        page_count = len(document.pages)
        if not 0 < page_count <= MAX_PAGES:
            raise ValueError("Docling PDF page count is invalid")
        structure_json = document.model_dump_json(exclude_none=True)
        if not structure_json:
            raise ValueError("Docling structure is empty")
        rows = []
        covered_pages = set()
        for index, chunk in enumerate(HierarchicalChunker().chunk(document)):
            page_number = _chunk_page(chunk, page_count)
            text = chunk.text
            encoded = text.encode("utf-8") if isinstance(text, str) else b""
            if not text or not text.strip() or len(encoded) > MAX_CHUNK_BYTES or any(
                unicodedata.category(char) == "Cc" and char not in "\n\r\t" for char in text
            ):
                raise ValueError("Docling chunk text is invalid")
            refs = [item.self_ref for item in chunk.meta.doc_items]
            if not refs or any(not isinstance(ref, str) or not ref.startswith("#/") for ref in refs):
                raise ValueError("Docling chunk item reference is invalid")
            digest = hashlib.sha256(encoded).hexdigest()
            binding = {"filing_id": filing["filing_id"], "source_id": filing["source_id"],
                       "version_id": filing["version_id"], "raw_sha256": filing["raw_sha256"],
                       "parser_version": parser_version, "chunk_index": index,
                       "page_number": page_number, "text_sha256": digest, "item_refs": refs}
            chunk_id = hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            rows.append({"chunk_id": chunk_id, "filing_id": filing["filing_id"],
                         "parser_version": parser_version, "chunk_index": index,
                         "page_number": page_number, "text_sha256": digest,
                         "text": text, "item_refs_json": json.dumps(refs, separators=(",", ":"))})
            covered_pages.add(page_number)
        if covered_pages != set(range(1, page_count + 1)):
            raise ValueError("Docling PDF page has no anchored text")
        return page_count, structure_json, rows
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Docling PDF parser failed") from exc


def _receipt(filing, parser_version, page_count, structure_json, rows, recorded_at):
    return {"filing_id": filing["filing_id"], "parser_version": parser_version,
            "source_id": filing["source_id"], "version_id": filing["version_id"],
            "raw_sha256": filing["raw_sha256"], "recorded_at": recorded_at,
            "page_count": page_count, "chunk_count": len(rows),
            "structure_sha256": hashlib.sha256(structure_json.encode()).hexdigest(),
            "structure_json": structure_json}


def _compare(db, filing, parser_version, page_count, structure_json, rows):
    old = db.execute("SELECT * FROM docling_extractions WHERE filing_id=? AND parser_version=?",
                     (filing["filing_id"], parser_version)).fetchone()
    if old is None:
        return None
    stored = db.execute("SELECT * FROM docling_chunks WHERE filing_id=? AND parser_version=? ORDER BY chunk_index",
                        (filing["filing_id"], parser_version)).fetchall()
    if dict(old) != _receipt(filing, parser_version, page_count, structure_json, rows, old["recorded_at"]) or [dict(row) for row in stored] != rows:
        raise ValueError("stored Docling extraction or chunks differ from source")
    return old


def extract_docling_pilot(catalog_path: Path, project_dir: Path, filing_id: str) -> dict:
    parser_version = _parser_version()
    with closing(_connect(catalog_path)) as db:
        _tables(db)
        filing = _filing(db, filing_id)
        page_count, structure_json, rows = _expected(filing, project_dir, parser_version)
        with db:
            db.execute("BEGIN IMMEDIATE")
            if _compare(db, filing, parser_version, page_count, structure_json, rows) is None:
                receipt = _receipt(filing, parser_version, page_count, structure_json, rows, _now())
                db.execute("INSERT INTO docling_extractions VALUES (?,?,?,?,?,?,?,?,?,?)", tuple(receipt.values()))
                db.executemany("INSERT INTO docling_chunks VALUES (?,?,?,?,?,?,?,?)", [tuple(row.values()) for row in rows])
    return {"filing_id": filing_id, "parser_version": parser_version,
            "page_count": page_count, "chunk_ids": [row["chunk_id"] for row in rows],
            "publication_allowed": False}


def query_docling_pilot(catalog_path: Path, project_dir: Path, filing_id: str,
                        cutoff_timestamp: str) -> list[dict]:
    cutoff = _timestamp(cutoff_timestamp, "cutoff_timestamp")
    parser_version = _parser_version()
    if not Path(catalog_path).is_file():
        return []
    with closing(_connect(catalog_path)) as db:
        _tables(db)
        filing = db.execute("SELECT * FROM filings WHERE filing_id=?", (filing_id,)).fetchone()
        if filing is None or not _visible(db, filing, project_dir, cutoff):
            return []
        receipt = db.execute("SELECT * FROM docling_extractions WHERE filing_id=? AND parser_version=?",
                             (filing_id, parser_version)).fetchone()
        if receipt is None or receipt["recorded_at"] > cutoff:
            return []
        page_count, structure_json, rows = _expected(filing, project_dir, parser_version)
        _compare(db, filing, parser_version, page_count, structure_json, rows)
        return [{**row, "source_id": filing["source_id"], "version_id": filing["version_id"],
                 "raw_sha256": filing["raw_sha256"], "issuer_id": filing["issuer_id"],
                 "isin": filing["isin"], "document_type": filing["document_type"],
                 "period_end": filing["period_end"], "published_at": filing["published_at"],
                 "first_seen_at": filing["first_seen_at"],
                 "extraction_recorded_at": receipt["recorded_at"],
                 "offset_basis": "DOCLING_DERIVED_PAGE", "speaker_role": "UNKNOWN",
                 "availability_mode": "LIVE_STRICT", "publication_allowed": False}
                for row in rows]
