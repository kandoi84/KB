"""CLI exposes explicit change packets but no activation command."""

import json
import sys

import pytest

from test_change_proposal import _ready
from test_change_regression import _run_fixture
from test_change_approval import _approval_fixture
from src.kb_runtime.__main__ import main


def _invoke(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["kb", *map(str, args)])
    code = main()
    captured = capsys.readouterr()
    return code, captured


def test_register_proposal_cli_with_replayed_candidate(tmp_path, monkeypatch, capsys):
    packet_path, _, kwargs, state = _ready(tmp_path)
    replay = kwargs["case_replay_inputs"]
    args = ["register-change-proposal", "--packet", packet_path,
            "--baseline-artifact", kwargs["baseline_artifact"],
            "--candidate-artifact", kwargs["candidate_artifact"],
            "--state-dir", state, "--project-dir", replay["project_dir"],
            "--catalog", replay["catalog"], "--case-packet", replay["case_packet_path"],
            "--due-packet", f"post-1={replay['due_packet:post-1']}"]
    for key in ("source_request", "claim_request", "passage_packet", "review_packet",
                "workflow_contract", "claim_review_report", "analysis_packet", "analysis_report"):
        args.extend(["--" + key.replace("_", "-"), replay[key]])
    code, output = _invoke(monkeypatch, capsys, *args)
    assert code == 0
    assert json.loads(output.out)["eval_candidate_ids"] == ["post-1"]


def test_run_regression_cli_blocks_without_production_executor(tmp_path, monkeypatch, capsys):
    packet_path, _, _, _, kwargs, _ = _run_fixture(tmp_path)
    code, output = _invoke(monkeypatch, capsys, "run-change-regression", "--packet",
                           packet_path, "--state-dir", kwargs["state_dir"],
                           "--project-dir", kwargs["project_dir"])
    assert code == 0
    assert json.loads(output.out)["status"] == "BLOCKED_NO_EXECUTOR"


def test_record_rejection_cli_and_no_activate_command(tmp_path, monkeypatch, capsys):
    packet_path, _, state = _approval_fixture(tmp_path)
    code, output = _invoke(monkeypatch, capsys, "record-change-approval", "--packet",
                           packet_path, "--state-dir", state)
    assert code == 0
    assert json.loads(output.out)["approval_status"] == "REJECTED"
    monkeypatch.setattr(sys, "argv", ["kb", "activate-change"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_bad_approval_cli_returns_error_not_json(tmp_path, monkeypatch, capsys):
    packet_path, packet, state = _approval_fixture(tmp_path)
    packet["decision"] = "APPROVED"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    code, output = _invoke(monkeypatch, capsys, "record-change-approval", "--packet",
                           packet_path, "--state-dir", state)
    assert code == 1
    assert output.out == ""
    assert "trusted real regression" in output.err
