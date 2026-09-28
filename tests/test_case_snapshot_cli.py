"""CLI contract for replay-verified sandbox case opening."""

import json
import subprocess
import sys
from pathlib import Path

from test_case_snapshot import _fixture


ROOT = Path(__file__).resolve().parents[1]


def test_open_sandbox_case_cli_freezes_only_internal_case(tmp_path):
    project, state, catalog, paths, packet, _, _ = _fixture(tmp_path)
    args = [sys.executable, "-m", "src.kb_runtime", "open-sandbox-case",
            "--packet", str(packet), "--project-dir", str(project),
            "--catalog", str(catalog), "--state-dir", str(state)]
    for name, path in paths.items():
        args += ["--" + name.replace("_", "-"), str(path)]
    first = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    assert first.returncode == 0, first.stderr
    case = json.loads(first.stdout)
    assert case["case_status"] == "SANDBOX_OPEN"
    assert case["publication_allowed"] is False
    assert case["live_decision_allowed"] is False
    assert case["promotion_status"] == "NOT_EVALUATED"
    assert (state / "cases/case-1.json").is_file()
    replay = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout) == case


def test_open_sandbox_case_cli_rejects_unsupported_poker_label(tmp_path):
    project, state, catalog, paths, packet_path, packet, _ = _fixture(tmp_path)
    packet["poker"] = {"status": "ASSESSED", "hand": "AA", "draw": None}
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    args = [sys.executable, "-m", "src.kb_runtime", "open-sandbox-case",
            "--packet", str(packet_path), "--project-dir", str(project),
            "--catalog", str(catalog), "--state-dir", str(state)]
    for name, path in paths.items():
        args += ["--" + name.replace("_", "-"), str(path)]
    completed = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    assert completed.returncode == 1
    assert completed.stdout == ""
    assert "poker labels are unavailable" in completed.stderr
    assert not (state / "cases/case-1.json").exists()
