---
name: html-effectiveness
description: "Create polished, self-contained HTML artifacts and validated inline-SVG diagrams. Use whenever the user asks for an HTML artifact, visual report, comparison, dashboard, code review, presentation, interactive editor, architecture diagram, workflow, sequence, data flow, lifecycle, roadmap, chart, or spatial explanation. Prefer this skill when Markdown cannot express the structure, interaction, or visual hierarchy clearly. Outputs work offline with no CDN or build step."
---

# HTML Effectiveness

Create one offline-ready HTML file. Inline all CSS, JavaScript, and SVG. The reader must not need a package manager, network connection, or browser extension.

This skill has two connected parts:

1. **Artifact composer** for reports, comparisons, reviews, decks, research, prototypes, editors, design systems, and changelogs.
2. **Diagram compiler** for typed, validated diagrams that render to static inline SVG and gain optional browser interactions.

## Core contract

- Match the user's language. Set the correct BCP 47 `lang` value.
- Put the answer or main claim before supporting detail.
- Keep the document readable when JavaScript is disabled.
- Use interaction only when it makes understanding faster.
- Never leave an external script, stylesheet, font, frame, or image dependency in the final HTML.
- Never claim visual success without opening the artifact at the required viewports.

## Start with the CLI

Use the bundled Node CLI. Resolve all paths relative to this skill directory.

```bash
node bin/html-effectiveness.mjs doctor
node bin/html-effectiveness.mjs list
```

Create an artifact scaffold:

```bash
node bin/html-effectiveness.mjs init <artifact-type> "<title>" <output.html> [lang]
```

Artifact types:

- `exploration`
- `code-review`
- `design`
- `prototype`
- `research`
- `report`
- `deck`
- `illustration`
- `editor`
- `changelog`

The scaffold is a starting structure. Replace its sample copy with the user's real content. Do not add a second CSS system.

## Decide whether to draw

Draw only when the figure communicates hierarchy, direction, state, position, or magnitude better than prose.

- Compare two things: use a table.
- Show one labeled object: write a sentence.
- Show a relationship, transition, distribution, or trend: use a diagram.

Read `references/diagram-selection.md` before selecting a diagram type.

For ambiguous requests:

```bash
node bin/html-effectiveness.mjs guide "<scenario>"
```

## Diagram types

### Technical relationships

- `architecture`: components, boundaries, infrastructure, security domains
- `architecture-board`: a whole-system panorama with 10–25 major blocks
- `workflow`: flowcharts, swimlanes, approvals, CI/CD, runbooks
- `sequence`: participants, messages, returns, request lifecycles
- `dataflow`: stages, producers, transformations, governance, consumers
- `lifecycle`: states, waiting, decisions, retries, recovery, terminal outcomes

### Spatial relationships

- `quadrant`
- `timeline`
- `tree`
- `layer-stack`
- `venn`

### Data charts

- `bar`
- `line`
- `donut`
- `candlestick`
- `waterfall`

### Software models

- `class`
- `er`

Flowcharts and swimlanes are modes of `workflow`. State machines are `lifecycle`. Do not create parallel diagram types for the same semantic model.

## Diagram authoring workflow

1. Read `schemas/diagram.schema.json` and `references/diagram-authoring.md`.
2. Write a small JSON specification. The specification is the source of truth.
3. Validate it:

   ```bash
   node bin/html-effectiveness.mjs validate diagram.json
   ```

4. Fix the reported subject. Do not hide a structural problem with manual coordinates.
5. Deliver the final HTML:

   ```bash
   node bin/html-effectiveness.mjs deliver diagram.json diagram.html
   ```

6. Do not edit the delivered HTML after a passing delivery. Change the JSON and deliver again.

The final receipt reports semantic, budget, geometry, self-contained, and accessibility checks plus SHA-256 values for the input and artifact.

## Complexity budgets

- Editorial figure: at most 9 primary items.
- Teaching figure: at most 12 primary items.
- Architecture board: at most 25 major blocks.
- Use one or two focal items.
- A node contains a title and at most two short supporting lines.
- Split a figure instead of shrinking type or packing more cards.

Chart limits:

- Bar: 8 categories and 3 series.
- Line: 12 points and 3 lines.
- Donut: 6 segments. Use a bar chart for 7 or more.
- Candlestick: 30 periods.
- Waterfall: 8 steps.

## Mermaid input

Mermaid is an input format, not a browser dependency.

```bash
node bin/html-effectiveness.mjs convert-mermaid input.mmd output.json
node bin/html-effectiveness.mjs deliver output.json output.html
```

Supported inputs:

- flowchart or graph → workflow
- sequenceDiagram → sequence
- stateDiagram-v2 → lifecycle
- classDiagram → class
- erDiagram → er
- xychart-beta → bar or line

Read `references/mermaid-input.md` when the user provides Mermaid. Never ship Mermaid source that needs a CDN to render.

## Visual system

Use the bundled parchment system in `assets/artifact.css`.

- Page: warm parchment `#f5f4ed`.
- Main text: near-black `#141413`.
- Structure accent: ink blue `#1B365D`.
- Other structural elements: warm gray.
- Use semantic green, amber, and red only for real status, diff, or warning meaning.
- Use one or two structural focal elements.
- Do not use gradients, glow, glass effects, hard shadows, 3D, or rainbow node categories.
- Keep body text at 16px or larger.
- Use serif-led typography and monospace only for code and metadata.

Read `references/design.md` for page and diagram tokens.

## Interaction contract

Static content comes first. Optional diagram interaction is already included in delivered diagrams:

- search
- node focus and details
- zoom and reset
- relationship trace
- SVG export
- PNG export

Do not put essential facts only in hover text, a modal, or a hidden panel. Respect `prefers-reduced-motion`.

For custom editors:

- Store state in a JavaScript object or array.
- Render from that state.
- Export the state, not the DOM.
- Include a clear JSON, Markdown, CSV, or prompt export action.

Read `references/interaction-recipes.md` and `references/js-patterns.md` only for interactive artifacts.

## Build the artifact

- Use semantic HTML: `main`, `header`, `section`, `article`, `aside`, `figure`, `figcaption`, `table`, and real buttons.
- Keep normal reading content in continuous vertical flow.
- Use tabs only for true state changes, such as files or versions.
- Use `<details>` only for optional supporting information.
- Use data tables for tabular information.
- Make all controls keyboard accessible.
- Keep the narrow layout usable at 375px.

Read `references/categories.md` for category-specific information order.

## Validate and inspect

Validate every completed artifact:

```bash
node bin/html-effectiveness.mjs validate output.html
```

Then open the actual file in a browser and inspect:

- 1280px wide
- 375px wide
- every shipped locale
- keyboard focus for interactive controls
- JavaScript-disabled readability when the artifact contains a diagram

For diagrams, also inspect:

- no overlapping nodes
- no route through unrelated nodes
- no label on top of a route
- no clipped text
- clear main reading path
- focal color matches the caption's claim
- PNG and SVG exports match the browser view

Read `references/delivery-contract.md` for the full acceptance gate.

## Definition of done

Return:

1. The final HTML path.
2. The diagram specification path when a diagram exists.
3. The validation result and delivery receipt.
4. The 1280px and 375px visual verdict.
5. Any remaining factual gap.

Do not say “done” when the build passed but the rendered surface was not inspected.

<!-- nmem:skill-outcome-footer v1 -->
## Improving this skill

When you apply this skill, print:

```text
nmem-skill-used: html-effectiveness
```

If a step fails or needs a deviation, record the outcome with `skill_id="skill_c16846323e77"`, `skill_version=3`, and a short factual note.
