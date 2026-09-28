# Codex efficiency setup design

Date: 2026-09-28
Status: proposed design for review

## Goal and scope

Make this Codex workspace faster and more reliable across coding tasks. Improve useful work per token, time to a verified change, context continuity, and delivery quality. Keep the existing research publication gate and Git ownership rules.

This design covers the global Codex setup and this repository's local layer. It specifies hooks, instructions, skill use, context management, verification, and measurement. It does not change the KB research runtime, install hooks, or change model settings yet. Any implementation must first compare this design with the Codex version and available hook events at that time.

## Current baseline

- Global rules live in `codex.md`, copied to `~/.codex/codex.md` and linked from `~/.codex/AGENTS.md`. The root `AGENTS.md` adds KB rules; narrower project rules apply by directory.
- `~/.codex/config.toml` uses `gpt-6-sol` at medium reasoning and sets `model_auto_compact_token_limit = 108800`, described there as 40% of a 272,000 token window. Recalculate this value after a model change; do not infer actual session usage from it.
- Two global hooks already run: `SessionStart` repeats communication and ownership reminders; `PreCompact` says the active task continues. They do not preserve a structured handoff.
- KB has one project `Stop` hook in `.codex/hooks.json`. It asks Codex to finish review, checks, commit, and feature branch push. It does not mutate Git and avoids a repeated continuation through `stop_hook_active`. Six tests cover its main decisions.
- The setup has many enabled skills and plugins. Their descriptions consume context. The global and repository instructions already ask for targeted reads, focused checks, and short updates.
- No measured baseline exists for tokens, latency, repeated reads, failed checks, or hook cost. Claims of improvement need a baseline and comparable tasks.

## Design choices

### Approaches considered

1. **Recommended: small event driven layer plus short instructions.** Keep stable policy in `AGENTS.md` and `codex.md`; add only hooks with an event specific job; use Superpowers for design and implementation plans when a task needs them. Lowest recurring cost and clear ownership.
2. **Instruction only.** Simplest installation, but compaction recovery and end of turn delivery depend entirely on the agent remembering instructions.
3. **Hook heavy automation.** More automatic prompts and checks, but every matching event adds latency and context. Concurrent hooks can conflict, and hooks cannot safely determine ownership or auto commit.

Select approach 1. Do not turn ordinary judgment into a hook. In particular, do not add a hook on every tool call merely to repeat `AGENTS.md` or run the full test suite.

### Layer responsibilities

| Layer | Job | Change |
| --- | --- | --- |
| Global `codex.md` | Stable behavior across repositories | Tighten the efficiency section: read task relevant files, batch independent reads, preserve a compact task handoff, run affected checks once after edits, report evidence, and route skills only when useful. Keep the source file reviewable and copy it to `~/.codex/codex.md` after an approved edit. |
| Root `AGENTS.md` | KB ownership and research safeguards | Keep the existing publication gate, task only staging, verified commit, and feature branch push. Add only KB specific guidance that is absent from global rules. |
| Project `AGENTS.md` | Domain constraints | Leave research rules scoped to their project. Do not inject them into unrelated coding tasks. |
| Skills | Detailed process when triggered | Use Superpowers brainstorming for new behavior, writing plans for approved architectural specs, debugging for failures, and verification before completion. Avoid loading several skills for a small read only question. The task instruction takes precedence over skill defaults. |
| Hooks | Short event specific signals | Keep output small, deterministic, and free of secrets. Never let hooks stage, commit, push, change project files, or silently alter user prompts. |

### Hook set

Use one representation per config layer: global inline hooks in `~/.codex/config.toml`, project hooks in `.codex/hooks.json`. Keep the existing project `Stop` hook and its tests.

1. **Global `SessionStart`: revise.** Emit one short reminder on `startup`, `resume`, `clear`, and `compact`. On `compact`, include the location of a task handoff only if a real handoff exists. Do not read the whole repository or print Git status on every start. Cap model visible output at about 200 tokens.
2. **Global `PreCompact`: keep a short continuity signal.** It should say that the active task continues after compaction and point to the handoff fields: goal, decisions, owned changes, checks, blockers, and next action. The working instructions require Codex to keep that handoff during the task; the hook cannot create it at compaction time. The hook must not parse the transcript or assert that it saved state. Return valid JSON; plain text is ignored for this event. Keep the signal under about 150 tokens. Test both `manual` and `auto` triggers.
3. **Global `PostCompact`: add only if a probe shows the handoff is lost in a real compaction.** Return a short reminder to resume the active task. Otherwise omit it; `SessionStart` already runs for the `compact` source and duplicate context wastes tokens.
4. **Project `Stop`: retain and refine only if needed.** Its current logic already handles dirty trees, unpushed commits, protected branch, and loop prevention. Add cases only for observed failures. Preserve its advisory behavior: Codex owns file selection and verification.
5. **No default `PreToolUse`, `PostToolUse`, or `UserPromptSubmit` hook.** These run too often or can inspect sensitive prompt/tool data. Add one later only for a measured failure that instructions and focused tests cannot address. Any such hook needs an exact matcher, timeout, error policy, and cost test.

