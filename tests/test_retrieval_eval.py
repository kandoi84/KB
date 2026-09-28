import json
import subprocess
import sys

import pytest

from test_filtered_retrieval import _cutoff, _setup_filings
from test_metric_store import _setup, _source, _write
from src.kb_runtime.filtered_retrieval import search_chunks
from src.kb_runtime.metric_store import register_filing
from src.kb_runtime.retrieval_eval import evaluate_retrieval
from src.kb_runtime.text_chunks import extract_text_filing


def _write_jsonl(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    return path


def _fixture(tmp_path):
    project, catalog = _setup_filings(tmp_path)
    cutoff = _cutoff()
    hit = next(row for row in search_chunks(catalog, project, 'SBI', 'guidance', cutoff)
               if row['filing_id'] == 'TEXT1')
    other = next(row for row in search_chunks(catalog, project, 'SBI', 'guidance', cutoff)
                 if row['filing_id'] == 'PDF1')
    for filing_id, published, seen, reviewed, content, predecessor in (
            ('REV1', '2026-09-28T09:10:00+05:30', '2026-09-28T09:11:00+05:30',
             '2026-09-28T09:12:00+05:30', 'Capital guidance was old', None),
            ('REV2', '2026-09-28T09:13:00+05:30', '2026-09-28T09:14:00+05:30',
             '2026-09-28T09:15:00+05:30', 'Capital guidance is revised', 'REV1')):
        folder = tmp_path / filing_id
        folder.mkdir()
        _, _, path, request = _setup(folder)
        source = _source(folder, project, filing_id, content, published, seen)
        request.update(filing_id=filing_id, source_id=filing_id, version_id=source['version_id'],
                       document_type='ANNUAL_REPORT', metrics=[], published_at=published,
                       first_seen_at=seen, reviewed_at=reviewed,
                       supersedes_filing_id=predecessor)
        register_filing(_write(path, request), project, catalog)
        extract_text_filing(catalog, project, filing_id)
    revised = next(row for row in search_chunks(catalog, project, 'SBI', 'capital', _cutoff())
                   if row['filing_id'] == 'REV2')
    base = {'dataset_kind': 'SYNTHETIC_FIXTURE', 'corpus_snapshot_id': 'synthetic-v1',
            'rubric_version': 'text-eval-v1', 'issuer_id': 'SBI', 'isin': 'INE062A01020',
            'document_types': ['CONCALL_TRANSCRIPT'], 'speaker_role': None,
            'reviewer_id': 'SYNTHETIC_TEST', 'reviewed_at': cutoff}
    cases = []
    for number in range(20):
        cases.append({**base, 'case_id': f'DIRECT-{number:02}', 'category': 'DIRECT',
                      'question': 'management guidance', 'cutoff': cutoff,
                      'expected_state': 'ANSWERABLE', 'gold_answer': 'Demand guidance',
                      'evidence_groups': [[{'version_id': hit['version_id'],
                                            'raw_sha256': hit['raw_sha256'],
                                            'quote': 'Management guidance demand'}]]})
    for number in range(5):
        cases.append({**base, 'case_id': f'MISSING-{number:02}', 'category': 'MISSING',
                      'question': f'unknownconcept{number}', 'cutoff': cutoff,
                      'expected_state': 'ABSENT', 'gold_answer': None, 'evidence_groups': []})
    for number in range(4):
        cases.append({**base, 'case_id': f'FUTURE-{number:02}', 'category': 'FUTURE_CUTOFF',
                      'question': 'management guidance', 'cutoff': '2026-09-28T09:03:00+05:30',
                      'expected_state': 'ABSENT', 'gold_answer': None, 'evidence_groups': []})
    cases.append({**base, 'case_id': 'REVISION-00', 'category': 'REVISION',
                  'question': 'capital guidance', 'document_types': ['ANNUAL_REPORT'],
                  'cutoff': cutoff,
                  'expected_state': 'ANSWERABLE', 'gold_answer': 'Revised capital guidance',
                  'evidence_groups': [[{'version_id': revised['version_id'],
                                        'raw_sha256': revised['raw_sha256'],
                                        'quote': 'Capital guidance is revised'}]]})
    cases.append({**base, 'case_id': 'WRONG-ISSUER-00', 'category': 'WRONG_ISSUER',
                  'issuer_id': 'OTHER', 'isin': None, 'question': 'supply guidance', 'cutoff': cutoff,
                  'expected_state': 'ABSENT', 'gold_answer': None, 'evidence_groups': []})
    cases.append({**base, 'case_id': 'CONFLICT-00', 'category': 'CONTRADICTION',
                  'question': 'management guidance', 'cutoff': cutoff,
                  'expected_state': 'CONFLICT', 'gold_answer': None,
                  'evidence_groups': [
                      [{'version_id': hit['version_id'], 'raw_sha256': hit['raw_sha256'],
                        'quote': 'Management guidance demand'}],
                      [{'version_id': other['version_id'], 'raw_sha256': other['raw_sha256'],
                        'quote': 'Management supply guidance'}]]})
    return project, catalog, _write_jsonl(tmp_path / 'gold.jsonl', cases), cases, hit, other, revised


def test_synthetic_gold_scores_retrieval_and_submitted_answers(tmp_path):
    project, catalog, gold, cases, hit, other, revised = _fixture(tmp_path)
    answers = []
    for case in cases:
        if case['expected_state'] == 'ANSWERABLE':
            chosen = revised if case['category'] == 'REVISION' else hit
            answers.append({'case_id': case['case_id'], 'status': 'ANSWER',
                            'answer_text': case['gold_answer'], 'citations': [chosen['chunk_id']]})
        elif case['expected_state'] == 'CONFLICT':
            answers.append({'case_id': case['case_id'], 'status': 'CONFLICT',
                            'answer_text': '', 'citations': [hit['chunk_id'], other['chunk_id']]})
        else:
            answers.append({'case_id': case['case_id'], 'status': 'ABSTAIN',
                            'answer_text': '', 'citations': []})
    answer_file = _write_jsonl(tmp_path / 'answers.jsonl', answers)
    report = evaluate_retrieval(gold, catalog, project, answer_file)
    assert report['case_count'] == 32
    assert report['unique_query_count'] < report['case_count']
    assert report['unique_evidence_anchor_count'] == 3
    assert len(report['catalog_sha256']) == 64
    assert report['retrieval']['recall_at_5'] == 1.0
    assert report['answers']['accuracy'] == 1.0
    assert report['answers']['citation_precision'] == 1.0
    assert report['answers']['abstention_accuracy'] == 1.0
    assert report['promotion_allowed'] is False


def test_answer_quality_not_run_without_submissions(tmp_path):
    project, catalog, gold, _, _, _, _ = _fixture(tmp_path)
    report = evaluate_retrieval(gold, catalog, project)
    assert report['answers']['status'] == 'NOT_RUN'
    assert report['dataset_kind'] == 'SYNTHETIC_FIXTURE'
    cli = subprocess.run([sys.executable, '-m', 'src.kb_runtime', 'eval-retrieval',
                          '--gold', str(gold), '--project-dir', str(project),
                          '--catalog', str(catalog)], capture_output=True, text=True)
    assert cli.returncode == 0, cli.stderr
    assert json.loads(cli.stdout)['retrieval']['answerable_hit'] == 21


def test_gold_rejects_wrong_citation_and_invalid_set(tmp_path):
    project, catalog, gold, cases, hit, _, _ = _fixture(tmp_path)
    answers = [{'case_id': case['case_id'], 'status': 'ABSTAIN',
                'answer_text': '', 'citations': []} for case in cases]
    answers[0] = {'case_id': cases[0]['case_id'], 'status': 'ANSWER',
                  'answer_text': 'Demand guidance', 'citations': ['wrong-chunk']}
    report = evaluate_retrieval(gold, catalog, project,
                                _write_jsonl(tmp_path / 'answers.jsonl', answers))
    assert report['answers']['citation_precision'] == 0.0
    assert report['answers']['accuracy'] < 1.0
    cases[0]['case_id'] = cases[1]['case_id']
    _write_jsonl(gold, cases)
    with pytest.raises(ValueError, match='duplicate'):
        evaluate_retrieval(gold, catalog, project)


def test_gold_anchor_and_category_are_checked(tmp_path):
    project, catalog, gold, cases, _, _, _ = _fixture(tmp_path)
    cases[0]['evidence_groups'][0][0]['quote'] = 'quote never present'
    _write_jsonl(gold, cases)
    report = evaluate_retrieval(gold, catalog, project)
    assert report['retrieval']['answerable_hit'] == 20
    cases[0]['category'] = 'MISSING'
    _write_jsonl(gold, cases)
    with pytest.raises(ValueError, match='category and state'):
        evaluate_retrieval(gold, catalog, project)


@pytest.mark.parametrize('field', ['dataset_kind', 'speaker_role', 'category', 'expected_state'])
def test_malformed_gold_value_is_rejected(tmp_path, field):
    project, catalog, gold, cases, _, _, _ = _fixture(tmp_path)
    cases[0][field] = []
    _write_jsonl(gold, cases)
    with pytest.raises(ValueError):
        evaluate_retrieval(gold, catalog, project)


def test_duplicate_answer_citations_are_rejected(tmp_path):
    project, catalog, gold, cases, hit, _, _ = _fixture(tmp_path)
    answers = [{'case_id': case['case_id'], 'status': 'ABSTAIN',
                'answer_text': '', 'citations': []} for case in cases]
    answers[0] = {'case_id': cases[0]['case_id'], 'status': 'ANSWER',
                  'answer_text': 'Demand guidance',
                  'citations': [hit['chunk_id'], hit['chunk_id']]}
    with pytest.raises(ValueError, match='citations'):
        evaluate_retrieval(gold, catalog, project,
                           _write_jsonl(tmp_path / 'answers.jsonl', answers))


def test_conflict_requires_two_distinct_evidence_groups(tmp_path):
    project, catalog, gold, cases, _, _, _ = _fixture(tmp_path)
    cases[-1]['evidence_groups'][1] = cases[-1]['evidence_groups'][0]
    _write_jsonl(gold, cases)
    with pytest.raises(ValueError, match='conflict evidence'):
        evaluate_retrieval(gold, catalog, project)
