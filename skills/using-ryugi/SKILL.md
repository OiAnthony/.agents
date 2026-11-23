---
name: using-ryugi
description: Use when starting any conversation - routes each task to the Ryugi workflow for its stage
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, ignore this skill.
</SUBAGENT-STOP>

# Ryugi Workflows

Before you read project files or write code for a task, load the skill for its stage with the `Skill` tool and follow it:

- Building or changing behavior ("let's build X", plan mode): `ryugi:brainstorming`
- An approved spec to implement or resume: `ryugi:executing-specs`
- A bug, failing test or unexpected behavior: `ryugi:systematic-debugging`
- Writing implementation code: `ryugi:test-driven-development`, also when your human partner says to skip discussion
- Work built or a bug fixed, and a visible bug before you fix it: `ryugi:verifying`, before calling it done
- Something to show (mockups, a design doc, a share link): `ryugi:artifacts`

Plain questions and read-only checks need no skill. Your human partner's instructions override skills. A project's own skill for a step (its design system, checking the running app, shipping) does that step.

**A change of output format re-opens the contract.** When the deliverable changes (document → html, code → spec), re-read the skill's docs before writing; "already read once" does not carry over.

## Evidence Before Claims

Before saying anything is done, fixed, or passing — and before committing, pushing, or opening a PR — run the command that proves it in this session, read its full output, and state the result with that evidence. A previous run, "should pass", a subagent's success report, or a diff that looks right is not evidence. If the check fails, report the actual state.

## Your Final Message

Your human partner reads the end of your turn to decide what to do next. Write it for that:

1. **The state, first line:** done, not done, or waiting on whom.
2. **What needs them**, numbered so they can answer by number: verdicts, decisions, actions only they can take. This list is complete.
3. **What could change their decision:** a claim not verified, a risk to landing or shipping. Nothing else.

Everything else is a link, not prose: test tables, commit lists, review findings, the steps you took, notes about your tools or other agents. Put it in the verify report or the file that already holds it.

Write in the language your human partner writes to you, after compaction too; ids, commands and output stay as they are. When they speak mid-run, answer what they said, add at most one line on where the run is, and carry on.

## Platform Adaptation

Read your harness's file first: Codex `references/codex-tools.md`, Pi `references/pi-tools.md`, Antigravity `references/antigravity-tools.md`, Hermes Agent `references/hermes-tools.md`, Muse `references/muse-tools.md`.
