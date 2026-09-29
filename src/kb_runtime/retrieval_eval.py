"""Reviewed-gold scoring for cited text retrieval and submitted answers."""

import json
import hashlib
import re
from pathlib import Path

from .filtered_retrieval import search_chunks
from .identity_store import _timestamp, _valid_isin
from .metric_store import DOCUMENTS, _id


CASE_FIELDS = {"case_id", "dataset_kind", "corpus_snapshot_id", "rubric_version",
               "question", "issuer_id", "isin", "cutoff", "document_types",
               "speaker_role", "category", "expected_state", "gold_answer",
               "evidence_groups", "reviewer_id", "reviewed_at"}
ANSWER_FIELDS = {"case_id", "status", "answer_text", "citations"}
STATES = {"ANSWERABLE", "ABSENT", "CONFLICT"}
CATEGORIES = {"DIRECT", "MISSING", "REVISION", "FUTURE_CUTOFF",
              "WRONG_ISSUER", "CONTRADICTION"}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _jsonl(path: Path, label: str) -> list[dict]:
    try:
        if Path(path).stat().st_size > 1_000_000:
            raise ValueError(f"{label} is too large")
        raw = Path(path).read_bytes()
        if len(raw) > 1_000_000:
            raise ValueError(f"{label} is too large")
        lines = raw.decode("utf-8").splitlines()
        rows = [json.loads(line) for line in lines if line.strip()]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be UTF-8 JSONL") from exc
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"{label} must contain objects")
    return rows


def _gold(path: Path) -> list[dict]:
    cases = _jsonl(path, "gold set")
    if not 30 <= len(cases) <= 50:
        raise ValueError("gold set must contain 30 to 50 cases")
    seen = set()
    for case in cases:
        if set(case) != CASE_FIELDS:
            raise ValueError("gold case fields are invalid")
        _id(case["case_id"], "case_id")
        if case["case_id"] in seen:
            raise ValueError("duplicate gold case ID")
        seen.add(case["case_id"])
        _id(case["issuer_id"], "issuer_id")
        _id(case["reviewer_id"], "reviewer_id")
        _id(case["corpus_snapshot_id"], "corpus_snapshot_id")
        _id(case["rubric_version"], "rubric_version")
        case["cutoff"] = _timestamp(case["cutoff"], "cutoff")
        case["reviewed_at"] = _timestamp(case["reviewed_at"], "reviewed_at")
        if type(case["dataset_kind"]) is not str or case["dataset_kind"] not in {"SYNTHETIC_FIXTURE", "REVIEWED_REAL"}:
            raise ValueError("dataset_kind is invalid")
        if not isinstance(case["question"], str) or not case["question"].strip() or len(case["question"]) > 500:
            raise ValueError("gold question is invalid")
        if case["isin"] is not None and not _valid_isin(case["isin"]):
            raise ValueError("gold ISIN is invalid")
        types = case["document_types"]
        if types is not None and (not isinstance(types, list) or not types or
                                  any(type(t) is not str or t not in DOCUMENTS for t in types) or
                                  len(types) != len(set(types))):
            raise ValueError("gold document types are invalid")
        if case["speaker_role"] is not None and (type(case["speaker_role"]) is not str or
                                                 case["speaker_role"] not in
                                                 {"UNKNOWN", "MANAGEMENT", "ANALYST", "MODERATOR"}):
            raise ValueError("gold speaker role is invalid")
        if (type(case["category"]) is not str or case["category"] not in CATEGORIES or
                type(case["expected_state"]) is not str or case["expected_state"] not in STATES):
            raise ValueError("gold category or state is invalid")
        expected_category_state = {"DIRECT": "ANSWERABLE", "REVISION": "ANSWERABLE",
                                   "MISSING": "ABSENT", "FUTURE_CUTOFF": "ABSENT",
                                   "WRONG_ISSUER": "ABSENT", "CONTRADICTION": "CONFLICT"}
        if case["expected_state"] != expected_category_state[case["category"]]:
            raise ValueError("gold category and state disagree")
        if case["dataset_kind"] == "REVIEWED_REAL" and case["reviewer_id"] == "SYNTHETIC_TEST":
            raise ValueError("real gold needs a named reviewer")
        groups = case["evidence_groups"]
        if not isinstance(groups, list):
            raise ValueError("gold evidence groups are invalid")
        if case["expected_state"] == "ABSENT":
            if groups or case["gold_answer"] is not None:
                raise ValueError("absent case cannot have an answer or evidence")
        elif (len(groups) < (2 if case["expected_state"] == "CONFLICT" else 1) or
              (case["expected_state"] == "ANSWERABLE" and
               (not isinstance(case["gold_answer"], str) or not case["gold_answer"].strip())) or
              (case["expected_state"] == "CONFLICT" and case["gold_answer"] is not None)):
            raise ValueError("answerable or conflict case lacks gold evidence")
        for group in groups:
            if not isinstance(group, list) or not group:
                raise ValueError("gold evidence group is empty")
            for anchor in group:
                if not isinstance(anchor, dict) or set(anchor) not in (
                        {"version_id", "raw_sha256", "quote"},
                        {"version_id", "raw_sha256", "quote", "page_number"}):
                    raise ValueError("gold evidence anchor fields are invalid")
                if any(not isinstance(anchor[key], str) or not SHA256.fullmatch(anchor[key])
                       for key in ("version_id", "raw_sha256")):
                    raise ValueError("gold evidence identity is invalid")
                if not isinstance(anchor["quote"], str) or not anchor["quote"].strip() or len(anchor["quote"]) > 500:
                    raise ValueError("gold quote is invalid")
                if "page_number" in anchor and (type(anchor["page_number"]) is not int or anchor["page_number"] < 1):
                    raise ValueError("gold page number is invalid")
        if case["expected_state"] == "CONFLICT":
            identities = [{(a["version_id"], a["raw_sha256"], a["quote"], a.get("page_number"))
                           for a in group} for group in groups]
            if len(set().union(*identities)) < 2 or any(left == right for index, left in enumerate(identities)
                                                        for right in identities[index + 1:]):
                raise ValueError("conflict evidence groups must be distinct")
    if len({(c["dataset_kind"], c["corpus_snapshot_id"], c["rubric_version"]) for c in cases}) != 1:
        raise ValueError("gold set mixes dataset or rubric versions")
    if sum(c["expected_state"] == "ABSENT" for c in cases) < 5:
        raise ValueError("gold set needs five absent cases")
    if sum(c["category"] in {"REVISION", "FUTURE_CUTOFF"} for c in cases) < 5:
        raise ValueError("gold set needs five revision or future cases")
    if not any(c["category"] == "REVISION" for c in cases):
        raise ValueError("gold set needs a revision case")
    if not any(c["category"] == "WRONG_ISSUER" for c in cases):
        raise ValueError("gold set needs a wrong-issuer case")
    if not any(c["expected_state"] == "CONFLICT" for c in cases):
        raise ValueError("gold set needs a conflict case")
    if cases[0]["dataset_kind"] == "REVIEWED_REAL":
        unique = {(c["issuer_id"], c["isin"], c["question"].casefold().strip(), c["cutoff"],
                   tuple(c["document_types"] or []), c["speaker_role"]) for c in cases}
        if len(unique) != len(cases):
            raise ValueError("real gold has duplicate query cases")
    return cases


