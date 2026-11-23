# Landing a branch

Run the `<base>` steps in the checkout that has `<base>` checked out: the
main repo root if you worked in a worktree, the same checkout if you
worked on a branch. Run the branch steps where the branch is checked out.

**Squash** ("merge it" means this):

```bash
git switch <base> && git pull --ff-only
git merge --squash <branch>
git commit          # one message for the whole branch, in the repo's style
<the project's test command>
```

**Rebase** (only when they ask for it):

```bash
git switch <base> && git pull --ff-only
git rebase <base>                 # on the branch
<the project's test command>      # on the rebased branch
git merge --ff-only <branch>      # on <base>
```

**PR:** push the branch and open it against `<base>`. If you are asked to
merge it, use `gh pr merge --squash` (or `--rebase` when asked).

Once it has landed, remove the worktree if you made one, per
ryugi:using-git-worktrees, delete this spec's workspace directory, then delete the branch: `git branch -d
<branch>` after a rebase, `git branch -D <branch>` after a squash (git
cannot see a squashed branch as merged).
