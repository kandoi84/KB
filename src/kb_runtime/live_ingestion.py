"""Live KB ingestion pipeline: Raw File -> Docling -> Chunks -> Storage.

Ensures that raw content is converted to structured chunks with 
temporal metadata for point-in-time retrieval.
"""

import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .live_storage import LiveKBStorage, Filing, Company

@dataclass(frozen=True)
class IngestionConfig:
    chunk_size: int = 1000
    chunk_overlap: int = 200
    embedding_dim: int = 1536

class LiveIngestionEngine:
    def __init__(self, storage: LiveKBStorage, config: IngestionConfig = IngestionConfig()):
        self.storage = storage
        self.config = config

    def _generate_version_id(self, metadata: Dict[str, Any], raw_hash: str) -> str:
        """Canonical version ID for a source."""
        canonical = json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        payload = f"{canonical}|{raw_hash}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _mock_docling_parse(self, file_path: Path) -> str:
        """
        Simulates Docling parsing. In a real implementation, this 
        would call the Docling library to convert PDF to Markdown.
        """
        # For demo/testing, we just read the file if it's text, 
        # or return a synthetic structured string for PDFs.
        if file_path.suffix == ".txt":
            return file_path.read_text()
        return f"# Document {file_path.name}\n\nThis is a simulated parsed content from Docling for {file_path.name}. It contains multiple sections and data points."

    def _chunk_text(self, text: str) -> List[str]:
        """Simple overlapping window chunking."""
        chunks = []
        for i in range(0, len(text), self.config.chunk_size - self.config.chunk_overlap):
            chunks.append(text[i : i + self.config.chunk_size])
        return chunks

    def _mock_embed(self, text: str) -> List[float]:
        """
        Simulates an embedding call. 
        In real implementation, this would use an LLM API.
        """
        # Deterministic mock embedding based on text hash
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [((hash_val >> (i * 8)) & 0xFF) / 255.0 for i in range(self.config.embedding_dim)]

    def ingest_document(self, isin: str, doc_type: str, filing_date: str, 
                       period_end: str, source_url: str, file_path: Path):
        """
        The full ingestion loop:
        1. Record raw content and metadata in structured store.
        2. Parse content using Docling.
        3. Chunk and embed content.
        4. Store in vector store.
        """
        # 1. Record structured metadata
        raw_bytes = file_path.read_bytes()
        raw_hash = hashlib.sha256(raw_bytes).hexdigest()
        
        metadata = {
            "isin": isin, "doc_type": doc_type, "filing_date": filing_date,
            "period_end": period_end, "source_url": source_url
        }
        version_id = self._generate_version_id(metadata, raw_hash)
        
        filing = Filing(isin, doc_type, filing_date, period_end, source_url, version_id)
        self.storage.record_filing(filing)
        
        # 2. Parse
        text = self._mock_docling_parse(file_path)
        
        # 3. Chunk & Embed
        chunks = self._chunk_text(text)
        vector_data = []
        for i, chunk_text in enumerate(chunks):
            vector_data.append({
                "vector": self._mock_embed(chunk_text),
                "isin": isin,
                "filing_date": filing_date,
                "doc_id": version_id,
                "chunk_id": i,
                "text": chunk_text
            })
        
        # 4. Store in vector DB
        self.storage.add_chunks("kb_chunks", vector_data)
        
        return version_id
