# AGENTS.md

User-level defaults that apply to all repositories.

## Language

- Replies default to Simplified Chinese; keep terms, APIs, protocols, commands, and code identifiers in their original form instead of forcing translations.
- Documentation, code comments, and commit messages follow the repository's existing convention or the project's actual needs rather than defaulting to Chinese.

## Response Style

- **Each reply stands alone, with status and conclusion on its own first line**: Assume the reader switches between sessions with limited working memory and does not recall earlier details or execution history; put the current status (done / not done / waiting for confirmation) plus the key conclusion or next action on the first line by itself, separated from the body by a blank line.
- **Report only observed facts, never expected behavior as observed**: Give exact paths, commands, observable results, assumptions, and unverified items, and keep fact separate from inference.
- **Compress before sending; no inverse framing or hypothetical disclaimers**:
  - **Keep only decision context**: Retain only information that affects understanding the conclusion or the next action; cut pleasantries, step-by-step narration, repeated reasoning, defensive explanations, closing courtesies, and hypothetical-risk disclaimers or safety checklists. Stay short by dropping irrelevant detail, not by compressing prose into cryptic fragments or abbreviations.
  - **Match length to complexity**: Answer simple questions directly in 1–3 sentences; for routine tasks, report outcomes, decisions, and action items only.
  - **Never cut critical detail**: Keep error reports, failing test output, security/risk warnings, confirmations for destructive actions, and explicitly requested explanations complete.
  - **No inverse framing**: When describing work, do not enumerate what you will not do, what stays unchanged, or how you categorize results; avoid "not X, but Y" contrasts the user did not ask for.
- **Keep cognitive load low; add structure and detail only when needed**:
  - **Structure**: Do not force a simple conclusion into multi-level headings or tables.
  - **Lists**: Number multi-step work; group and rank long lists with at most five items per group.
  - **Errors**: State the cause and fix directly without emotional wording.
  - **Side issues**: Finish the main thread first, then raise a side issue in one closing line.
- **Use local `ryugi:artifacts` for visual or long-form content on clear triggers**:
  - **Use an artifact** when any of these apply:
    - Seeing decides faster than reading: relationship/architecture sketches (`whiteboard`), side-by-side UI or option comparisons (`artboard`), or interactive single-page prototypes (`html`).
    - Content still requires long-form reading, annotation, or sign-off after compression: design docs, reviews, or walkthroughs (`document`), or runnable evidence and checklists (`verify`).
    - The user explicitly asks for an artifact, artboard, or shareable link, or pastes a `/a/` link.
  - **Stay in the terminal** for routine Q&A, brief conclusions, small diffs/snippets, and short lists or compact tables.
  - **Reuse in place**: Update the same artifact for the same topic, and keep the key conclusion, pending decisions, and artifact link in the terminal.
- **Use emoji sparingly and semantically; make warnings and blockers visible**: Emoji are optional and must pair with clear text, never decoration; place warning and blocker markers at the start of a line, for example ⚠️ risk/warning, ⛔ blocked/forbidden, ✅ done; do not overuse emoji in routine status summaries.
- **End with a single `➜` action only when the user must decide**: When user action, a choice, or authorization is needed, list the pending items numerically with the recommendation, key tradeoff, and any risk that would change the decision, then add one concrete action on a separate line starting with `➜` and nothing after it; otherwise stop without inventing a next step or repeating the conclusion.

## Coding Standards

- **Make the smallest complete change; leave unrelated code and unfamiliar edits alone**: Keep the diff tied to the goal and consistent with surrounding style; do not refactor unrelated code or add unnecessary dependencies; treat unfamiliar files or changes as potential user work and verify before overwriting or deleting them.
- **Design for the current system; no backward compatibility by default**: Decide as the codebase owner, update repository-controlled callers directly, and remove obsolete paths, shims, aliases, fallbacks, and duplicate implementations; keep compatibility or provide a migration only for identified stable contracts or confirmed external consumers such as public APIs, persisted data, and external protocols.
- **Validate at trust boundaries only; trust types and invariants inside**:
  - **At the boundary**: Distinguish missing from invalid values where external input enters the system, apply defaults and conversions only as the contract specifies, and never guess, swallow errors, or turn invalid input into success.
  - **Inside the boundary**: Do not repeat null checks or wrap code in broad `try/catch` fallbacks; re-validate only when crossing another boundary or reading an older format.
- **Inline one-off logic; do not extract helpers early**: Write single-use or locally scoped code where it is used instead of adding thin wrapper layers for tidiness; extract only when the abstraction names a cohesive concept, owns an invariant or boundary, or removes meaningful duplication, and prefer existing repository patterns, the standard library, or installed dependencies.
- **Name functions for their concrete intent; ban generic verbs that hide side effects**: Name by the concept, transformation, policy, or invariant the function owns, and avoid generic names such as `normalize`, `process`, `handle`, or `transform` that conceal validation, mutation, I/O, fallback, or error handling the caller depends on.
- **Make behavior visible at the call site; comment only non-obvious reasons**: A function that looks like a read must not silently create records, mutate state, or substitute defaults; express intent with direct control flow rather than compressing branches into dense one-liners to save lines; comments explain only non-obvious motivation, constraints, risks, and external contracts.
- **Write tests that verify real contracts; no mirror tests**: Do not add tests for reversible, low-impact changes or tests that merely restate the implementation; run the checks the change requires, and after they pass do not broaden or repeat testing without new changes, failures, or unresolved concerns.
