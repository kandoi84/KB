"""Temporal RAG query engine for the Live KB.

Allows retrieving both structured metrics and unstructured chunks
as they existed at a specific point in time.
"""

from pathlib import Path
from typing import List, Dict, Any, Union, Optional
import pandas as pd

from .live_storage import LiveKBStorage

class LiveQueryEngine:
    def __init__(self, storage: LiveKBStorage):
        self.storage = storage

    def get_company_snapshot(self, isin: str, as_of_date: str) -> Dict[str, Any]:
        """
        Return a complete state of a company as of a specific date.
        Includes the most recent metrics available on that date.
        """
        metrics_df = self.storage.get_metrics_as_of(isin, as_of_date)
        
        metrics = {}
        for _, row in metrics_df.iterrows():
            metrics[row["metric_name"]] = {
                "value": row["value"],
                "period_end": row["period_end"],
                "filing_date": row["filing_date"]
            }
            
        return {
            "isin": isin,
            "as_of_date": as_of_date,
            "metrics": metrics
        }

    def query_context(self, isin: str, as_of_date: str, query_vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Perform a temporal RAG search.
        Returns chunks that are semantically relevant AND were filed on or before as_of_date.
        """
        chunks_df = self.storage.query_chunks(
            table_name="kb_chunks",
            query_vector=query_vector,
            isin=isin,
            as_of_date=as_of_date,
            limit=limit
        )
        
        results = []
        for _, row in chunks_df.iterrows():
            results.append({
                "text": row["text"],
                "filing_date": row["filing_date"],
                "doc_id": row["doc_id"],
                "chunk_id": row["chunk_id"],
                "score": row.get("_distance", None)
            })
            
        return results
