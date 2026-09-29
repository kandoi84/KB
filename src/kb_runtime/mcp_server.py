"""MCP Server for the Live KB.

Exposes Knowledge Base operations as tools for AI agents.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, List, Optional
from datetime import datetime

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("IndianEquitiesKB")

# Resource paths
ROOT_DIR = Path(".")
from src.kb_runtime.live_storage import LiveKBStorage
from src.kb_runtime.live_query import LiveQueryEngine
from src.kb_runtime.thesis_wiki import ThesisWiki

# Global components
storage = LiveKBStorage(ROOT_DIR)
query_engine = LiveQueryEngine(storage)
wiki = ThesisWiki(ROOT_DIR)

@mcp.tool()
def list_companies() -> str:
    """Lists all companies currently available in the Knowledge Base."""
    companies = storage.conn.execute("SELECT isin, symbol FROM companies").fetchall()
    if not companies:
        return "No companies found in the KB."
    
    res = [f"{symbol} ({isin})" for isin, symbol in companies]
    return "\n".join(res)

@mcp.tool()
def get_metrics(isin: str, as_of: str = None) -> str:
    """
    Retrieves a snapshot of financial metrics for a company as of a specific date.
    
    Args:
        isin: The ISIN of the company.
        as_of: Date in YYYY-MM-DD format. Defaults to today.
    """
    if not as_of:
        as_of = datetime.now().strftime("%Y-%m-%d")
    
    snapshot = query_engine.get_company_snapshot(isin, as_of)
    metrics = snapshot.get("metrics", {})
    
    if not metrics:
        return f"No metrics found for {isin} as of {as_of}."
    
    res = [f"{name}: {data['value']} (Filed: {data['filing_date']})" for name, data in metrics.items()]
    return f"Metrics for {isin} as of {as_of}:\n" + "\n".join(res)

@mcp.tool()
def query_kb(isin: str, query: str, as_of: str = None) -> str:
    """
    Performs a RAG query over the company's documents.
    
    Args:
        isin: The ISIN of the company.
        query: The natural language question.
        as_of: Date in YYYY-MM-DD format. Defaults to today.
    """
    if not as_of:
        as_of = datetime.now().strftime("%Y-%m-%d")
    
    # Use mock vector for this implementation as real embedding 
    # requires an API key and external call.
    import hashlib
    hash_val = int(hashlib.md5(query.encode()).hexdigest(), 16)
    mock_vector = [((hash_val >> (i * 8)) & 0xFF) / 255.0 for i in range(1536)]
    
    results = query_engine.query_context(isin, as_of, mock_vector)
    
    if not results:
        return f"No relevant context found for {isin} as of {as_of}."
    
    res = []
    for i, r in enumerate(results):
        res.append(f"Source {i+1} (Date: {r['filing_date']}):\n{r['text']}\n")
    
    return f"Search results for {isin} as of {as_of}:\n\n" + "\n---\n".join(res)

@mcp.tool()
def update_thesis(isin: str, content: str) -> str:
    """
    Appends a new update to the company's core thesis.
    
    Args:
        isin: The ISIN of the company.
        content: The text to add to the thesis.
    """
    wiki.update_thesis(isin, content)
    return f"Successfully updated thesis for {isin}."

@mcp.tool()
def add_research_note(isin: str, note_id: str, content: str, links: str = "[]") -> str:
    """
    Adds a dated research note to the company's wiki.
    
    Args:
        isin: The ISIN of the company.
        note_id: Unique identifier for the note (e.g., 'note_2026_q1').
        content: The note content.
        links: JSON list of version IDs this note refers to (e.g., '["v1", "m_rev_2025"]').
    """
    try:
        import json
        link_list = json.loads(links)
        wiki.add_note(isin, note_id, content, link_list)
        return f"Successfully added note {note_id} for {isin}."
    except Exception as e:
        return f"Error adding note: {str(e)}"

if __name__ == "__main__":
    mcp.run()
