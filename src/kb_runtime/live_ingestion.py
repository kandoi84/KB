"""Live KB ingestion pipeline: Raw File -> Docling -> Chunks -> Storage.

Ensures that raw content is converted to structured chunks with 
temporal metadata for point-in-time retrieval.
"""

import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .live_storage import LiveKBStorage, Filing, Company, Metric
from .guardrails import NumericSanityGate, RetrievalEvalHarness

@dataclass(frozen=True)
class IngestionConfig:
    chunk_size: int = 1000
    chunk_overlap: int = 200
    embedding_dim: int = 1536
    golden_set_dir: Path = Path("data/golden_sets")

class LiveIngestionEngine:
    def __init__(self, storage: LiveKBStorage, config: IngestionConfig = IngestionConfig()):
        self.storage = storage
        self.config = config
        self.sanity_gate = NumericSanityGate()
        self.eval_harness = RetrievalEvalHarness(storage, config.golden_set_dir)

    def _generate_version_id(self, metadata: Dict[str, Any], raw_hash: str) -> str:
        """Canonical version ID for a source."""
        canonical = json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        payload = f"{canonical}|{raw_hash}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _mock_docling_parse(self, file_path: Path) -> str:
        """Simulates Docling parsing."""
        if file_path.suffix == ".txt":
            return file_path.read_text()
        return f"# Document {file_path.name}\n\nSimulated parsed content from Docling for {file_path.name}."

    def _chunk_text(self, text: str) -> List[str]:
        """Simple overlapping window chunking."""
        chunks = []
        for i in range(0, len(text), self.config.chunk_size - self.config.chunk_overlap):
            chunks.append(text[i : i + self.config.chunk_size])
        return chunks

    def _mock_embed(self, text: str) -> List[float]:
        """Simulates an embedding call."""
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [((hash_val >> (i * 8)) & 0xFF) / 255.0 for i in range(self.config.embedding_dim)]

    def ingest_document(self, isin: str, doc_type: str, filing_date: str, 
                       period_end: str, source_url: str, file_path: Path,
                       metrics_to_record: Optional[List[Metric]] = None) -> Tuple[str, bool, List[str]]:
        """
        The guarded ingestion loop:
        1. Sanity check metrics.
        2. Record raw metadata.
        3. Parse, chunk, and embed content.
        4. Retrieval eval via Golden Set.
        5. Commit if all gates pass.
        """
        logs = []
        
        # 1. Sanity Check Metrics
        if metrics_to_record:
            # Get current state for variance checks
            current_state = self.storage.get_metrics_as_of(isin, filing_date).set_index("metric_name")["value"].to_dict()
            for m in metrics_to_record:
                failure = self.sanity_gate.check(m, current_state)
                if failure and failure.severity == "BLOCK":
                    return "", False, [f"Sanity BLOCK: {failure.metric_name} - {failure.reason}"]
                if failure:
                    logs.append(f"Sanity WARN: {failure.metric_name} - {failure.reason}")

        # 2. Record Raw Metadata
        raw_bytes = file_path.read_bytes()
        raw_hash = hashlib.sha256(raw_bytes).hexdigest()
        metadata = {"isin": isin, "doc_type": doc_type, "filing_date": filing_date, 
                    "period_end": period_end, "source_url": source_url}
        version_id = self._generate_version_id(metadata, raw_hash)
        
        filing = Filing(isin, doc_type, filing_date, period_end, source_url, version_id)
        self.storage.record_filing(filing)
        
        # 3. Parse, Chunk, Embed
        text = self._mock_docling_parse(file_path)
        chunks = self._chunk_text(text)
        vector_data = []
        for i, chunk_text in enumerate(chunks):
            vector_data.append({
                "vector": self._mock_embed(chunk_text),
                "isin": isin, "filing_date": filing_date, "doc_id": version_id, "chunk_id": i, "text": chunk_text
            })
        
        self.storage.add_chunks("kb_chunks", vector_data)
        
        # 4. Retrieval Eval
        # Use the same mock_embed as the provider
        recall, eval_failures = self.eval_harness.evaluate(
            isin, lambda q: self._mock_embed(q), filing_date
        )
        
        if recall < 1.0:
            logs.extend(eval_failures)
            # Block if recall is completely broken (e.g., < 80%)
            if recall < 0.8:
                return version_id, False, logs + [f"Recall too low: {recall:.2%}"]

        # 5. Final Commit of Metrics
        if metrics_to_record:
            for m in metrics_to_record:
                self.storage.record_metric(m)
        
        return version_id, True, logs
