---
name: brainstorming
description: 'You MUST use this before any creative work - creating features, building components, adding functionality, modifying behavior, or planning anything new, in software or out of it (a talk, a business, a renovation).'
---

# Brainstorming

You are very good at building. You build what you believe your human
partner wants, and that belief is usually thinner than it feels. This
skill is for finding out what they actually want, and why, before
anything gets built.

When you understand the why, you make the hundred decisions they never
mention the way they would have made them.

## Pick the Path

Before you reply, ask yourself: what do I know about what they want, and
why? Everything said earlier in the conversation counts, and so does what
their project already shows: read the code, files or data before you ask
about them.

| What you know                                                                                                                 | Do                                                                                                                                                    |
| ----------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Everything that matters is in the request ("make the icon cornflower blue")                                                   | Do it, and say what you did.                                                                                                                          |
| Earlier turns already settled what and why (you proposed an approach and they agreed)                                         | No questions. Size the work and give the full description, your calls marked.                                                                         |
| They asked for a design, an architecture or a kickoff document, or their message is already a brief                           | Questions in a document, a round at a time: read `doc-rounds.md` first.                                                                               |
| Something with an interface is to be built, and both what it's for and how it looks are open ("let's make a react todo list") | Open an artboard round: 2–3 directions, each a different use drawn as that use would look. Picking one answers both. Read `artboard-rounds.md` first. |
| Enough to make a good guess                                                                                                   | Say what you'd build, your calls marked, and ask the one question that would change it, if any.                                                       |
| Too little to guess: what it's for or who it's for is unknown                                                                 | One open question that gets them describing a real moment or a concrete picture.                                                                      |

When what they asked for is a plan or a proposal, not the change itself,
the description is the deliverable: send it and end your turn.

Whenever they say to just start, stop asking: state any significant
how-it-gets-made choice (platform, language, medium) in one plain line,
then do what they asked through the normal workflow. This skill is done.

## Talking It Through

These hold on every path.

Lead with what matters, in their vocabulary.

**Ask only what changes what gets built.** Before each question, ask
yourself: would a different answer change what I build? If not, or if a
sensible default exists, pick it and say it as your call. What only they
can answer is the why, what success looks like, and what would make this
a failure.

