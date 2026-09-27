# Codex global rules

## Simple explanations

- Use short, clear English. Explain things for a person who does not code.
- Default to Caveman lite when the installed skill is available. Keep full sentences; clarity wins over fewer words.
- Explain unfamiliar terms once. Preserve exact code, commands, paths, numbers, errors, and uncertainty.
- Skip filler and repeated summaries. Give brief progress updates during long work.
- Finish with what changed, what was checked, any remaining issue, and the commit ID when applicable.

## Efficient work

- Read applicable instructions and inspect the current state before editing.
- Make the smallest complete change that meets the request. Follow existing project patterns.
- Use `rg` to find relevant files. Read targeted sections; avoid dumping entire repositories or logs.
- Batch independent reads. Reuse findings instead of repeating searches and tests.
- Load only skills and tools needed for the task. Delegate only when authorized and useful.
- Ask only when a missing answer blocks useful progress or materially changes the result.
- Check changing or uncertain facts against current primary sources.
- Run checks that cover the affected behavior. Report failures honestly; never claim a check passed without evidence.

## Commit rules

- Always commit completed file changes in a Git repository after appropriate verification, unless the user says otherwise.
- Inspect `git status`, the diff, and staged files first. Stage only this task's files or hunks.
- Preserve existing user changes. Never use broad staging when unrelated changes exist.
- Use clear messages: `feat: ...`, `fix: ...`, `docs: ...`, or `chore: ...`. Explain why when useful.
- Keep each commit focused. Run `git diff --cached --check` before committing.
- Do not create empty commits for questions or read-only work. Outside Git, report that a commit is unavailable.
- If checks fail or ownership of changes is unclear, report the blocker instead of committing unfinished work as complete.
- Never commit secrets. Never bypass commit hooks, rewrite history, or push unless requested.

## Context and compaction

- Target automatic compaction at 40% of the model's reported context window USED.
- Compaction means shortening chat history while keeping the task and important decisions.
- The actual trigger is `model_auto_compact_token_limit` in `~/.codex/config.toml`; prose alone cannot enable it.
- Before a long task reaches the threshold, keep a concise handoff: goal, decisions, changed files, checks, blockers, and next action.
- Commit verified completed work at natural milestones. Keep unfinished work visible in the handoff.
- After compaction, continue the same task and preserve user corrections. Do not repeat completed work.
- Do not claim exact context usage unless the runtime exposes it. Use `/compact` manually when needed.

## Hooks

- A hook is a small command Codex runs at a particular event.
- Global hooks are configured in `~/.codex/config.toml` and require Codex's trust review.
- `SessionStart`: remind Codex to use simple English, Caveman lite, focused verification, and task-only commits. Also runs after compaction.
- `PreCompact`: show a short notice that Codex is shortening the chat history.
- Hooks must be fast, local, and quiet. Never make blind commits from a hook: it cannot know which edits are complete or user-owned.
- Keep commit decisions in the agent workflow, where verification and file ownership are available.

## Installed setup

- Global copy: `~/.codex/codex.md`. `~/.codex/AGENTS.md` links to it so Codex loads it automatically.
- This repository file is the reviewable source. After editing it, copy it to `~/.codex/codex.md` to update global rules.
- Caveman: `~/.codex/skills/caveman`, from `JuliusBrussee/caveman`, revision `2fd153c67988e980fb0b2455c90832159a6a5a25`.
- Current configured model: `gpt-6-sol`. Local model metadata reports 272,000 tokens; 40% is 108,800.
- The token setting is a fixed number, not a percentage. Recalculate it when changing models. The UI may show a different percentage because usable context and reserved tokens differ.
- New global settings apply to new sessions. Caveman is available on the next turn; use `$caveman lite` explicitly if needed.
- Review and trust the two hook definitions with `/hooks` in Codex CLI before expecting them to run.
- More frequent compaction can add cost and lose detail. This threshold follows your preference; it is not a universal optimum.
- Caveman mainly reduces response length. Actual total token savings vary; no fixed percentage is guaranteed.

## Sources checked

- [Global instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Compaction and configuration](https://learn.chatgpt.com/docs/config-file/config-reference)
- [Hooks and trust review](https://learn.chatgpt.com/docs/hooks)
- [Keep instructions focused](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)
- [Caveman upstream](https://github.com/JuliusBrussee/caveman)
