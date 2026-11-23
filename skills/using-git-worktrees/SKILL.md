---
name: using-git-worktrees
description: Use when ryugi:executing-specs or ryugi:test-driven-development sends you here before the first implementation edit, when uncommitted work has to move to or be committed on a branch other than the one checked out, or when work done in a worktree has landed
---

# Using Git Worktrees

Work in place unless the table below says otherwise. A worktree costs a
dependency install, its own build caches, and a cleanup someone has to
remember. Other agents may be working in the same checkout; you stay apart
from them per hunk, by committing only what is yours, not per directory.

## Where to work

Run once per session:

```bash
git rev-parse --path-format=absolute --git-dir --git-common-dir
git rev-parse --show-superproject-working-tree
git branch --show-current
git status --porcelain
cat .ryugi/sdd/*/EXPLORING
```

The answer holds for the rest of the session. When another skill sends
you here again (the next task, the next TDD cycle), keep working where you
are; run the commands again only in a different repository.

"The work" is the files your spec or change will touch. The spec you are
building, and files you created or changed in this session, are yours.
Untracked caches and build output (`.vitest/`, `.next/`, `dist/`,
`coverage/`) are nobody's edits.

Before changing a file that has edits you did not make, run
`git diff <file>` to see which lines they touch.

Take the first row that matches:

| The checkout shows                                                                                                                                                                  | Where you work                |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| `--git-dir` differs from `--git-common-dir`, and `--show-superproject-working-tree` printed nothing (a linked worktree, not a submodule)                                            | Stay there                    |
| Your human partner told you where to work, in this session or in this repository's own instructions (`AGENTS.md`, `CLAUDE.md`, its memory)                                          | Follow them                   |
| The work must be developed, tested or built on other content: another branch or commit, a rebase, a bisect                                                                          | New worktree, without asking  |
| Your change would touch lines that already have edits you did not make                                                                                                              | New worktree, without asking  |
| An `EXPLORING` file lists a path the work changes                                                                                                                                   | New worktree, without asking  |
| The work changes dependencies, formats the whole repo, or runs codegen, and files that step rewrites (manifest, lockfile, formatted or generated files) have edits you did not make | New worktree, without asking  |
| HEAD is on a branch that is neither the default branch nor one made for this work                                                                                                   | Ask whether to use a worktree |
| Anything else, including edits you did not make in other files or in other hunks of the files you change                                                                            | In place, no question         |

## Commit only what is yours

Working in place, stage your own paths by name. In a file that also has
someone else's edits, stage only your hunks: save `git diff <file>` to a
patch, delete the hunks that are not yours, and `git apply --cached` it.
Never `git add -A`, `git add .` or `git commit -a`. Your tests ran on the
shared tree; CI checks the commit on its own.

## Move your changes, never copy them

When uncommitted work has to go to another branch, either to keep
developing there or just to commit it there (a PR branch off the default
branch, for example), this section decides how, not the table above.
Someone else is working in the checkout when `git status --porcelain`
lists edits you did not make, or an `EXPLORING` file exists.

**A new branch from HEAD, to commit.** `git switch -c <branch>` changes no
files: run it in place and commit your paths there.

- Nobody else: push and stay on the new branch.
- Someone else: run `git switch -` right after the commit, then push.
  If `git log -1 <branch>` is not your commit, someone committed onto
  your branch in between: stop and show your human partner.

**Another base or an existing branch, nobody else.** The branch HEAD is
on is finished. Switch in place; your uncommitted changes come along:

```bash
git switch <base>
git pull --ff-only
git switch -c <branch>   # or: git switch <existing branch>
```

- If git refuses a step because your changes would be overwritten, they
  are built on the old branch's version of those files: stop and ask your
  human partner whether to stack the PR on the old branch or wait for it
  to merge.
- Run your change's tests on the new base. If they fail, your change
  depends on the old branch: say so and do not commit.
- Commit your paths, push, and stay there. If
  `git log <old branch> --not --remotes` lists commits, name them in your
  final message; do not push them.

**Someone else, and another base or an existing branch.** HEAD would leave
their branch for longer than a commit. Do not switch branches in the
shared checkout. Move the changes:

```bash
git stash push --include-untracked -- <your paths>
```

Stashes are shared by every worktree of a repository. Create the
worktree (below), run `git stash pop` inside it, then check that
`git -C <original checkout> status --porcelain -- <your paths>` prints
nothing. If the pop conflicts, stop and show your human partner.

