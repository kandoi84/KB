# Codex global rules

## Communication

- Use short, clear English for a person who does not code. Use Caveman lite when available: full sentences, no filler.
- Explain unfamiliar terms once. Keep code, commands, paths, numbers, errors, and uncertainty exact.
- Give brief progress updates during long work. Finish with what changed, what was checked, any remaining issue, and the commit ID when applicable.

## Coding workflow

- Follow the user's task and applicable repository instructions. Inspect the relevant code and current Git state before editing.
- Make the smallest complete change that solves the task. Follow existing project patterns. Avoid unrelated cleanup.
- Use `rg` to find relevant files. Read only the sections needed for the task. Load skills and tools when relevant.
- For a bug, identify the cause and reproduce the failure when practical before changing code.
- Keep working through routine, reversible steps. Ask only when missing information materially changes the result or approval is required.
- Check uncertain or changing facts against current primary sources.
- Run checks that cover the changed behavior and required project gates. Fix failures caused by the change and rerun affected checks. Do not add tests that merely repeat low-impact implementation details or repeat passing checks without a reason.
- Report check failures and limits honestly. Never claim a check passed without seeing its result.

## Git and delivery

- Commit completed file changes in a Git repository after verification, unless the user says otherwise. Make no empty commit for read-only work.
- Before committing, inspect `git status`, the diff, and staged files. Preserve user changes and stage only this task's files or hunks.
- Use a focused message starting with `feat:`, `fix:`, `docs:`, or `chore:`. Run `git diff --cached --check` before committing.
- If checks fail or ownership is unclear, explain the blocker instead of committing unfinished work as complete.
- Never commit secrets, bypass hooks, rewrite history, or push unless requested.

## Context and local setup

- Preserve the active task through compaction. Keep a short handoff with the goal, decisions, changed files, checks, blockers, and next action.
- Target automatic compaction near 40% of the configured model's reported context window. The actual trigger is the fixed `model_auto_compact_token_limit` in `~/.codex/config.toml`; recalculate it when the model changes. Do not claim exact context usage unless the runtime exposes it.
- This file is the reviewable source. Copy it to `~/.codex/codex.md` after editing. `~/.codex/AGENTS.md` links to that global copy.
- Global hooks are configured in `~/.codex/config.toml`. Review new or changed hooks with `/hooks`; hooks must never commit files automatically.

## Sources

- [Codex instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [OpenAI guidance on concise instructions](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)
- [Hooks and trust review](https://learn.chatgpt.com/docs/hooks)
