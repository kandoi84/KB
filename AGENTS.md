# KB repository rules

- Follow the global Codex rules in `codex.md` and preserve work already in progress.
- For Indian equity research, follow `projects/indian-equities/AGENTS.md` and its `MASTER.md`.
- Keep source documents and raw data separate from derived analysis. Never present synthetic inputs as real research.
- Before changing the runtime, read the relevant code and run checks for the affected path. The current runtime blocks real research publication until source validation exists; keep that gate intact.
- Stage only files owned by the current task. Do not commit other untracked research files.
- After a verified change, commit the task's completed files and push the feature branch to `origin` automatically. Do not push `main`, bypass checks, or include another session's changes. If push fails, report the exact blocker.
- The Stop hook can deliver a prepared commit. After reviewing the diff, running affected checks, and staging only this session's completed files, write the ignored `.codex-git-delivery.json` with `session_id` from `$CODEX_SESSION_ID`, current `branch`, current `head` SHA, exact staged `files`, a focused `message`, and `check_argv` as an argument list for the affected check. The hook reruns that check, commits only if the staged paths still match, and pushes to `origin`. Do not create the manifest for unfinished or mixed-session work. If it blocks, fix the cause and retry; do not bypass it.
