import pytest
import subprocess
import json
from pathlib import Path

def test_cli_update_and_query(tmp_path):
    # Setup
    isin = "INE123"
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("The company reported growth of 10% in Q3.")
    
    metrics = json.dumps([{"name": "Revenue", "value": 100, "period_end": "2023-12-31", "filing_date": "2024-01-01"}])
    
    # 1. Test Update
    # We call the script using python3 src/kb_runtime/cli.py
    update_cmd = [
        "python3", "src/kb_runtime/cli.py",
        "--project-dir", str(tmp_path),
        "update",
        "--isin", isin,
        "--file", str(doc_path),
        "--filing-date", "2024-01-01",
        "--period-end", "2023-12-31",
        "--metrics", metrics
    ]
    result = subprocess.run(update_cmd, capture_output=True, text=True)
    assert result.returncode == 0
    assert "Update SUCCESSFUL" in result.stdout

    # 2. Test Query
    query_cmd = [
        "python3", "src/kb_runtime/cli.py",
        "--project-dir", str(tmp_path),
        "query",
        "--isin", isin,
        "--as-of", "2024-01-15",
        "--query", "What is the growth?"
    ]
    result = subprocess.run(query_cmd, capture_output=True, text=True)
    assert result.returncode == 0
    assert "Revenue: 100.0" in result.stdout
    assert "10%" in result.stdout

def test_cli_audit(tmp_path):
    isin = "INE123"
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("test")
    
    # Ingest something first
    subprocess.run([
        "python3", "src/kb_runtime/cli.py",
        "--project-dir", str(tmp_path),
        "update", "--isin", isin, "--file", str(doc_path),
        "--filing-date", "2024-01-01", "--period-end", "2023-12-31"
    ], capture_output=True)
    
    # Audit
    audit_cmd = [
        "python3", "src/kb_runtime/cli.py",
        "--project-dir", str(tmp_path),
        "audit",
        "--isin", isin
    ]
    result = subprocess.run(audit_cmd, capture_output=True, text=True)
    assert result.returncode == 0
    assert "Total filings: 1" in result.stdout

