# AI Maintainability Structural Findings

Loaded from `health` Step 3 for the AI-maintainability lane. Summary mode reads `AI MAINTAINABILITY SUMMARY`; deep audits, Complex projects, and explicit code-rot requests read `DETAIL`. The agent-config lane (instruction drift) stays in `SKILL.md`. The `$HEALTH_SCRIPT` and `$HEALTH_LAUNCHER` variables below are the ones Step 1 already resolved.

**AI-maintainability gaps.** Use `AI MAINTAINABILITY SUMMARY` in summary mode and `AI MAINTAINABILITY DETAIL` in deep mode. Report `FAIL` when the project has no executable verification command, no agent instruction surface for a non-trivial repo, or broken doc references. Report `WARN` when instructions exist but lack a project map, verification guidance, boundary/non-goal language, when TODO/HACK markers are concentrated, when large source hotspots lack ownership/boundary and verification guidance, when durable docs contain raw one-off review reports, scorecards, dated line references, or diagnostic dumps instead of stable invariants, or when a runtime supports path-scoped instruction loading (Claude Code `.claude/rules/*.md` with `paths` frontmatter, nested-directory `CLAUDE.md`) but a large always-loaded instruction file carries domain- or language-specific rules that only apply under certain paths, so every unrelated session pays their full context cost. The action for the last case is to add `paths` frontmatter (or move the block to a nested `CLAUDE.md` / a skill), not to delete the rule. Treat missing `docs/`, `specs/`, `.specify/`, `HANDOFF.md`, `CHANGELOG`, issue templates, and PR templates as informational unless project complexity makes them necessary for handoff. The action for stale reports is to extract stable rules into public instructions, rules, references, or verifier scripts, then remove or archive the transient report.

**Conversation-derived guidance.** When a health audit reads recent agent conversations, do not recommend copying the conversation or a scorecard into docs. Recommend a candidate-matrix pass instead:

| Field | Question |
|---|---|
| Independent recurrence | Were cloned prompts, retries, automated fan-out sessions, pasted assistant output, and platform-resume messages collapsed into one underlying event? |
| Repeated failure | Did this recur across fixes, releases, agents, or user reports? |
| Durable invariant | Can the lesson be stated as a stable rule, not a dated incident summary? |
| Target layer | Should it live in project instructions, a Waza skill, a global rule, or private memory? |
| Verifier | Is there a deterministic command, script, artifact check, or runtime smoke that can enforce it? |
| Redaction risk | Does the lesson require local paths, issue numbers, customer details, machine state, secrets, or unpublished release facts? |

Layering rule: project-specific commands, app names, artifact names, and release rituals stay in the project; reusable workflows such as cancelled-release review gates or native-freeze evidence ladders belong in Waza skills; universal honesty and verification rules belong in global CLAUDE/AGENTS; private user preferences and one-machine facts stay in memory. If the lesson cannot pass the redaction-risk field, keep it out of public guidance.

Scope by load surface, not just by layer. A rule kept in the project still pays context on every session unless it is bound to where it applies: language and framework rules carry file-type `paths` scope, project-domain rules bind to their source directories (`paths` frontmatter or a nested-directory `CLAUDE.md`), and only genuinely cross-cutting constraints load unconditionally in the always-loaded root. A rule that only matters under one path does not belong in an always-loaded file.

**Concentrated fix chains.** Run `git -c core.fsmonitor=false log --oneline --since='2 weeks ago' | grep -i fix` and group by area (the prefix before `:` or `(`). When the same area has 3+ fix commits in a short window, it signals a missing structural invariant: each fix is a guess at a rule that was never written down. Report a Structural `WARN` with the area name, fix count, and recommend adding an explicit rule to `AGENTS.md` / `CLAUDE.md` / project rules that captures the invariant those fixes were converging toward. A concentrated fix chain that touches the same file 4+ times is a stronger signal than scattered fixes across different files.

