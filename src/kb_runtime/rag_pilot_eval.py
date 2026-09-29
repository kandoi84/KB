"""Paired, nonpromoting comparison of lexical and Haystack retrieval."""

import hashlib
import sys
from importlib import metadata
from pathlib import Path
from time import perf_counter

from . import filtered_retrieval, haystack_pilot
from .filtered_retrieval import _verified_chunks, search_chunks
from .haystack_pilot import search_haystack_pilot
from .retrieval_eval import _anchor_matches, _catalog_digest, _file_digest, _gold


AUDIT_FIELDS = ("chunk_id", "filing_id", "source_id", "version_id", "raw_sha256",
                "issuer_id", "isin", "document_type", "speaker_role", "page_number",
                "text", "published_at", "first_seen_at", "extraction_recorded_at",
                "byte_start", "byte_end", "offset_basis", "availability_mode",
                "publication_allowed")
HARD_CATEGORIES = {"REVISION", "FUTURE_CUTOFF", "WRONG_ISSUER", "CONTRADICTION"}


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _corpus_digest(project_dir: Path) -> tuple[str, int]:
    """Fingerprint local evidence files; this is not an externally frozen corpus."""
    root = Path(project_dir)
    digest = hashlib.sha256()
    count = 0
    for relative in (Path("data/registry/sources"), Path("data/raw/sha256")):
        folder = root / relative
        if folder.is_symlink():
            raise ValueError("corpus path is a symlink")
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            if path.is_symlink():
                raise ValueError("corpus path is a symlink")
            if not path.is_file():
                continue
            count += 1
            if count > 100_000:
                raise ValueError("corpus has too many files for pilot evaluation")
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(_file_digest(path).encode("ascii"))
            digest.update(b"\n")
    return digest.hexdigest(), count


def _version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _score_case(case: dict, chunks: list[dict], verified: dict[str, dict]) -> dict:
    groups = case["evidence_groups"]
    group_hits = [any(any(_anchor_matches(anchor, chunk) for anchor in group)
                      for chunk in chunks) for group in groups]
    anchor_hit = bool(groups) and all(group_hits)
    matching_ranks = [index for index, chunk in enumerate(chunks, 1)
                      if any(_anchor_matches(anchor, chunk) for group in groups for anchor in group)]
    cutoff_violations = wrong_issuer_citations = citation_violations = 0
    for chunk in chunks:
        wrong_issuer_citations += int(chunk.get("issuer_id") != case["issuer_id"] or
                                      (case["isin"] is not None and chunk.get("isin") != case["isin"]))
        cutoff_violations += int(any(not isinstance(chunk.get(key), str) or chunk[key] > case["cutoff"]
                                     for key in ("published_at", "first_seen_at", "extraction_recorded_at")))
        expected = verified.get(chunk.get("chunk_id"))
        citation_violations += int(expected is None or any(chunk.get(key) != expected.get(key)
                                                           for key in AUDIT_FIELDS))
    return {"anchor_hit": anchor_hit, "group_hits": group_hits, "empty": not chunks,
            "retrieved_chunk_ids": [chunk.get("chunk_id") for chunk in chunks],
            "first_anchor_rank": min(matching_ranks) if matching_ranks else None,
            "anchor_matches": len(matching_ranks), "retrieved_count": len(chunks),
            "wrong_issuer_citations": wrong_issuer_citations,
            "cutoff_violations": cutoff_violations, "citation_violations": citation_violations,
            "error": None}


def _failed_case(exc: Exception) -> dict:
    return {"anchor_hit": False, "group_hits": [], "empty": False,
            "retrieved_chunk_ids": [], "first_anchor_rank": None,
            "anchor_matches": 0, "retrieved_count": 0,
            "wrong_issuer_citations": 0, "cutoff_violations": 0,
            "citation_violations": 0, "error": type(exc).__name__}


def _summarize(cases: list[dict], label: str, elapsed: float) -> dict:
    from haystack import Document
    from haystack.components.evaluators import DocumentRecallEvaluator

    answerable = [c[label] for c in cases if c["expected_state"] == "ANSWERABLE"]
    absent = [c[label] for c in cases if c["expected_state"] == "ABSENT"]
    conflict = [c[label] for c in cases if c["expected_state"] == "CONFLICT"]
    rows = [c[label] for c in cases]
    matches = sum(row["anchor_matches"] for row in rows)
    retrieved = sum(row["retrieved_count"] for row in rows)
    ground_truth, found_groups = [], []
    for case in cases:
        hits = case[label]["group_hits"]
        if not hits:
            continue
        group_docs = [Document(id=f"{case['case_id']}:{index}", content="source anchor group")
                      for index in range(len(hits))]
        ground_truth.append(group_docs)
        found_groups.append([doc for doc, hit in zip(group_docs, hits) if hit])
    # Haystack handles multi-group recall; the exact quote, version, raw hash,
    # and page match that defines each group remains the KB's local contract.
    group_recall = (DocumentRecallEvaluator(mode="multi_hit", document_comparison_field="id")
                    .run(ground_truth_documents=ground_truth,
                         retrieved_documents=found_groups)["score"] if ground_truth else None)
    return {"retrieval_method": "TOKEN_OVERLAP_V1" if label == "baseline" else "HAYSTACK_BM25_PILOT",
            "answerable_hit": sum(row["anchor_hit"] for row in answerable),
            "answerable_total": len(answerable),
            "recall_at_5": _rate(sum(row["anchor_hit"] for row in answerable), len(answerable)),
            "absent_empty": sum(row["empty"] for row in absent), "absent_total": len(absent),
            "abstention_accuracy": _rate(sum(row["empty"] for row in absent), len(absent)),
            "conflict_hit": sum(row["anchor_hit"] for row in conflict), "conflict_total": len(conflict),
            "haystack_anchor_group_recall": group_recall,
            "retrieval_anchor_precision": _rate(matches, retrieved),
            "anchor_matches": matches, "retrieved_total": retrieved,
            "wrong_issuer_citations": sum(row["wrong_issuer_citations"] for row in rows),
            "cutoff_violations": sum(row["cutoff_violations"] for row in rows),
            "citation_violations": sum(row["citation_violations"] for row in rows),
            "parse_failures": sum(row["error"] is not None for row in rows),
            "elapsed_seconds": round(elapsed, 6)}


