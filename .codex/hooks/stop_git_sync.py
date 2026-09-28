"""Ask Codex to finish KB Git delivery before ending a turn.

The hook does not stage, commit, or push. Codex retains the task context
needed to select owned files, run checks, and report failures.
"""

import json
import subprocess
import sys


def git(cwd, *args):
    return subprocess.run(
        ["git", "-C", cwd, *args], text=True, capture_output=True, check=False
    )


def main():
    event = json.load(sys.stdin)
    if event.get("hook_event_name") != "Stop" or event.get("stop_hook_active"):
        print("{}")
        return

    cwd = event.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        print("{}")
        return
    root = git(cwd, "rev-parse", "--show-toplevel")
    if root.returncode:
        print("{}")
        return
    repo = root.stdout.strip()

    status = git(repo, "status", "--porcelain=v1", "--untracked-files=normal")
    branch = git(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
    remote = git(repo, "remote", "get-url", "origin")
    if status.returncode or branch.returncode or remote.returncode:
        print("{}")
        return

    dirty = bool(status.stdout.strip())
    name = branch.stdout.strip()
    if name in {"main", "master"}:
        if dirty:
            reason = (
                "KB has local changes on the protected branch. Create a feature "
                "branch, review and verify only this task's files, then commit and "
                "push that branch. Never push directly to main."
            )
        else:
            print("{}")
            return
    elif dirty:
        reason = (
            "KB has uncommitted changes. Review ownership and the diff, run "
            "affected checks, stage only completed files for this task, check "
            "the staged diff, commit, then push this feature branch to origin. "
            "Leave unrelated changes alone and report any blocker."
        )
    else:
        upstream = git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
        if upstream.returncode:
            reason = (
                "KB feature branch has no upstream. Push it with "
                "git push -u origin HEAD, then verify the remote branch. "
                "Report any authentication or network blocker."
            )
        else:
            ahead = git(repo, "rev-list", "--count", "@{upstream}..HEAD")
            if ahead.returncode or not ahead.stdout.strip().isdigit():
                print("{}")
                return
            if int(ahead.stdout.strip()) == 0:
                print("{}")
                return
            reason = (
                f"KB feature branch has {ahead.stdout.strip()} unpushed commit(s). "
                "Push to its upstream, verify the remote branch, and report "
                "any authentication or network blocker."
            )

    print(json.dumps({"decision": "block", "reason": reason}))


if __name__ == "__main__":
    main()
