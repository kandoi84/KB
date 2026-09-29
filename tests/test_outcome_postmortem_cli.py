"""The outcome commands expose frozen sandbox receipts and fail closed."""

import json
import subprocess
import sys
from pathlib import Path

from test_outcome_postmortem import _due_packet, _setup, _write


ROOT = Path(__file__).resolve().parents[1]


def _run(command, packet, setup):
    kwargs = setup[4]
    arguments = [sys.executable, "-m", "src.kb_runtime", command,
                 "--packet", str(packet), "--case-packet", str(kwargs["case_packet_path"]),
                 "--project-dir", str(kwargs["project_dir"]),
                 "--catalog", str(kwargs["catalog"]),
                 "--state-dir", str(kwargs["state_dir"])]
    for name, path in kwargs["case_replay_inputs"].items():
        arguments.extend((f"--{name.replace('_', '-')}", str(path)))
    return subprocess.run(arguments, cwd=ROOT, text=True, capture_output=True, check=False)


def test_outcome_commands_complete_and_reject_changed_replay(tmp_path):
    setup = _setup(tmp_path)
    event_path = _write(tmp_path / "event-cli.json", setup[3])
    appended = _run("append-case-outcome", event_path, setup)
    assert appended.returncode == 0, appended.stderr
    event = json.loads(appended.stdout)
    assert event["event_id"] == "event-1"
    assert event["publication_allowed"] is False

    due = _due_packet(setup[1])
    due_path = _write(tmp_path / "due-cli.json", due)
    completed = _run("evaluate-due-case", due_path, setup)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["postmortem_status"] == "COMPLETE"
    assert result["publication_allowed"] is False

    due["process_review"]["reasoning"] = "A changed later review cannot replace the original"
    _write(due_path, due)
    rejected = _run("evaluate-due-case", due_path, setup)
    assert rejected.returncode != 0
    assert rejected.stdout == ""


def test_due_command_keeps_missing_actual_pending(tmp_path):
    setup = _setup(tmp_path)
    due = _due_packet(setup[1], event_id=None)
    due["process_review"] = None
    result = _run("evaluate-due-case", _write(tmp_path / "due-cli.json", due), setup)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["postmortem_status"] == "AWAITING_OBSERVATION"
    assert receipt["quadrant"] is None
    assert receipt["publication_allowed"] is False
