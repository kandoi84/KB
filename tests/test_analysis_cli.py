"""The analyst worksheet CLI keeps its internal-only result visible."""

import json
import subprocess
import sys
from pathlib import Path

from test_analysis_judgment import setup


def test_analyze_judgment_command(tmp_path):
    project, state, catalog, review, packet, _, _ = setup(tmp_path)
    completed = subprocess.run(
        [sys.executable, "-m", "src.kb_runtime", "analyze-judgment",
         "--packet", str(packet), "--claim-review-report", str(review),
         "--project-dir", str(project), "--catalog", str(catalog),
         "--state-dir", str(state), "--run-id", "analysis-cli"],
        cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["analysis_status"] == "CALCULATED_MODEL_UNVERIFIED"
    assert report["publication_allowed"] is False
    assert (state / "analysis_runs" / "analysis-cli.json").exists()
