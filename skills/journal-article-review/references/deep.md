# Deep review

A deep review searches the manuscript segment by segment before the conversation starts, then
surfaces what it found one candidate at a time. It is slower than the default review: every segment
is read in sequence, and high-scrutiny segments are read several times. Use it only when the user
asks for it.

All commands return JSON. Never put manuscript text in shell arguments. Write every scan file (plan,
initial summary, proposals, sweep) as a new file at the path creview returns, inside the scan's
private directory, never in a shared scratch or working directory: `scan purge` deletes only the
scan's directory. Do not read such a file before writing it; creview does not create it.

## 1. Start and plan

After `creview session start` has passed and the policy confirmation is recorded, propose design
profiles and wait for the reviewer to confirm them. Then start the scan with the confirmed profiles
and the reviewer's own words confirming them:

```bash
creview scan start MANUSCRIPT --profile NAME [--profile NAME] --confirmation "REVIEWER'S WORDS" [--supplement FILE]
creview scan start MANUSCRIPT --no-profile --confirmation "REVIEWER'S WORDS"
```

The confirmation must quote the reviewer's own words: creview checks it against their messages in
this Hermes session and refuses anything they did not write. If they have not answered, ask and
wait.
It reads the profiles from its own package and returns their `monitoring_areas`; a segment's or a
candidate's `profile_area` must be one of them. It reads the attached file in place (no copy is
kept) and writes a draft segment plan to `plan_draft_path`. Refine the draft as the skill
describes, write the refined plan at `plan_path`, and propose it:

```bash
creview scan plan SCAN PLAN_PATH
creview scan plan SCAN PLAN_PATH --confirmation "REVIEWER'S WORDS"
```

Segment ids may be any short slug of letters, digits, `-`, or `_`. The tier sets how many
independent passes a segment gets: light 1, medium 2, high 3. The first command only proposes the
plan: show the reviewer every segment with its tier, the total number of passes, and that more
passes take longer; ask them to confirm the tiers, change any segment's tier, or set one tier for
all segments; and end your turn. When they answer, write the plan with their tiers and run the
second command with their words; creview stores the plan only with words the reviewer sent after
the proposal. If `scan plan` warns that the scan needs more tool calls than the profile's
`agent.max_turns`, tell the reviewer that Hermes will pause the scan part-way and that replying
"continue" resumes it; the scan's progress is stored, so no pass is repeated.

## 2. Initial summary

The confirmed `scan plan` returns an `overview_template`. Before any pass, write the initial summary and store it:

```bash
creview scan overview SCAN OVERVIEW_PATH
```

It is a faithful account of the article as the authors present it, not a preliminary review:
`summary` (what it asks, does, and concludes), `analysis` (design, data or sources, methods, and
models or frameworks, as the authors describe them), and up to five `considerations`, the article's
own special considerations: what the authors themselves single out about scope, acknowledged
limitations, ethics, context, or a choice they justify. Each consideration is
`{kind, consideration, quote}`, with `kind` one of `scope`, `limitation`, `ethics`, `context`, or
`choice`, and a verbatim quote of the authors' words; creview refuses one without it. Add one to
four `main_conclusions`: what the article concludes, proposes, or recommends, each quoted verbatim.
Describe; do not evaluate. The summary is stored once and `scan next` refuses to start until it is.

## 3. Passes

Run `creview scan next SCAN` once. Then, for each task, write the returned `proposal_template`,
filled in, at `proposal_path`, and submit it:

```bash
creview scan submit SCAN PROPOSAL_PATH
```

`submit` returns the next task as `next_task`; continue until it returns none.

Each task gives one segment, its blocks, the outline of all segments, the pass number, the confirmed
profiles' `false_alarms`, the `major_flaws` for this design (the general rubric's and the
profiles'), and the `concern_register`: the key and label of every concern raised so far, without
their content. Read the segment closely; read other segments when a claim depends on them, and
before claiming that something is missing or unexplained, search the whole manuscript for it. A
concern that matches one of the `false_alarms` is not a candidate; check the segment for each listed
major flaw it could show.

Each candidate has `potential_issue`, `why_it_matters`, `severity` (major or minor, your judgement;
creview counts it as one vote), `type` (`inconsistency`, `unsupported`, `argument`, `method`,
`reporting`, or `other`), `profile_area`, `evidence` (each `{source_id, locator, quote}`, the quote
copied verbatim), `solution_candidates`, `major_flaw` (the listed major flaw its evidence shows, or
`none`), and `concern_key`. Reuse a key from `concern_register` when the candidate raises the same
concern, even where the manuscript states it in other words or another place; give a new key, with a
`concern_label` of at most 15 neutral words, only for a new concern. creview merges candidates by
key, so a new key for an old concern makes a duplicate. Evidence may quote any segment; when you do
not know a quote's locator, leave it empty and creview finds it. An `inconsistency` must quote both
statements, at two different places. An empty candidate list is a valid result.