def _answers(path: Path, case_ids: set[str]) -> dict[str, dict]:
    rows = _jsonl(path, "answer file")
    result = {}
    for row in rows:
        if set(row) != ANSWER_FIELDS or not isinstance(row["case_id"], str) or row["case_id"] in result:
            raise ValueError("answer row fields or duplicate ID are invalid")
        if (type(row["status"]) is not str or row["status"] not in {"ANSWER", "ABSTAIN", "CONFLICT"}
                or not isinstance(row["answer_text"], str)):
            raise ValueError("answer status or text is invalid")
        if (not isinstance(row["citations"], list) or
                any(not isinstance(c, str) for c in row["citations"]) or
                len(row["citations"]) != len(set(row["citations"]))):
            raise ValueError("answer citations are invalid")
        result[row["case_id"]] = row
    if set(result) != case_ids:
        raise ValueError("answer IDs do not match gold cases")
    return result


def _anchor_matches(anchor: dict, chunk: dict) -> bool:
    return (anchor["version_id"] == chunk["version_id"] and
            anchor["raw_sha256"] == chunk["raw_sha256"] and
            anchor["quote"] in chunk["text"] and
            ("page_number" not in anchor or anchor["page_number"] == chunk["page_number"]))


def _normalize_answer(value: str) -> str:
    return " ".join(value.casefold().split())


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise ValueError("evaluation input is missing or unreadable") from exc
    return digest.hexdigest()


def _catalog_digest(path: Path) -> str:
    if not Path(path).is_file():
        raise ValueError("evaluation catalog is missing")
    digest = hashlib.sha256()
    for candidate in (Path(path), Path(f"{path}-wal")):
        if candidate.is_file():
            digest.update(candidate.name.encode("utf-8"))
            digest.update(_file_digest(candidate).encode("ascii"))
    return digest.hexdigest()


