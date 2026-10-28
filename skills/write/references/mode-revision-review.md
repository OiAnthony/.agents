# Revision Review Mode

Loaded from `write` when the input is a before/after pair of the same text (an uncommitted diff, two drafts, a polish pass from another model or editor) and the question is whether the new version is better.

Done when every changed hunk has a verdict (keep, revert, or blend), each revert or blend names what the new wording lost, and the surfaces that repeat the edited text agree with it. Read the word-level diff (`git diff --word-diff`) against the whole article, not the hunks in isolation: most losses only show against the surrounding paragraphs.

What a polish pass tends to lose, and what to check before keeping a hunk:

- **Raw reaction swapped for a tidy abstraction.** The author's exclamation, slang or physical image becomes a neutral noun phrase ("friction", "a knowing smile", "the top priority is always"). The new line reads smoother and belongs to no one. Revert to the author's words; a blend may keep the new version's trims around them.
- **A motif chain broken at one link.** A heading, a mid-section line and the closing paragraph often call back to the same image. Neutralizing one occurrence orphans the others. Treat the chain as one unit: keep it all or change it all.
- **Reasoning cut to a bare claim.** A trade-off clause, a "because", or a closing stance gets trimmed for length, leaving a definition the reader could have written. Shorter is not better when the cut part was the point of the paragraph.
- **A concrete number or name blurred.** "All 850 are free to read" becomes "click into any app to read it". Restore the specific.
- **A new word that contradicts the article's thesis.** A casual "along the way" in front of work the article frames as deliberate, laborious effort. Check each added adverb and framing word against the piece's main claim.
- **Doubled phrasing introduced by the edit.** The same noun twice in one sentence, or a closing call-to-action that repeats the ask in the previous paragraph.

Accept the edits that are better: typo and grammar fixes, a truer opening motivation, a run-on that genuinely misread. The author asked whether the new version is better, not for a defense of the old one, so a review that reverts every hunk has failed too.

Titles get a lighter touch. When the author has just chosen a title, flag it only if it misreads or misleads. Any alternative you offer must read more smoothly aloud than the original; an alternative that is merely more literal or more correct gets rejected, and rightly so.

Sync surfaces after the verdicts:

- **Mirrors.** An edit applied to one language only (a figure changed in English, a list extended in Chinese) is drift. Carry each kept change to the other version or revert it on both.
- **Title echoes.** When title words change, find every place that repeats them: cover or social-card image text, image alt text, the mirror's title, summary fields, and cross-links from other posts. An image whose text no longer matches the title needs a new asset, not just new alt text.

Output follows the request. "Is it better?" gets per-hunk verdicts ranked by impact, read-only. "Fix it" gets the edits plus a list of every restored or rewritten sentence the author can veto.
