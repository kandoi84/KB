# KB

A Markdown research journal and curated knowledge base for voice practice, Codex work sessions, and company analysis. No app or account is required.

Start with the [governing workflow](KB-GUIDE.md) and [evidence rubric](EVIDENCE-POLICY.md), then browse the [topic index](topics/README.md). Automated contributors must follow [AGENTS.md](AGENTS.md).

## Record a session

Start with the [session templates](templates/sessions/README.md). Browse the [voice journal](topics/voice-practice/README.md) and [Codex work journal](topics/codex-work/README.md). Save source notes first, record the work outcome, then optionally add a short voice review. Coding remains the main focus during work sessions.

## Add a research topic

1. Copy `templates/topic` into `topics/your-topic-name`.
2. Rename the topic in its README and replace all placeholders.
3. Save original inputs in `raw/` and record each in `raw/SOURCES.md`.
4. Write source-specific notes, compare evidence in `analysis/`, then draft wiki pages.
5. Record dated thesis changes in `analysis/thesis-journal.md`, including what changed your view and what would disprove it.
6. Add your topic to the topic index. Review citations and changes before marking a wiki page curated.

The [company-analysis example](topics/example-company/README.md) uses fictional reports and shows evidence, analysis, a company wiki, and dated thesis changes.

## Check and review

With Python 3.9 or newer installed, run from this folder:

```sh
python3 scripts/check_kb.py
```

The check finds broken local file links, missing folders, unfinished topic placeholders, and missing evidence links in notes, analysis, and wiki pages. It cannot judge whether a source supports a claim. See the [checking limits](scripts/README.md).

Use your editor's Git changes view to review edits, then save an approved local commit. Nothing is uploaded automatically. Keep sensitive sources on approved storage; Git history retains deleted content.
