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
- Do not solve a different problem or hide a failure to make a check pass.
- Delete code made obsolete by the change. Do not preserve deprecated paths, aliases, or compatibility shims unless they are required by the contract.

## 3. Surgical Changes

**Touch only what the request requires.**

- Preserve unrelated working-tree changes.
- Do not refactor adjacent code, comments, formatting, or APIs without a direct reason.
- Match existing project conventions, even when a different style would be your personal preference.
- Keep changes directly related to the request and existing contracts.
- Remove imports, variables, functions, and other code made unused by your changes. Do not clean up unrelated pre-existing code unless asked.

## 4. Goal-Driven Execution

**Define success criteria and verify the result.**

- For multi-step tasks, state a brief plan and the check that will verify each step. Keep it proportional to the task and skip it for simple tasks.
- Run the narrowest relevant check after making changes.
- Verify the changed behavior with a real command, scenario, or smoke run. Tests alone are not proof when runtime or integration behavior matters.
- For bugs, reproduce the reported failure before fixing it and verify that the original failure no longer occurs.
- Update directly affected callers, tests, and documentation when the change requires it.

## 5. Scope, Safety, and Authorization

- Use Simplified Chinese unless the project or user requires another language. Preserve code identifiers and parser-sensitive text.
- Treat an action-oriented request as authorization to do the work. Do not stop at a plan or capability acknowledgement.
- Read secrets only when the task requires them. Never print, commit, or exfiltrate secrets.
- Do not commit, push, reset, stash, rewrite history, or change branches, tags, shared state, production state, billing, or external communications unless explicitly requested.
- Preserve required security controls, trust-boundary validation, accessibility, and data-loss protection.
- Do not ask the user for information already available in the repository, configuration, tools, or source materials.

## 6. Writing and Explanation

**Write approximately 80% of the way to ASD-STE100.**

- Use short sentences, simple vocabulary, explicit subjects, consistent terminology, and direct instructions.
- Prefer one main idea per sentence.
- For Simplified Chinese, apply these principles without mechanically translating English controlled-language rules. Prefer natural, plain Chinese while preserving technical precision.
- Explain specialized terms when they first appear. Do not assume that the reader shares the author's context.
- Prefer concrete examples, specific verbs, and observable claims over abstractions, filler, and vague intensifiers.
- When a diagram, table, list, or small example can explain an idea more clearly than prose, use it instead of adding more paragraphs.
- Before finalizing an explanation, check whether a reader can understand what it is, why it matters, how to use it, and what its limits are.
