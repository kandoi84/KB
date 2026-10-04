import pytest
import json
from pathlib import Path
from src.kb_runtime.live_storage import LiveKBStorage, Company, Metric
from src.kb_runtime.live_ingestion import LiveIngestionEngine, IngestionConfig
from src.kb_runtime.guardrails import NumericSanityGate, RetrievalEvalHarness
from test_live_ingestion import _pdf

def test_sanity_gate_blocks_negative_revenue():
    gate = NumericSanityGate()
    # Negative Revenue should block
    metric = Metric("INE123", "Revenue", -100.0, "2023-12-31", "2024-01-01", "v1")
    failure = gate.check(metric, {})
    assert failure is not None
    assert failure.severity == "BLOCK"
    assert "cannot be negative" in failure.reason

def test_sanity_gate_warns_extreme_variance():
    gate = NumericSanityGate()
    # Current Revenue is 100, new is 2000 (20x increase)
    current_state = {"Revenue": 100.0}
    metric = Metric("INE123", "Revenue", 2000.0, "2023-12-31", "2024-01-01", "v1")
    failure = gate.check(metric, current_state)
    assert failure is not None
    assert failure.severity == "WARN"
    assert "Extreme variance" in failure.reason

def test_retrieval_eval_detects_missing_chunk(tmp_path):
    storage = LiveKBStorage(tmp_path)
    isin = "INE123"
    golden_set_dir = tmp_path / "golden_sets"
    golden_set_dir.mkdir()
    
    # Golden set: Question "Q1" expects chunk "v1_0"
    golden_set = {"queries": [{"question": "Q1", "expected_chunk_id": "v1_0"}]}
    (golden_set_dir / f"{isin}.json").write_text(json.dumps(golden_set))
    
    harness = RetrievalEvalHarness(storage, golden_set_dir)
    
    # Case 1: No chunks ingested -> recall 0.0
    recall, failures = harness.evaluate(isin, lambda q: [0.0]*1536, "2024-01-01")
    assert recall == 0.0
    assert len(failures) == 1

    # Case 2: Ingest correct chunk -> recall 1.0
    # Since we use mock_embed in LiveIngestionEngine, we'll just mock the vector storage directly for the harness test
    storage.add_chunks("kb_chunks", [
        {"vector": [0.0]*1536, "isin": isin, "filing_date": "2024-01-01", "doc_id": "v1", "chunk_id": 0, "text": "ans"}
    ])
    
    # Mock the vector search to return the chunk
    import pandas as pd
    def mock_search(vector):
        return pd.DataFrame([{"doc_id": "v1", "chunk_id": 0, "text": "ans"}])
    
    # We need to monkeypatch storage.query_chunks
    storage.query_chunks = lambda *args, **kwargs: mock_search([0.0]*1536)
    
    recall, failures = harness.evaluate(isin, lambda q: [0.0]*1536, "2024-01-01")
    assert recall == 1.0
    assert len(failures) == 0

def test_ingestion_engine_blocks_on_sanity_failure(tmp_path):
    storage = LiveKBStorage(tmp_path)
    isin = "INE123"
    storage.upsert_company(Company(isin, "TEST", "Tech", "Software"))
    engine = LiveIngestionEngine(storage)
    
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(_pdf("Report with ordinary business details"))
    
    # Metric with negative revenue should block
    metrics = [Metric(isin, "Revenue", -1.0, "2023-12-31", "2024-01-01", "v1")]
    
    version_id, success, logs = engine.ingest_document(
        isin, "ANNUAL", "2024-01-01", "2023-12-31", "url", pdf_path, metrics_to_record=metrics
    )
    
    assert success is False
    assert any("Sanity BLOCK" in log for log in logs)
    assert version_id == ""

def test_ingestion_engine_blocks_on_low_recall(tmp_path):
    storage = LiveKBStorage(tmp_path)
    isin = "INE123"
    storage.upsert_company(Company(isin, "TEST", "Tech", "Software"))
    
    # Create a failing golden set
    golden_set_dir = tmp_path / "golden_sets"
    golden_set_dir.mkdir()
    golden_set = {"queries": [{"question": "Impossible Question", "expected_chunk_id": "absent_0"}]}
    (golden_set_dir / f"{isin}.json").write_text(json.dumps(golden_set))
    
    engine = LiveIngestionEngine(storage, IngestionConfig(golden_set_dir=golden_set_dir))
    engine._parse_with_docling = lambda _: "Report with ordinary business details"
    
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(_pdf("Report with ordinary business details"))
    
    version_id, success, logs = engine.ingest_document(
        isin, "ANNUAL", "2024-01-01", "2023-12-31", "url", pdf_path
    )
    
    assert success is False
    assert any("Recall too low" in log for log in logs)
