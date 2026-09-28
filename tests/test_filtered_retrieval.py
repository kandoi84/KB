from datetime import datetime, timedelta, timezone
import json
import sqlite3
import subprocess
import sys

import pytest

from test_metric_store import _setup, _source, _write
from test_pdf_chunks import _pdf
from src.kb_runtime.metric_store import register_filing
from src.kb_runtime.pdf_chunks import extract_pdf_filing
from src.kb_runtime.source_store import record_source
from src.kb_runtime.text_chunks import extract_text_filing
from src.kb_runtime.filtered_retrieval import search_chunks


def _cutoff(seconds=1):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _setup_filings(tmp_path):
    project, catalog, path, request = _setup(tmp_path)
    request['document_type'] = 'CONCALL_TRANSCRIPT'
    request['metrics'] = []
    source = _source(tmp_path, project, 'TEXT1', 'Management guidance demand\n',
                     '2026-09-28T09:00:00+05:30', '2026-09-28T09:02:00+05:30')
    request.update(filing_id='TEXT1', source_id='TEXT1', version_id=source['version_id'])
    register_filing(_write(path, request), project, catalog)
    extract_text_filing(catalog, project, 'TEXT1')
    raw = tmp_path / 'pdf1.pdf'
    raw.write_bytes(_pdf(['Analyst demand question'], ['Management supply guidance']))
    metadata = {'source_id': 'PDF1', 'entity': 'SBI', 'source_kind': 'EXCHANGE_FILING',
                'url': 'https://example.org/pdf1', 'source_date': '2026-09-28',
                'observed_at': '2026-09-28T09:00:00+05:30',
                'retrieved_at': '2026-09-28T09:02:00+05:30'}
    pdf_source = record_source(_write(tmp_path / 'source.json', metadata), raw, project)
    request.update(filing_id='PDF1', source_id='PDF1', version_id=pdf_source['version_id'])
    register_filing(_write(path, request), project, catalog)
    extract_pdf_filing(catalog, project, 'PDF1')
    return project, catalog


def test_search_filters_and_cites_both_formats(tmp_path):
    project, catalog = _setup_filings(tmp_path)
    found = search_chunks(catalog, project, 'SBI', 'demand', _cutoff())
    assert [row['filing_id'] for row in found] == ['PDF1', 'TEXT1']
    assert all(row['chunk_id'] and row['raw_sha256'] and row['publication_allowed'] is False for row in found)
    assert {row['offset_basis'] for row in found} == {'DERIVED_PAGE_UTF8', 'RAW_UTF8'}
    assert [row['page_number'] for row in found] == [1, None]
    assert search_chunks(catalog, project, 'SBI', 'demand', _cutoff(), limit=1) == found[:1]
    assert [row['filing_id'] for row in search_chunks(catalog, project, 'SBI', 'demand', _cutoff(),
                                                      document_types=['CONCALL_TRANSCRIPT'])] == ['PDF1', 'TEXT1']
    assert search_chunks(catalog, project, 'SBI', 'absentword', _cutoff()) == []


def test_cutoff_issuer_isin_and_role_filters(tmp_path):
    project, catalog = _setup_filings(tmp_path)
    assert search_chunks(catalog, project, 'SBI', 'demand', '2026-09-28T09:03:00+05:30') == []
    assert search_chunks(catalog, project, 'OTHER', 'demand', _cutoff()) == []
    assert len(search_chunks(catalog, project, 'SBI', 'demand', _cutoff(), isin='INE062A01020')) == 2
    assert len(search_chunks(catalog, project, 'SBI', 'demand', _cutoff(), speaker_role='UNKNOWN')) == 2
    assert search_chunks(catalog, project, 'SBI', 'demand', _cutoff(), speaker_role='MANAGEMENT') == []
    with pytest.raises(ValueError, match='ISIN|isin'):
        search_chunks(catalog, project, 'SBI', 'demand', _cutoff(), isin='INE000A01000')


