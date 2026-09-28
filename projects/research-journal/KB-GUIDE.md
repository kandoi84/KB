# How KB works

## Purpose and authority

KB is a research journal and curated wiki. Its primary journals track voice practice and Codex work; company analysis remains an additional supported use. Use one ongoing topic per journal and one topic per company. Approved wiki pages are the knowledge base's source of truth for day-to-day use. They are a reviewed account of the evidence, not a guarantee that every statement is objectively true. Raw sources remain the record of what was received and can overturn a curated claim after review.

This guide governs the workflow. If pages disagree, record the conflict rather than choosing whichever is newest. Ask the owner to resolve policy conflicts. Never treat an unreviewed note or draft as an approved answer.

## Folder rules

Each topic lives in `topics/<topic-name>/` and has:

| Location | Purpose |
| --- | --- |
| `README.md` | Topic scope, navigation, and review history |
| `raw/` | Original inputs plus a `SOURCES.md` register |
| `notes/` | Faithful summaries of individual inputs |
| `analysis/` | Comparisons, inferences, contradictions, and questions |
| `wiki/` | Readable answers, clearly marked draft or curated |

Copy [the topic template](templates/topic/README.md) to start. Avoid duplicating a source across topics; link to its existing file. Store a text extraction in notes beside a link to the original, and label extraction errors. Large, private, or restricted material may stay in approved external storage; register its exact location, access limits, version, and availability. Do not claim you inspected unavailable material.

## Ingestion

1. Define the question and topic scope.
2. Save the original input unchanged. Use a stable, descriptive filename; never overwrite a received version.
3. Assign a stable ID such as `S001`. In `raw/SOURCES.md`, record the local file or external location, title, author if known, source date if known, received date, origin, and relevant limits. Write `unknown` for missing metadata.
4. Write normalized notes with links to the original and useful page, section, timestamp, or line references. Distinguish quotation, paraphrase, and your own observations. Note missing sections and extraction limitations.
5. Compare sources in analysis. Then write a draft wiki answer based on the evidence.

The source register is maintained metadata; unlike original inputs, it may be edited with reviewable changes.

## Analysis standards and hallucination control

Put evidence beside each material factual claim. Use relative links to raw files wherever possible; a note may help readers navigate, but must not hide the original source. Keep exact quotations short and exact. Never use a citation merely because it discusses the same topic.

Separate these categories in prose:

- **Supported:** directly established by the cited evidence, within its scope.
- **Inference:** a reasoned interpretation; explain its assumptions and cite its basis.
- **Uncertain:** evidence is incomplete or unreliable; say why.
- **Conflict:** sources disagree; cite both and describe the disagreement.
- **Missing evidence:** identify the unanswered question and what would answer it.

Do not fill gaps from memory as if they came from the supplied sources. New external research is a new source and must be registered. Dates, numbers, and causal claims need particular care. Repetition across sources is not automatically independent confirmation. Absence of a statement is not proof of its opposite.

## Curation and changes

Each wiki page starts with `Status: draft` or `Status: curated`. Curated pages also name the approving reviewer, approval date, and evidence cutoff date. Draft pages use `pending` for review fields. Only the owner or an explicitly authorized reviewer may approve curation.

Before approval, check that claims match sources, limitations are visible, links work, and the page answers its stated question. Record what changed and why in the topic README's review history. For an existing curated page, propose changes in a separate draft until approval; then apply the reviewed change and record which page it supersedes. Drafts are never the source of truth.

Use Git diffs and local commits to retain reviewable history. Preserve earlier raw versions, and record corrections or withdrawals in the register and affected pages. If evidence is withdrawn, flag affected claims immediately for review; do not quietly erase the provenance trail. If a secret or personal information was accidentally added, stop distributing the repository and ask the owner how to remove it from history.

## Practical review checklist

- Can another reader locate the exact evidence for each important claim?
- Are interpretations, conflicts, and unanswered questions explicit?
- Are source dates and the evidence cutoff clear?
- Did the checker pass, and did a human assess citation quality?
- Is approval real and recorded, rather than inferred from a draft being present?

## Company research and the thesis journal

Use the company topic README to record legal name, ticker/exchange if applicable, reporting currency, fiscal year-end, research question, and coverage boundaries. Mark unknown details explicitly. Keep original filings, annual reports, earnings materials, and external research in `raw/`; the register should distinguish company-reported facts from third-party opinions.

For financial numbers, record period, currency, scale, accounting basis, and exact source location. Separate reported actuals, management guidance, external estimates, and your assumptions. Show formulas for derived metrics; do not compare unlike periods or quietly treat adjusted measures as statutory results. Restatements need a new source version and an explanation of affected conclusions.

Keep dated entries in `analysis/thesis-journal.md`: prior view, new evidence, revised view, confidence and limitations, evidence that would prove or disprove the thesis, and next review trigger. Link stable source IDs and the relevant analysis. Append new entries rather than rewriting earlier judgments with hindsight. Corrections should identify the entry they correct. A journal entry is a research record, not automatically a curated conclusion or a trading instruction.

The company wiki should summarize the business, evidence-backed financial observations, thesis status, valuation questions if relevant, risks, uncertainties, and next evidence needed. Unknown valuation or market data stays unknown. Record a date and source for any price, estimate, or valuation assumption. The workflow also supports non-company topics by replacing company identifiers and financial measures with relevant topic metadata.

## Voice and Codex session journals

Use [session templates](templates/sessions/README.md). Put dated originals or received session notes in raw, faithful session records in notes, cross-session comparisons in analysis, and reviewed conclusions in wiki. Shared evidence can live in one topic and be linked from the other. Use matching session IDs for linked voice/work entries. Record the date and timezone when known; distinguish a retrospective recording date from the time an event happened.

During coding sessions, focus on the work. At the end, optionally record a short combined review: coding outcomes and decisions first, followed by evidence-based voice feedback and one next step. Record installed tools with versions and whether the status was directly verified or merely reported.

Do not infer pronunciation, intonation, pauses, or pace from an ordinary text transcript. Audio or explicitly attributed observations are needed for acoustic claims. Verbatim transcripts may support filler counts only if their completeness and transcription conventions are known. Text can support comments about wording or organization, with exact examples, but not claims about how it sounded. Practice words are not automatically errors. Give balanced feedback in simple language; when evidence is absent, say not assessed.

Progress measures must state the method, source, denominator, and comparable task conditions. Keep missing values as not measured, never zero. Cite every session used in trend analysis; distinguish observed differences from improvement or causal explanations. A single session is a starting record, not a trend. Preserve past entries and append dated corrections rather than silently rewriting earlier feedback.

## Source quality, freshness, and gaps

Follow [EVIDENCE-POLICY.md](EVIDENCE-POLICY.md) for source metadata and grading. Maintain `analysis/evidence-gaps.md` in every topic. Quality, source confidence, conclusion confidence, and freshness are different judgments; reassess freshness before answering current-state questions. The rubric is intentionally small and adjustable.
