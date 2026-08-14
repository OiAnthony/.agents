# Long-form Article Mode

Loaded from `write` when the input is a long draft (roughly 10k characters or more) that needs structural work before line edits.

Activate when: editing a Markdown article or file over ~300 lines, or one with multiple `##` sections plus tables and images (technical long-reads, blog posts, deep dives).

In long-form, the dominant problem is usually structural: the same checklist repeated across sections, prose that re-reads a table sitting right above it, list bloat, whole redundant sections. Sentence-level AI taste is the smaller half. A single in-place polish pass cannot see or fix the structural half, which is why a plain `/write` on a long article feels like it changed wording but left the bloat. This mode therefore overrides two Hard Rules: structural cuts and merges are in-scope, and the output is change-points for review, not a rewritten blob.

Workflow:

1. **Map first, read-only.** Before editing anything, read the whole article and list every `##` section, table, list, and image. Flag three structural problems: cross-section repetition (same checklist / judgment list / core claim in 2+ sections), table re-reading (a section whose prose walks the rows of the table above it), and whole redundant sections or paragraphs.
2. **Name what each paragraph stands on.** For every paragraph, say privately which material holds it up: user-supplied experience, a public source, a runnable artifact, a number, a quote. When the honest answer is "it further explains the paragraph above" or "it is a possible implication", that paragraph has no new material and is a cut candidate. Then run the compression test: drop a third of the draft and re-read. If the facts, actions, judgments, and reading experience barely change, the original was padded, and the shorter version is the draft.
3. **Propose cuts as change-points.** Show before to after for each structural cut or merge and let the user pick the subset. Never delete a whole section or paragraph silently; confirm first, since it may hold a fact found nowhere else (see `references/write-zh.md` 删段之前先确认信息量).
4. **Then line-level de-AI**, section by section, per `references/write-zh.md`.
5. **Output is change-points, not a blob.** Show what changed so the user can review and keep their own hand-edits. Only return fully rewritten text when the user says 直接改 / just rewrite; when you do return a full rewrite, run the Punctuation Gate on it first.

Do not single-pass rewrite a 40k-character article: it silently overwrites the author's hand-tuned phrasing and cannot be reviewed as a diff. See `references/write-zh.md` 结构级重复与表格复读（长文专项）for the matching content rules.
