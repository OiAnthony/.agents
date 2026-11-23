# When verdicts come back

**They said it in chat.** "All pass", "pass, release it", "reject the header
one, it still doubles", "skip the production one": record it first, on the
artifact it belongs to — `comment pass … --all`, `comment pass … --group
<id>` or `--claim <id>`, `comment reject … --text <their reason>`, `comment
waive … --gap <id>` — then do the rest of what they asked. The pages have
to match what they said.

**They said ship and nothing about passing.** "Push", "PR", "release it"
while groups or claims are pending is not a verdict. Do what they asked,
record no pass, leave them pending, and say in one line which went out
without a verdict.

**They decided on the page.** On their next message, read both. The
report: `comment list --artifact verify/<id>`. The artboard: use the
artifacts launcher to read `comment list --sections groups,threads --detail`
for this project and artboard in Brief. Inspect groups with `kind=verify`. Follow
each collection's printed `More`; the delivered thread page includes
complete messages. Use the evidence before its exact `Acknowledge`. Verify
groups use the human's `verdict`, independently of choice-round submission.

- `pass`: done for that group. Leave its files alone.
- `checked by agent` (reports): yours, settled. Nothing to do unless they
  reject it.
- `reject`: read the reason and any pins on its boards, and fix it inside
  that group:
  - Behaviour or state (wrong content, a disabled control, a broken flow,
    a wrong result): under ryugi:test-driven-development.
  - Look only (layout, spacing, color, type): the rejected screenshot is
    the failing reproduction and the new screenshot is the check.
  - One commit per fix; exploratory work stays uncommitted, as
    ryugi:executing-specs says.
  - Replace the evidence (same file, or add a board to the group), update
    `from` and `capturedAt`, reply on the reject thread with what changed
    and the commit, and leave the thread open.
  - The fix changes what a passed group shows: replace that group's
    evidence too — it goes back to pending — and say so in your reply.
  - A rejected claim that was `judge="agent"` now waits on their pass like
    any other. Your new evidence does not settle it.
- `pending`: waiting on your human partner. Say so; don't call it done.

A new round is for new work on the same page — a later spec, another bug —
not for a reject. Put it below the last round with new groups. Passed
groups of earlier rounds drop `"verify": true`; groups that have not
passed keep it.
