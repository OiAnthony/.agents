# Brainstorming in a document

The questions go into a document artifact your human partner answers in
their browser, a round at a time. Each round holds only questions whose
answers don't depend on each other; between rounds you rewrite what comes
next from what they said. Most work converges in two or three rounds.

**REQUIRED SUB-SKILL:** Use ryugi:artifacts, type `document`, for creating
the document, editing it and reading comments. Name it after the
topic (`mention-notifications`, `queue-redis-streams`).

## The Document

Write it in their language. Top to bottom:

1. **Title**, and one line on how to answer, such as: "Pick on each
   question, or comment on it; anything untouched I'll take as agreed.
   Submit at the bottom of the page when this round is done."
2. **What I understand so far**: the playback, 200-300 words. Mark each
   guess as your guess; only what they said goes in as theirs.
3. **Settled**: decisions already made, each one line, marked theirs or
   your call. On a fresh start, what their request already decided.
4. **Round N**: five to seven items. Each item is a heading with the
   question, then your recommendation, then one line of why. When the item
   has options, the recommendation is an `<ask>` holding them, with
   `recommend` on yours (ryugi:artifacts, Questions); an open item is an
   `<ask>` with no options. They pick or write on it, or comment.

## Building a Round

- Item 1 is the fork: the question whose answer decides whether other
  questions exist. Label it. Leave out the questions that depend on it
  until it is answered.
- Every item carries a recommendation. A guess they can correct beats a
  question. The exception: at most two open items per round, with no
  recommendation, for what only they can describe (why now, what would make
  this a failure). Ask those in plain words and leave room under them.
- What exists now (code, services, config, what the project already uses)
  is for you to look up, not for them to answer. Make it one item: "Shall I
  read X and Y first?", recommending yes, and look before the next round.
- Mockups don't go in the document. When an item is about something they'll
  look at, put it on the artboard (`artboard-rounds.md`) or an `html` page.
  For an artboard, write a group `<ref>` under the section's heading in the
  same change (artifacts CLI document writing description, References); for an
  `html` page, link it from the item. Their answer there settles the item.

## Starting Fresh

When they asked for a design, an architecture or a kickoff document, or
their message is already a brief, skip the opening chat question. Write the
outline first as ryugi:artifacts says, then fill it. Round 1's open items
cover what the brief leaves out.

Your first message is one line on how to answer, and the link. That's the
whole message.

## Coming From Chat

Everything said in chat carries over: what they decided goes under
Settled, the rest of what you understand goes in the playback. Round 1
holds only what is still open. Never ask again in the document something
they already answered in chat.

## Between Rounds

When they submit or say the round is done, or a comment lands:

1. Re-read the document. Read Brief from `comment list --sections threads,asks --detail`
   for this project and document. Follow each collection's `More`;
   complete thread messages are included on the delivered page. Use the evidence before its exact
   `Acknowledge`, as ryugi:artifacts says.
2. Process each question whose state is `submitted` and write its
   `comment note` after applying it. Move answered items to Settled as one line: changed, written
   or commented ones as theirs, submitted recommendations as accepted.
   A submitted question with no answer also gets a note stating the assumption
   or what stayed unchanged; a question still needed uses a new id. Page
   submission is already recorded. An item settled on the artboard names the
   chosen board with a `<ref>`, not as plain text.
3. Drop the questions their answers made moot. Answer each comment, then
   resolve it.
4. Write the next round from what you now know.
5. In the terminal, one line: what changed, and how many items are in the
   new round.

A comment mid-round that changes another item in the same round: change that
item now and say so in the reply.

## Converging

When nothing is left that only they can answer, rewrite the document in
place into the written design (`written-design.md`), keeping
Settled as its decisions. Run the builder check on it; the "theirs" pile is
the last round. Approval happens on this document: once no other question
is open, its last paragraph holds an approval question in their language,
`<ask id="approve">` with the options `approve` and `revise` and no
`recommend`, and your message says to pick and submit it. A submitted
`approve` pick is the approval; a submit that leaves it unanswered is not. A `revise`, or
comments, gets applied, and the question comes back with a new id
(`approve-2`). Then write the pointer and commit as `written-design.md`
says.

## Without a Browser

When they declined artifacts earlier or the server won't start, run the same
rounds in chat: one message per round, numbered items with question,
recommendation and why. They answer by number; an item they skip is
accepted.
