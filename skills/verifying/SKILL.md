---
name: verifying
description: Use before telling your human partner that work is done, fixed, live or ready, whatever it touched — UI, an API, a CLI, data, a deploy, performance — and before fixing a bug they can see, to capture it first
---

# Verifying

A claim is proved where it is about, by you, before you make it. Whatever a
command can decide, you decide and show. Your human partner is asked only
for what needs a person: how something looks, moves, feels, sounds or
reads, and whether a trade-off is right.

**REQUIRED BACKGROUND:** ryugi:artifacts — start the verify report or artboard
through its launcher. The CLI response supplies the complete writing description,
including evidence provenance and verdict semantics; start --artifact … --help
retrieves that same description for existing content.

## How much verification

Two things decide it: does a person have to judge something a reply cannot
show, and does the proof fit in a reply. Who reported the work does not.

| The work                                                                                                                                                            | What you do                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| One claim a line or two of output proves, nothing for a person to judge (an off-by-one, a failing command)                                                          | Prove it inline: the command, its output, where it ran. No page.                                               |
| One small visible change (a padding, a colour), reported bug or not                                                                                                 | Prove it inline, with the before and after screenshot paths in the reply. No page, and no verdict to wait for. |
| Work built from a spec where nothing waits on them: no call to judge, no gap, no screen                                                                             | Prove it in your final message: the results, the routine checks in one line. No page.                          |
| Several results to show, a proof that is a run of several steps or flows, a call you made that changes what someone gets, or a judgement about motion, feel, a flow | A verify report, an artboard verify page, or both: see Where the evidence goes.                                |
| They say skip it                                                                                                                                                    | Skip it, and say what was not verified.                                                                        |

A fix proved by driving a flow end to end (sync between two clients, an
import, a deploy and what it serves) is a run of several steps: its log goes
in a verify report, where it can be kept and linked, not into the reply.
When a small row and the last row still both seem to fit, the small row
wins.

## Before fixing a visible bug

Capture the broken state from the running app now, while you reproduce it.
After the fix there is no honest "before".

## Your proof

This part always runs, at every size.

1. **The claim sets the place.** "Fixed" is proved where the bug was seen.
   "Live" is proved on the deployed thing, after the deploy carrying the
   change has finished and you have confirmed which build is running. A
   library change is proved in something that consumes the built package.
   A feature behind a flag is proved with the flag on. A check somewhere
   nearer and easier — unit tests, a mock, a local build, a simulator, your
   own dev server — is supporting evidence. Label it as that; it never
   upgrades the claim.
2. **Run the whole chain** as a user or caller would, with real data and
   real sign-in where the project allows it. Before the first run, read how
   the project says to verify (its agent instructions, acceptance or
   verification docs, its own skill for driving the app) and use its
   commands and fixtures over your own habits.
3. **Say where evidence came from**: environment, build or commit, and
   time. Evidence captured before the last change to the code it covers is
   stale. Capture it again.
4. **Walk the neighbours.** Once the change is proved, exercise the other
   flows that share what you touched — the same screen, component,
   endpoint, table or command — in the running thing, and say which ones
   you walked. Stop at what the diff touched.
5. **A check you state is a check you ran**, in this session, with its
   command and output: "typecheck clean" and "N tests pass" included.

**No homework.** Your final message never ends with a check for your human
partner to run. Verify it before you report, or list it under "Not
verified" with why you cannot do it and the one thing you need from them.

**Never ask permission to verify.** Running the checks needs no approval.
Destructive and outward-facing actions keep their usual confirmation.

**When only they can act** — fold a device, unlock it, a passkey, an
account you have no access to — first try the tools this environment has.
If none can do it, ask once: one numbered list of the exact actions, with
what to reply after each. Do everything around those actions yourself.

## Where the evidence goes

Ask of each claim: is it judged by looking at a screen, or by reading output
and numbers?