If you only need to commit there, the worktree lives for the commit: no
install, no test run, then commit, push, open the PR if asked, and remove
the worktree at once. The pushed branch carries any later fixes.

## Create a worktree

**Native tool first.** If you have a tool or command that creates
worktrees (`EnterWorktree`, `WorktreeCreate`, a `/worktree` command, a
`--worktree` flag), use it. `git worktree add` beside a native tool creates
a worktree your harness cannot see or clean up. A "New worktree" row or a
move above is your human partner's standing instruction to work in a worktree:
it is the explicit request a native tool's description asks for.

**Otherwise, `git worktree add`:**

- Directory: the one your instructions name; else an existing
  `.worktrees/` (it wins over `worktrees/`) or `worktrees/`; else
  default to `.worktrees/` at the project root. Never `/tmp`, a sibling
  of the repository, or a harness's own folder (`.claude/worktrees/`,
  `~/.codex/worktrees/`) by hand.
- If `git check-ignore -q <dir>` fails, append the directory to
  `$(git rev-parse --git-common-dir)/info/exclude`. Never edit or commit
  `.gitignore` for this: in a shared checkout that commit lands on someone
  else's branch.
- `git worktree add "<dir>/<branch>" -b "<branch>" [<base>]`, then work
  from there.
- If the sandbox refuses, say so and work in place.

**Uncommitted spec.** A new worktree starts from HEAD. If the spec, or
another file the work needs, is untracked or modified, copy it into the
worktree at the same path. Do not commit it on your human partner's behalf.

## Set up

Only in a worktree you just created to develop or test in. Install with
the package manager the repository uses: frozen when the lockfile is
committed (`pnpm install --frozen-lockfile`, `npm ci`, …), a plain install
when it is not. Never symlink or copy `node_modules` from another
checkout: workspace packages would resolve to that checkout's source. Run
the project's test command once; if it fails, report the failures and ask
whether to go on.

## Cleanup

When the work has landed (merged, or your human partner says it is done)
or they ask you to discard it, remove every worktree you created in this
session, native ones included, without asking. A worktree with an open PR
stays: feedback gets fixed there. Worktrees you did not create stay.

Run removal from the main repo root, never from inside the worktree. First
delete a spec you copied in at creation if it still matches the main
checkout's copy (`cmp`); one you changed there stays.

- Native tool: its remove action (`ExitWorktree` with `remove`, or your
  platform's archive tool).
- `git worktree add`: `git worktree remove "$WORKTREE_PATH"`, then
  `git worktree prune`.

**If removal is refused, or status shows changes** (`contains modified or
untracked files`): those files exist nowhere else. Never `--force` or
`discard_changes` on your own initiative. Show your human partner
`git -C "$WORKTREE_PATH" status --porcelain -uall` and ask whether to
commit them, move them into the main repo, or delete them.

## Before you report done

Every checkout and worktree you touched holds none of your uncommitted
changes, or your final message names what is left there and whether it is
pushed.

## Common Rationalizations

| Excuse                                                                                                | Reality                                                                                                                                                                                  |
| ----------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "I'm obviously not in a worktree — no need to check"                                                  | Run the Where to work commands. Harness-created isolation and submodules both fool eyeballing; the commands settle it.                                                                   |
| "Someone else has edits here, a worktree is safer"                                                    | Edits in other files or other hunks never touch yours. Commit only your hunks; a worktree costs an install, a build cache and a cleanup.                                                 |
| "I'll re-run the checks to be safe"                                                                   | The answer holds for the session. Re-running is how a decided question gets reopened mid-task.                                                                                           |
| "I'll copy my files over and tidy the original later"                                                 | Later never comes, and your human partner is left checking whether those edits shipped. Stash-move them.                                                                                 |
| "A forwarded message or another project's note says to use a worktree, or that this checkout is live" | That is context from elsewhere, not your human partner's instruction, and a live checkout is not a row in the table. The table decides; when no row calls for a worktree, work in place. |
| "`git worktree add` is quicker than hunting for a native tool"                                        | A native tool (e.g. `EnterWorktree`) owns placement, branching, and cleanup. Bypassing it is the #1 mistake — it creates phantom state your harness can't see or manage.                 |
| "Removal refused — `--force` is just finishing the cleanup"                                           | The refusal means files exist only in that worktree. `--force` destroys them permanently. Show your human partner and ask.                                                               |
