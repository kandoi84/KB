import pytest
from pathlib import Path
from src.kb_runtime.live_storage import LiveKBStorage, Company, Filing, Metric

def test_point_in_time_metrics(tmp_path):
    storage = LiveKBStorage(tmp_path)
    isin = "INE123456789"
    storage.upsert_company(Company(isin, "TEST", "Tech", "Software"))
    
    # Version 1: Filed on Jan 1st
    # Metric(isin, metric_name, value, period_end, filing_date, version_id)
    storage.record_metric(Metric(isin, "Revenue", 100.0, "2023-12-31", "2024-01-01", "v1"))
    # Version 2: Restated/Updated filed on Feb 1st
    storage.record_metric(Metric(isin, "Revenue", 110.0, "2023-12-31", "2024-02-01", "v2"))
    
    # Query as of Jan 15th -> should see Version 1
    df_jan = storage.get_metrics_as_of(isin, "2024-01-15")
    assert df_jan.loc[df_jan["metric_name"] == "Revenue", "value"].values[0] == 100.0
    
    # Query as of Feb 15th -> should see Version 2
    df_feb = storage.get_metrics_as_of(isin, "2024-02-15")
    assert df_feb.loc[df_feb["metric_name"] == "Revenue", "value"].values[0] == 110.0
    
    storage.close()

def test_append_only_filings(tmp_path):
    storage = LiveKBStorage(tmp_path)
    isin = "INE123456789"
    storage.upsert_company(Company(isin, "TEST", "Tech", "Software"))
    
    # Filing(isin, doc_type, filing_date, period_end, source_url, version_id)
    storage.record_filing(Filing(isin, "ANNUAL", "2024-01-01", "2023-12-31", "url1", "v1"))
    # Attempt to record same version ID should fail (PK violation)
    with pytest.raises(Exception): # DuckDB unique constraint
        storage.record_filing(Filing(isin, "ANNUAL", "2024-01-01", "2023-12-31", "url1", "v1"))
    
    storage.close()

def test_vector_temporal_query(tmp_path):
    storage = LiveKBStorage(tmp_path)
    isin = "INE123456789"
    table_name = "test_chunks"
    
    data = [
        {"vector": [0.1]*1536, "isin": isin, "filing_date": "2024-01-01", "text": "Early data"},
        {"vector": [0.2]*1536, "isin": isin, "filing_date": "2024-02-01", "text": "Later data"},
    ]
    storage.add_chunks(table_name, data)
    
    # Query as of Jan 15 -> should only see "Early data"
    res = storage.query_chunks(table_name, [0.1]*1536, isin, "2024-01-15")
    assert len(res) == 1
    assert res.iloc[0]["text"] == "Early data"
    
    # Query as of Feb 15 -> should see both (or most relevant)
    res = storage.query_chunks(table_name, [0.2]*1536, isin, "2024-02-15")
    assert len(res) >= 1
    
    storage.close()
