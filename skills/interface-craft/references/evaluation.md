# Review and refinement

A screenshot is visual evidence, not proof of interaction. Source code is behavioral context, not proof of rendering. Measure what can be measured; name what cannot.

## Observe before judging

1. Read the project's design system, the accepted direction and the files that render the screen.
2. Render it when you can — desktop width and one narrow width — and look at both. If it cannot be rendered, inspect the code and say which claims are therefore unverified. Never describe a rendered result you have not seen.
3. Before fixing a visual defect, capture the broken state: a screenshot, a measurement, or element rectangles proving the overlap. That capture is what makes it a defect rather than an opinion.

## Audit

Walk [signs](signs.md) and write one line per finding with a location: `file:selector`, Artboard board plus element, or a screenshot region. Then classify:

- **Objective defect** — covered, clipped or overlapping text, alignment that breaks a column, contrast below 4.5:1, a control that does not work. Fix inside the authorized scope.
- **Design hypothesis** — unclear hierarchy, a missing moment, a template-shaped composition. Propose with evidence; do not apply unasked.
- **Preference** — taste. Report only if asked; never as a bug.

Add no pixel measurements you did not measure. Do not invent a defect to justify the skill; an effective screen gets a short "already good" and at most two or three exact refinements.

## Scope

| Scope        | Use when                                                                                                          |
| ------------ | ----------------------------------------------------------------------------------------------------------------- |
| **None**     | The screen works. Report why, stop                                                                                |
| **Targeted** | Isolated, evidenced issues. Change only those                                                                     |
| **Broad**    | Foundational problems are evidenced: covered text, broken hierarchy, a template composition with no product in it |

A request to critique returns findings, not edits. A request to change one value changes one value. Never silently replace a selected board or a settled direction with another style; that is a new question for the existing Brainstorming/Artboard step, not a fix.

## Fix in ordered passes

Finish one pass across the whole screen before starting the next.

1. **Spacing** — put values on the scale; equal things equal; groups grouped; columns aligned; padding follows density. Check the navigation first, it breaks most often.
2. **Color** — one neutral ramp, three text roles, one accent used rarely; hairlines for borders; depth from surface steps, not colored glow.
3. **Icons** — one set, one size and stroke, text-role color, one icon box width; drop icons that carry no information; replace emoji used as glyphs.
4. **Copy** — headline says what the product does for whom; changes carry their reference; no hype, no invented claims; short labels; punctuation per [signs](signs.md).
5. **Type** — one family plus at most one partner; sizes from one scale; two weights; numbers tabular and in one format; display face only for large headlines.
6. **Layout** — keep the sections and their order; fix composition, proportions and alignment inside them; compose the first screen as a whole; one primary action.
7. **Details** — nested radii, quiet meta, keycaps for shortcuts, chart hierarchy and chart type matched to the data, real states (hover, focus, active).
8. **Visuals** — replace decorative filler with something the product actually produces; one moment, not one per section; no generated image where a coded preview is stronger.
9. **Motion** — remove looping decoration; keep motion that explains cause, space or state; one curve, a few durations; transform and opacity only.

The order is not cosmetic: spacing changes how everything reads, copy length decides type size and position, and motion must fit a screen that already works without it.

## Verify

- Re-render and compare against the audit list and the direction. At most three renders per run; keep a run quick.
- Report per finding: what was fixed, where, and how it was checked. Then what remains unverified and what is only a preference.
- After a fix, the audit line is answered only when the re-render or the measurement shows it.
- For built UI, hand the final verdict to ryugi:verifying; the human partner decides, not the agent.
