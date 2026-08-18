# Diagram Authoring

The JSON specification is the source of truth. The delivered SVG is compiled output.

## Common envelope

Every specification contains:

```json
{
  "schema_version": 1,
  "diagram_type": "architecture",
  "meta": {
    "title": "Request path",
    "subtitle": "The gateway owns authentication",
    "caption": "Authentication occurs before business routing.",
    "description": "Accessible description of the complete figure.",
    "density": "editorial",
    "animation": "none"
  }
}
```

Use stable, short IDs. Use domain labels, not generic labels such as Service 1.

## Relationship types

### Architecture

Use `components`, `connections`, and optional `boundaries`.

A component needs `id`, `label`, and optional `sublabel`, `detail`, `row`, `col`, `focal`, or `maturity`.

A connection needs `from`, `to`, and optional `label`, `role`, or `variant`.

### Workflow

Use `lanes`, `nodes`, and `edges`.

Each node has `lane` and `col`. Use edge roles `main`, `branch`, `async`, `return`, or `error`.

### Sequence

Use `participants` and `messages`. A message has `from`, `to`, `label`, and optional `variant: return`.

### Dataflow

Use `stages`, `nodes`, and `flows`. Each node has a numeric `stage` and `row`.

### Lifecycle

Use `lanes`, `states`, and `transitions`. State types are `start`, `active`, `waiting`, `decision`, `success`, `failure`, `neutral`, and `external`.

## Editorial types

- Architecture board: `sections` and `blocks`; each block names a section.
- Quadrant: `axes` and normalized `points` with x/y from 0 to 1.
- Timeline: `events` with `label`, `date`, and optional detail.
- Tree: `nodes`; child nodes name `parent`.
- Layer stack: ordered `layers`.
- Venn: up to three `sets`.

## Charts

- Bar and line: `categories` plus `series`, where each series has `name` and `values`.
- Donut: `values` containing `{label, value}`.
- Candlestick: `values` containing `{label, open, high, low, close}`.
- Waterfall: `values` containing `{label, value}` and optional `total`.

## Software models

- Class: `classes` and `relationships`; a class can have `attributes`.
- ER: `entities` and `relationships`; an entity can have `fields`.

## Visual discipline

- Mark one or two nodes with `focal: true`.
- Use `maturity: future` for uncommitted future nodes.
- Keep labels short.
- Put explanation in `detail`, not in the node title.
- Remove an edge when its meaning is already obvious from the layout.
- Change structure before adding coordinates.
