import pytest
from pathlib import Path
from src.kb_runtime.live_storage import LiveKBStorage, Company
from src.kb_runtime.live_ingestion import LiveIngestionEngine, IngestionConfig

def test_full_ingestion_pipeline(tmp_path):
    storage = LiveKBStorage(tmp_path)
    isin = "INE123456789"
    storage.upsert_company(Company(isin, "TEST", "Tech", "Software"))
    
    engine = LiveIngestionEngine(storage)
    
    # Create a dummy PDF file
    pdf_path = tmp_path / "annual_report.pdf"
    pdf_path.write_bytes(b"Simulated PDF Content")
    
    # Run ingestion
    version_id = engine.ingest_document(
        isin=isin,
        doc_type="ANNUAL",
        filing_date="2024-01-01",
        period_end="2023-12-31",
        source_url="http://example.com/report.pdf",
        file_path=pdf_path
    )
    
    assert version_id is not None
    
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
    
    # Doc 1: Filed Jan 1st
    doc1 = tmp_path / "doc1.pdf"
    doc1.write_bytes(b"Content One")
    engine.ingest_document(isin, "REPORT", "2024-01-01", "2023-12-31", "url1", doc1)
    
    # Doc 2: Filed Feb 1st
    doc2 = tmp_path / "doc2.pdf"
    doc2.write_bytes(b"Content Two")
    engine.ingest_document(isin, "REPORT", "2024-02-01", "2024-01-31", "url2", doc2)
    
    # Query as of Jan 15 -> should only see Doc 1
    res_jan = storage.query_chunks("kb_chunks", [0.0]*1536, isin, "2024-01-15")
    assert len(res_jan) > 0
    assert all(res_jan.iloc[i]["filing_date"] == "2024-01-01" for i in range(len(res_jan)))
    
    # Query as of Feb 15 -> should see both
    res_feb = storage.query_chunks("kb_chunks", [0.0]*1536, isin, "2024-02-15")
    assert len(res_feb) > len(res_jan)
    
    storage.close()
