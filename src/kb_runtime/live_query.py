"""Temporal RAG query engine for the Live KB.

Allows retrieving both structured metrics and unstructured chunks
as they existed at a specific point in time.
"""

from pathlib import Path
from typing import List, Dict, Any, Union, Optional
import pandas as pd
import numpy as np

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
        Perform a temporal RAG search (Vector only).
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

    def query_hybrid_context(self, isin: str, as_of_date: str, query_text: str, query_vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Perform a Hybrid temporal RAG search combining Vector and Keyword retrieval.
        Uses Reciprocal Rank Fusion (RRF) to merge results.
        """
        # 1. Vector Search
        vector_results = self.query_context(isin, as_of_date, query_vector, limit=limit*2)
        
        # 2. Keyword Search (Simple BM25-like search using DuckDB)
        # We search for chunks that contain the keywords of the query
        keywords = [word for word in query_text.split() if len(word) > 3]
        keyword_results = []
        
        if keywords:
            # Construct a query that checks for any of the keywords
            conditions = " OR ".join([f"text LIKE '%{kw}%'" for kw in keywords])
            sql = f"SELECT text, filing_date, doc_id, chunk_id FROM kb_chunks WHERE isin = ? AND filing_date <= ? AND ({conditions}) ORDER BY filing_date DESC LIMIT {limit*2}"
            
            try:
                kw_df = self.storage.conn.execute(sql, (isin, as_of_date)).df()
                for _, row in kw_df.iterrows():
                    keyword_results.append({
                        "text": row["text"],
                        "filing_date": row["filing_date"],
                        "doc_id": row["doc_id"],
                        "chunk_id": row["chunk_id"]
                    })
            except Exception as e:
                print(f"Keyword search error: {e}")

        # 3. Reciprocal Rank Fusion (RRF)
        # RRF score = sum(1 / (k + rank))
        k = 60 
        scores = {} # { (doc_id, chunk_id): score }
        
        # Rank vector results
        for rank, res in enumerate(vector_results):
            key = (res["doc_id"], res["chunk_id"])
            scores[key] = scores.get(key, 0) + 1 / (k + rank + 1)
            
        # Rank keyword results
        for rank, res in enumerate(keyword_results):
            key = (res["doc_id"], res["chunk_id"])
            scores[key] = scores.get(key, 0) + 1 / (k + rank + 1)
            
        # Sort by fused score
        sorted_keys = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        
        # Resolve back to actual chunk data
        final_results = []
        # Create a lookup for the data
        all_data = { (r["doc_id"], r["chunk_id"]): r for r in vector_results }
        all_data.update({ (r["doc_id"], r["chunk_id"]): r for r in keyword_results })
        
        for key, score in sorted_keys:
            data = all_data[key]
            data["score"] = score
            final_results.append(data)
            
        return final_results
