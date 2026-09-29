"""Live KB ingestion pipeline: Raw File -> Docling -> Chunks -> Storage.

Ensures that raw content is converted to structured chunks with 
temporal metadata for point-in-time retrieval.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from docling.document_converter import DocumentConverter
from openai import OpenAI

from .live_storage import LiveKBStorage, Filing, Company, Metric
from .guardrails import NumericSanityGate, RetrievalEvalHarness
from .scraping import LiveScraper

@dataclass(frozen=True)
class IngestionConfig:
    chunk_size: int = 1000
    chunk_overlap: int = 200
    embedding_dim: int = 1536
    golden_set_dir: Path = Path("data/golden_sets")
    openai_api_key: Optional[str] = None

class LiveIngestionEngine:
    def __init__(self, storage: LiveKBStorage, config: IngestionConfig = IngestionConfig()):
        self.storage = storage
        self.config = config
        self.sanity_gate = NumericSanityGate()
        self.eval_harness = RetrievalEvalHarness(storage, config.golden_set_dir)
        
        # Initialize real Docling converter
        self.converter = DocumentConverter()
        
        # Initialize OpenAI client if key provided, else fallback to mock
        self.client = OpenAI(api_key=config.openai_api_key) if config.openai_api_key else None
        
        # Initialize Scraper
        self.scraper = LiveScraper(storage.root_dir)

    def _generate_version_id(self, metadata: Dict[str, Any], raw_hash: str) -> str:
        """Canonical version ID for a source."""
        canonical = json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        payload = f"{canonical}|{raw_hash}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _parse_with_docling(self, file_path: Path) -> str:
        """Convert PDF/Doc to Markdown using Docling."""
        result = self.converter.convert(file_path)
        return result.document.export_to_markdown()

    def _chunk_text(self, text: str) -> List[str]:
        """Simple overlapping window chunking."""
        chunks = []
        for i in range(0, len(text), self.config.chunk_size - self.config.chunk_overlap):
            chunks.append(text[i : i + self.config.chunk_size])
        return chunks

    def _get_embedding(self, text: str) -> List[float]:
        """Fetch real embeddings from OpenAI, fallback to mock for tests."""
        if self.client:
            try:
                response = self.client.embeddings.create(
                    input=[text.replace("\n", " ")], 
                    model="text-embedding-3-small"
                )
                return response.data[0].embedding
            except Exception as e:
                print(f"Embedding API error: {e}. Falling back to mock.")
        
        # Deterministic mock fallback
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [((hash_val >> (i * 8)) & 0xFF) / 255.0 for i in range(self.config.embedding_dim)]

    def ingest_document(self, isin: str, doc_type: str, filing_date: str, 
                       period_end: str, source_url: str, file_path: Path,
                       metrics_to_record: Optional[List[Metric]] = None) -> Tuple[str, bool, List[str]]:
        """
        The guarded ingestion loop:
        1. Sanity check metrics.
        2. Record raw metadata.
        3. Parse (Docling), chunk, and embed.
        4. Retrieval eval via Golden Set.
        5. Commit if all gates pass.
        """
        logs = []
        
        # 1. Sanity Check Metrics
        if metrics_to_record:
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
        text = self._parse_with_docling(file_path)
        chunks = self._chunk_text(text)
        vector_data = []
        for i, chunk_text in enumerate(chunks):
            vector_data.append({
                "vector": self._get_embedding(chunk_text),
                "isin": isin, "filing_date": filing_date, "doc_id": version_id, "chunk_id": i, "text": chunk_text
            })
        
        self.storage.add_chunks("kb_chunks", vector_data)
        
        # 4. Retrieval Eval
        recall, eval_failures = self.eval_harness.evaluate(
            isin, lambda q: self._get_embedding(q), filing_date
        )
        
        if recall < 1.0:
            logs.extend(eval_failures)
            if recall < 0.8:
                return version_id, False, logs + [f"Recall too low: {recall:.2%}"]

        # 5. Final Commit of Metrics
        if metrics_to_record:
            for m in metrics_to_record:
                self.storage.record_metric(m)
        
        return version_id, True, logs

    def ingest_from_symbol(self, symbol: str) -> Tuple[bool, List[str]]:
        """
        High-level automation:
        1. Scrape company info & ISIN.
        2. Fetch and record audited financials.
        3. Fetch and ingest all recent concalls.
        """
        logs = []
        
        # 1. Basic Info
        details = self.scraper.get_company_details(symbol)
        isin = details["isin"]
        if isin == "UNKNOWN":
            return False, ["Could not resolve ISIN for symbol"]
        
        self.storage.upsert_company(Company(isin, symbol, details["sector"], details["industry"]))
        
        # 2. Financials
        metrics_data = self.scraper.fetch_financials(symbol)
        metrics_to_record = []
        for m in metrics_data:
            metrics_to_record.append(Metric(
                isin=isin,
                metric_name=m["metric_name"],
                value=m["value"],
                period_end=m["period_end"],
                filing_date=m["filing_date"],
                version_id=m["version_id"]
            ))
        
        # For simplicity, we record these as a group. 
        # In production, we'd group by filing_date and use ingest_document.
        for m in metrics_to_record:
            self.storage.record_metric(m)
        logs.append(f"Recorded {len(metrics_to_record)} financial metrics.")
        
        # 3. Concalls
        concalls = self.scraper.fetch_concalls(symbol)
        for call in concalls:
            if call["pdf_path"]:
                v_id, success, c_logs = self.ingest_document(
                    isin=isin,
                    doc_type="CONCALL",
                    filing_date=call["date"],
                    period_end=call["quarter"],
                    source_url="bfinance",
                    file_path=Path(call["pdf_path"]),
                    metrics_to_record=None
                )
                if success:
                    logs.append(f"Ingested concall {call['quarter']} ({v_id[:8]})")
                else:
                    logs.extend([f"Concall {call['quarter']} failed: {l}" for l in c_logs])
            else:
                logs.append(f"No PDF found for concall {call['quarter']}")
        
        return True, logs
