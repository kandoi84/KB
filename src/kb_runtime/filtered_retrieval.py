"""Small deterministic lexical baseline over verified filing chunks."""

import re
from contextlib import closing
from pathlib import Path

from .identity_store import _connect, _timestamp, _valid_isin
from .metric_store import DOCUMENTS, _id
from .pdf_chunks import _tables, query_pdf_chunks
from .text_chunks import query_text_chunks


MAX_CANDIDATE_FILINGS = 500
MAX_QUERY_CHARS = 500
MAX_RESULTS = 20
ROLES = {"UNKNOWN", "MANAGEMENT", "ANALYST", "MODERATOR"}


def _terms(value):
    return set(re.findall(r"\w+", value.casefold(), flags=re.UNICODE))


def search_chunks(catalog_path: Path, project_dir: Path, issuer_id: str, query: str,
                  cutoff_timestamp: str, *, isin: str | None = None,
                  document_types: list[str] | None = None,
                  speaker_role: str | None = None, limit: int = 5,
                  include_superseded: bool = False) -> list[dict]:
    """Return cited text matches; this never supplies a numeric answer."""
    _id(issuer_id, "issuer_id")
    cutoff = _timestamp(cutoff_timestamp, "cutoff_timestamp")
    if not isinstance(query, str) or not 0 < len(query) <= MAX_QUERY_CHARS or not query.strip():
        raise ValueError("query is invalid")
    terms = _terms(query)
    if not terms:
        raise ValueError("query has no search terms")
    if type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
        raise ValueError("limit is invalid")
    if type(include_superseded) is not bool:
        raise ValueError("include_superseded is invalid")
    if isin is not None and not _valid_isin(isin):
        raise ValueError("ISIN is invalid")
    if document_types is not None and (not isinstance(document_types, list) or
                                       not document_types or any(type(d) is not str or d not in DOCUMENTS
                                                                 for d in document_types) or
                                       len(document_types) != len(set(document_types))):
        raise ValueError("document_types is invalid")
    if speaker_role is not None and (type(speaker_role) is not str or speaker_role not in ROLES):
        raise ValueError("speaker_role is invalid")
    if not Path(catalog_path).is_file():
        return []
    with closing(_connect(catalog_path)) as db:
        _tables(db)
        if isin is not None:
            security = db.execute("SELECT issuer_id FROM securities WHERE isin=?", (isin,)).fetchone()
            if security is None or security["issuer_id"] != issuer_id:
                raise ValueError("ISIN does not belong to issuer_id")
        conditions = ["issuer_id=?", "published_at<=?", "first_seen_at<=?", "reviewed_at<=?"]
        parameters = [issuer_id, cutoff, cutoff, cutoff]
        if isin is not None:
            conditions.append("isin=?")
            parameters.append(isin)
        if document_types is not None:
            conditions.append(f"document_type IN ({','.join('?' for _ in document_types)})")
            parameters.extend(document_types)
        filings = db.execute(f"""SELECT filing_id, issuer_id, isin, document_type, period_end,
            published_at, supersedes_filing_id, rights_status, review_decision
            FROM filings WHERE {' AND '.join(conditions)} ORDER BY filing_id""", parameters).fetchall()
        if len(filings) > MAX_CANDIDATE_FILINGS:
            raise ValueError("too many candidate filings for one issuer")
        if any(row["rights_status"] != "REVIEWED" or row["review_decision"] != "CONFIRMED"
               for row in filings):
            raise ValueError("candidate filing rights or review is invalid")
        superseded_ids = set()
        for row in filings:
            if row["supersedes_filing_id"] is None:
                continue
            prior = db.execute("""SELECT issuer_id, isin, document_type, period_end, published_at
                FROM filings WHERE filing_id=?""", (row["supersedes_filing_id"],)).fetchone()
            if prior is None or any(prior[key] != row[key] for key in
                                    ("issuer_id", "isin", "document_type", "period_end")) or \
                    prior["published_at"] >= row["published_at"]:
                raise ValueError("filing revision is invalid")
            superseded_ids.add(row["supersedes_filing_id"])
        selected = []
        for filing in filings:
            if filing["filing_id"] in superseded_ids and not include_superseded:
                continue
            text_receipt = db.execute("SELECT 1 FROM text_extractions WHERE filing_id=?", (filing["filing_id"],)).fetchone()
            pdf_receipt = db.execute("SELECT 1 FROM pdf_extractions WHERE filing_id=?", (filing["filing_id"],)).fetchone()
            if text_receipt and pdf_receipt:
                raise ValueError("filing has conflicting text and PDF extraction paths")
            if text_receipt:
                selected.append((filing, "TEXT"))
            elif pdf_receipt:
                selected.append((filing, "PDF"))
    matches = []
    for filing, kind in selected:
        if kind == "TEXT":
            chunks = query_text_chunks(catalog_path, project_dir, filing["filing_id"], cutoff)
        else:
            chunks = query_pdf_chunks(catalog_path, project_dir, filing["filing_id"], cutoff)
        for chunk in chunks:
            if speaker_role is not None and chunk["speaker_role"] != speaker_role:
                continue
            score = len(terms & _terms(chunk["text"]))
            if score:
                matches.append({**chunk, "issuer_id": issuer_id,
                                "offset_basis": "RAW_UTF8" if kind == "TEXT" else "DERIVED_PAGE_UTF8",
                                "superseded_at_cutoff": filing["filing_id"] in superseded_ids,
                                "score": score, "retrieval_method": "TOKEN_OVERLAP_V1",
                                "numeric_authority": "TYPED_METRICS", "publication_allowed": False})
    matches.sort(key=lambda row: (-row["score"], row["filing_id"],
                                  row["page_number"] or 0, row["byte_start"], row["chunk_id"]))
    return matches[:limit]