**Hotspot ownership gaps.** In deep mode, read `HOTSPOT OWNERSHIP SURFACE`. If a largest source file exceeds the hotspot threshold and `AGENTS.md` / `CLAUDE.md` / shared instruction files do not name who owns the hotspot, what boundary should stay stable, and which verification command covers it, report a Structural `WARN`. Do not treat documented large files as code rot by size alone; some modules are intentionally large.

**Missing stable verifier wrapper.** If the repo exposes multiple verification commands through CI, scripts, or manifests but `Makefile` has no `check`, `test`, or `verify` target, report a Structural `WARN`. This is an AI-maintainability gap because agents need one stable default entrypoint, not because the project is broken.

Quick check from the project root, reusing `$HEALTH_SCRIPT` resolved in Step 1:

```powershell
& "$POWERSHELL" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "$HEALTH_LAUNCHER" maintainability . summary
```

On Linux and macOS:

```bash
BASH_ENV= ENV= /bin/bash -p "${HEALTH_SCRIPT%/*}/check-maintainability.sh" . summary
```

For deep audits:

```powershell
& "$POWERSHELL" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "$HEALTH_LAUNCHER" maintainability . deep
```

On Linux and macOS:

```bash
BASH_ENV= ENV= /bin/bash -p "${HEALTH_SCRIPT%/*}/check-maintainability.sh" . deep
```

Keep actions concrete and non-invasive: add or fix the smallest useful instruction surface, add one executable validation command, document hotspot ownership and tests, split only when the boundary is already clear, or repair the broken reference. Do not propose broad rewrites from the script output alone.

**Broken doc references.** Scan `AGENTS.md`, `CLAUDE.md`, `.claude/rules/*.md`, and every `.claude/skills/*/SKILL.md` for references shaped like `@<path>`, `~/.claude/rules/<name>.md`, `~/.claude/skills/<name>/`, `docs/<name>.md`, or `references/<name>.md`. For each match, check that the target exists on disk. Report every "referenced but missing" pointer with the source file and line.

Common offenders:
- A project-level rule references a global rule file that was never created (e.g. `~/.claude/rules/swift.md`).
- A `CLAUDE.md` uses an `@AGENTS.md` placeholder but the actual `AGENTS.md` is missing or empty.
- A skill body references `references/<name>.md` but only `references/<name>-v2.md` exists.
- A rule file references a deleted skill path.

Quick check from the project root, reusing `$HEALTH_SCRIPT` resolved in Step 1:

```powershell
& "$POWERSHELL" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "$HEALTH_LAUNCHER" doc-refs .
```

On Linux and macOS:

```bash
BASH_ENV= ENV= /bin/bash -p "${HEALTH_SCRIPT%/*}/check-doc-refs.sh" .
```

The checker resolves `@...` and `docs/...` from the project root, expands `~`, resolves `references/...` from each `.claude/skills/<name>/SKILL.md` directory, checks every reference on a line, skips fenced code examples, and exits non-zero when any target is missing.

Report missing references as Structural findings, not Critical, unless the missing file is named as a hard dependency (e.g. `release.md` for the project's release skill).

**Broken Markdown references.** In deep mode, `check-maintainability.sh` also scans repository Markdown links. Report these as Structural findings when they point to missing local files, especially design, security, release, or handoff docs that agents may follow during future work.

**Stale verifier cache output.** If validation output points at a deleted temp worktree or non-existent `/tmp` / `/private/tmp` file, parse the captured log with:

```powershell
& "$POWERSHELL" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "$HEALTH_LAUNCHER" verifier-output . <log-file>
```

On Linux and macOS:

```bash
BASH_ENV= ENV= /bin/bash -p "${HEALTH_SCRIPT%/*}/check-verifier-output.sh" . <log-file>
```

Only use this script for existing command output supplied by the user or generated during the current audit. Do not run project tests just to feed this checker. Known actions include `golangci-lint cache clean`, `go clean -cache -testcache`, and `npm cache verify`; unknown tools get a diagnostic rerun action.
