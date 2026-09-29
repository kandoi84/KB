# PDF page extraction and reviewed roles: 04C2

**Goal:** Create page-cited text from a reviewed PDF filing, then attach speaker roles only to exact spans approved by a reviewer. Keep raw PDF evidence immutable and real publication blocked.

**Design:** Use a pinned `pypdf` parser. A deterministic parser version binds the library version and extraction mode. Store one immutable extraction receipt, one derived UTF-8 page text row per PDF page, and bounded chunks whose byte offsets refer to that page text. Never call these offsets raw PDF offsets. Recompute extraction from the source on replay and reads; mismatches block. Reject encrypted, corrupt, blank/scanned, oversized, or too-many-page PDFs. Any failed page blocks the whole run. The parser does not infer speaker identity.

Role annotations are separate append-only receipts. A reviewer supplies a page, exact whole-chunk UTF-8 byte span, role, evidence locator, review time, and ID. The span must match the supplied quote. Queries show a role only after both review time and system-recorded arrival time; otherwise `UNKNOWN`. A correction names the prior review ID; `UNKNOWN` revokes a label. Competing branches and overlaps block. Extraction itself has a system-recorded arrival time for strict live reads. Label changes append a revision, never mutate a prior receipt.

## Implementation loop

1. Add tests for multi-page citations, Unicode offsets, replay, cutoff, and CLI output. Show failure first.
2. Add PDF parser and immutable page/chunk receipts with source and identity checks.
3. Add tests and code for explicit reviewed role spans, conflicting labels, tampering, late review, and wrong quote.
4. Run affected and full checks, review the diff and staged files, then commit and push only owned files.

**Boundary:** This is a controlled extraction path, not an endorsement of OCR accuracy or a live filing adapter. A licensed real sample, visual page check, and parser process resource/time limits remain source-adapter activation gates. No real company result can be published from this slice.
