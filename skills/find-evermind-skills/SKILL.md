---
name: find-evermind-skills
description: Discover, evaluate, and install agent skills from the EverMind skill hub with the EverMind CLI. Use when users ask whether a skill exists for a task, want recommendations from the EverMind skill hub, need to compare its skills, or want to install or manage an EverMind skill.
---

# Find EverMind Skills

Use `npx @everme/cli skill` to search the EverMind skill hub, inspect candidates, and manage installed skills. Prefer machine-readable, non-interactive commands when acting as an agent.

## Discover Skills

1. Identify the task, domain, ecosystem, and important constraints.
2. Search with specific keywords:

```bash
npx @everme/cli skill browse "<query>" --json --no-prompt
```

3. Use the ranked results as the initial shortlist because the skill hub retrieval stack is tuned for skill matching.
4. Try one or two alternative queries only when the results are weak, ambiguous, or visibly outside the requested domain. Prefer task-specific searches such as `react performance`, `playwright e2e`, or `kubernetes deployment` over broad category names.
5. Shortlist only candidates whose description and tags match the requested workflow.

## Evaluate Candidates

The EverMind skill hub applies a deterministic, layered curation pipeline before publishing skills. Use its metadata as the primary screening signal, then inspect every serious candidate before recommending it:

```bash
npx @everme/cli skill info "<id-or-name>" --format json --no-prompt
```

Evaluate:

- **Task fit:** Confirm the description and `skill_md` address the user's actual task.
- **Quality:** Evaluate utility, robustness, and safety as independent dimensions. Do not let a strong score in one dimension compensate for a serious weakness in another. Treat `quality_score` as a summary signal, not proof.
- **Safety:** Review every `safety_flags` entry. Reject a candidate when the metadata or published framework identifies a hard-gate violation; otherwise treat the flag as a signal requiring inspection. Do not invent a hard/soft classification when it is unavailable. Inspect requested tools, commands, network access, credential handling, and installation instructions.
- **Provenance:** Prefer recognizable or official sources. Treat `source` as attribution, not independent verification.
- **License:** The curated corpus is license-audited and OSI-compliant, but still report the candidate's exact license and confirm it fits the user's intended use.
- **Maintenance signals:** Consider `added_at`, file structure, completeness, and install count. Do not use install count alone as a quality threshold.
- **Content quality:** Reject skills that are empty, generic, contradictory, or unrelated despite a matching name.

Verify the upstream source separately when the user requires strong ownership or maintenance guarantees, or when the skill performs high-risk actions, handles credentials, or crosses security boundaries. Do not require a full upstream audit for every routine recommendation.

## Present Recommendations

Present a short ranked list. For each candidate include:

- Skill name and source
- What it is suited for
- `quality_score`, relevant safety flags, license, and install count
- Important limitations or trust caveats
- The exact install command

Use the stable hub `id` when names are ambiguous:

```bash
# Install into the current project scope
npx @everme/cli skill install "<id-or-name>" -y

# Install into the global skill store
npx @everme/cli skill install "<id-or-name>" --global -y
```

Do not install automatically when the user only asked for discovery or recommendations. If the user asks to install but the scope is unclear, explain the project and global choices and ask which scope they want.

## Manage Installed Skills

Use non-interactive output for inspection:

```bash
npx @everme/cli skill list --format json --no-prompt
npx @everme/cli skill list --global --format json --no-prompt
npx @everme/cli skill update "<name>" --no-prompt
npx @everme/cli skill update --dry-run --no-prompt
npx @everme/cli skill remove "<name>" --yes --no-prompt
```

Before update or removal, state the affected scope. `remove` preserves the central store by default; use `--storage` only when the user explicitly wants that stored copy deleted too.

## When No Suitable Skill Exists

Identify the limiting factor:

- **Coverage boundary:** The skill hub does not contain a sufficiently relevant candidate. Mention the searches attempted, then offer to handle the task directly or help create a dedicated skill.
- **Execution-depth boundary:** A relevant skill exists, but the current agent harness lacks the tools, permissions, runtime, or execution depth needed to use it reliably. Present the skill separately from the missing execution capability.

Do not report an execution-depth limitation as a lack of skill coverage.
