# Long-Running Agent Stop Conditions

Loaded from `health` Step 1c when the project uses `/loop`, autonomous agents, or any long-running agent flow. Skip entirely for projects without one.

The project must define explicit stop conditions. An agent that never stops is a budget and safety incident waiting to happen.

Audit for these four hard stop signals; flag the absence of each as a Structural finding:

1. **No progress across two consecutive checkpoints.** Same files touched, same errors logged, no new commits/tests/output. Recommend killing the loop and surfacing the state, not retrying.
2. **Repeated identical failure.** Same stack trace, same error message, same failed assertion three times in a row means the hypothesis is wrong; more attempts will not help.
3. **Cost or token budget exceeded.** Project should declare a per-run budget (tokens, API spend, wall-clock minutes). Loop exits when the budget is hit, not when work is done.
4. **External blockers.** Merge conflict on the target branch, dependency lock the agent cannot resolve, missing credential, network unreachable. Any of these halt the loop and ask the user, not retry forever.

The stop conditions should live in tracked project docs (`AGENTS.md`, the loop's launch script, or a dedicated config), not only in the agent's prompt. Prompts are forgettable; tracked config is enforceable. Recommend hooks (PostToolUse on the relevant tools) over prompt instructions when the project supports them: a hook physically cannot be skipped, a prompt instruction can. Confirm the host's hook coverage before recommending one: some agents only fire PostToolUse for a subset of tools (for example, a runtime may match shell/Bash only), so a fixup that must run after file edits belongs on a Stop or session-end hook there instead.
