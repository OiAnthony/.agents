# Incident Ledger And Review Evals

Loaded from `check` when a fix targets a defect that reached users or a published build, when a review prompt, skill, reviewer persona, or model changes, or when the user asks whether review is catching what it should. The project's own ledger and layer names win over this shape.

## The ledger

A project that ships to users keeps one table, conventionally `docs/incidents.md`, with one row per defect that reached a user or a published build. The row lands in the same change as the fix; a fix without its row is incomplete in a project that keeps the ledger.

```markdown
## Incidents

<!-- layers: write-time, unit, integration, review, e2e, release, field -->

| ID | Reported | Symptom | Introduced | Fixed | Layer | Caught by |
|---|---|---|---|---|---|---|
| I-01 | 2026-01-02 | What the user saw, in their words | unknown | 1a2b3c4d | unit | `test_name_that_fails_on_the_old_code` |
```

- `Symptom` is the observed failure, not the mechanism.
- `Introduced` is the commit that brought the defect in, or `unknown`; it measures how long defects stay in.
- `Layer` is the earliest layer that should have caught it, from the project's ordered list (earliest first). The retro question is which layer missed it, never who wrote it.
- `Caught by` names, in backticks, the test or gate that now fails on the pre-fix code: a test function or test title, or a gate script's repository path. A row with no live catcher is a note, not coverage.

Validate it with `python3 <skill-base-dir>/scripts/incident_ledger.py --root <project>`: unique IDs, dates, commits that resolve (shape-checked only in a shallow clone, which it says), layers from the `<!-- layers: ... -->` declaration or `--layers`, and catchers that are tracked files or names a test file defines. Wire it into the project's fast check so a renamed or deleted test fails its row instead of silently orphaning it. Projects may keep their own checker with a stricter catcher resolver; the contract is the same.

## Replay eval

The ledger is the regression suite for review itself. Rerun it when a review prompt, skill, persona, or model changes, and before trusting a new reviewer:

1. `incident_ledger.py --plan` prints each row's pre-fix revision (`<Fixed>^`) and the files the fix touched.
2. Run the changed reviewer on those files as they were at that revision, from a detached worktree, without telling it the symptom.
3. Count recovered rows: a row is recovered when a finding names the defect at the right place with a trigger that matches the symptom. Report recovered over total, per layer, beside the previous run's count.
4. Run the same reviewer on a few known-clean changes (merged changes with no later fix touching them). Every finding there is noise; report the count beside the recovered rows. A reviewer that recovers more rows by also doubling noise is not better.

A drop in recovered rows blocks adopting the change until explained. Record the run's counts where the project keeps review history, not in the ledger rows.

## Recurring classes

When two incidents, or two review rounds, share a bug class, the next fix belongs at the source: a lint rule, a source gate that enumerates the call sites, a type, or a routed project rule, with the earlier rows pointing at that one catcher. Another per-site test beside the last one is not the fix.
