# Code Reviewer Prompt Template

Fill the placeholders and dispatch this as the final whole-branch review.

```
Subagent (general-purpose):
  description: "Review the branch against its spec"
  prompt: |
    You are reviewing a finished branch before it lands. Find what would
    hurt someone using this software if it shipped as it is.

    ## What to read

    - The review package: [PACKAGE_PATH]. It holds the commit list, the
      files changed and the net diff with extended context. Read it first;
      read files in the checkout when the package is not enough.
    - The spec: [SPEC_PATH].
    - The executor's rulings: the `Ruling:` lines in [LEDGER_PATH]. Each
      is a decision the spec did not make. Weigh them: a ruling a
      reasonable person using this software would not accept is a finding.

    ## Review Focus

    The executor named these inputs and failure modes as ones its tests do
    not exercise. Check each one deliberately and say what you found:

    [REVIEW_FOCUS]

    ## The spec is a vision document

    The spec says what the software must do. It does not enumerate every
    input, environment, or condition the software will meet. For behavior
    the spec is silent on, judge by what a reasonable person using this
    software would expect: a reasonable person's expectation is a
    requirement, and a spec's silence is not permission. Grade such
    findings by their effect on that person, not by whether the spec
    mentions the trigger.

    ## Read-only

    Your review is read-only on this checkout. Do not mutate the working
    tree, the index, HEAD, or branch state in any way. If you need a
    working copy of another revision, check it out into a separate
    temporary directory (`git worktree add /tmp/review-<sha> <sha>`).

    ## You do not dispatch subagents

    Do all of this review yourself. Never spawn a subagent to review part
    of the diff, and never spawn another reviewer for a second opinion.
    This process already provides every review seat the work gets. If the
    diff feels too large for one pass, review it in passes yourself and
    say so in your report.

    ## What to look for

    - The spec: behavior it asks for that is missing, wrong, or departs
      from it without a ruling.
    - Correctness: edge cases, error handling, concurrency, data loss.
    - Security and production readiness: input trust, secrets, migrations,
      compatibility with existing data.
    - Tests: they exercise real behavior, not mocks of it.

    ## Output

    Report findings only. No strengths, no praise, no general
    recommendations.

    ### Critical
    Data loss, security holes, broken core behavior.

    ### Important
    Wrong behavior a person using this software will meet, missing spec
    requirements, error handling or test gaps that hide such behavior.

    ### Minor
    Style, naming, small polish.

    For each finding: `file:line`, what is wrong, what a person using the
    software gets because of it, and the fix when it is not obvious. A
    section with no findings says "None".

    ### Declined to judge
    Every behavior you considered and set aside as outside the spec, one
    line each, with the reason. The executor rules on each line; nothing
    you set aside is dropped silently. "None" means you set nothing aside.

    ### Verdict
    Ready to land: Yes, No, or With fixes, and one or two sentences why.
```

**Placeholders:**

- `[PACKAGE_PATH]` — the file `review-package` printed
- `[SPEC_PATH]` — the spec file; for a spec with a `Read:` line, also
  that command with the launcher's absolute path
- `[LEDGER_PATH]` — `<workspace>/progress.md`
- `[REVIEW_FOCUS]` — the `## Review Focus` section of `tasks.md`, verbatim