def evaluate_retrieval(gold_path: Path, catalog_path: Path, project_dir: Path,
                       answers_path: Path | None = None) -> dict:
    """Score text evidence; candidate answers are optional and never generated here."""
    gold_digest = _file_digest(gold_path)
    cases = _gold(gold_path)
    if _file_digest(gold_path) != gold_digest:
        raise ValueError("gold set changed during validation")
    submissions = _answers(answers_path, {c["case_id"] for c in cases}) if answers_path else None
    catalog_digest = _catalog_digest(catalog_path)
    results = []
    answerable = retrieval_hits = absent = empty_absent = 0
    correct = abstention_total = abstention_correct = valid_citations = citation_total = 0
    for case in cases:
        chunks = search_chunks(catalog_path, project_dir, case["issuer_id"], case["question"],
                               case["cutoff"], isin=case["isin"],
                               document_types=case["document_types"],
                               speaker_role=case["speaker_role"], limit=5)
        for chunk in chunks:
            if (chunk["issuer_id"] != case["issuer_id"] or
                    (case["isin"] is not None and chunk["isin"] != case["isin"]) or
                    any(chunk[key] > case["cutoff"] for key in
                        ("published_at", "first_seen_at", "extraction_recorded_at"))):
                raise ValueError("retrieval violated issuer or cutoff provenance")
        group_ids = [{chunk["chunk_id"] for chunk in chunks
                      if any(_anchor_matches(anchor, chunk) for anchor in group)}
                     for group in case["evidence_groups"]]
        hit = bool(group_ids) and all(group_ids)
        if case["expected_state"] == "ANSWERABLE":
            answerable += 1
            retrieval_hits += int(hit)
        if case["expected_state"] == "ABSENT":
            absent += 1
            empty_absent += int(not chunks)
        row = {"case_id": case["case_id"], "category": case["category"],
               "expected_state": case["expected_state"], "retrieval_hit": hit,
               "retrieved_chunk_ids": [chunk["chunk_id"] for chunk in chunks]}
        if submissions is not None:
            submitted = submissions[case["case_id"]]
            gold_ids = set().union(*group_ids) if group_ids else set()
            citations = submitted["citations"]
            citation_total += len(citations)
            valid_citations += sum(citation in gold_ids for citation in citations)
            cited = set(citations)
            covered = bool(group_ids) and all(ids & cited for ids in group_ids)
            if case["expected_state"] == "ANSWERABLE":
                passed = (submitted["status"] == "ANSWER" and
                          _normalize_answer(submitted["answer_text"]) ==
                          _normalize_answer(case["gold_answer"]) and
                          bool(citations) and set(citations) <= gold_ids and covered)
            elif case["expected_state"] == "CONFLICT":
                abstention_total += 1
                passed = (submitted["status"] == "CONFLICT" and not submitted["answer_text"].strip()
                          and bool(citations) and set(citations) <= gold_ids and covered)
                abstention_correct += int(passed)
            else:
                abstention_total += 1
                passed = (submitted["status"] == "ABSTAIN" and not submitted["answer_text"].strip()
                          and not citations)
                abstention_correct += int(passed)
            correct += int(passed)
            row["answer_passed"] = passed
        results.append(row)
    answer_report = {"status": "NOT_RUN"} if submissions is None else {
        "status": "SCORED", "correct": correct, "total": len(cases),
        "accuracy": correct / len(cases),
        "citation_valid": valid_citations, "citation_total": citation_total,
        "citation_precision": valid_citations / citation_total if citation_total else None,
        "abstention_correct": abstention_correct, "abstention_total": abstention_total,
        "abstention_accuracy": abstention_correct / abstention_total if abstention_total else None}
    if _catalog_digest(catalog_path) != catalog_digest:
        raise ValueError("evaluation catalog changed during scoring")
    if _file_digest(gold_path) != gold_digest:
        raise ValueError("gold set changed during scoring")
    unique_queries = {(c["issuer_id"], c["isin"], c["question"].casefold().strip(),
                       c["cutoff"], tuple(c["document_types"] or []), c["speaker_role"])
                      for c in cases}
    unique_anchors = {(a["version_id"], a["raw_sha256"], a["quote"], a.get("page_number"))
                      for c in cases for group in c["evidence_groups"] for a in group}
    return {"dataset_kind": cases[0]["dataset_kind"],
            "corpus_snapshot_id": cases[0]["corpus_snapshot_id"],
            "catalog_sha256": catalog_digest, "gold_sha256": gold_digest,
            "corpus_frozen": False, "retrieval_method": "TOKEN_OVERLAP_V1",
            "rubric_version": cases[0]["rubric_version"], "case_count": len(cases),
            "unique_query_count": len(unique_queries), "unique_evidence_anchor_count": len(unique_anchors),
            "retrieval": {"answerable_hit": retrieval_hits, "answerable_total": answerable,
                          "recall_at_5": retrieval_hits / answerable if answerable else None,
                          "absent_empty": empty_absent, "absent_total": absent},
            "answers": answer_report, "cases": results,
            "promotion_allowed": False,
            "promotion_reason": "real reviewed corpus and frozen baseline required"}
