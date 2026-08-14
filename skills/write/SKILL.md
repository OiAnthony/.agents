---
name: write
description: "Rewrites and polishes prose in Chinese or English, removes AI-like wording, and reviews product localization copy while preserving intent for drafts, docs, release notes, launch copy, and social posts. Use when users ask in any language to draft, rewrite, proofread, localize, polish release notes, remove AI-like wording, or prepare launch and social copy. Not for code comments, commit messages, or inline docs."
when_to_use: "帮我写, 改稿, 润色, 去AI味, 写一段, 审稿, 文档review, 本地化文案, 多语言文案, i18n copy, localization copy, check this document, 推特, twitter, X推文, tweet, social post, 连贯性, 段落连贯, draft, edit text, proofread, sound natural, polish, rewrite"
dispatch_intent: "Writing, editing prose, polish, release notes, launch/social copy, remove AI tone"
---

# Write: Cut the AI Taste

Prefix your first line with 🥷 inline, not as its own paragraph.

Strip AI patterns from prose and rewrite it to sound human. Do not improve vocabulary; remove the performance of improvement.

## Outcome Contract

- Outcome: the prose preserves the author's intent while sounding natural for its audience and surface.
- Done when: meaning, factual claims, and structure are preserved unless the user asked to change them, and AI-like wording is removed; punctuation and CJK/Latin mixing pass the Punctuation Gate for the output language.
- Evidence: supplied text, target audience, project style references, release or product state, and requested language.
- Output: the edited prose only, unless the user asked for notes, variants, or review comments.

## Core Stance

This skill is a catalog of smells, not a checklist to run top to bottom. Use it to recognize AI taste, then make judgment calls. The reference files (especially `write-zh.md`) are long because they accumulated examples over many sessions; do not try to apply every rule to every text. Applying more rules is not doing a better job.

- **Over-editing is failure, equal to under-editing.** If a sentence is already natural, clear, and stable, leave it. Most polish is subtraction (cut repetition, summary-tone, restated conclusions), not phrase-by-phrase replacement.
- **A piece has a speaker.** The reader's test is not "any banned words" but "can I tell who is talking". Prose that reads smooth and could have been written by anyone has already failed, whatever its word choice; unattributable fluency is the defect, not a neutral outcome. A speaker becomes legible through something this person knows, a judgment they would defend, and a thing they dislike. So the author's voice wins: keep their existing colloquial words, cadence, and stance, and when a rule collides with a deliberate authorial or genre choice (a question title in a narrative piece, a list they want kept), the author wins. Rules are defaults, not laws. Keep the sentences only this author would write and cut the ones anyone would.
- **Banned-phrase lists and replacement tables are examples, not find-and-replace.** A flagged word that reads naturally in context stays. Match the smell, not the string.
- **Prefer fewer, stronger edits.** Three changes that matter beat thirty mechanical swaps that flatten the voice.

When distilling a new lesson into this skill, fold it into an existing principle instead of appending another banned phrase. This skill must not grow monotonically; collapsing specifics back into principles is part of maintaining it.

## Pre-flight

1. **Text present?** If the user gave only an instruction with no actual prose to edit, ask for the text in one sentence. Do not proceed.
2. **Audience locked?** If the intended audience is unclear and cannot be inferred from the text (blog reader vs RFC vs email), ask before editing. Junior engineer and senior architect prose should read completely different.
3. **Language detected from the text being edited**, not the user's command:
   - Contains Chinese characters + release notes or social post mode → load `references/write-zh-release-notes.md`
   - Contains Chinese characters + bilingual or translation review → load `references/write-zh-bilingual.md`
   - Product/site/app localization review across multiple locales → load `references/write-product-localization.md`; also load `references/write-zh-bilingual.md` when Chinese copy is present
   - Contains Chinese characters (default prose) → load `references/write-zh-prose.md` (quick rules); load `references/write-zh.md` for the full AI-taste pattern catalog
   - Otherwise → load `references/write-en.md`

No summary, no commentary, no explanation of changes unless explicitly asked.

## Mode Picker

Default is a line-level rewrite of the supplied text. Take a mode only when its row matches, and load a mode file only when its row points at one.

