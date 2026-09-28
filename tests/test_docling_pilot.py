"""Derived Docling receipts must keep the filing and physical-page boundary."""

import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

pytest.importorskip('docling', reason='Docling belongs to the isolated RAG pilot environment')

from test_pdf_chunks import _filing, _pdf
from src.kb_runtime.docling_pilot import extract_docling_pilot, query_docling_pilot
import src.kb_runtime.docling_pilot as pilot


def _cutoff(seconds=1):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def test_two_page_extraction_replays_and_keeps_physical_pages(tmp_path):
    project, catalog, _ = _filing(tmp_path, _pdf(['Synthetic guidance 12'], ['Synthetic analyst question']))
    first = extract_docling_pilot(catalog, project, 'F1')
    assert extract_docling_pilot(catalog, project, 'F1') == first
    assert first['page_count'] == 2
    rows = query_docling_pilot(catalog, project, 'F1', _cutoff())
    assert [r['page_number'] for r in rows] == [1, 2]
    assert [r['text'] for r in rows] == ['Synthetic guidance 12', 'Synthetic analyst question']
    assert all(r['raw_sha256'] and r['source_id'] == 'PDF1' and r['version_id'] for r in rows)
    assert all(r['speaker_role'] == 'UNKNOWN' and r['publication_allowed'] is False for r in rows)


def test_late_extraction_is_not_backdated(tmp_path):
    project, catalog, _ = _filing(tmp_path)
    old_cutoff = _cutoff(0)
    extract_docling_pilot(catalog, project, 'F1')
    assert query_docling_pilot(catalog, project, 'F1', old_cutoff) == []
    assert query_docling_pilot(catalog, project, 'F1', _cutoff())


def test_raw_and_derived_tampering_are_blocked(tmp_path):
    project, catalog, raw = _filing(tmp_path)
    extract_docling_pilot(catalog, project, 'F1')
    with sqlite3.connect(catalog) as db:
        db.execute('DROP TRIGGER docling_chunks_no_update')
        db.execute("UPDATE docling_chunks SET text='tampered' WHERE filing_id='F1'")
    with pytest.raises(ValueError, match='stored Docling'):
        query_docling_pilot(catalog, project, 'F1', _cutoff())
    raw.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='source|digest'):
        extract_docling_pilot(catalog, project, 'F1')


def test_parser_uses_exact_verified_bytes_if_raw_path_changes(tmp_path, monkeypatch):
    project, catalog, raw_path = _filing(tmp_path, _pdf(['Original synthetic text']))
    original_raw = pilot._raw

    def change_after_read(filing, project_dir):
        checked = original_raw(filing, project_dir)
        raw_path.write_bytes(_pdf(['Changed synthetic text']))
        return checked

    monkeypatch.setattr(pilot, '_raw', change_after_read)
    extract_docling_pilot(catalog, project, 'F1')
    with sqlite3.connect(catalog) as db:
        text = db.execute("SELECT text FROM docling_chunks WHERE filing_id='F1'").fetchone()[0]
    assert text == 'Original synthetic text'


def test_missing_or_ambiguous_page_anchor_is_blocked(tmp_path, monkeypatch):
    project, catalog, _ = _filing(tmp_path)
    original = pilot._chunk_page
    monkeypatch.setattr(pilot, '_chunk_page', lambda chunk, page_count: None)
    with pytest.raises(ValueError, match='page'):
        extract_docling_pilot(catalog, project, 'F1')
    monkeypatch.setattr(pilot, '_chunk_page', original)
    ambiguous = SimpleNamespace(meta=SimpleNamespace(doc_items=[
        SimpleNamespace(prov=[SimpleNamespace(page_no=1)]),
        SimpleNamespace(prov=[SimpleNamespace(page_no=2)]),
    ]))
    with pytest.raises(ValueError, match='ambiguous'):
        pilot._chunk_page(ambiguous, 2)


def test_blank_page_is_blocked_without_a_citation_anchor(tmp_path):
    project, catalog, _ = _filing(tmp_path, _pdf(['Synthetic visible text'], []))
    with pytest.raises(ValueError, match='page'):
        extract_docling_pilot(catalog, project, 'F1')


def test_unreviewed_rights_are_blocked(tmp_path):
    project, catalog, _ = _filing(tmp_path)
    with sqlite3.connect(catalog) as db:
        db.execute('PRAGMA ignore_check_constraints=ON')
        db.execute('DROP TRIGGER filings_no_update')
        db.execute("UPDATE filings SET rights_status='PENDING' WHERE filing_id='F1'")
    with pytest.raises(ValueError, match='review'):
        extract_docling_pilot(catalog, project, 'F1')


def test_parser_identity_change_keeps_prior_derived_version(tmp_path, monkeypatch):
    project, catalog, _ = _filing(tmp_path)
    first = extract_docling_pilot(catalog, project, 'F1')
    original = pilot.version
    monkeypatch.setattr(pilot, 'version', lambda name: '2.99.1' if name == 'docling-core' else original(name))
    second = extract_docling_pilot(catalog, project, 'F1')
    assert second['parser_version'] != first['parser_version']
    with sqlite3.connect(catalog) as db:
        count = db.execute("SELECT count(*) FROM docling_extractions WHERE filing_id='F1'").fetchone()[0]
    assert count == 2
