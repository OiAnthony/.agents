---
name: interface-craft
description: Use when a visible product interface needs design judgment, including UI mockups during brainstorming, landing and marketing pages, visual direction exploration, reviewing an existing screen, or refining a prototype that feels generic or inconsistent.
---

# Interface Craft

A design technique, not a mandatory extra phase. Two halves, in order: set a direction from the product, then check the screen against things that can fail. Nothing here is a house style; the project's system and accepted decisions outrank every default below.

**Integration:** Project design system and explicit decisions take priority. Ryugi:brainstorming owns requirements and approval; ryugi:artifacts owns visual presentation; ryugi:verifying owns the human verdict for built UI. This skill adds **no new approval gate**.

## Pick the mode

| Mode       | When                                                                      | What to do                                                                                             |
| ---------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Create** | A new surface or a new visual direction, especially with no design system | Write the five direction lines, then apply [tokens](references/tokens.md) and the passes while drawing |
| **Repair** | An existing screen, with defects or with a request to improve it          | Audit with [signs](references/signs.md), report findings with locations, fix only the agreed scope     |
| **Edit**   | One exact visual change is specified                                      | Make that change. No audit, no direction, no questions                                                 |

Not a UI task: backend work, architecture diagrams, pure copy, generic documents that happen to have a visual format. Building a whole design system: ryugi:design-system orders the stages; this skill judges each board.

Landing pages, marketing and pricing pages, onboarding, empty states, settings and emails are product interfaces too; use this skill for them.

## The five lenses

Infer from the product, brief, current screen and user decisions. Read [direction](references/direction.md) when deriving a new direction; it contains the shape of the answer and one worked example.

1. **Product:** Who uses this interface, for which job, under what conditions?
2. **Character:** Which two or three specific qualities should it communicate? Reject _modern_, _clean_, _premium_, _sleek_: they describe every template.
3. **World:** What materials, places, objects or metaphors actually belong to this product? This sets the tint of the neutrals, the accent and the visual.
4. **Moments:** Where does richness concentrate? One or two places where the product itself is shown well; not a mandatory hero.
5. **Signature:** One small repeatable detail only this product would have. Omit it rather than invent one.

Write these five lines before drawing or editing. They are decisions, not questions for your human partner.

## Values only where nothing exists

The project's tokens, brand and accepted direction win. When they do not exist, [tokens](references/tokens.md) gives starting values: a 4px spacing grid, nested radius math, a type scale, three text roles, one accent, one easing curve. Adapt the tint and accent from the **World**; never copy an example palette verbatim.

## Audit before judging

Read [signs](references/signs.md) and list what you find, one line each, as `location — sign — fix`. Classify each finding:

- **Objective defect** — clipped or covered text, overlap, broken alignment, contrast below 4.5:1, a control that does not work.
- **Design hypothesis** — hierarchy, density, or a missing moment. Worth proposing, not fixing unasked.
- **Preference** — taste. Never a bug.

If the screen is already effective, say so and stop, with at most two or three exact refinements. Do not redesign to justify the skill.

## Fix in ordered passes

Read [evaluation](references/evaluation.md). Apply one pass across the whole screen before starting the next, in this order: **spacing → color → icons → copy → type → layout → details → visuals → motion.** Spacing first because it changes how everything reads; copy before type and layout because headline length decides size and position; visuals and motion last because they must fit a screen that already works.

## Check what can fail

Render the result when the screen is code that can be rendered, at least at desktop width and one narrow width. At most three renders per run. Compare the render with the audit list and with the direction; a claim about visual quality without a render is unverified, so say so.

- [ ] Every audit finding is answered, and each fix names its location
- [ ] No text is covered, clipped or overlapped at either width
- [ ] Spacing values sit on the scale, and equal things have equal sizes
- [ ] One neutral ramp, three text roles, one accent with readable contrast
- [ ] Figures use tabular numbers and one format across the screen
- [ ] No prices, logos, customer names or claims that the user did not supply
- [ ] Nothing from the signs list survives in the touched area
- [ ] **Name-swap test:** if another product's name replaced this one, would the screen still fit? If yes, push the copy, visual and signature detail harder

Adapted from [Unslop by Damir Sokolovsky](https://github.com/heydamir/unslop) (CC BY 4.0): the audit signs and token tables derive from it, generalized to creation, review and design-system-aware workflows.
