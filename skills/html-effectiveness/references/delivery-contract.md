# Delivery Contract

A completed artifact passes four gates.

## 1. Structural gate

Run:

```bash
node bin/html-effectiveness.mjs validate artifact.html
```

The artifact must have:

- document language
- viewport metadata
- title
- no unfilled placeholders
- no external scripts, stylesheets, fonts, frames, media, or dynamic imports
- SVG `role="img"`, `<title>`, and `<desc>` when a diagram exists

## 2. Diagram gate

A diagram specification must pass:

```bash
node bin/html-effectiveness.mjs validate diagram.json
```

Fix every semantic, item-budget, dangling-reference, overlap, route-crossing, and short-segment error.

## 3. Visual gate

Open the real HTML at 1280px and 375px.

Check:

- no clipped or overlapping text
- no accidental horizontal page scroll
- diagram viewport remains usable on mobile
- main claim appears before supporting detail
- controls have visible keyboard focus
- selected and filtered states remain legible
- focal color matches the written claim

Disable JavaScript once. Static content and diagrams must remain readable.

## 4. Export gate

For delivered diagrams:

- Export SVG and open it.
- Export PNG and inspect it at 100%.
- Confirm the export has the same content, crop, background, and labels as the browser view.

## Receipt

`deliver` returns:

- specification and artifact SHA-256
- byte counts
- diagram type
- completed check groups
- warnings

Do not edit a delivered HTML after this receipt. Change the specification and deliver again.
