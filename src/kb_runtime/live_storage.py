"""Live KB storage with point-in-time correctness.

Uses DuckDB for structured data and LanceDB for vector data.
Every record is versioned to prevent lookahead bias.
"""

import duckdb
import lancedb
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass

@dataclass(frozen=True)
class Company:
    isin: str
    symbol: str
    sector: str
    industry: str

@dataclass(frozen=True)
class Filing:
    isin: str
    doc_type: str
    filing_date: str
    period_end: str
    source_url: str
    version_id: str

@dataclass(frozen=True)
class Metric:
    isin: str
    metric_name: str
    value: float
    period_end: str
    filing_date: str
    version_id: str

class LiveKBStorage:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.db_path = root_dir / "kb_structured.duckdb"
        self.vector_path = root_dir / "kb_vector"
        
        # Initialize Structured Store
        self.conn = duckdb.connect(str(self.db_path))
        self._init_structured_schemas()
        
        # Initialize Vector Store
        self.vdb = lancedb.connect(str(self.vector_path))

    def _init_structured_schemas(self):
        """Initialize append-only temporal tables."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                isin VARCHAR PRIMARY KEY,
                symbol VARCHAR,
                sector VARCHAR,
                industry VARCHAR
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS filings (
                version_id VARCHAR PRIMARY KEY,
                isin VARCHAR,
                doc_type VARCHAR,
                filing_date DATE,
                period_end DATE,
                source_url VARCHAR,
                FOREIGN KEY (isin) REFERENCES companies(isin)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                version_id VARCHAR PRIMARY KEY,
                isin VARCHAR,
                metric_name VARCHAR,
                value DOUBLE,
                period_end DATE,
                filing_date DATE,
                FOREIGN KEY (isin) REFERENCES companies(isin)
            )
        """)

    def upsert_company(self, company: Company):
        """Upsert basic company info."""
        self.conn.execute(
            "INSERT OR REPLACE INTO companies VALUES (?, ?, ?, ?)",
            (company.isin, company.symbol, company.sector, company.industry)
        )

    def record_filing(self, filing: Filing):
        """Record a filing. Must be append-only."""
        self.conn.execute(
            "INSERT INTO filings VALUES (?, ?, ?, ?, ?, ?)",
            (filing.version_id, filing.isin, filing.doc_type, filing.filing_date, filing.period_end, filing.source_url)
        )

    def record_metric(self, metric: Metric):
        """Record a metric. Must be append-only."""
        self.conn.execute(
            "INSERT INTO metrics VALUES (?, ?, ?, ?, ?, ?)",
            (metric.version_id, metric.isin, metric.metric_name, metric.value, metric.period_end, metric.filing_date)
        )

    def get_metrics_as_of(self, isin: str, as_of_date: str) -> pd.DataFrame:
        """
        Point-in-time retrieval: Get the most recent version of each metric 
        that was available (filed) on or before the as_of_date.
        """
        query = """
            SELECT metric_name, value, period_end, filing_date
            FROM (
                SELECT *, 
                       ROW_NUMBER() OVER (PARTITION BY metric_name ORDER BY filing_date DESC) as rank
                FROM metrics
                WHERE isin = ? AND filing_date <= ?
            ) WHERE rank = 1
        """
        return self.conn.execute(query, (isin, as_of_date)).df()

    def create_vector_table(self, table_name: str):
        """Create a LanceDB table for chunks."""
        pass

    def add_chunks(self, table_name: str, data: List[Dict[str, Any]]):
        """Add embeddings and metadata to the vector store."""
        if table_name in self.vdb.table_names():
            table = self.vdb.open_table(table_name)
            table.add(data)
        else:
            self.vdb.create_table(table_name, data=data)

    def query_chunks(self, table_name: str, query_vector: List[float], isin: str, as_of_date: str, limit: int = 5):
        """
        Temporal RAG query: Search only chunks that existed before the as_of_date.
        """
        if table_name not in self.vdb.table_names():
            return pd.DataFrame()
            
        table = self.vdb.open_table(table_name)
        return table.search(query_vector).where(f"isin = '{isin}' AND filing_date <= '{as_of_date}'").limit(limit).to_pandas()

    def close(self):
        self.conn.close()
