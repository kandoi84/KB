import io
import pytest
from pathlib import Path
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from src.kb_runtime.live_storage import LiveKBStorage, Company
from src.kb_runtime.live_ingestion import LiveIngestionEngine, IngestionConfig


def _pdf(text):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                             NameObject('/Subtype'): NameObject('/Type1'),
                             NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
    stream = DecodedStreamObject()
    stream.set_data(('BT /F1 12 Tf 72 720 Td (' + text + ') Tj ET').encode('ascii'))
    page[NameObject('/Contents')] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()

def test_full_ingestion_pipeline(tmp_path):
    storage = LiveKBStorage(tmp_path)
    isin = "INE123456789"
    storage.upsert_company(Company(isin, "TEST", "Tech", "Software"))
    
    engine = LiveIngestionEngine(storage)
    engine._parse_with_docling = lambda _: "Annual report revenue and business outlook"
    
    pdf_path = tmp_path / "annual_report.pdf"
    pdf_path.write_bytes(_pdf("Annual report revenue and business outlook"))
    
    # Run ingestion
    version_id, success, logs = engine.ingest_document(
        isin=isin,
        doc_type="ANNUAL",
        filing_date="2024-01-01",
        period_end="2023-12-31",
        source_url="http://example.com/report.pdf",
        file_path=pdf_path
    )
    
    assert success, logs
    assert version_id
    
    # Verify structured store
    df_filings = storage.conn.execute("SELECT * FROM filings WHERE version_id = ?", (version_id,)).df()
    assert len(df_filings) == 1
    assert df_filings.iloc[0]["isin"] == isin
    
    # Verify vector store
    res = storage.query_chunks("kb_chunks", [0.0]*1536, isin, "2024-01-02")
    assert len(res) >= 1
    assert res.iloc[0]["doc_id"] == version_id
    
    storage.close()

def test_ingestion_temporal_isolation(tmp_path):
    storage = LiveKBStorage(tmp_path)
    isin = "INE123456789"
    storage.upsert_company(Company(isin, "TEST", "Tech", "Software"))
    engine = LiveIngestionEngine(storage)
    engine._parse_with_docling = lambda path: {
        "doc1.pdf": "First report filed in January",
        "doc2.pdf": "Second report filed in February",
    }[path.name]
    
    # Doc 1: Filed Jan 1st
    doc1 = tmp_path / "doc1.pdf"
    doc1.write_bytes(_pdf("First report filed in January"))
    version1, success1, logs1 = engine.ingest_document(isin, "REPORT", "2024-01-01", "2023-12-31", "url1", doc1)
    assert success1, logs1
    
    # Doc 2: Filed Feb 1st
    doc2 = tmp_path / "doc2.pdf"
    doc2.write_bytes(_pdf("Second report filed in February"))
    version2, success2, logs2 = engine.ingest_document(isin, "REPORT", "2024-02-01", "2024-01-31", "url2", doc2)
    assert success2, logs2
    
    # Query as of Jan 15 -> should only see Doc 1
    res_jan = storage.query_chunks("kb_chunks", [0.0]*1536, isin, "2024-01-15")
    assert len(res_jan) > 0
    assert all(res_jan.iloc[i]["filing_date"] == "2024-01-01" for i in range(len(res_jan)))
    
    # Query as of Feb 15 -> should see both
    res_feb = storage.query_chunks("kb_chunks", [0.0]*1536, isin, "2024-02-15")
    assert len(res_feb) > len(res_jan)
    
    storage.close()


def test_invalid_pdf_is_blocked_without_partial_filing(tmp_path):
    storage = LiveKBStorage(tmp_path)
    storage.upsert_company(Company("INE123456789", "TEST", "Tech", "Software"))
    engine = LiveIngestionEngine(storage)
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"not a pdf")

    version_id, success, logs = engine.ingest_document(
        "INE123456789", "ANNUAL", "2024-01-01", "2023-12-31", "url", path)

    assert version_id == ""
    assert success is False
    assert any("PDF parse failed" in item for item in logs)
    assert storage.conn.execute("SELECT count(*) FROM filings").fetchone()[0] == 0
    assert len(storage.query_chunks("kb_chunks", [0.0] * 1536,
                                    "INE123456789", "2024-02-01")) == 0
    storage.close()
