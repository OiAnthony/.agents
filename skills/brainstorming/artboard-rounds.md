# Designing on the Artboard

Visual questions go on an artboard a round at a time, like the document's
rounds: each group is one question, its boards are the options, and one
board is your recommendation.

**REQUIRED SUB-SKILL:** Use ryugi:artifacts, type `artboard`, for the
canvas, the boards and reading what they selected. Name it after the topic
(`settings-page`).

## A Round

- When a document section sent you here, write the group references first:
  before `canvas.json`, put one `<ref artboard="…" group="…" />` per group,
  each in its own `<p>`, under that section's heading (References
  in the artifacts CLI document writing description). A missing artboard is only a warning,
  so the reference can come before the drawing. Tell them the section now
  links to the board.
- A title note for the round, with one line on how to answer, in their
  language, such as: "Pick on the board and submit; anything you don't pick
  I'll take as the recommendation."
- Up to five groups. Group 1 is the fork: the visual choice that decides
  which other questions exist (the navigation layout before the contents of
  each pane). Leave out what depends on it until it is answered.
- Two to four boards per group, differing only in what that group asks.
  Every group is a choice group: `"choose": true` and `"recommend": "<board
id>"` for your recommended board (the viewer tags it), and a sticky beside
  the group with one line of why.
- Real copy and data from their project, drawn with their design system
  when it has one.
- When what is being decided is a path through several screens (what an
  action opens, where a condition forks, where an error returns), draw those
  screens as a connected flow with labelled edges and condition notes
  (Flows in the artifacts CLI artboard writing description). Options for one
  step of the path still sit in a choice group.

- Use ryugi:interface-craft for UI design judgment. If direction is the open question, compare coherent directions and explain their rationale; once chosen, keep the **selected visual direction** and tokens fixed while comparing one layout or interaction dimension per later group.

Your message is one line on what's on the board, plus the link.

## Between Rounds

When they answer:

1. Read Brief from `comment list --sections threads,groups,rounds --detail`
   for this project and artboard, as ryugi:artifacts says under Choice groups.
   Match each group's `round` to a `submitted` round. Follow printed
   `More` for each collection; complete thread messages are included on each
   delivered page. A preview instead requires its printed `Read`. Use the evidence before its
   exact `Acknowledge`. When they answered in the terminal instead, record
   it on the board first. A page submit is already recorded: read it before
   continuing. Read what they selected when they point at nodes or tweaks.
2. Record each answered group as a decision, theirs or the recommendation
   they accepted: in the document's Settled when one is open, in your next
   playback otherwise. In the document, name the chosen board with a
   `<ref artboard=… board=…>` (artifacts CLI document writing description), not as plain
   text.
3. Append the next round below the last one, as ryugi:artifacts says.
   Earlier rounds stay as history.
4. In the terminal, one line: what changed, and what the new round asks.

When nothing visual is left to decide, the chosen boards go in the written
design by board id, with what was decided on each.
