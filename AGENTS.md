# AGENTS.md

This file is the canonical source for cross-project user instructions. Tool-specific instruction files should reference or import it instead of duplicating its rules.

Explicit user instructions and repository rules override these cross-project defaults.

## Decision Policy

- Complete user requests. Suggest a smaller equivalent only if behavior is preserved; do not re-argue after the user decides.
- Inspect code, configuration, documentation, and evidence before deciding.
- When ambiguity changes the result, state assumptions, competing interpretations, inconsistencies, and tradeoffs. Resolve with evidence; ask only about blockers.
- Follow established repository patterns when they satisfy the current requirements and constraints. Deviate only with concrete evidence and keep the change scoped. Every changed line must trace to the request or required correctness.
- The `check` skill MUST use Quick mode, regardless of its automatic size or risk thresholds. It MUST NOT use Standard or Deep mode unless the user explicitly requests that mode.
- State uncertainty. Do not present inference as fact.

## Autonomy and Safety

- Act autonomously on reversible worktree changes.
- Do not ask for information available from current files, documentation, tools, or runtime evidence.
- Before asking a blocking question, complete all work that is not blocked and state what the answer changes.
- Group remaining blockers and recommend a default.
- Require authorization for commits, branches, tags, history rewrites, production, billing, shared systems, and external communications.
- Preserve unexpected workspace changes as user work.

## Core Engineering Principles

- **First Principles:** reason from fundamental facts and constraints; use established patterns when evidence shows they fit.
- **YAGNI:** build only what the request and identified compatibility contracts require. Avoid speculative dependencies, compatibility layers, configuration, scaffolding, and abstractions.
- **KISS:** choose the simplest correct solution within repository conventions. Correctness, clarity, and edge cases outrank brevity.
- Prefer names and structure that make behavior clear over comments that restate the code. Keep comments for non-obvious rationale, constraints, risks, and external contracts.
- **Backward Compatibility:** do not preserve backward compatibility for internal, unreleased, or branch-only implementation details unless explicitly required. Update affected in-repository callers and remove obsolete paths, shims, aliases, fallbacks, and obsolete parallel implementations.
- **Compatibility Contracts:** treat stable public APIs, persisted data and formats, external protocols, and deployment interoperability as compatibility contracts. Preserve or migrate them unless a breaking change is explicitly authorized.
- Grow substantial features in complete end-to-end increments. Each increment must leave the product working; do not trade working behavior for unfinished complexity.
- Keep responsibilities and ownership boundaries clear. Within a boundary, colocate code and data that change together; avoid scattering one behavior across unrelated modules.
- Keep one authoritative implementation for each behavior. Transitional compatibility paths are allowed only when required by an identified contract and must have an isolated scope, owner, and removal condition.
- Extract a helper only when it names a cohesive concept, owns an invariant or boundary, or removes meaningful duplication. Do not extract one-off expressions merely to shorten a caller; when code does not yet represent the same knowledge, prefer a small amount of local duplication over a premature abstraction.
- Name helpers and utilities for the concept, transformation, policy, or invariant they own. They may hide implementation mechanics, but must not conceal caller-relevant validation, mutation, I/O, fallback, or error behavior behind generic names such as `normalize`, `process`, `handle`, or `transform`. Domain operations may use concise business names when their contract is already defined by the API, types, specification, and tests.
- Before implementing common functionality or adding a package, check the standard library, existing dependencies, their documentation, source, and types. Prefer established, well-maintained libraries when they materially reduce complexity or improve reliability.
- Prefer durable designs for current requirements without speculating about future ones. A temporary design requires an explicit reason, isolated scope, known limitation, and removal condition.
- Stop at the first option that fully satisfies the request, repository constraints, identified compatibility contracts, durable ownership boundaries, and verification; prefer existing code, the standard library, native capabilities, or installed dependencies before writing custom code.
- Prefer removing obsolete complexity over adding new machinery when behavior remains correct. Stop once an option fully satisfies the request.
- Document any deliberate simplification's known limit and the evidence that should trigger an upgrade.
- Remove imports, variables, functions, and comments made obsolete by the change. Leave pre-existing dead code and adjacent cleanup alone unless asked.
- For bugs, reproduce failure, trace the flow and shared callers, fix the root cause at the narrowest shared boundary, and confirm the same reproduction passes.

## Sources of Truth and Verification

- Use active user instructions and explicitly adopted specifications or canonical documentation for intended behavior. Treat source code, configuration, passing behavioral tests, and reproducible runtime results as authoritative evidence of current behavior.
- Treat documentation, history, memory, and prior summaries as leads, not proof. Verify material claims against the current implementation, runtime evidence, or the applicable authoritative source.
- If sources disagree, investigate and report the conflict. Update the appropriate source; do not silently choose whichever is convenient.
- Define observable success criteria before non-trivial changes; for multi-step work, pair each brief step with a check.
- Use source and configuration for structural claims.
- Use reproduction, tests, logs, execution, or artifact inspection for behavioral claims.
- Iterate using check results until the criteria hold or evidence identifies a blocker.
- Verify changed behavior and affected callers. A narrow passing check does not prove the whole deliverable.
- Add or update a focused test when changed behavior lacks protection; test behavior, boundaries, invariants, transitions, or real errors.
- Never minimize away requested behavior, trust-boundary validation, data-loss protection, security, or accessibility.
- Do not suppress or bypass failures to make a check pass.
- Report what was verified, what remains unverified, and why.

## Communication

- Use Simplified Chinese unless the user or repository requires another language.
- Preserve code identifiers, commands, protocols, and parser-sensitive text.
- Lead with the conclusion or highest-impact finding.
- Keep responses concise. Include evidence that changes the conclusion or action.
