# Mermaid Input

Mermaid is an authoring input. It is not a final browser dependency.

Convert and deliver:

```bash
node bin/html-effectiveness.mjs convert-mermaid input.mmd diagram.json
node bin/html-effectiveness.mjs validate diagram.json
node bin/html-effectiveness.mjs deliver diagram.json output.html
```

Supported forms:

| Mermaid | Native type |
|---|---|
| `graph` or `flowchart` | `workflow` |
| `sequenceDiagram` | `sequence` |
| `stateDiagram-v2` | `lifecycle` |
| `classDiagram` | `class` |
| `erDiagram` | `er` |
| `xychart-beta` | `bar` or `line` |

The adapter preserves nodes and relationships. It does not preserve Mermaid styling.

After conversion:

- Replace generated titles.
- Check node order and lanes.
- Add a clear caption and accessible description.
- Mark no more than two focal items.
- Validate before delivery.

Do not include `esm.sh`, Mermaid runtime scripts, or remote modules in the final HTML.