def test_missing_extraction_is_skipped_but_damaged_registered_source_blocks(tmp_path):
    project, catalog = _setup_filings(tmp_path)
    source = _source(tmp_path, project, 'UNEXTRACTED', 'demand unretrieved',
                     '2026-09-28T09:00:00+05:30', '2026-09-28T09:02:00+05:30')
    (tmp_path / 'other').mkdir()
    _, _, path, request = _setup(tmp_path / 'other')
    request.update(filing_id='UNEXTRACTED', source_id='UNEXTRACTED', version_id=source['version_id'],
                   document_type='CONCALL_TRANSCRIPT', metrics=[])
    register_filing(_write(path, request), project, catalog)
    assert len(search_chunks(catalog, project, 'SBI', 'demand', _cutoff())) == 2
    raw = project / 'data/raw/sha256' / source['raw_sha256']
    raw.write_text('damaged')
    assert len(search_chunks(catalog, project, 'SBI', 'demand', _cutoff())) == 2
    source_text = next((project / 'data/registry/sources/TEXT1').glob('*.json'))
    text_hash = json.loads(source_text.read_text())['raw_sha256']
    (project / 'data/raw/sha256' / text_hash).write_text('damaged')
    with pytest.raises(ValueError, match='source|digest'):
        search_chunks(catalog, project, 'SBI', 'demand', _cutoff())


def test_search_cli_returns_same_ids(tmp_path):
    project, catalog = _setup_filings(tmp_path)
    cutoff = _cutoff()
    expected = search_chunks(catalog, project, 'SBI', 'demand', cutoff)
    result = subprocess.run([sys.executable, '-m', 'src.kb_runtime', 'search-chunks',
                             '--issuer-id', 'SBI', '--query', 'demand', '--cutoff', cutoff,
                             '--project-dir', str(project), '--catalog', str(catalog)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert [row['chunk_id'] for row in json.loads(result.stdout)['chunks']] == [row['chunk_id'] for row in expected]


def test_visible_filing_revision_hides_prior_by_default(tmp_path):
    project, catalog = _setup_filings(tmp_path)
    (tmp_path / 'revision').mkdir()
    _, _, path, request = _setup(tmp_path / 'revision')
    source = _source(tmp_path, project, 'TEXT2', 'Management demand revised\n',
                     '2026-09-28T09:05:00+05:30', '2026-09-28T09:06:00+05:30')
    request.update(filing_id='TEXT2', source_id='TEXT2', version_id=source['version_id'],
                   document_type='CONCALL_TRANSCRIPT', metrics=[], supersedes_filing_id='TEXT1',
                   published_at='2026-09-28T09:05:00+05:30',
                   first_seen_at='2026-09-28T09:06:00+05:30',
                   reviewed_at='2026-09-28T09:07:00+05:30')
    register_filing(_write(path, request), project, catalog)
    extract_text_filing(catalog, project, 'TEXT2')
    assert [row['filing_id'] for row in search_chunks(catalog, project, 'SBI', 'demand', _cutoff())] == ['PDF1', 'TEXT2']
    old = search_chunks(catalog, project, 'SBI', 'demand', _cutoff(), include_superseded=True)
    assert [row['filing_id'] for row in old] == ['PDF1', 'TEXT1', 'TEXT2']
    assert [row['superseded_at_cutoff'] for row in old] == [False, True, False]


def test_damaged_revision_link_blocks_search(tmp_path):
    project, catalog = _setup_filings(tmp_path)
    with sqlite3.connect(catalog) as db:
        db.execute('DROP TRIGGER filings_no_update')
        db.execute("UPDATE filings SET supersedes_filing_id='PDF1' WHERE filing_id='TEXT1'")
    with pytest.raises(ValueError, match='filing revision is invalid'):
        search_chunks(catalog, project, 'SBI', 'demand', _cutoff())


def test_candidate_limit_follows_document_filter(tmp_path, monkeypatch):
    project, catalog = _setup_filings(tmp_path)
    with sqlite3.connect(catalog) as db:
        db.execute('DROP TRIGGER filings_no_update')
        db.execute("UPDATE filings SET document_type='ANNUAL_REPORT' WHERE filing_id='PDF1'")
    monkeypatch.setattr('src.kb_runtime.filtered_retrieval.MAX_CANDIDATE_FILINGS', 1)
    found = search_chunks(catalog, project, 'SBI', 'demand', _cutoff(),
                          document_types=['CONCALL_TRANSCRIPT'])
    assert [row['filing_id'] for row in found] == ['TEXT1']
    with pytest.raises(ValueError, match='too many candidate filings'):
        search_chunks(catalog, project, 'SBI', 'demand', _cutoff())


@pytest.mark.parametrize('query,limit', [('', 5), ('...', 5), ('demand', 0), ('demand', 21)])
def test_invalid_search_input_blocks(tmp_path, query, limit):
    project, catalog = _setup_filings(tmp_path)
    with pytest.raises(ValueError):
        search_chunks(catalog, project, 'SBI', query, _cutoff(), limit=limit)
