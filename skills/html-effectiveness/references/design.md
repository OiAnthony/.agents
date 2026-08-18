# Design System

The final artifact includes `assets/artifact.css` inline. Do not load Tailwind, web fonts, or another design system.

## Tokens

| Role | Value |
|---|---|
| Page | `#f5f4ed` parchment |
| Raised surface | `#faf9f5` ivory |
| Structural accent | `#1B365D` ink blue |
| Primary text | `#141413` near-black |
| Secondary text | `#504e49` olive |
| Tertiary text | `#6b6a64` stone |
| Border | `#e8e6dc` warm border |
| Success | `#4a7c59` |
| Danger | `#8b3a3a` |
| Warning | `#9b6728` |

Ink blue is the only structural accent. Use semantic colors only when the underlying data has success, danger, or warning meaning.

## Type

- Use the bundled serif system stack for prose and headings.
- Use the bundled monospace stack for code, identifiers, and metadata.
- Body text starts at 16px.
- Headings use weight 500.
- Labels can use weight 600.
- Do not use italic text or weight 700 and above.

## Space and shape

- Use a 4px spacing base.
- Keep content within 1120px.
- Use 12px panel radius, 8px row radius, and pill action buttons.
- Use dotted separators for document structure.
- Use only a low-contrast hover shadow. Diagrams use no shadows.

## Page components

The stylesheet provides:

- `.shell`
- `.grid`, `.grid-2`, `.grid-3`
- `.card`
- `.metrics`, `.metric`, `.metric-value`, `.metric-label`
- `.callout`
- `.tag`, `.badge`
- `.doc-footer`
- `.diagram-shell`, `.diagram-toolbar`, `.diagram-viewport`, `.diagram-detail`

Use semantic HTML around these classes. Do not reproduce the class list as nested generic `div` elements when `article`, `section`, `aside`, `figure`, or `table` is correct.

## Diagram rules

- Use one or two focal nodes.
- Keep standard nodes neutral.
- Use dashed reduced-opacity nodes for future work.
- Use solid lines for primary relations and dashed lines for asynchronous or future relations.
- Put edge labels on a parchment mask so the route does not run through the text.
- Use open chevron arrowheads.
- Put accessible title and description inside every SVG.
- Do not use gradients, filters, glow, glass effects, or 3D.
