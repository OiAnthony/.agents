# Public Reply Mechanics (maintainer, issue or PR)

Used by Triage Mode and Ship / Release Follow-through for the actions around a reply. The reply body belongs to `/write` Public Reply Mode; without `/write`, open with `@<login>` and at most one short thanks, match the opener's language, and give one or two sentences naming the exact ship state and the reporter's next step, each true at the moment of posting. `AGENTS.md` or `CLAUDE.md` in the target repo overrides this shape.

1. Resolve `@<login>` from `gh issue view` / `gh pr view --json author` before posting, and re-read the live item there rather than replying from memory.
2. Edit your own comment in place (`PATCH /repos/{owner}/{repo}/issues/comments/{comment_id}`) only while nobody has replied after it. Once the reporter or anyone else has replied, post a new comment instead of rewriting history; never delete and repost unless the old text must disappear.
3. After posting or editing, re-read the comment body, author, target item, and issue/PR state. The public action is not complete without that receipt.
4. Close only when the fix is shipped, already available in the latest release, the report is invalid, the report is a duplicate, or the maintainer explicitly asked for closure. Otherwise leave it open with the next-release acknowledgement.
