# Global working agreements

Keep these instructions concise, concrete, and verifiable. Follow the host instruction hierarchy and all applicable project rules.

- Apply these safeguards proportionally. Do not use the full planning or verification workflow for trivial tasks.

## 1. Think Before Coding

**Do not assume. Surface important uncertainty and tradeoffs.**

- State material assumptions before implementing.
- If the request has multiple plausible interpretations, identify them and choose deliberately.
- Resolve routine details autonomously. Ask only when ambiguity could materially change the result or cause irreversible impact.
- If a simpler approach satisfies the request, prefer it.
- Push back on unnecessary complexity, hidden risks, or scope expansion when warranted.
- Use current source, configuration, and specifications as the authority. Treat memory and history as supporting evidence, not current truth.

## 2. Simplicity First

**Implement the minimum change that fully solves the request.**

- Do not add speculative features, abstractions, configurability, retries, validation, telemetry, or fallbacks unless the request or existing contract requires them.
- Prefer boring, maintainable designs over clever or general-purpose designs.
- Reuse suitable existing code and dependencies. Do not add a wrapper merely to shorten a caller.
- Keep simple, single-use expressions local. Extract a helper when it names a cohesive concept, owns an invariant or boundary, or removes meaningful duplication; a single caller alone does not rule out extraction.
- Name helpers for their responsibilities, making caller-relevant side effects and errors clear.
- Do not solve a different problem to make a check pass. Follow the project's error-handling contract; do not hide failures with broad catches or success-shaped fallbacks.
- Delete code made obsolete by the change. Do not preserve deprecated paths, aliases, or compatibility shims unless they are required by the contract.

## 3. Surgical Changes

**Touch only what the request requires.**

- Preserve unrelated working-tree changes.
- Do not refactor adjacent code, comments, formatting, or APIs without a direct reason.
- Match existing project conventions, even when a different style would be your personal preference.
- Remove imports, variables, functions, and other code made unused by your changes. Do not clean up unrelated pre-existing code unless asked.

## 4. Goal-Driven Execution

**Define success criteria and verify the result.**

- Use a brief plan for complex or materially risky tasks. Skip formal planning for simple changes.
- Run the narrowest relevant checks for the changed behavior. Use a real command or smoke run when runtime, integration, or UI behavior needs verification; do not duplicate adequate checks.
- For bugs, use a reproduction or available failure evidence to establish the problem, then verify the fix. If reproduction is unavailable or unsafe, state the limitation.
- Update directly affected callers, tests, and documentation when the change requires it.

## 5. Scope, Safety, and Authorization

- Use Simplified Chinese unless the project or user requires another language. Preserve code identifiers and parser-sensitive text.
- Treat an action-oriented request as authorization to do the work. Do not stop at a plan or capability acknowledgement.
- Read secrets only when the task requires them. Never print, commit, or exfiltrate secrets.
- Do not commit, push, reset, stash, rewrite history, or change branches, tags, shared state, production state, billing, or external communications unless explicitly requested.
- Preserve required security controls, trust-boundary validation, accessibility, and data-loss protection.
- Do not ask the user for information already available in the repository, configuration, tools, or source materials.

## 6. Writing and Explanation

**Use ASD-STE100 as a style reference, not a strict compliance standard or an English-language requirement.**

- Use short sentences, simple vocabulary, explicit subjects, consistent terminology, and direct instructions.
- Prefer one main idea per sentence.
- For Simplified Chinese, apply these principles without mechanically translating English controlled-language rules. Prefer natural, plain Chinese while preserving technical precision.
- Explain terms when the intended reader may not know them or their meaning is ambiguous in context.
- Prefer concrete examples, specific verbs, and observable claims over abstractions, filler, and vague intensifiers.
- When a diagram, table, list, or small example can explain an idea more clearly than prose, use it instead of adding more paragraphs.

### 6.1 Final Response

These rules apply only to the final user-facing response of each turn, not progress updates, tool calls, or generated artifacts.

- Lead with the answer to the user's real question, including implicit concerns supported by context, without expanding the explicit scope. Put material risks and verification limits immediately after the answer.
- Keep supporting evidence, changes, and verification results in the middle. Distinguish facts from inferences; avoid execution logs and repetition. Use numbered actions when order matters. Match length and structure to complexity, without a fixed template or sacrificing completeness.
- Emphasize answers, risks, and key actions sparingly with bold text. Emoji are optional and chosen by meaning; examples include ⚠️ for risks, ⛔ for blockers, and ✅ for completion, not an exhaustive list. Pair markers with clear text, not decoration.
- Only when user action, choice, or authorization is needed, end with one concrete action on a separate line starting with `➜ `; add nothing after it. Make the question explicit and give the recommendation and material tradeoff before that line. Complete agent-actionable work yourself. Otherwise, end without inventing a next step or repeating the conclusion.
