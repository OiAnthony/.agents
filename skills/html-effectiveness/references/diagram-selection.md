# Diagram Selection

Select a diagram from the claim the reader must understand.

| Claim | Type |
|---|---|
| Components, services, boundaries, ownership | `architecture` |
| Whole platform, control plane, governance | `architecture-board` |
| Ordered process, branch, approval, swimlane | `workflow` |
| Calls between participants over time | `sequence` |
| Data stages, transformations, lineage | `dataflow` |
| State transitions, retry, recovery, outcome | `lifecycle` |
| Two-axis position or priority | `quadrant` |
| Events or milestones over time | `timeline` |
| Parent-child hierarchy | `tree` |
| Vertical technical layers | `layer-stack` |
| Set intersection | `venn` |
| Category comparison | `bar` |
| Trend over time | `line` |
| Share of a whole, at most six parts | `donut` |
| OHLC market data | `candlestick` |
| Additive and subtractive bridge | `waterfall` |
| Software type relationships | `class` |
| Data entities and cardinality | `er` |

## Do not draw

- Two-item comparison: use a table.
- One object: use prose.
- Long argument: use prose with one supporting figure.
- Seven or more shares: use a horizontal bar chart, not a donut.
- Absolute counts with large changes over time: use bars unless rate or continuity is the claim.

## Scale

Use `meta.density`:

- `editorial`: up to 9 primary items.
- `teaching`: up to 12 primary items.
- `board`: up to 25 major blocks.

If the requested content exceeds the budget, merge domains or make two figures. Do not reduce the font size.
