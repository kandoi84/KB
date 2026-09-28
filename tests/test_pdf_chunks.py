import io
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from test_metric_store import _setup, _write
from src.kb_runtime.metric_store import register_filing
from src.kb_runtime.source_store import record_source
from src.kb_runtime.pdf_chunks import extract_pdf_filing, query_pdf_chunks, review_pdf_role
import src.kb_runtime.pdf_chunks as pdf_chunks


def _cutoff(seconds=1):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _pdf(*pages):
    writer = PdfWriter()
    for lines in pages:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        stream = DecodedStreamObject()
        stream.set_data(('BT /F1 12 Tf 72 720 Td ' + ' '.join(f'({line}) Tj 0 -18 Td' for line in lines) + ' ET').encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _filing(tmp_path, raw=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    project, catalog, path, request = _setup(tmp_path)
    request['document_type'] = 'CONCALL_TRANSCRIPT'
    request['metrics'] = []
    raw = raw if raw is not None else _pdf(['Management: guidance 12'], ['Analyst: why now?'])
    raw_path = tmp_path / 'transcript.pdf'
    raw_path.write_bytes(raw)
    metadata = {'source_id': 'PDF1', 'entity': 'SBI', 'source_kind': 'EXCHANGE_FILING',
                'url': 'https://example.org/pdf1', 'source_date': '2026-09-28',
                'observed_at': '2026-09-28T09:00:00+05:30',
                'retrieved_at': '2026-09-28T09:02:00+05:30'}
    source = record_source(_write(tmp_path / 'pdf-source.json', metadata), raw_path, project)
    request['source_id'] = 'PDF1'
    request['version_id'] = source['version_id']
    register_filing(_write(path, request), project, catalog)
    return project, catalog, project / 'data/raw/sha256' / source['raw_sha256']


def test_pages_are_cited_and_replay_is_exact(tmp_path):
    project, catalog, _ = _filing(tmp_path)
    first = extract_pdf_filing(catalog, project, 'F1')
    assert extract_pdf_filing(catalog, project, 'F1') == first
    assert first['page_count'] == 2
    assert query_pdf_chunks(catalog, project, 'F1', '2026-09-28T09:02:30+05:30') == []
    chunks = query_pdf_chunks(catalog, project, 'F1', _cutoff())
    assert [row['page_number'] for row in chunks] == [1, 2]
    assert [row['text'].strip() for row in chunks] == ['Management: guidance 12', 'Analyst: why now?']
    assert all(row['offset_basis'] == 'DERIVED_PAGE_UTF8' and row['speaker_role'] == 'UNKNOWN' for row in chunks)
    assert all(row['publication_allowed'] is False for row in chunks)


def test_reviewed_role_applies_only_after_review_time(tmp_path):
    project, catalog, _ = _filing(tmp_path)
    extract_pdf_filing(catalog, project, 'F1')
    first = query_pdf_chunks(catalog, project, 'F1', _cutoff())[0]
    before_review = _cutoff(0)
    request = {'review_id': 'R1', 'supersedes_review_id': None, 'filing_id': 'F1', 'chunk_id': first['chunk_id'],
               'page_number': first['page_number'], 'byte_start': first['byte_start'],
               'byte_end': first['byte_end'], 'quote': first['text'],
               'speaker_role': 'MANAGEMENT', 'reviewer_id': 'analyst-1',
               'reviewed_at': '2026-09-28T09:04:00+05:30', 'evidence_locator': 'page 1 speaker label'}
    request_path = _write(tmp_path / 'role.json', request)
    assert review_pdf_role(request_path, catalog, project)['review_id'] == 'R1'
    assert review_pdf_role(request_path, catalog, project)['review_id'] == 'R1'
    assert query_pdf_chunks(catalog, project, 'F1', before_review)[0]['speaker_role'] == 'UNKNOWN'
    assert query_pdf_chunks(catalog, project, 'F1', _cutoff())[0]['speaker_role'] == 'MANAGEMENT'
    before_correction = _cutoff(0)
    request['review_id'] = 'R2'
    request['speaker_role'] = 'ANALYST'
    with pytest.raises(ValueError, match='conflict'):
        review_pdf_role(_write(request_path, request), catalog, project)
    request['supersedes_review_id'] = 'R1'
    assert review_pdf_role(_write(request_path, request), catalog, project)['review_id'] == 'R2'
    assert query_pdf_chunks(catalog, project, 'F1', before_correction)[0]['speaker_role'] == 'MANAGEMENT'
    assert query_pdf_chunks(catalog, project, 'F1', _cutoff())[0]['speaker_role'] == 'ANALYST'
    request['review_id'] = 'R3'
    request['supersedes_review_id'] = 'R2'
    request['speaker_role'] = 'UNKNOWN'
    review_pdf_role(_write(request_path, request), catalog, project)
    assert query_pdf_chunks(catalog, project, 'F1', _cutoff())[0]['speaker_role'] == 'UNKNOWN'


def test_role_quote_and_page_must_match(tmp_path):
    project, catalog, _ = _filing(tmp_path)
    extract_pdf_filing(catalog, project, 'F1')
    first = query_pdf_chunks(catalog, project, 'F1', _cutoff())[0]
    request = {'review_id': 'R1', 'supersedes_review_id': None, 'filing_id': 'F1', 'chunk_id': first['chunk_id'],
               'page_number': 2, 'byte_start': first['byte_start'], 'byte_end': first['byte_end'],
               'quote': first['text'], 'speaker_role': 'MANAGEMENT', 'reviewer_id': 'analyst-1',
               'reviewed_at': '2026-09-28T09:04:00+05:30', 'evidence_locator': 'page 1'}
    with pytest.raises(ValueError, match='span|quote'):
        review_pdf_role(_write(tmp_path / 'role.json', request), catalog, project)
    request['page_number'] = first['page_number']
    request['speaker_role'] = []
    with pytest.raises(ValueError, match='speaker_role'):
        review_pdf_role(_write(tmp_path / 'role.json', request), catalog, project)


@pytest.mark.parametrize('raw', [b'%PDF-1.4\ncorrupt', b'hello'])
def test_bad_pdf_is_blocked(tmp_path, raw):
    project, catalog, _ = _filing(tmp_path, raw)
    with pytest.raises(ValueError, match='PDF'):
        extract_pdf_filing(catalog, project, 'F1')


def test_encrypted_pdf_and_parser_spoof_are_blocked(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt('password')
    output = io.BytesIO()
    writer.write(output)
    project, catalog, _ = _filing(tmp_path, output.getvalue())
    with pytest.raises(ValueError, match='encrypted PDF'):
        extract_pdf_filing(catalog, project, 'F1')
    with pytest.raises(ValueError, match='parser_version'):
        extract_pdf_filing(catalog, project, 'F1', 'pypdf_6_20_0_plain_v1')


def test_blank_page_and_tampering_are_blocked(tmp_path):
    project, catalog, _ = _filing(tmp_path, _pdf(['visible'], []))
    with pytest.raises(ValueError, match='page'):
        extract_pdf_filing(catalog, project, 'F1')
    project, catalog, raw = _filing(tmp_path / 'second')
    extract_pdf_filing(catalog, project, 'F1')
    with sqlite3.connect(catalog) as db:
        db.execute('DROP TRIGGER pdf_pages_no_update')
        db.execute("UPDATE pdf_pages SET text='bad' WHERE page_number=1")
    with pytest.raises(ValueError, match='stored PDF'):
        query_pdf_chunks(catalog, project, 'F1', _cutoff())
    raw.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='source|digest'):
        extract_pdf_filing(catalog, project, 'F1')


def test_extraction_recorded_time_blocks_backdated_cutoff(tmp_path):
    project, catalog, _ = _filing(tmp_path)
    old_cutoff = _cutoff(0)
    extract_pdf_filing(catalog, project, 'F1')
    assert query_pdf_chunks(catalog, project, 'F1', old_cutoff) == []
    assert query_pdf_chunks(catalog, project, 'F1', _cutoff())


def test_role_chain_wins_timestamp_ties_and_rejects_extra_root(tmp_path, monkeypatch):
    project, catalog, _ = _filing(tmp_path)
    extract_pdf_filing(catalog, project, 'F1')
    first = query_pdf_chunks(catalog, project, 'F1', _cutoff())[0]
    tie = _cutoff(0)
    monkeypatch.setattr(pdf_chunks, '_now', lambda: tie)
    request = {'review_id': 'Z', 'supersedes_review_id': None, 'filing_id': 'F1',
               'chunk_id': first['chunk_id'], 'page_number': first['page_number'],
               'byte_start': first['byte_start'], 'byte_end': first['byte_end'],
               'quote': first['text'], 'speaker_role': 'MANAGEMENT', 'reviewer_id': 'analyst-1',
               'reviewed_at': '2026-09-28T09:04:00+05:30', 'evidence_locator': 'page 1'}
    path = tmp_path / 'role.json'
    review_pdf_role(_write(path, request), catalog, project)
    request.update(review_id='A', supersedes_review_id='Z', speaker_role='ANALYST')
    review_pdf_role(_write(path, request), catalog, project)
    assert query_pdf_chunks(catalog, project, 'F1', _cutoff())[0]['speaker_role'] == 'ANALYST'
    with sqlite3.connect(catalog) as db:
        db.execute("INSERT INTO pdf_role_reviews SELECT 'EXTRA', filing_id, parser_version, chunk_id, page_number, byte_start, byte_end, quote, 'MODERATOR', reviewer_id, reviewed_at, recorded_at, evidence_locator, NULL FROM pdf_role_reviews WHERE review_id='Z'")
    with pytest.raises(ValueError, match='two roots'):
        query_pdf_chunks(catalog, project, 'F1', _cutoff())


def test_long_pdf_line_is_bounded_and_covers_derived_page_bytes(tmp_path):
    project, catalog, _ = _filing(tmp_path, _pdf(['X' * 3000]))
    extract_pdf_filing(catalog, project, 'F1')
    chunks = query_pdf_chunks(catalog, project, 'F1', _cutoff())
    assert len(chunks) >= 2
    assert chunks[0]['byte_start'] == 0
    assert all(row['byte_end'] - row['byte_start'] <= 2048 for row in chunks)
    assert all(left['byte_end'] == right['byte_start'] for left, right in zip(chunks, chunks[1:]))
    with sqlite3.connect(catalog) as db:
        page_text = db.execute('SELECT text FROM pdf_pages WHERE page_number=1').fetchone()[0]
    assert ''.join(row['text'] for row in chunks) == page_text