**Guess before you ask.** A guess they can correct ("I'm guessing this is
because X keeps biting you?") beats a question. When you can't guess yet,
ask about a real moment: "What's the moment you find yourself wishing
this existed?" Offer a short menu only when they're stuck; when they say
"just guess", propose something concrete.

**One question per message.** A follow-up waits for their answer.

**Your calls, marked.** Every default you pick goes in the description as
your call, never as something they agreed to.

**How it gets made.** Platform, language, libraries, medium: find out
early which of these they want to choose and which they hand to you, then
give sensible defaults in plain words. Build on what existing work
already uses.

**Look before you ask.** What exists now (code, services, config, their
files) is for you to read without asking, not for them to answer. Offer
before going outside the project, to the web or their accounts.

**Think wide privately.** Before you propose anything, come up with
several ideas and drop the weak ones, including any that fight what
they've told you about why. Show the comparison only when it helps them
decide.

**Play it back.** Once you understand a part well enough to describe it
(what it's for and who it serves, say, or how one piece behaves),
describe it back in a few short paragraphs, guesses marked as yours, and
ask what's wrong or missing. For a small change, the full description is
the only playback.

**Spike to feel things out.** A quick throwaway build is often the
cheapest way to learn what they want or whether something works. Offer
one when it would help; when they just want to spike, get out of the way.
Spikes get minimal tests or none and skip the spec, execution and review
process. Bring what the spike taught you back into the conversation.

## Step Up to the Document

Before every playback in chat, check what you now know. Step up when any
of these is true:

- it spans several modules, services or repos that each need decisions of
  their own (one field carried from the screen to the database is one
  change, not several)
- it changes the architecture: how parts talk to each other, where data
  lives, how it deploys
- more than five decisions are still open
- one open answer decides whether other questions exist at all

When one is true, the playback goes into a document instead of chat:
follow `doc-rounds.md`, starting at "Coming From Chat". Open it without
asking first. Your message is one line on why the conversation moved,
plus the link.

## Designing What They'll See

When the next question is about something they'll look at, show it
instead of describing it:

- a screen, a page, a printout, a sign
- a layout or arrangement: of a screen, a room, a schedule
- a flow or a sequence of steps
- options that would look different from each other

| What is being decided                               | Where                                             |
| --------------------------------------------------- | ------------------------------------------------- |
| Several screens, states or visual questions at once | an artboard, in rounds: read `artboard-rounds.md` |
| One surface or one dimension to tune                | an `html` page as ryugi:artifacts says            |
| Structure, architecture, tradeoffs                  | words: chat or the document                       |

Requirements, scope, tradeoffs, and conceptual choices stay in words. A
question about a UI topic isn't automatically a visual question. One
exception: when something with an interface is being built and both its
purpose and its look are open, the directions carry the purpose: a todo
list becomes a quick list, a daily planner with due dates, and a shared
list, each drawn as that use would look.

Open it without asking first; your message is one line on what's there,
plus the link. Showing a mockup doesn't send every question to the
browser. When they say they'd rather not use the browser, describe in
words and don't open one again unless they raise it.

**REQUIRED SUB-SKILL for visual UI exploration:** Use ryugi:interface-craft before the first UI mockup; on later rounds, reuse the selected direction. It informs design judgment, not another question or approval gate. An exact cosmetic edit already specified by your human partner needs no new design exploration.

**Mockups of their product look like their product.** Before drawing
one, check whether the project has its own design skill or design system
(tokens, components, type). If it does, load it first and draw with it.
If it has none and several screens or a whole UI are being designed, or
they ask for a design system, use ryugi:design-system: its first round is
the direction round, each direction drawn as a complete system. A single
screen goes ahead as above.

## Size the Work

Once you understand what they want, pick a size and say it in plain
words. They can override it.

| Size                | The full description                       | Then                                                                                 |
| ------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------ |
| A quick, clear task | the request itself                         | do it                                                                                |
| A small change      | in chat, your calls marked                 | build it in the same turn; under ryugi:test-driven-development when behavior changes |
| A project           | a written design: read `written-design.md` | wait for approval, then the handoff below                                            |

If it grows mid-task, stop, say so, and step up a size.

If this is really several independent projects, say so, agree on an
order, and brainstorm them one at a time.

<HARD-GATE>
Nothing gets built for a project until your human partner approves the
written design. Building includes writing product code, scaffolding,
installing dependencies, creating projects, and invoking an
implementation skill. Reading and exploring are fine.

A small change has no approval round: send its full description with
your calls marked, then build it in the same turn. When they push back,
stop and change course.

If they opted out of the questions, the skill is done and the gate goes
with it. A spike they said yes to may be built; it stays labeled
throwaway, and keeping what it produced is a new request that comes back
through this gate.

</HARD-GATE>

## The Handoff

The approved document is what gets built from. There is no plan document
in between.

After your human partner approves a project's document, say in one line
that you're building it from the spec, then invoke ryugi:executing-specs
with the spec path (the pointer, for a document design). When they ask to just code it, now or in their
instructions, build it under ryugi:test-driven-development instead, then
report.

## Red Flags

| Thought                                      | Reality                                                                                               |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| "I just loaded the skill, so I start asking" | The conversation so far counts. If what and why are settled, give the full description.               |
| "I'll ask so they get describing"            | Ask only when a different answer would change what you build. Otherwise guess and say so.             |
| "I'll offer recon instead of looking"        | Reading their project needs no permission. Look, then ask what the code can't tell you.               |
| "I'll offer options to save them effort"     | Options steer. Guess one thing, or ask them to describe it.                                           |
| "I'll fill in sensible defaults"             | Good. Say them out loud, marked as your call. A default they never heard is one they couldn't reject. |
| "They said 'sounds good' to the idea"        | For a project, approval covers what you showed them. A design you haven't written isn't approved.     |
| "The spike works, I'll keep building on it"  | Keeping it is a new request. Back through the gate.                                                   |
