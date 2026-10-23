#!/usr/bin/env bash
set -euo pipefail
cd /workspace/KB
python3 -m venv /workspace/venvs/kb
KB_PY=/workspace/venvs/kb/bin/python
"$KB_PY" -m pip install -r requirements.txt
"$KB_PY" -m pip install 'torch==2.14.0+cpu' 'torchvision==0.29.0+cpu' --index-url https://download.pytorch.org/whl/cpu
"$KB_PY" -m pip install 'duckdb==2.0.0' 'lancedb==0.40.0' 'pandas==3.1.0' 'numpy==2.5.4' 'openai==3.37.0' 'bfinance==0.1.3' 'mcp==1.30.0' 'flake8==7.4.1' -r requirements-rag-pilot.txt
"$KB_PY" -m pip check
export PATH="/workspace/venvs/kb/bin:$PATH"
export PYTHONPATH="/workspace/KB"
export HAYSTACK_TELEMETRY_ENABLED=false
"$KB_PY" -m src.kb_runtime --help >/dev/null
"$KB_PY" -m pytest -q tests/test_live_storage.py tests/test_source_store.py tests/test_source_refresh.py
