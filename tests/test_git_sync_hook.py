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


if __name__ == "__main__":
    unittest.main()
