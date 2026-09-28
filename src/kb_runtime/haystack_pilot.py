"""Disposable Haystack ranking over source-verified KB chunks.

The framework index is never evidence. Existing readers establish eligibility,
and returned document IDs map back to those verified records.
"""

from pathlib import Path

from .filtered_retrieval import (MAX_QUERY_CHARS, MAX_RESULTS, ROLES, _terms,
                                 _verified_chunks)
from .identity_store import _timestamp, _valid_isin
from .metric_store import DOCUMENTS, _id


MAX_INDEXED_CHUNKS = 20_000


def search_haystack_pilot(catalog_path: Path, project_dir: Path, issuer_id: str,
                          query: str, cutoff_timestamp: str, *, isin: str | None = None,
                          document_types: list[str] | None = None,
                          speaker_role: str | None = None, limit: int = 5) -> list[dict]:
    """Rank verified chunks; never supply a numeric answer or publication right."""
    _id(issuer_id, "issuer_id")
    cutoff = _timestamp(cutoff_timestamp, "cutoff_timestamp")
    if not isinstance(query, str) or not 0 < len(query) <= MAX_QUERY_CHARS or not query.strip():
        raise ValueError("query is invalid")
    if not _terms(query):
        raise ValueError("query has no search terms")
    if type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
        raise ValueError("limit is invalid")
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

    verified = {}
    for chunk in _verified_chunks(catalog_path, project_dir, issuer_id, cutoff, isin,
                                  document_types, speaker_role):
        if chunk["publication_allowed"] is not False or chunk["availability_mode"] != "LIVE_STRICT":
            raise ValueError("chunk publication or availability differs")
        if chunk["published_at"] > cutoff or chunk["first_seen_at"] > cutoff or \
                chunk["extraction_recorded_at"] > cutoff:
            raise ValueError("chunk is later than cutoff")
        if chunk["chunk_id"] in verified:
            raise ValueError("duplicate verified chunk ID")
        verified[chunk["chunk_id"]] = chunk
        if len(verified) > MAX_INDEXED_CHUNKS:
            raise ValueError("too many verified chunks for pilot index")
    if not verified:
        return []

    # Optional import keeps the production runtime free of the pilot package.
    from haystack import Document
    from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
    from haystack.document_stores.in_memory import InMemoryDocumentStore

    store = InMemoryDocumentStore()
    metadata_keys = ("issuer_id", "isin", "document_type", "speaker_role", "source_id",
                     "version_id", "raw_sha256", "published_at", "first_seen_at",
                     "extraction_recorded_at", "page_number")
    store.write_documents([Document(id=chunk_id, content=row["text"],
                                    meta={key: row[key] for key in metadata_keys})
                           for chunk_id, row in verified.items()])
    conditions = [{"field": "meta.issuer_id", "operator": "==", "value": issuer_id}]
    if isin is not None:
        conditions.append({"field": "meta.isin", "operator": "==", "value": isin})
    if document_types is not None:
        conditions.append({"field": "meta.document_type", "operator": "in", "value": document_types})
    if speaker_role is not None:
        conditions.append({"field": "meta.speaker_role", "operator": "==", "value": speaker_role})
    filters = {"operator": "AND", "conditions": conditions}
    # Request every eligible hit so equal BM25 scores can be ordered stably here.
    docs = InMemoryBM25Retriever(document_store=store, top_k=len(verified)).run(
        query=query, filters=filters)["documents"]
    matches = []
    for doc in docs:
        row = verified.get(doc.id)
        if row is None or doc.content != row["text"] or \
                doc.meta != {key: row[key] for key in metadata_keys}:
            raise ValueError("retrieval result differs from verified chunk")
        if row["issuer_id"] != issuer_id or (isin is not None and row["isin"] != isin) or \
                (document_types is not None and row["document_type"] not in document_types) or \
                (speaker_role is not None and row["speaker_role"] != speaker_role) or \
                any(row[key] > cutoff for key in ("published_at", "first_seen_at", "extraction_recorded_at")):
            raise ValueError("retrieval result violates identity or cutoff")
        matches.append({**row, "score": doc.score, "retrieval_method": "HAYSTACK_BM25_PILOT"})
    matches.sort(key=lambda row: (-row["score"], row["filing_id"],
                                  row["page_number"] or 0, row["byte_start"], row["chunk_id"]))
    return matches[:limit]
