# Checking KB

Run `python3 scripts/check_kb.py` from the repository root. No third-party packages are needed. A nonzero exit means a check failed.

The checker checks relative inline Markdown links and images for existing files, requires each topic's four folders and source register, rejects template placeholders in real topics, and requires an evidence link in each note, analysis, and wiki page. It checks wiki status and curated review fields.

Use simple inline links like `[source](../raw/source.md)`. Reference-style links, HTML links, headings/anchors, remote URLs, and complex Markdown syntax are outside this lightweight check. It checks whether an evidence path exists, not whether every claim is cited, the citation is relevant, or an approval is authentic. Manually verify those points before curation. Templates are allowed to contain placeholders.

Voice and Codex notes must include session type, session ID, a valid date, a linked source, and limitations. The checker cannot determine whether audio supports feedback or whether session measurements are comparable; these still require review.

Every registered source ID requires a metadata block with quality, confidence, dates, data class, market/pricing flag, and freshness policy/status. Each real topic requires an evidence/gap register with the documented question fields. Checks validate dates and grade labels, not whether a source is actually current or high quality.
