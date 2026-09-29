import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HOOK = Path(__file__).resolve().parents[1] / ".codex" / "hooks" / "stop_git_sync.py"


def git(*args, cwd):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, text=True, capture_output=True
    ).stdout.strip()


class StopGitSyncTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.remote = base / "remote.git"
        self.repo = base / "repo"
        git("init", "--bare", str(self.remote), cwd=base)
        git("init", "-b", "feature/test", str(self.repo), cwd=base)
        git("config", "user.name", "Test", cwd=self.repo)
        git("config", "user.email", "test@example.com", cwd=self.repo)
        git("remote", "add", "origin", str(self.remote), cwd=self.repo)
        (self.repo / "note.txt").write_text("initial\n")
        git("add", "note.txt", cwd=self.repo)
        git("commit", "-m", "docs: initial", cwd=self.repo)
        git("push", "-u", "origin", "feature/test", cwd=self.repo)

    def run_hook(self, **payload):
        event = {"hook_event_name": "Stop", "cwd": str(self.repo), **payload}
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(event),
            text=True,
            capture_output=True,
            cwd=self.repo,
            check=True,
        )
        return json.loads(result.stdout)

    def test_synced_branch_allows_stop(self):
        self.assertNotEqual(self.run_hook().get("decision"), "block")

    def test_dirty_tree_requests_review_commit_and_push(self):
        (self.repo / "note.txt").write_text("changed\n")
        output = self.run_hook()
        self.assertEqual(output["decision"], "block")
        self.assertIn("review", output["reason"].lower())

    def test_unpushed_commit_requests_push(self):
        (self.repo / "note.txt").write_text("changed\n")
        git("add", "note.txt", cwd=self.repo)
        git("commit", "-m", "docs: change", cwd=self.repo)
        self.assertIn("push", self.run_hook()["reason"].lower())

    def test_feature_branch_without_upstream_requests_first_push(self):
        git("branch", "--unset-upstream", cwd=self.repo)
        self.assertIn("push -u origin HEAD", self.run_hook()["reason"])

    def test_main_branch_changes_are_not_pushed_directly(self):
        git("branch", "-m", "main", cwd=self.repo)
        (self.repo / "note.txt").write_text("changed\n")
        self.assertIn("feature branch", self.run_hook()["reason"].lower())

    def test_second_stop_does_not_loop(self):
        (self.repo / "note.txt").write_text("changed\n")
        self.assertNotEqual(
            self.run_hook(stop_hook_active=True).get("decision"), "block"
        )

    def test_manifest_commits_only_selected_staged_files_and_pushes(self):
        (self.repo / "note.txt").write_text("completed\n")
        (self.repo / "unrelated.txt").write_text("leave alone\n")
        git("add", "note.txt", cwd=self.repo)
        self.write_manifest()

        self.assertNotEqual(self.run_hook(session_id="session-1").get("decision"), "block")
        self.assertEqual(git("show", "--format=", "--name-only", "HEAD", cwd=self.repo), "note.txt")
        self.assertEqual(git("log", "-1", "--format=%s", cwd=self.repo), "docs: deliver note")
        self.assertEqual(
            git("rev-parse", "HEAD", cwd=self.repo),
            git("--git-dir", str(self.remote), "rev-parse", "refs/heads/feature/test", cwd=self.repo),
        )
        self.assertTrue((self.repo / "unrelated.txt").exists())
        self.assertFalse((self.repo / ".codex-git-delivery.json").exists())

    def test_manifest_rejects_other_session_and_extra_staged_file(self):
        (self.repo / "note.txt").write_text("completed\n")
        (self.repo / "other.txt").write_text("unrelated\n")
        git("add", "note.txt", cwd=self.repo)
        self.write_manifest()
        before = git("rev-parse", "HEAD", cwd=self.repo)
        self.assertIn("session", self.run_hook(session_id="different")["reason"].lower())
        git("add", "other.txt", cwd=self.repo)
        self.assertIn("staged", self.run_hook(session_id="session-1")["reason"].lower())
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.repo), before)

    def test_manifest_failed_check_leaves_staging_for_retry(self):
        (self.repo / "note.txt").write_text("completed\n")
        git("add", "note.txt", cwd=self.repo)
        self.write_manifest(check_argv=[sys.executable, "-c", "raise SystemExit(1)"])
        before = git("rev-parse", "HEAD", cwd=self.repo)
        self.assertIn("check", self.run_hook(session_id="session-1")["reason"].lower())
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.repo), before)
        self.assertEqual(git("diff", "--cached", "--name-only", cwd=self.repo), "note.txt")

    def test_manifest_rejects_protected_branch_and_unstaged_selected_change(self):
        (self.repo / "note.txt").write_text("staged\n")
        git("add", "note.txt", cwd=self.repo)
        self.write_manifest()
        (self.repo / "note.txt").write_text("newer\n")
        self.assertIn("unstaged", self.run_hook(session_id="session-1")["reason"].lower())
        git("branch", "-m", "main", cwd=self.repo)
        self.write_manifest(branch="main")
        self.assertIn("feature branch", self.run_hook(session_id="session-1")["reason"].lower())

    def test_manifest_push_failure_can_retry_without_second_commit(self):
        (self.repo / "note.txt").write_text("completed\n")
        git("add", "note.txt", cwd=self.repo)
        self.write_manifest()
        git("remote", "set-url", "origin", str(self.repo / "missing.git"), cwd=self.repo)
        self.assertIn("push failed", self.run_hook(session_id="session-1")["reason"].lower())
        committed = git("rev-parse", "HEAD", cwd=self.repo)
        self.assertEqual(json.loads((self.repo / ".codex-git-delivery.json").read_text())["commit_sha"], committed)
        git("remote", "set-url", "origin", str(self.remote), cwd=self.repo)
        self.assertNotEqual(self.run_hook(session_id="session-1").get("decision"), "block")
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.repo), committed)
        self.assertEqual(git("--git-dir", str(self.remote), "rev-parse", "refs/heads/feature/test", cwd=self.repo), committed)

    def write_manifest(self, **overrides):
        data = {
            "session_id": "session-1", "branch": "feature/test",
            "head": git("rev-parse", "HEAD", cwd=self.repo),
            "files": ["note.txt"], "message": "docs: deliver note",
            "check_argv": [sys.executable, "-c", "pass"],
        }
        data.update(overrides)
        (self.repo / ".codex-git-delivery.json").write_text(json.dumps(data))


if __name__ == "__main__":
    unittest.main()