| The work has       | You make                                                                                                                                          |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Only output claims | A verify report. No artboard.                                                                                                                     |
| Only screen claims | The artboard verify page. No report; "Not verified" goes in your final message.                                                                   |
| Both               | Both. Screen verdicts happen on the artboard: give its link first, then the report's. The report references the groups and sums them in one line. |

Work whose whole question is how a screen looks, moves or feels has only
screen claims. What you measured or ran to back them — pixel sizes, sampled
frames, the test suite, a typecheck — is your proof of those same claims,
not a second kind: put it in the group's sticky or your final message. An
output claim is one that would still need proving if nobody looked at a
screen: an API result, data, a deploy, a number against a threshold.

## What is a claim

A claim is a result of this work that someone would still ask about: what
an API answers, which build is deployed and what it serves, the data after a
migration, a number against a threshold, a flow run end to end. Routine
checks (the test suites, typecheck, lint, a build) are not claims. Run them,
then state them as one line of numbers in the report's opening paragraph and
in your final message, with no output file.

## Reports and verify pages

Before you write a verify report or a verify page, or add a recording to
one, read `pages.md` in this directory and follow it.

## Running the checks

Each check has one output location. A retry or rerun writes over the
previous result; never create numbered copies (`-1`, `-2`, `-final`) of
the same check. Keep two runs side by side only when the point is comparing
two builds, and name them for the builds. Delete scratch output you created
once the evidence you need is copied to the verify page.

## When verdicts come back

They pass, reject, skip or say ship, in chat or on the page: read
`verdicts.md` in this directory before you act on it.

**Done** means: your proof is complete, every gap is gone or waived, and
every claim and group that waits on them has passed. Until
then your final message carries the link and what is waiting on whom.

## Red Flags

| Thought                                                 | Reality                                                                                 |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| "Tests pass, so it works"                               | Tests ran against a stand-in. Run the chain where the claim is about.                   |
| "It works locally, so it's live"                        | Live is the deployed build. Confirm which build is running, then exercise it.           |
| "Next: open X and check Y"                              | That is your check. Run it, or list it under "Not verified" with why you can't.         |
| "Shall I run the acceptance check?"                     | Run it. Verifying needs no permission.                                                  |
| "I'll ask them to tap, then ask for the next step"      | One numbered list of every physical action, once. Everything else is yours.             |
| "It isn't visible, so this skill doesn't apply"         | Output is evidence. A verify report: `judge="agent"`, the output file, where it ran.    |
| "It looks right to me; I'll mark it checked"            | Look, motion and feel are theirs, on the artboard. `"verify": true`, with the question. |
| "I'll put the log on the artboard next to the screens"  | The artboard is for screens. Output goes in the report; the report sums the groups.     |
| "They said push, so they passed it"                     | Push. Record nothing. Say which groups went out without a verdict.                      |
| "They said all pass in chat; the page can stay pending" | Record it first. A page that disagrees with them is wrong evidence.                     |
| "Each suite gets its own claim, to be thorough"         | Routine checks are one line of numbers. A claim is a result of the work.                |
| "A verify page, to be thorough" (for a one-line change) | One claim, nothing to judge: the command and its output, inline.                        |
| "I measured it in the browser; it's aligned"            | Measurements show what you measured. Put the screenshots up.                            |
| "Tests pass, so the UI matches"                         | Tests don't see font size, spacing or color. Compare against the approved board.        |
| "Screenshots were scratch; delete them"                 | They are the evidence. They go on the verify page.                                      |
| "The project's verify skill already checked it"         | It made evidence. What needs a person still goes to the page; the verdict is theirs.    |
| "I'll mock the result in HTML"                          | A mockup isn't evidence. Capture the real thing or say you can't.                       |
| "That screenshot is from before my last edit"           | Stale. Capture it again and update `capturedAt`.                                        |
| "Pending means fine"                                    | Pending means nobody has looked.                                                        |
