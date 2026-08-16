# AI Maintainability Structural Findings

Loaded from `health` Step 3 for the AI-maintainability lane. Summary mode reads `AI MAINTAINABILITY SUMMARY`; deep audits and explicit code-rot requests read `DETAIL`. The agent-config lane (instruction drift) stays in `SKILL.md`. The `$HEALTH_SCRIPT` and `$HEALTH_LAUNCHER` variables below are the ones Step 1 already resolved.

**AI-maintainability gaps.** Use `AI MAINTAINABILITY SUMMARY` in summary mode and `AI MAINTAINABILITY DETAIL` in deep mode. Report `FAIL` when implementation, CI, generation, publishing, deployment, or another material risk makes substantive executable verification expected but `verifier_evidence` is empty, or when a required documentation reference is broken. `commands` is discovery inventory, not proof: targets or scripts listed under `hollow_verifiers` only print, perform shell setup, or exit and do not satisfy coverage. Report `WARN` for verified generated-mirror drift, referenced commands that do not exist, stable non-obvious constraints that relevant tasks cannot reach, recurring failures without a durable invariant and verifier, hollow wrappers that miss the real failure layer, durable rules available only in ignored/private overlays, or durable docs that preserve raw one-off reports, scorecards, dated line references, or diagnostic dumps instead of stable invariants. Also warn when a runtime supports path-scoped loading but unrelated sessions repeatedly pay for substantial domain-specific guidance that can be routed safely; move it to a path-scoped rule, nested instruction file, or skill without deleting its behavioral value. `context_status: UNKNOWN` means implementation or CI risk exists but tracked context evidence is absent; inspect the actual risk before deciding whether a routed invariant is needed. `NOT_APPLICABLE` means the collector observed no implementation/CI context need. Neither status justifies a fabricated clean bill or a map requirement. File counts, contributor counts, skill counts, TODO counts, largest files, and missing maps/specs/templates are inventory only until connected to risk, failure evidence, or verifier coverage. The action for stale reports is to extract stable rules into public instructions, rules, references, or verifier scripts, then remove or archive the transient report.

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

**Concentrated fix chains.** Run `git -c core.fsmonitor=false log --oneline --since='2 weeks ago' | grep -i fix` and group by area (the prefix before `:` or `(`). Repetition is a lead, not a finding: read enough evidence to confirm that several fixes converge on the same invariant or failure layer rather than unrelated work sharing a prefix. Report a Structural `WARN` only after that validation, naming the recurring failure and recommending the narrowest routed rule plus executable verifier that would have prevented it.

**Non-obvious constraint reachability and risk-backed hotspot ownership.** File size and module shape do not create documentation requirements. When real failures or high-consequence paths concentrate in an area and expose a stable boundary that cannot be recovered cheaply from code, verify that the relevant task can reach a concise ownership rule and the executable check that locks it. Report the unreachable constraint or missing verifier, not an absent blanket "hotspot map".

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

Keep actions concrete and non-invasive: add or fix the smallest useful routed instruction surface, add one executable validation command at the real failure layer, repair a generated-mirror check, or repair the broken reference. Split only when the boundary is already clear. Do not propose broad rewrites from the script output alone.

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
