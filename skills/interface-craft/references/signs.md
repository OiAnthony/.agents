# Signs

Scan this list and write findings as `location — sign — fix`. One line per finding, no essay.

These are **defaults to decide against**, not a house style. When the project's design system, an accepted direction or your human partner deliberately chose something on the list, keep it, note the evidence, and move on. The objective-defect group has no such exception: those are broken regardless of taste.

## Objective defects

Measure these before classifying anything else. They are not opinions.

- Text covered by a floating card, pill or device → move the text into space left empty for it, or drop the float; never let a decorative layer sit on a headline or a paragraph. Check with element rectangles: any overlap between a positioned card and a heading or paragraph is a defect.
- Text clipped by a fixed width, `overflow: hidden`, `white-space: nowrap` or a `min-width` that is narrower than the content → let it size to content, or shorten it.
- Headline wider than its container, so it runs off the viewport or under the next column → change the measure, size or copy.
- A control that looks interactive and is not, or a static mockup labeled as interactive → make it work or say it is a mockup.
- Contrast under 4.5:1 for body text, 3:1 for large text and for UI boundaries that carry meaning → darken the text or lighten the surface. Do not rely on hue alone for state.
- Rows, cards or labels sharing a list but not sharing height, padding or baseline → one value for all of them.
- Elements nudged off a column with a one-off `margin`/`translate` to fake alignment → fix the container instead.
- No visible keyboard focus, or a focus ring removed without a replacement → restore one that fits the palette.
- Touch targets under 40px, text under 11px inside a preview → enlarge or simplify the preview.
- A number, price or availability claim with no source → remove it or ask.

## Template look

The most likely failure of a clean screen is that it could belong to any product.

- A headline that survives a name swap → say what this product does, for whom, using its own nouns.
- Nav, centered hero, three feature cards, pricing tiers, footer, in that order with no reason → change composition or cut a section the product does not need.
- Equal cards side by side, each with the same content shape → vary the rhythm: compact stats above one wide block, a wide chart beside a narrow list.
- The same palette, type and layout the model uses for everything → let **World** pick the neutral tint, the accent and the type.
- A visual that is an empty box, a labeled placeholder or generic stock → show the product's own output, built in code.
- Every section carrying a visual or a colored band → one moment, quiet elsewhere.

## Surfaces and color

- Hue-to-hue gradients on backgrounds, cards, buttons or the active nav item → one neutral surface; a small tone shift inside a single neutral is fine.
- Gradient text, glowing text, colored shadows, neon borders → solid text color, depth from surface steps and hairlines.
- Radial washes, blurred blobs, orbs behind content → remove; show the product instead.
- Five near-identical tints of one hue used for text → three text roles: primary, secondary, muted.
- Every element highlighted, so nothing leads → one accent used a few times per screen.
- Glass cards with an inner highlight and a colored shadow → a plain raised surface with a hairline. Keep glass where it is part of an accepted direction.
- Page surfaces reading as an orange, brown, blue or green cast on a long-lived app → keep surfaces neutral, let the world show in the accent, charts and moments. Landing pages may tint further.
- Borders as bright lines → hairline at 6–10% of the text color.
- Dark themes using shadow for depth → surface steps plus a hairline.

## Type

- Headings at 800–900 for hierarchy → size and color carry hierarchy; weights 400–600.
- `UPPERCASE` labels with wide tracking → sentence case at normal tracking.
- Five sizes and four weights on one screen → a few steps from one scale and two weights.
- Numbers in mixed formats, like `$48,210` next to `$124,860.40` → one format, tabular figures, aligned columns.
- Negative letter spacing on small text → zero; tight tracking only for display sizes.
- Italic for emphasis → weight or color.
- A display serif used on labels, buttons or numbers → serif only for large headlines.
- A default family nobody chose, on a product with a clear character → choose one that matches the character, and at most one partner.

## Icons

- Emoji as icon, status, nav glyph or label decoration → one line-icon set at one size and stroke, or nothing.
- An emoji inside a count or pill → the plain number.
- Icons at several sizes and colors → one size, one stroke, text-role color.
- Icons with varying widths so labels fail to align → one icon box width per column.
- A sparkle used for anything AI → a plain icon, or remove it.

## Spacing and layout

- Arbitrary values like `13px`, `7px`, `31px` → steps on the scale.
- Groups closer to their neighbours than to their own items → space inside groups smaller than space between groups.
- Unequal padding inside sibling cards → one padding.
- A dead empty band in the first screen, or a cramped one → compose the first screen as a whole.
- An app squeezed into a narrow centered column → real app proportions: side bar 240–280, content fluid and capped, page as long as its content.
- Long headline centered across two lines in a way that breaks the reading line → left-align long headlines; centering is for one or two short lines.
- Three or more buttons under the hero, or chips and avatars stacked under them → one primary, at most one secondary.

## Copy

- Greeting headline such as `Welcome back, Name 👋` → name the context or period.
- Exclamation marks, or `!!` → plain statement.
- A change without its reference, like `+12%` alone → `+12% vs last month`.
- Placeholder-shaped copy, like `Search anything...` → `Search`.
- Hype words: supercharge, seamless, unlock, magic, revolutionize, game-changing, AI-powered everywhere → what the thing actually does.
- Trailing periods on labels, buttons and headings → none. Paragraphs keep theirs.
- Invented prices, customer names, logo walls, testimonials or metrics → remove, or ask before shipping. Mock data is allowed; fabricated claims are not.
- `PRO`, `New ✨`, `Beta 🚀` badges → remove, or one quiet text label that carries information.
- A headline that states a feeling instead of a fact about the product → say what happens, for whom.

## Components and details

- Everything a pill, from search to cards → radius by size, and nested radius: inner = outer − padding, never below 4.
- Glowing pills for counts, plans or shortcuts → mono text or a keycap.
- Stat cards filled with sparklines, tallies, mini bars or decorative icons → label, big figure, change with its reference. A real object is fine when the card counts that object.
- Several charts of equal size on one screen → one leading chart, other data as a list or table.
- Rainbow bars, glowing bars, pill bars or uppercase day labels in a chart → muted grid, mono labels, one highlight color.
- The wrong chart for the data: a trend drawn as bars, a share drawn as a line → trend = line, comparison = bars, share = one stacked bar or a list with bars, goal = progress bar.
- The active state as a gradient and glow → a surface step with a hairline.
- Hover or press motion larger than a few pixels, `transition-all`, bouncy springs → named transitions on color, background, border, opacity and transform.
- Looping motion on things that are not live (`pulse`, `ping`, shimmer, breathing glow) → static.
- Everything entering on load from different directions → one short fade and rise, small stagger.

## Landing heroes

- A pill badge above the headline announcing the product → remove, or a quiet link if it is real news.
- Text, buttons or a fake logo baked into an image → real text in the page.
- A hero with no visual and everything stacked → an asymmetric split with the product at half the width, or a product view below the text.
- A visual on every section → one, usually the hero.
- An image whose edge does not blend with the page → match the background, or mask the edge.

## Motion

- Motion that loops for no reason → remove.
- Motion larger than a few pixels on hover → color or surface change; press scale 0.97–0.98.
- Animated `width`, `height`, `top`, `left`, margins or large blurs → transform and opacity only.
- Several easing curves or durations → one curve, a few durations.
