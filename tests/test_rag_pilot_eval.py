"""Paired RAG pilot scoring on the existing 04E gold contract."""

import pytest

pytest.importorskip("haystack")

from test_retrieval_eval import _fixture, _write_jsonl
from src.kb_runtime.rag_pilot_eval import compare_rag_pilot


def test_synthetic_pairs_same_32_cases_and_never_promotes(tmp_path):
    project, catalog, gold, cases, *_ = _fixture(tmp_path)
    report = compare_rag_pilot(gold, catalog, project)
    assert report["dataset_kind"] == "SYNTHETIC_FIXTURE"
    assert report["case_count"] == len(cases) == 32
    assert [r["case_id"] for r in report["cases"]] == [c["case_id"] for c in cases]
    assert report["baseline"]["answerable_total"] == report["candidate"]["answerable_total"] == 21
    assert report["baseline"]["recall_at_5"] == report["candidate"]["recall_at_5"] == 1.0
    assert report["candidate"]["absent_empty"] == 10
    assert report["candidate"]["conflict_hit"] == 1
    assert report["candidate"]["haystack_anchor_group_recall"] == 1.0
    assert report["gold_sha256"] and report["catalog_sha256"] and report["corpus_sha256"]
    assert report["package_versions"]["haystack-ai"] == "3.2.0"
    assert report["promotion_status"] == "NOT_PROMOTED"
    assert report["promotion_allowed"] is False
    assert report["corpus_frozen"] is False
    assert report["answer_quality"] == "NOT_RUN"


def test_changed_gold_and_corpus_change_receipt_hashes(tmp_path):
    project, catalog, gold, cases, *_ = _fixture(tmp_path)
    original = compare_rag_pilot(gold, catalog, project)
    cases[0]["gold_answer"] = "New wording"
    _write_jsonl(gold, cases)
    changed_gold = compare_rag_pilot(gold, catalog, project)
    assert changed_gold["gold_sha256"] != original["gold_sha256"]
    assert changed_gold["corpus_sha256"] == original["corpus_sha256"]
    extra = project / "data/raw/sha256" / ("a" * 64)
    extra.write_bytes(b"new synthetic byte sequence")
    changed_corpus = compare_rag_pilot(gold, catalog, project)
    assert changed_corpus["corpus_sha256"] != changed_gold["corpus_sha256"]


def test_wrong_page_and_future_chunk_are_violations(tmp_path, monkeypatch):
    project, catalog, gold, cases, _, other, _ = _fixture(tmp_path)
    cases[-1]["evidence_groups"][1][0]["page_number"] = other["page_number"]
    _write_jsonl(gold, cases)
    from src.kb_runtime import rag_pilot_eval
    real_search = rag_pilot_eval.search_haystack_pilot

    def forged(*args, **kwargs):
        chunks = real_search(*args, **kwargs)
        if chunks and kwargs.get("document_types") == ["CONCALL_TRANSCRIPT"]:
            changed = {**chunks[0], "page_number": 999,
                       "extraction_recorded_at": "2099-01-01T00:00:00+00:00"}
            return [changed, *chunks[1:]]
        return chunks

    monkeypatch.setattr(rag_pilot_eval, "search_haystack_pilot", forged)
    report = compare_rag_pilot(gold, catalog, project)
    assert report["candidate"]["cutoff_violations"] > 0
    assert report["candidate"]["citation_violations"] > 0
    assert report["promotion_allowed"] is False


def test_parse_failure_and_missing_baseline_block_promotion(tmp_path, monkeypatch):
    project, catalog, gold, *_ = _fixture(tmp_path)
    from src.kb_runtime import rag_pilot_eval
    def failed(*args, **kwargs):
        raise ValueError("synthetic parse failed")
    monkeypatch.setattr(rag_pilot_eval, "search_haystack_pilot", failed)
    report = compare_rag_pilot(gold, catalog, project)
    assert report["candidate"]["parse_failures"] == report["case_count"]
    assert report["candidate"]["recall_at_5"] == 0.0
    assert report["promotion_status"] == "NOT_PROMOTED"
    monkeypatch.setattr(rag_pilot_eval, "search_chunks", failed)
    report = compare_rag_pilot(gold, catalog, project)
    assert report["baseline"]["parse_failures"] == report["case_count"]
    assert "baseline retrieval failed" in report["promotion_reasons"]


def test_zero_answerable_denominator_is_explicit(tmp_path):
    from src.kb_runtime import rag_pilot_eval
    assert rag_pilot_eval._rate(0, 0) is None
    absent = {"anchor_hit": False, "group_hits": [], "empty": True,
              "retrieved_count": 0, "anchor_matches": 0,
              "wrong_issuer_citations": 0, "cutoff_violations": 0,
              "citation_violations": 0, "error": None}
    row = {"case_id": "ABSENT-00", "expected_state": "ABSENT",
           "baseline": absent, "candidate": absent}
    report = rag_pilot_eval._summarize([row], "candidate", 0.0)
    assert report["recall_at_5"] is None
    assert report["haystack_anchor_group_recall"] is None


def test_absent_and_conflict_cases_are_separate(tmp_path):
    project, catalog, gold, cases, *_ = _fixture(tmp_path)
    report = compare_rag_pilot(gold, catalog, project)
    missing = [r for r in report["cases"] if r["expected_state"] == "ABSENT"]
    conflict = [r for r in report["cases"] if r["expected_state"] == "CONFLICT"]
    assert len(missing) == 10 and len(conflict) == 1
    assert all(r["candidate"]["empty"] for r in missing)
    assert conflict[0]["candidate"]["anchor_hit"] is True
