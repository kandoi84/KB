"""Deliver an explicitly prepared KB commit, or remind Codex to finish it."""

import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath


MANIFEST = ".codex-git-delivery.json"
MESSAGE = re.compile(r"^(feat|fix|docs|chore): .+")
SHA = re.compile(r"^[0-9a-f]{40}$")


class DeliveryError(Exception):
    pass


def git(cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), *args], text=True, capture_output=True,
        check=False, timeout=15,
    )


def require_git(cwd, *args):
    result = git(cwd, *args)
    if result.returncode:
        raise DeliveryError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def staged_files(repo):
    return set(require_git(repo, "diff", "--cached", "--name-only", "-z").split("\0")) - {""}


def validate_manifest(repo, event, path):
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise DeliveryError(f"invalid delivery manifest: {exc}") from exc
    if not isinstance(data, dict) or set(data) not in (
        {"session_id", "branch", "head", "files", "message", "check_argv"},
        {"session_id", "branch", "head", "files", "message", "check_argv", "commit_sha"},
    ):
        raise DeliveryError("invalid delivery manifest fields")
    if not isinstance(data["session_id"], str) or not data["session_id"]:
        raise DeliveryError("invalid manifest session")
    if event.get("session_id") != data["session_id"]:
        raise DeliveryError("manifest belongs to another session")
    branch = require_git(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch in {"main", "master"} or data["branch"] != branch:
        raise DeliveryError("manifest branch is not the current feature branch")
    if not isinstance(data["head"], str) or not SHA.fullmatch(data["head"]):
        raise DeliveryError("invalid manifest head")
    files = data["files"]
    if not isinstance(files, list) or not files or any(
        not isinstance(item, str) or not item or item.startswith("-")
        or PurePosixPath(item).is_absolute() or ".." in PurePosixPath(item).parts
        or "\\" in item for item in files
    ) or len(set(files)) != len(files):
        raise DeliveryError("invalid manifest files")
    if not isinstance(data["message"], str) or not MESSAGE.fullmatch(data["message"]):
        raise DeliveryError("invalid commit message")
    argv = data["check_argv"]
    if not isinstance(argv, list) or not argv or any(
        not isinstance(item, str) or not item for item in argv
    ):
        raise DeliveryError("invalid check command")
    if "commit_sha" in data and (
        not isinstance(data["commit_sha"], str)
        or not SHA.fullmatch(data["commit_sha"])
    ):
        raise DeliveryError("invalid committed SHA")
    return data


def deliver(repo, event, path):
    data = validate_manifest(repo, event, path)
    files = set(data["files"])
    current = require_git(repo, "rev-parse", "HEAD")
    if "commit_sha" in data:
        if current != data["commit_sha"] or staged_files(repo):
            raise DeliveryError("committed delivery changed before push retry")
        if require_git(repo, "rev-parse", "HEAD^") != data["head"]:
            raise DeliveryError("committed delivery has a different parent")
        if set(require_git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines()) != files:
            raise DeliveryError("committed delivery contains different files")
    else:
        if current != data["head"]:
            raise DeliveryError("HEAD changed since manifest was prepared")
        if staged_files(repo) != files:
            raise DeliveryError("staged files differ from manifest")
        if require_git(repo, "diff", "--name-only", "-z", "--", *data["files"]):
            raise DeliveryError("selected files have unstaged changes")
        require_git(repo, "diff", "--cached", "--check")
        try:
            check = subprocess.run(
                data["check_argv"], cwd=repo, text=True, capture_output=True,
                check=False, timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DeliveryError(f"check could not finish: {exc}") from exc
        if check.returncode:
            raise DeliveryError(f"check failed (exit {check.returncode}): {check.stderr.strip()[-500:]}")
        if require_git(repo, "rev-parse", "HEAD") != data["head"] or staged_files(repo) != files:
            raise DeliveryError("HEAD or staged files changed during check")
        if require_git(repo, "diff", "--name-only", "-z", "--", *data["files"]):
            raise DeliveryError("selected files changed during check")
        require_git(repo, "diff", "--cached", "--check")
        require_git(repo, "commit", "-m", data["message"])
        data["commit_sha"] = require_git(repo, "rev-parse", "HEAD")
        path.write_text(json.dumps(data) + "\n")
    pushed = git(repo, "push", "origin", f"{data['commit_sha']}:refs/heads/{data['branch']}")
    if pushed.returncode:
        raise DeliveryError(f"push failed: {pushed.stderr.strip()}")
    path.unlink()


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
    manifest = Path(repo) / MANIFEST
    if manifest.exists():
        try:
            deliver(repo, event, manifest)
        except (DeliveryError, OSError, subprocess.TimeoutExpired) as exc:
            print(json.dumps({"decision": "block", "reason": f"KB delivery stopped: {exc}"}))
        else:
            print("{}")
        return

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
