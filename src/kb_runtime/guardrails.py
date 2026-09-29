"""Verification guardrails for the Live KB.

Includes numeric sanity checks for structured data and 
retrieval evaluation for the vector store.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .live_storage import Metric

@dataclass(frozen=True)
class SanityFailure:
    metric_name: str
    value: float
    reason: str
    severity: str # "BLOCK" or "WARN"

class NumericSanityGate:
    """Enforces basic accounting and sanity rules on metrics."""
    
    def __init__(self, strict: bool = True):
        self.strict = strict

    def check(self, metric: Metric, current_state: Dict[str, Any]) -> Optional[SanityFailure]:
        # 1. Absolute Bounds
        if metric.metric_name in ("Revenue", "Assets", "Equity") and metric.value < 0:
            return SanityFailure(metric.metric_name, metric.value, "Value cannot be negative", "BLOCK")
        
        # 2. Extreme Variance (e.g., > 1000% change)
        prev_val = current_state.get(metric.metric_name)
        if prev_val is not None and prev_val != 0:
            variance = abs((metric.value - prev_val) / prev_val)
            if variance > 10.0: # 1000%
                return SanityFailure(metric.metric_name, metric.value, f"Extreme variance: {variance:.2%}", "WARN")
        
        return None

class RetrievalEvalHarness:
    """Evaluates RAG retrieval quality using a Golden Set of queries."""
    
    def __init__(self, storage, golden_set_dir: Path):
        self.storage = storage
        self.golden_set_dir = golden_set_dir

    def _load_golden_set(self, isin: str) -> List[Dict[str, Any]]:
        path = self.golden_set_dir / f"{isin}.json"
        if not path.exists():
            return []
        return json.loads(path.read_text()).get("queries", [])

    def evaluate(self, isin: str, query_vector_provider: Any, as_of_date: str) -> Tuple[float, List[str]]:
        """
        Runs the Golden Set.
        Returns (recall_score, failure_reasons).
        """
        queries = self._load_golden_set(isin)
        if not queries:
            return 1.0, ["No golden set found; skipping eval"]

        hits = 0
        failures = []
        
        for q in queries:
            # Generate query vector for the question
            q_vector = query_vector_provider(q["question"])
            
            # Search chunks
            res = self.storage.query_chunks(
                table_name="kb_chunks",
                query_vector=q_vector,
                isin=isin,
                as_of_date=as_of_date,
                limit=5
            )
            
            # Check if expected chunk is in the results
            found = False
            for _, row in res.iterrows():
                # Chunk ID = version_id + chunk_id
                chunk_id = f"{row['doc_id']}_{row['chunk_id']}"
                if chunk_id == q["expected_chunk_id"]:
                    found = True
                    break
            
            if found:
                hits += 1
            else:
                failures.append(f"Query '{q['question']}' failed to retrieve {q['expected_chunk_id']}")

        recall = hits / len(queries)
        return recall, failures