| Ask | Mode |
|---|---|
| Release note, changelog entry, update-feed copy | load `references/mode-release-notes.md` |
| Maintainer reply on a public issue or PR | load `references/mode-public-reply.md` |
| Long draft (roughly 10k characters or more) needing structural work | load `references/mode-long-form.md` |
| EN/CN pair to check for drift | [Bilingual Review](#bilingual-review-mode) |
| Product, site, or app copy across locales | [Product Localization Review](#product-localization-review-mode) |
| Document, PDF, or white paper to review | [Document Review](#document-review-mode) |
| Paragraphs that read disconnected | [Paragraph Coherence](#paragraph-coherence-mode) |
| Tweet, thread, or launch post | [Tweet / Social Post](#tweet--social-post-mode) |

## Durable Context Preflight

See [references/durable-context.md](references/durable-context.md) for when durable context is in scope and the redaction gate that applies before any of it becomes a durable rule.

For `/write`: the supplied text and current release state override memory. Durable preferences can set brevity, tone, and social-post shape; they do not override the hard rule to edit in place, keep meaning intact, and avoid change lists unless the user explicitly asks.

## Hard Rules

- **Meaning first, style second.** If removing an AI pattern would change the author's intended meaning, keep the original.
- **No silent restructuring.** Do not reorganize headings, reorder paragraphs, or merge sections unless structural changes are explicitly requested. Edit in place. Structural assets are not cleanup noise: image placeholders, links, frontmatter, and example blocks stay unless the user asked to remove them, and any deletion gets listed with its reason instead of discovered later in the diff. (Exception: `references/mode-long-form.md` treats structural cuts and merges as in-scope, since structure is the main problem there; it still proposes them as change-points first instead of doing them silently.)
- **No invented first-person experience.** When ghostwriting as the author, every personal anecdote, tool history, opinion, and quote must come from the supplied material or the author's published writing. The material lacking an example is a question to ask, not a gap to fill. Before drafting in the author's voice (rather than editing supplied text), read one or two of their published pieces as the voice and length baseline.
- **Material gate before drafting long-form.** When asked to write rather than edit, count what you actually hold before choosing a length: supplied experience, numbers, quotes, actions, and verifiable public sources. A category name is not a material, and a restated idea is not a second material. Reasoning connects material; it does not breed material. If you cannot name a distinct material for each planned section, the plan is longer than the evidence. Resolve it by researching first, asking at most three questions in one round, or shipping a shorter piece. A target word count is not a reason to pad with invented examples or a fourth phrasing of the same point.
- **Shorter than the first draft wants to be.** Outward copy (README paragraphs, tweets, release notes, maintainer replies) defaults to the length of the user's previously accepted pieces; when a physical constraint exists (tweet fold line, single-line rendering), derive the budget from the constraint before writing, not after the user trims it.
- **Artifact-grounded claims.** For launch copy, release notes, social posts, product pages, and public replies, ground factual claims in real source material: current app behavior, runnable artifact, screenshot, product page, release page, changelog, issue/PR, or user-provided draft. Do not present handoffs, plans, old memory, or stale screenshots as current product truth, and do not turn concrete product evidence into generic marketing language.
- **No em-dash.** Never produce em-dash (U+2014) or en-dash (U+2013) in Chinese or English output. Em-dash is the strongest AI-tone fingerprint in this style of writing. Use commas, periods, colons, semicolons, or parentheses to break clauses. Hyphen-minus (`-`) inside compound words is allowed; replace it with a space or a period when possible. When editing a draft that contains em-dashes, replace every one before returning the text.
- **Stop after output.** Deliver the rewritten text. Do not append a list of changes, a justification, or a closer. (Exception: `references/mode-long-form.md` returns change-points for review instead of a rewritten blob.)

## Punctuation Gate

Before returning any produced text (a rewrite, or generated release / reply / social copy), resolve the checker across install layouts and run it:

```bash
GATE=""
for candidate in \
  "<skill-base-dir>/scripts/check-punctuation.sh" \
  "<skill-base-dir>/skills/write/scripts/check-punctuation.sh"; do
  [ -f "$candidate" ] && GATE="$candidate" && break
done
[ -f "${GATE:-}" ] || { echo "punctuation gate not found under the installed skill base; reinstall Waza" >&2; exit 1; }
bash "$GATE" --lang <zh|en|ja|auto> <file>   # or pipe text via stdin
```

Replace `<skill-base-dir>` with the installed Write skill or Waza dispatcher directory. The first path covers direct/plugin installs; the second covers the inlined-root release ZIP.

It enforces character-level punctuation by locale (half/full-width marks, CJK/Latin spacing, em/en dashes) and skips code, inline code, URLs, and markdown link targets, so it never fires on code; the script header documents the exact rule set. Fix every finding while preserving meaning; `--fix` rewrites only the zero-ambiguity zh cases to stdout. `--lang auto` classifies the whole input by fixed priority: any kana routes to ja, else any CJK to zh, else any Hangul to ko (reserved, skipped), else en, so a mostly-Chinese text that merely quotes a Korean glyph still routes to zh; pass an explicit `--lang` for mixed-locale or predominantly-English text. The checker owns character-level punctuation only; quote direction and other judgment calls stay with you and the reference files.

## Bilingual Review Mode

Activate when: mixed Chinese/English, "Chinese copywriting", "bilingual consistency", "release notes"

Load `references/write-zh-bilingual.md`. Character-level spacing and punctuation belong to the Punctuation Gate script; this mode owns the judgment half: terminology consistency across all instances, unexplained English left untranslated in Chinese documents, and EN/CN pairs that drift in meaning (mark translation loss instead of silently rewriting one side).

## Product Localization Review Mode

Activate when: "本地化文案", "多语言文案", "localization copy", "i18n copy", product/site/app strings, release feed copy, runtime catalog, or a user asks whether localized copy feels native.

Load `references/write-product-localization.md`. If Chinese is one of the locales, also load `references/write-zh-bilingual.md`.

Default workflow:

1. Separate surfaces first: release feed, website pages, docs/help, runtime strings, legal/privacy copy, and generated pages may have different locale coverage and source files.
2. Preserve factual structure: versions, dates, links, item order, placeholders, and product behavior remain fixed unless the user asks to change them.
3. Review by locale artifacts, not by English meaning alone. Missing accents, ASCII fallbacks, literal possessives, stale locale paths, and mechanical plural or apostrophe errors are first-class issues.
4. After broad cleanup, run a second pass for replacement damage. Do not trust accent sweeps or glossary replacements until the generated output has been checked.
5. When asked to implement, patch the source localization files and rebuild generated pages. When asked only to review, return findings grouped by surface and severity.

## Document Review Mode

Activate when: PDF, document, white paper, "review this document", "check this document", "审稿"

Review checklist:
- **Privacy scan**: Detect PII (names, companies, employment dates, salary hints, location details). Hard stop if any text implies job seeking, competitor info, or personal data leakage.
- **Tone consistency**: Flag voice shifts, register mismatches, formulaic phrasing. Check for AI patterns using the loaded `write-zh.md` or `write-en.md` rules.
- **Bilingual validation**: For CN/EN pairs, confirm translation accuracy and terminology consistency. Apply Bilingual Review Mode rules.
- **Rendering check**: Placeholder text remaining (`Lorem ipsum`, `TODO`, `[TBD]`), broken image links.
- **Durable-doc scan**: If the document is a review report, scorecard, or diagnostic snapshot, flag dated claims, stale line references, private paths, repo-specific commands, and current-score framing. Recommend extracting stable rules instead of preserving the snapshot as evergreen guidance.

Output format: same as prose rewrite, but append `privacy: clear / N issues found` after the reviewed text.

## Paragraph Coherence Mode

Activate when: "连贯性", "段落连贯", "可读性", "coherence", "flow check", "段落顺不顺"

Do not rewrite. Instead, work through each paragraph in sequence:
1. Flag transitions that abruptly shift topic without a signal.
2. Flag paragraphs where the opening sentence does not follow from the previous paragraph's close.
3. Flag rhythm issues: monotone sentence length (all short or all long across a whole paragraph).
4. Suggest the minimal fix for each: one word, one reordered clause, one bridging sentence.

Output: a numbered list of issues, each with the paragraph location and a one-line fix suggestion. Then ask if the user wants any applied.

## Tweet / Social Post Mode

Activate when: "推特", "twitter", "X推文", "tweet", "social post", "折叠长度", "长文推特", "发文"

Apply the five announcement rules for product-engineer projects when the project context or prior artifact shows this style:
1. **Lead with community**: open with the social anchor (star count, user thanks, whose feedback drove the fix). Changes follow, not lead.
2. **Highlights over completeness**: pick 2 to 4 of the most interesting changes. Dropping whole items is fine.
3. **UX framing**: phrase each point as "你用它的时候..." or "有一种...的感觉", not "这个工具做了...".
4. **One stance**: include at least one opinionated sentence revealing why decisions were made.
5. **Native Chinese rhythm**: use idiomatic phrasing. Avoid translation-sounding terms.

Close casually with an invitation, not a CTA. End with one short sentence inviting readers to try, not "立即升级".

For other engineering projects or English posts, apply the same structure (community lead, highlights, UX framing, one stance, casual close) adapted to the project's voice.

## Gotchas

| What happened | Rule |
|---------------|------|
| Reorganized headings without being asked | Do not restructure; edit in place unless structure changes are explicitly requested |
| Appended a "changes made" list after the rewrite | Output is the edited text only. No changelog, no commentary. |
| Used formal register for a blog draft | Match the target audience's register. Blog is conversational, not academic. |
| Applied Chinese/English spacing rules to a pure-English text | Bilingual spacing rules (半角/全角) only apply when the text mixes Chinese and English |
| Polished the user's voice into generic launch copy | Preserve the author's cadence and stance. Use real product artifacts to sharpen facts, not to replace the voice. |
| Drafted release or social copy from memory or a handoff | Read the current release page, changelog, issue/PR, runnable artifact, product page, screenshot, or supplied source before making factual claims. |
| Wrote launch copy in one pass without checking the live screenshots | Iterate: draft, compare against the real product screenshot or page, tighten wording to match what ships, repeat until copy and artifact agree |
| Polished a review report until it sounded timeless | Keep snapshots labeled as snapshots, or distill them into stable rules. Do not make dated claims sound evergreen |
| User flagged one word as "not my voice"; only that instance was fixed | A flagged word marks a smell class, not a typo. Sweep the whole text for the same class (same register, same template shape) before returning |
| Hit the requested word count by explaining the same three ideas from four angles | Count the material first. Research, ask up to three questions, or ship shorter. Padding is a failed draft, not a long one |

## Output

Return only the edited prose. If the text was truncated or if multiple versions were possible, note that in one sentence after the body. Otherwise, no wrapper, no preamble, no postscript.
