# Artifact Categories

Select the category from the reader's job.

| Type | Reader job | Required structure |
|---|---|---|
| `exploration` | Compare options and decide | question, constraints, equal-weight options, recommendation |
| `code-review` | Find defects and act | verdict, severity counts, evidence by file, fixes |
| `design` | Inspect a visual system | tokens, type, spacing, components, states |
| `prototype` | Experience one behavior | stage, controls, current values, reusable result |
| `research` | Understand evidence | answer, findings, sources, comparison, limits |
| `report` | Know status and next action | status, metrics, changes, risks, action |
| `deck` | Follow a live argument | one assertion per slide, evidence, conclusion |
| `illustration` | Understand a spatial relationship | claim, diagram, caption, optional details |
| `editor` | Change data and return it | state summary, controls, editing surface, export |
| `changelog` | Understand release impact | version, breaking changes, features, fixes, migration |

## Information order

Put the answer first. Then show evidence. End with the action, limit, or decision.

Do not hide normal reading sections in tabs. Use tabs only for a true state change, such as changed files or versions.

## Category constraints

### Exploration

Give each option equal visual weight. Use the recommendation after the comparison.

### Code review

Lead with P0 and P1 findings. Each finding names the file, location, evidence, impact, and fix.

### Prototype

Let the reader experience the behavior before showing implementation detail. Keep control changes reversible.

### Research

State source dates for facts that can change. Use `<details>` only for supporting evidence.

### Deck

Use one claim per slide. Keep slide body text at 28px or larger in the final deck-specific styling.

### Illustration

Create a typed diagram specification. Compile it to static inline SVG. Do not hand-edit the delivered SVG.

### Editor

Define data first. Render from the data. Export the data, not the DOM.

### Changelog

Place breaking changes first. Write each change as one user-visible result.
