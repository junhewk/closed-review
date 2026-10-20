# Deep review

A deep review reads the manuscript part by part before the conversation starts, then surfaces what
it found one finding at a time. It is slower than the default review. Use it only when the user asks
for it.

creview runs it as a sequence of tasks with its own rules:
orientation, one read per part, a check of each listed major flaw the reads flagged, a sweep that
sorts everything into concerns, a second check of majors rated on judgement, and screening. You
answer each task; creview checks every answer, refuses one it cannot verify with what to fix, and
does the steps in between.

All commands return JSON. Never put manuscript text in shell arguments. Write every answer as a new
file at the `answer_path` creview returns, inside the scan's private directory, never in a shared
scratch or working directory: `scan purge` deletes only the scan's directory. Do not read such a
file before writing it; creview does not create it.

## 1. Start

After `creview session start` has passed and the policy confirmation is recorded, propose design
profiles and wait for the reviewer to confirm them. Then start the scan with the confirmed profiles
and the reviewer's own words confirming them:

```bash
creview scan start MANUSCRIPT --profile NAME [--profile NAME] --confirmation "REVIEWER'S WORDS" [--supplement FILE]
creview scan start MANUSCRIPT --no-profile --confirmation "REVIEWER'S WORDS"
```

The confirmation must quote the reviewer's own words: creview checks it against their messages in
this Hermes session and refuses anything they did not write. If they have not answered, ask and
wait. creview reads the attached file in place (no copy is kept) and drafts the segments from its
headings.

## 2. Tasks

Run `creview scan next SCAN` once. Each task returns:

- `task`: its id, stage, and number (for example read 3 of 9);
- `instructions`: what to do, in creview's words; follow them exactly;
- `answer_template` and `answer_fields`: the JSON to write and what each field holds;
- for a read, the part's `content` (its blocks with their locators), the listed `major_flaws`, and
  the confirmed profiles' `false_alarms`.

Write `answer_template`, filled in, at `answer_path`, and submit it:

```bash
creview scan submit SCAN ANSWER_PATH
```

`submit` returns the next task as `next_task`; continue until the state is `ready`. When it refuses
an answer (`answer refused: …`), fix exactly what it names and submit again to the same path. Every
quote must be copied verbatim from the manuscript; creview finds a quote's locator itself.

The stages:

1. **Orientation.** The initial summary (`summary`, `analysis`, up to five `considerations`, the
   article's own special considerations, each `{kind, consideration, quote}`, and one to four
   `main_conclusions`, quoted) and the reading `units`: the segments grouped by the manuscript's
   structure, each unit in parts at its own breaks. It is a faithful account of the article as the
   authors present it, not a preliminary review: describe; do not evaluate.
2. **Reads**, one per part, in order. Each shows the concerns found so far. When the part bears on
   one of them, link to it with a role (restates, relies-on, contradicts, answers) and quotes from
   this part only; write a new concern in full, with its `target`, the passage it is about. Add a
   `number_checks` entry for every total, difference, sum of parts, or percentage: creview computes
   it; do no arithmetic yourself. List the major flaws the part could show in `flaws_to_check`.
3. **Checks**: one per flagged flaw, against the concerns found.
4. **The sweep**: every finding and check item sorted into the concerns a reviewer would report,
   each placed exactly once.
5. **Second checks** of concerns rated major on judgement that name a listed flaw. Answer on the
   flaw as listed; a concern the check does not confirm becomes minor.
6. **Screening**, when the confirmed profiles have common false alarms: for each concern, the false
   alarm it asks for, or none.

Between tasks, report progress only as the stage and task number. The scan's findings are private
working context: never show them, list them, or count them to the reviewer. If a task refuses the sweep five times,
creview goes on without it and says so.

If `scan next` or `submit` warns that the scan needs more tool calls than the profile's
`agent.max_turns`, tell the reviewer that Hermes will pause the scan part-way and that replying
"continue" resumes it; the scan's progress is stored, so no task is repeated.

## 3. Conversation

```bash
creview scan candidate SCAN
```

The first call also returns the initial summary as `overview`. Present it as stored before the
first finding, and tell the reviewer once that you can propose literature lookups.

Each call returns `candidates`: one major at a time, then, once the majors are done, minors in
batches of up to three, in creview's order (majors confirmed by a check first; among minors,
findings the manuscript verifiably shows first). Each carries `about`, the passage it is about,
`found_in`, the unit and segment, `later_units`, what later parts of the manuscript added to it,
`authors_answers`, passages where the authors address it, `checks`, what each check found, and
`severity_basis`, why creview set its severity. Present only what the call returns, never other
findings from memory. Open each with its context, what the authors do at that passage, and present
it as an issue record under the development contract; in why it matters, give the strongest reply
the authors could make from their own manuscript, starting from `authors_answers`, and why the
concern survives it, and say plainly if the reply answers it. For a `computed_check`, show the
expression and the stated figure, and ask the reviewer to confirm the expression is what the
manuscript implies. Ask for the reviewer's view and end the turn. When the reviewer responds, record
each disposition:

```bash
creview scan record SCAN ID accepted|developing|deferred|dismissed --words "THEIR WORDS"
```

`--words` quotes the reviewer's reply; creview refuses words that are not in a message they sent
after the finding was shown. Record only what the reviewer said; if their reply is ambiguous,
record `developing` and ask one follow-up. `scan candidate` refuses more findings while any surfaced
one has no recorded response. The reviewer's own issues take priority over the scan; test them
against the manuscript first.

Each finding also carries `literature`, creview's label for every work its text cites
(`manuscript_reported` when the manuscript cites the work, otherwise `model_lead`), with any
`content_claim`, a sentence saying what the work argues or requires, which stays `model_lead`
because only the source can confirm it. `lookups` are Crossref requests creview has prepared for
those works, not yet run. Use exactly those labels, show each lookup's query and URL, and ask
whether to run it; run one only after the reviewer approves it, with
`creview lookup run REQUEST_ID --approval-statement "THEIR WORDS"`, quoting their message.

When a major comes back with `next_severity: minor`, it is the last major. Once it has a recorded
response, say the majors are done and ask whether the reviewer wants the scan's minor points now,
later, or not at all, before calling `scan candidate` again; do not say how many there are. Record a
shared reply to a batch only for the items it clearly covers (see the development contract).

`more_available` and `next_severity` say only whether another finding exists and whether it is
major or minor. Do not tell the reviewer how many remain or what they concern, and do not hint that a
later finding is related to the current one. Only the first nine minors in creview's order are
surfaced by default (verifiable ones are never held back). When none remain, say the deep scan's
findings are exhausted; if `reserve_available` is true, say that further lower-priority minor
points exist, without their number or topics, and call `creview scan candidate SCAN --reserve` only
if the reviewer asks for them.

`creview scan status SCAN` reports the stage and task number, how many findings have been surfaced,
and `records`: the five status counts over surfaced findings (an unrecorded one counts as
`candidate`). It is safe to show; add the reviewer's own issues to those counts. Compile and export
exactly as in a direct review. When the review is finished, offer to delete the scan's private
records with `creview scan purge SCAN --confirm SCAN`.