Do not do arithmetic yourself. For every total, difference, sum of parts, or percentage the segment
reports, add a `number_checks` entry: `expression` (for example `112 - 74`), `stated` (the number
the manuscript gives for the result, for example `42`, never one of the expression's operands), and
a verbatim `quote` containing it. creview computes each one and records a candidate for any that
does not reconcile. A first pass of a segment that reports several numbers is refused without number
checks, unless `no_number_checks_reason` says why none of its numbers depend on each other.

On a segment's first pass, also write `summary`: two or three neutral sentences on what the segment
says and does. On a later pass, look from a different angle and do not try to recall earlier passes.
creview refuses a proposal with a quote that is not verbatim or a first pass without a summary; fix
it and submit again. Between passes, report progress only as segments monitored and remaining.

## 4. Synthesis and sweep

```bash
creview scan synthesize SCAN
creview scan sweep SCAN SWEEP_PATH
```

`synthesize` groups the candidates in code, by `concern_key`; a computed number check keeps its own
group with the candidates that restate it. It returns the sweep request: every entry of the pool
with its concern, issue, type, segments, the flaws its passes tagged, and any computed check, and
the `major_flaws` and `false_alarms`. Fill in the `sweep_template` once for the whole pool and write
it at `sweep_path`:

- `drops`: each entry to drop, with a reason: it matches one of the `false_alarms`, its own quotes
  do not support it, a careful reviewer would not put it in a report, or it is a computed check
  whose expression is not what the manuscript implies.
- `concerns`: every preliminary major (creview sets a preliminary severity from the passes' flaw
  tags and votes, and lists them in `preliminary_majors` by the main conclusion they bear on),
  sorted into the concerns they raise: one item per concern with all its entries in `ids`, and a
  reason when there are several. creview merges each item with several entries into one; an entry
  left alone is a concern of its own. Every preliminary major that is not dropped must appear
  exactly once.
- `merges`: groups of other entries that raise one concern under different keys (the same problem
  stated in other words or another place, which the reviewer would answer once), each with the entry
  that remains in `into`, the others in `ids`, and a reason. Never merge a computed number check
  with anything but the same check.
- `flaws`: for every listed major flaw, the entries whose evidence shows it, judged on the
  manuscript rather than on how the entry is worded, with a verbatim quote from those entries'
  evidence and one sentence on how it shows the flaw; leave `entries` empty when none does. An entry
  may show several flaws.

Then run `scan sweep`. creview refuses a sweep that leaves a preliminary major out of `concerns` or
lists one twice, leaves a flaw unanswered, drops or merges entries without a reason, merges a
dropped entry or chains merges, names a dropped entry or one that is not in the pool, quotes a
passage outside the named entries, or names an entry holding a computed number check. A flaw found
in a merged entry counts for the entry that remains. creview then sets every kept entry's severity
in code: major when a pass or the sweep found a listed major flaw in it, or when at least half the
passes over its segment rated it major; a computed number check is major only when the mismatched
figure recurs across the manuscript, whatever the votes or tags. The pool is private working
context: never show it, list it, or count it to the reviewer.

## 5. Conversation

```bash
creview scan candidate SCAN
```

The first call also returns the initial summary as `overview`. Present it as stored before the
first candidate, and tell the reviewer once that you can propose literature lookups.

Each call returns `candidates`: one major at a time in segment order (with any other majors on the
same main conclusion, presented together; ask whether the reviewer sees them as one point or
several), then, once the majors are done, minors in batches of up to three. creview orders minors
itself: entries the manuscript verifiably shows (a computed number check, or an inconsistency
quoting both statements) first, then by how many independent passes raised them. Each carries
`context`, the summaries of the segments it cites, and `severity_basis`, why creview set its
severity. Present only what the call returns, never other pool entries from memory. Open each
candidate with its context and present it as an issue record under the development contract; in why
it matters, give the strongest reply the authors could make from their own manuscript, citing where
it says so, and why the concern survives it, and say plainly if the reply answers it. For a
`computed_check`, show the expression and the stated figure, and ask the reviewer to confirm the
expression is what the manuscript implies. Ask for the reviewer's view and end the turn. When the
reviewer responds, record each disposition:

```bash
creview scan record SCAN POOL_ID accepted|developing|deferred|dismissed --words "THEIR WORDS"
```

`--words` quotes the reviewer's reply; creview refuses words that are not in a message they sent
after the candidate was shown. Record only what the reviewer said; if their reply is ambiguous,
record `developing` and ask one follow-up. `scan candidate` refuses more candidates while any
surfaced one has no recorded response. The reviewer's own issues take priority over the pool; test
them against the manuscript first.

Each candidate also carries `literature`, creview's label for every work its text cites
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

`more_available` and `next_severity` say only whether another candidate exists and whether it is
major or minor. Do not tell the reviewer how many remain or what they concern, and do not hint that a
later candidate is related to the current one. Only the first nine minors in creview's order are
surfaced by default (verifiable ones are never held back). When none remain, say the deep scan's
candidates are exhausted; if `reserve_available` is true, say that further lower-priority minor
points exist, without their number or topics, and call `creview scan candidate SCAN --reserve` only
if the reviewer asks for them.

`creview scan status SCAN` reports segment progress, how many candidates have been surfaced, and
`records`: the five status counts over surfaced scan candidates (an unrecorded one counts as
`candidate`). It is safe to show; add the reviewer's own issues to those counts. Compile and export
exactly as in a direct review. When the review is finished, offer to delete the scan's private
records with `creview scan purge SCAN --confirm SCAN`.
