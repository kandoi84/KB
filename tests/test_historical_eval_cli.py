"""Historical evaluation CLI stays explicit and nonpromotional."""

import json
import sys

import pytest

from test_historical_cohort import _setup as _cohort_setup
from test_case_snapshot import _write
from src.kb_runtime.__main__ import main


def _invoke(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["kb", *map(str, args)])
    code = main()
    return code, capsys.readouterr()


def test_historical_commands_are_wired_and_block_current_real_runtime(
        tmp_path, monkeypatch, capsys):
    data, case, manifest, _ = _cohort_setup(tmp_path)
    project, state, catalog, paths, packet_path, _, _ = data
    manifest_path = _write(tmp_path / "manifest.json", manifest)
    replay = {case["case_id"]: {"case_packet_path": str(packet_path),
                                **{key: str(value) for key, value in paths.items()}}}
    replay_path = _write(tmp_path / "replay.json", replay)
    code, output = _invoke(monkeypatch, capsys, "register-evaluation-cohort",
                           "--manifest", manifest_path, "--case-replay-inputs", replay_path,
                           "--project-dir", project, "--catalog", catalog, "--state-dir", state)
    assert code == 0
    cohort = json.loads(output.out)
    assert cohort["cohort_status"] == "BLOCKED"

    score_request = {"run_id": "cli-score", "cohort_id": cohort["cohort_id"],
                     "cohort_digest": cohort["cohort_digest"],
                     "rubric_version": cohort["rubric_version"], "scorer_id": "missing",
                     "scorer_version": "1", "scorer_source_sha256": "0" * 64,
                     "independent_run_id": "cli-score-repeat", "reviewer_id": "reviewer"}
    score_path = _write(tmp_path / "score.json", score_request)
    code, output = _invoke(monkeypatch, capsys, "freeze-historical-scores",
                           "--request", score_path, "--state-dir", state)
    assert code == 0
    score = json.loads(output.out)
    assert score["score_status"] == "BLOCKED_NO_SCORER"
    assert score["promotion_allowed"] is False

    reveal_request = {"run_id": "cli-reveal", "cohort_id": cohort["cohort_id"],
                      "cohort_digest": cohort["cohort_digest"], "score_run_id": score["run_id"],
                      "score_digest": score["score_digest"], "rubric_version": cohort["rubric_version"],
                      "feed_id": "missing", "feed_version": "1", "feed_source_sha256": "0" * 64,
                      "reviewer_id": "reviewer", "calendar_version": "calendar-v1",
                      "execution_lag_days": 1}
    reveal_path = _write(tmp_path / "reveal.json", reveal_request)
    code, output = _invoke(monkeypatch, capsys, "reveal-historical-outcomes",
                           "--request", reveal_path, "--state-dir", state)
    assert code == 0
    reveal = json.loads(output.out)
    assert reveal["reveal_status"] == "BLOCKED_NO_MARKET_FEED"

    report_request = {"report_id": "cli-report", "cohort_id": cohort["cohort_id"],
                      "cohort_digest": cohort["cohort_digest"], "score_run_id": score["run_id"],
                      "score_digest": score["score_digest"], "repeat_score_run_id": None,
                      "repeat_score_digest": None, "reveal_run_id": reveal["run_id"],
                      "reveal_digest": reveal["reveal_digest"],
                      "rubric_version": cohort["rubric_version"],
                      "thresholds": {"minimum_snapshots": 100,
                                     "repeatability_median_max": "3",
                                     "factor_agreement_min": "0.80",
                                     "maximum_lookahead_violations": 0,
                                     "minimum_quintile_spread": "0",
                                     "minimum_top_five_beat_rate": "0",
                                     "maximum_brier_score": "0.25"},
                      "baseline_receipts": []}
    report_path = _write(tmp_path / "report.json", report_request)
    code, output = _invoke(monkeypatch, capsys, "evaluate-historical-cohort",
                           "--request", report_path, "--state-dir", state)
    assert code == 0
    report = json.loads(output.out)
    assert report["report_status"] == "BLOCKED"
    assert all(report[name] is False for name in
               ("publication_allowed", "live_decision_allowed", "promotion_allowed"))


def test_historical_cli_rejects_bad_paths_and_has_no_activation_command(
        tmp_path, monkeypatch, capsys):
    code, output = _invoke(monkeypatch, capsys, "evaluate-historical-cohort",
                           "--request", tmp_path / "missing.json", "--state-dir", tmp_path)
    assert code == 1
    assert output.out == ""
    assert "Run failed" in output.err
    with pytest.raises(SystemExit) as exc:
        _invoke(monkeypatch, capsys, "activate-historical-evaluation")
    assert exc.value.code == 2
