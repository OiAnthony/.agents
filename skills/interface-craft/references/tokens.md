# Tokens

Starting values, used **only** where the project has nothing better. When a design system exists, keep its values and fix only how they are used. Let the **World** lens move the tint, accent and type; these are a floor, not a look.

## Spacing

4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128. Everything sits on the 4px grid; 28 and 104 are fine, and a 2px nudge inside a small control is allowed.

| Between                                 | Value                               |
| --------------------------------------- | ----------------------------------- |
| Inside a control                        | 4–12                                |
| Related items, rows in one list         | 2–8                                 |
| Groups, a label and its list, two cards | 12–24                               |
| Sections                                | 32–64; landing sections 80–128      |
| Navigation to headline, desktop         | 96–128                              |
| Row height                              | 32 compact, 36 default, 40–44 touch |

Space shows grouping: inside a group smaller than between groups. Equal things get equal sizes, and columns line up — icons in one column, labels on one line, figures right-aligned in one column.

## Radius

| Element                    | Radius |
| -------------------------- | ------ |
| Keycap, tag, small control | 4–6    |
| Row, input, button         | 8–10   |
| Card                       | 12–16  |
| Panel, window              | 14–20  |

Nested radius: `inner = outer − padding`, never below 4. Not everything is a pill.

## Type

One interface family, plus at most one partner: a mono for figures and meta, or a display face for large headlines only.

| Character                | Interface                          | Optional partner                                        |
| ------------------------ | ---------------------------------- | ------------------------------------------------------- |
| Precise, technical, calm | Geist, Inter, IBM Plex Sans        | Geist Mono, IBM Plex Mono, JetBrains Mono               |
| Warm, human, friendly    | Instrument Sans, DM Sans, Figtree  | Instrument Serif, Newsreader (headlines only)           |
| Editorial, crafted       | Inter, Instrument Sans             | Newsreader, Instrument Serif, Fraunces (headlines only) |
| Playful, bold            | Space Grotesk, Bricolage Grotesque | a mono for small labels                                 |

| Use                        | Size                        | Line height | Weight                            |
| -------------------------- | --------------------------- | ----------- | --------------------------------- |
| Meta, counts, small labels | 12                          | 16          | 400                               |
| Secondary text, captions   | 13–14                       | 20          | 400                               |
| Body, nav items            | 14–15                       | 20–22       | 400–500                           |
| Wordmark                   | 16–18                       | 1           | 500–600                           |
| Subhead                    | 18–20                       | 28–30       | 400, secondary color, ≤36rem wide |
| Card figure                | 28–32                       | 1           | 500, tabular                      |
| Page title                 | 28–36                       | 1.15        | 400–500                           |
| Hero headline              | 56–72 desktop, 36–44 mobile | 1.02–1.08   | 400–500                           |

Letter spacing is 0 under 16px, up to 0.01em for small muted text, −0.02em from 40px, −0.03em from 56px. Figures use `font-variant-numeric: tabular-nums` and one format across the screen.

## Neutrals

Three ramps, chosen by the **World**: graphite for long-lived apps and dashboards, warm for paper/ink/human products, ink for night/sky/technical products. Tint your own the same way with saturation kept very low, so a surface never reads as a color on its own.

| Role                 | Graphite  | Warm      | Ink       |
| -------------------- | --------- | --------- | --------- |
| Dark deepest surface | `#0f0f10` | `#12110f` | `#07080d` |
| Dark page            | `#141415` | `#161513` | `#0b0d14` |
| Dark card            | `#19191b` | `#1c1a18` | `#11141c` |
| Dark raised / active | `#232325` | `#262421` | `#1a1e28` |
| Dark primary text    | `#ededed` | `#efe9de` | `#eef0f5` |
| Dark secondary text  | `#a1a1a6` | `#aaa398` | `#a3a9b8` |
| Dark muted text      | `#85858b` | `#8a847a` | `#7a8296` |
| Light page           | `#fafafa` | `#f7f4ee` | `#f5f7fa` |
| Light card           | `#ffffff` | `#fdfbf7` | `#ffffff` |
| Light raised         | `#f4f4f5` | `#efe9df` | `#eceff4` |
| Light primary text   | `#171717` | `#1f1b16` | `#111827` |
| Light secondary text | `#525252` | `#5e554a` | `#4b5565` |
| Light muted text     | `#737373` | `#7b7266` | `#6b7487` |

Hairlines are the primary text color at 8–10%. Muted text is for meta only and stays near 4.5:1 on its surface. Semantic colors are toned to sit inside the ramp: positive `#4cc38a` on dark, `#16a34a` on light; negative `#e5484d` on dark, `#dc2626` on light.

## Accent and actions

- A real brand color stays as the accent and leaves the surfaces. Without one, take the accent from the **World**: warm worlds suit amber, coral, ember; cool worlds cobalt, teal, sky; natural worlds moss or sage. Avoid the purple-to-blue family unless that is really the brand.
- Text on the accent reaches 4.5:1, or the accent is darkened for text use.
- The accent covers a few percent of the screen: the primary action, the selection, one key figure.
- Hero buttons 44–48 tall, navigation buttons 32–36, horizontal padding 16–20. On dark, an off-white fill with dark text often reads better than a colored button; then keep the accent for the selection or one figure.
- Secondary: raised surface plus hairline, primary text.

## App layout

- Sidebar 240–280, content fluid, page padding 24–32, capped around 1440–1600.
- Top bar 56–64 tall. Navigation rows 32–36 with 2–4 between; section label 24 above and 8 below.
- A row of compact stat cards shares one height; numbers only.
- The main chart spans at least two thirds of the content and is 280–360 tall. A second data block is a narrower list or table, not another chart.

## Depth

- Dark: surface steps plus hairlines. An active row may carry `inset 0 1px 0 rgba(255,255,255,.12)`.
- Light: `0 1px 2px rgba(0,0,0,.05)` for small things, `0 8px 24px rgba(0,0,0,.06)` for floating ones.
- Keep the shadow neutral; colored shadows read as slop unless the direction says otherwise.

## Motion

One curve: `cubic-bezier(0.22, 1, 0.36, 1)`.

| Use                              | Duration                   |
| -------------------------------- | -------------------------- |
| Hover, press, toggles            | 120–180ms                  |
| Menus, popovers, tooltips        | 160–220ms                  |
| Entrances, sheets, layout change | 300–500ms                  |
| Stagger between items            | 40–60ms, at most six items |

Rise 6–12px on enter, press scale 0.97–0.98. Transition color, background, border, opacity and transform, named per property.