def compare_rag_pilot(gold_path: Path, catalog_path: Path, project_dir: Path) -> dict:
    """Run both retrievers over the same validated gold, without activation."""
    gold_digest = _file_digest(gold_path)
    cases = _gold(gold_path)
    if _file_digest(gold_path) != gold_digest:
        raise ValueError("gold set changed during validation")
    catalog_digest = _catalog_digest(catalog_path)
    corpus_digest, corpus_files = _corpus_digest(project_dir)
    case_rows = []
    elapsed = {"baseline": 0.0, "candidate": 0.0}
    for case in cases:
        kwargs = {"isin": case["isin"], "document_types": case["document_types"],
                  "speaker_role": case["speaker_role"], "limit": 5}
        try:
            verified = {chunk["chunk_id"]: chunk for chunk in _verified_chunks(
                catalog_path, project_dir, case["issuer_id"], case["cutoff"],
                case["isin"], case["document_types"], case["speaker_role"])}
        except Exception:
            verified = {}
        row = {"case_id": case["case_id"], "category": case["category"],
               "expected_state": case["expected_state"]}
        for label, search in (("baseline", search_chunks), ("candidate", search_haystack_pilot)):
            start = perf_counter()
            try:
                chunks = search(catalog_path, project_dir, case["issuer_id"], case["question"],
                                case["cutoff"], **kwargs)
                row[label] = _score_case(case, chunks, verified)
            except Exception as exc:
                row[label] = _failed_case(exc)
            elapsed[label] += perf_counter() - start
        case_rows.append(row)
    if _catalog_digest(catalog_path) != catalog_digest:
        raise ValueError("evaluation catalog changed during scoring")
    if _file_digest(gold_path) != gold_digest:
        raise ValueError("gold set changed during scoring")
    if _corpus_digest(project_dir)[0] != corpus_digest:
        raise ValueError("evaluation corpus changed during scoring")
    baseline = _summarize(case_rows, "baseline", elapsed["baseline"])
    candidate = _summarize(case_rows, "candidate", elapsed["candidate"])
    hard_regressions = [row["case_id"] for row in case_rows if row["category"] in HARD_CATEGORIES
                        and row["baseline"]["anchor_hit"] and not row["candidate"]["anchor_hit"]]
    reasons = ["externally frozen corpus and baseline required",
               "answer quality and citation precision were not evaluated"]
    if cases[0]["dataset_kind"] != "REVIEWED_REAL":
        reasons.insert(0, "real reviewed gold required")
    if baseline["parse_failures"]:
        reasons.append("baseline retrieval failed")
    if candidate["parse_failures"]:
        reasons.append("candidate retrieval failed")
    if hard_regressions:
        reasons.append("hard-case regression")
    if candidate["wrong_issuer_citations"] or candidate["cutoff_violations"] or candidate["citation_violations"]:
        reasons.append("candidate provenance violation")
    unique_queries = {(c["issuer_id"], c["isin"], c["question"].casefold().strip(), c["cutoff"],
                       tuple(c["document_types"] or []), c["speaker_role"]) for c in cases}
    unique_anchors = {(a["version_id"], a["raw_sha256"], a["quote"], a.get("page_number"))
                      for c in cases for group in c["evidence_groups"] for a in group}
    return {"dataset_kind": cases[0]["dataset_kind"],
            "corpus_snapshot_id": cases[0]["corpus_snapshot_id"],
            "rubric_version": cases[0]["rubric_version"], "case_count": len(cases),
            "unique_query_count": len(unique_queries),
            "unique_evidence_anchor_count": len(unique_anchors),
            "gold_sha256": gold_digest, "catalog_sha256": catalog_digest,
            "corpus_sha256": corpus_digest, "corpus_file_count": corpus_files,
            "corpus_frozen": False,
            "baseline_identity": {"module_sha256": _file_digest(Path(filtered_retrieval.__file__)),
                                  "retrieval_method": "TOKEN_OVERLAP_V1"},
            "candidate_identity": {"module_sha256": _file_digest(Path(haystack_pilot.__file__)),
                                   "retrieval_method": "HAYSTACK_BM25_PILOT"},
            "package_versions": {"python": sys.version.split()[0], "haystack-ai": _version("haystack-ai"),
                                 "docling": _version("docling"), "pypdf": _version("pypdf")},
            "baseline": baseline, "candidate": candidate,
            "comparison": {"recall_delta": (candidate["recall_at_5"] - baseline["recall_at_5"])
                           if candidate["recall_at_5"] is not None and baseline["recall_at_5"] is not None else None,
                           "hard_case_regressions": hard_regressions},
            "answer_quality": "NOT_RUN", "cases": case_rows,
            "promotion_status": "NOT_PROMOTED", "promotion_allowed": False,
            "promotion_reasons": reasons}
