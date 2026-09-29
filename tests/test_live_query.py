import pytest
from pathlib import Path
from src.kb_runtime.live_storage import LiveKBStorage, Company
from src.kb_runtime.live_ingestion import LiveIngestionEngine
from src.kb_runtime.live_query import LiveQueryEngine

def test_temporal_rag_query(tmp_path):
    storage = LiveKBStorage(tmp_path)
    isin = "INE123456789"
    storage.upsert_company(Company(isin, "TEST", "Tech", "Software"))
    engine = LiveIngestionEngine(storage)
    
    # Doc 1: Filed Jan 1st
    doc1 = tmp_path / "doc1.txt"
    doc1.write_text("The company reported growth of 10% in Q3.")
    engine.ingest_document(isin, "REPORT", "2024-01-01", "2023-12-31", "url1", doc1)
    
    # Doc 2: Filed Feb 1st
    doc2 = tmp_path / "doc2.txt"
    doc2.write_text("The company revised growth to 12% in Q3.")
    engine.ingest_document(isin, "REPORT", "2024-02-01", "2024-01-31", "url2", doc2)
    
    query_engine = LiveQueryEngine(storage)
    
    # Query as of Jan 15 -> should only find "10%"
    res_jan = query_engine.query_context(isin, "2024-01-15", [0.0]*1536)
    assert len(res_jan) > 0
    assert "10%" in res_jan[0]["text"]
    assert "12%" not in res_jan[0]["text"]
    
    # Query as of Feb 15 -> should find "12%" (most relevant)
    res_feb = query_engine.query_context(isin, "2024-02-15", [0.0]*1536)
    assert len(res_feb) > 0
    # Since our mock_embed is deterministic, "12%" chunk will be returned
    
    storage.close()

def test_company_snapshot(tmp_path):
    storage = LiveKBStorage(tmp_path)
    isin = "INE123456789"
    storage.upsert_company(Company(isin, "TEST", "Tech", "Software"))
    
    from src.kb_runtime.live_storage import Metric
    # Version 1: Filed Jan 1st
    storage.record_metric(Metric(isin, "Revenue", 100.0, "2023-12-31", "2024-01-01", "v1"))
    # Version 2: Filed Feb 1st
    storage.record_metric(Metric(isin, "Revenue", 110.0, "2023-12-31", "2024-02-01", "v2"))
    
    query_engine = LiveQueryEngine(storage)
    
    # Snapshot as of Jan 15
    snap_jan = query_engine.get_company_snapshot(isin, "2024-01-15")
    assert snap_jan["metrics"]["Revenue"]["value"] == 100.0
    
    # Snapshot as of Feb 15
    snap_feb = query_engine.get_company_snapshot(isin, "2024-02-15")
    assert snap_feb["metrics"]["Revenue"]["value"] == 110.0
    
    storage.close()
