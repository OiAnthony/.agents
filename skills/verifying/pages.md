# Verify reports and verify pages

## The verify report

For what is judged by reading: the log of an end-to-end run, API status,
counts, a migration result, which build is deployed and what it serves, a
number against a threshold, a downstream build, an eval tally. Use the complete verify writing description returned by the artifacts CLI. One report per piece of work, `verify/<topic>`. Write
everything they read in their language: titles, results, asks, table
headers and cells, gaps, notes, and any line you copy from a ledger or a
log, translated. Ids, commands and raw output stay as they are.

1. **One claim per thing you assert**, titled with the claim, each with
   `from` and `capturedAt`.
   - **A command decided it**, and it is a result of the work, not a
     routine check (see What is a claim in SKILL.md): `judge="agent"`, with the command's raw
     output as an `<output>` file and a one-line `<result>` saying what it
     proved; that line is all the page shows until it is opened. Claims
     from the same environment and build share one identical `from`
     string, so the page writes it once. Nothing waits on it. A check that
     failed never goes here: fix it first.
   - **This work left a judgement open, and it is not about a screen** (a
     threshold you picked, a trade-off you made, whether a sample is
     enough): `judge="human"` with an `<ask>` saying what would make it
     wrong. Most reports have none: never re-ask what the spec or the bug
     report already decided. From a spec run's rulings, take only those
     that change what someone using the software gets, at most five, each
     its own claim: the ruling in plain words as the title, the `<ask>`
     saying when it would be wrong, one paragraph on why. The rest stay in
     the ledger; never paste the ledger as a table.
2. **Every item under "Not verified" is a `<gap>`**: what, why you could
   not, and the one thing you need. An empty gaps section is part of done.
3. **Screen claims stay on the artboard**: add `<ref artboard="…" group="…" />`
   for each verify group so they count toward done; the report sums them
   in one status-line sentence that links to the artboard, not as rows.
4. Run `check`, clear its warnings and provenance notes, give the link (and
   the artboard's link first when screen groups wait on them), say how many
   claims need them and how many you checked, and ask them to tell
   you here when they have decided. End your turn; don't poll. While you
   wait you may start the next unrelated task; landing this work waits for
   the verdicts.

## The verify page on the artboard

For what is judged by looking: a built screen beside its prototype, a
visible bug before and after, motion, device screenshots.

1. **Where.** The artboard that holds the approved design gets a page
   `verify` (name "Verify"). No such artboard (a bug, work that skipped
   brainstorming, a design approved outside this project): a new artboard
   `verify-<topic>`, with the design's link in each group's sticky when
   there is one.
2. **One group per module or per bug**, `"verify": true`, with `from` and
   `capturedAt`. The title or a sticky says what you are asking, in their
   language: what to look at, and what would make it wrong.
   - Built from a spec: the approved board (a board with the same `file`)
     on the left, a screenshot of the real app on the right. A module with
     interaction also gets a short recording. No approved board: the
     screenshot alone, titled with the spec's requirement.
   - A bug: before on the left, after on the right; add a recording when
     the bug is about behaviour.
   - Motion, frame rate, how a gesture feels: also give the running thing
     itself — a link, or the exact command that opens it. A recording alone
     does not carry those.
3. **Evidence is real.** Screenshots and recordings come from the running
   thing, with whatever tool this environment has — a project skill that
   drives the app is a fine source. Never an HTML board standing in for
   "actual". Copy evidence under `pages/verify/`; keep each file under 8MB
   and the artboard under 20MB. Over 20MB the cloud copy stops updating:
   say so and shrink or drop the largest recordings.
4. **Link back.** When the spec lists the document where this was
   discussed and it still exists, add `<ref artboard="<id>" group="<verify
group>" />` to the section that discussed each module, as the artifacts CLI document writing description explains. The reference shows the verdict,
   and it is the only way back from the verify page to that discussion.
5. Set `focus` to the first group, run `check` and clear its warnings,
   provenance notes and `pending`, give the link (the report's link when
   there is a report; else the artboard's, the cloud link when there is
   one), say what each group asks, and ask them to tell you here when they
   have decided. End your turn; don't poll.

## Prepare each recording

Add the original recording normally; Artifacts prepares Verify videos
automatically. Replay the video on the Verify page: every action, loading
or error state, and final result must remain visible. When original timing
or narration is itself evidence (performance, timeouts), set `"trim": false`
on that video board.