Codex loads matching hooks from all active layers, and changed non-managed hooks need `/hooks` review and trust before they run. A `Stop` hook's `decision: "block"` creates a continuation prompt; it is not a Git gate. A `PreCompact` hook does not itself write a durable summary. These limits shape the design. See [official OpenAI hook documentation](https://learn.chatgpt.com/docs/hooks).

### Coding and token workflow

Use a short task loop: inspect Git state and the relevant path; define the smallest complete change; read only matching files with `rg`; edit; run focused checks; inspect the diff and staged files; commit owned work; push a verified KB feature branch. Batch independent searches and reads, but keep edits, approvals, and dependent checks in order. Stop optional checks when the affected behavior is verified.

Treat context as a working set. Keep static instructions short. Link to detailed project guides and load them only when the task enters that area. Avoid large command output, repeated file dumps, and whole repository maps for small changes. Use compaction to carry a task handoff, not a transcript. Aim to maximize useful work per token; do not raise the context window or compaction threshold without measured benefit. Review skill descriptions for overlap and excessive triggers, following [OpenAI's instruction guidance](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra).

For complex work, use a spec and implementation plan with explicit acceptance checks. For a narrow bug, reproduce it when practical and use a focused fix. No new standing requirement should force Superpowers planning for trivial edits. If an approved plan uses subagents, dispatch only independent work; include handoff and review costs in the decision. This design does not require subagents.

## Installation and rollout

1. Record a baseline from five comparable completed tasks, or start a prospective baseline if historical usage data is unavailable. Record task type, elapsed time, input/output tokens when the client exposes them, tool calls, repeated reads, checks, rework, and delivery failures. Mark missing values as missing.
2. Update and review `codex.md`; copy the approved text to `~/.codex/codex.md`. Keep repository and project instructions scoped. Check for conflicting directions before changing either file.
3. Implement the global `SessionStart` and `PreCompact` changes in `~/.codex/config.toml`. Prefer small dedicated scripts only if quoting or tests justify them. Preserve unrelated config and current trust entries. Review changed hook definitions with `/hooks`; do not bypass trust.
4. Keep the KB `Stop` hook unless a failing test or observed behavior justifies a targeted change. Do not install duplicate global delivery hooks.
5. Test hook inputs directly with fixture JSON, then verify one real startup, one real compaction, and one KB stop continuation. Confirm the expected hook is trusted and actually ran; passing unit tests alone is insufficient.
6. Run the affected repository tests, inspect Git status and staged diff, commit only task files, then push this feature branch under the repository rule. Global files outside the repo need separate backup and verification; never stage them in the KB commit.
7. Compare the next five similar tasks with the baseline. Keep a hook only if it improves recovery or delivery without material overhead. Remove duplicate reminders if they add context but do not change behavior.

## Acceptance checks

- Startup and compaction reminders are concise and accurate. No hook claims to save a handoff that it has not saved.
- A compacted task continues with goal, owned files, checks, blocker, and next action intact in a real session probe.
- The KB `Stop` hook still does not stage, commit, or push; its loop guard works; main is never pushed by hook action.
- Changed hooks appear in `/hooks`, are reviewed and trusted by the user, and run on their intended events. Untrusted hooks are reported as skipped, not as installed and active.
- Hook output contains no secrets or full prompts/transcripts. Hook commands have bounded execution time and fail without hiding the original task result.
- Documentation names exact setup files, event matchers, and commands; instructions do not duplicate each other or contradict project rules.
- Record the measured effect on token use, elapsed time, repeated reads, compaction recovery, and delivery failures. Do not claim token or speed gains from this design alone.

## Risks and limits

The global config is machine local and outside this repository. A KB commit cannot distribute it. Hook trust is tied to the exact definition, so any edit needs another review. Some Codex clients may not load local config; verify the client actually used for the work. Prompt and transcript formats can change; the proposed hooks must not parse either. The configured compaction threshold is a local policy, not proof of the active model's current context size.
