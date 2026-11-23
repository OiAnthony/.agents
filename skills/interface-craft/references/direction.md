# Deriving a product-specific design direction

Write the five lines before drawing anything. They are decisions, not five questions for your human partner: reuse the brief, the existing project, accepted designs and the design system. Inferences are yours; ask only when an unresolved choice materially changes the result, through the existing Brainstorming process.

| Lens      | Evidence to consult                                            | Actionable result                                                         |
| --------- | -------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Product   | Task, audience, work frequency, real data, primary action      | The primary job the screen optimizes                                      |
| Character | Voice, audience, existing identity, environment                | Two or three concrete attributes shaping decisions                        |
| World     | Domain objects, media, work context, physical metaphors        | Visual language rooted in the product: neutral tint, accent, type, visual |
| Moments   | Attention, risk, key insight, data or product imagery          | One or two intentional focal areas, if needed                             |
| Signature | Current brand, recurrent workflow, domain-specific interaction | One meaningful repeated detail, or explicitly none                        |

If a lens has no practical consequence for this screen, do not manufacture one. If you cannot say the **World** or the **Moments** in one plain sentence, the direction is not clear yet.

Translate the five lines into decisions about layout, hierarchy, density, copy, palette, contrast, typography, spacing, imagery, motion and states. [Tokens](tokens.md) supplies values only where the project has none.

## Example: incident monitoring dashboard

- **Product:** An on-call engineer locates an incident and assesses its impact quickly.
- **Character:** Exact, steady, operational.
- **World:** Diagnostic instruments, time-series and service dependencies.
- **Moments:** The active incident and the event-time graph establishing when failure started.
- **Signature:** A consistent incident timeline marker tied to actual events.

That might justify dense navigation, aligned data, clear incident status and restrained surroundings. Those are outcomes of this product, not tokens to copy into another app.

## Existing choices outrank defaults

Priority: direct current requirements and accepted decisions → project design system, platform conventions and existing brand → observed product needs → newly inferred direction.

Deliberate gradients, purple, translucent materials, serifs and animations are not inherent faults. A useful existing screen is not a blank canvas. When a direction is already settled, continue it instead of inventing a brand each round.

## Exploring direction on an Artboard

A direction comparison may change several linked visual properties, because that _is_ the question. Label each concept with what differentiates it beyond color, and explain the rationale in one line. Once chosen, treat the direction as fixed while comparing one layout or interaction dimension per group. Use real product copy and representative data, never randomized template text or speculative features.

Do not force a signature onto every product. Do not present design intent as another formal approval gate outside the existing Artboard choices.
