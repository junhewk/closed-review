# Deep review

A deep review searches the manuscript segment by segment before the conversation starts, then
surfaces what it found one candidate at a time. It is slower than the default review: every segment
is read in sequence, and high-scrutiny segments are read several times. Use it only when the user
asks for it.

All commands return JSON. Never put manuscript text in shell arguments.

## 1. Start

After `creview session start` has passed, the policy confirmation is recorded, and the design
profiles are confirmed:

```bash
creview scan start MANUSCRIPT [--supplement FILE]
```

It reads the attached file in place (no copy is kept) and writes a draft segment plan to
`plan_draft_path`. Refine the draft as the skill describes, show the reviewer the segment list, then
store it:

```bash
creview scan plan SCAN PLAN_PATH
```

The tier sets how many independent passes a segment gets: light 1, medium 2, high 3. Tell the
reviewer how many passes the scan will run and that it may take a while; nothing else about the
scan is reported until it finishes.

## 2. Passes

Repeat until `creview scan next` returns no task:

```bash
creview scan next SCAN
creview scan submit SCAN PROPOSAL_PATH
```

Each task gives one segment, its blocks, the outline of all segments, and the pass number. Read the
segment closely; read other segments when a claim depends on them, and before claiming that
something is missing or unexplained, search the whole manuscript for it. Write candidates to the
proposal file with `potential_issue`, `why_it_matters`, `severity` (major or minor),
`profile_area`, `evidence` (each `{source_id, locator, quote}`, the quote copied verbatim from that
locator), and `solution_candidates`. An empty list is a valid result. On a segment's first pass,
also write `summary`: two or three neutral sentences on what the segment says and does (its claims,
data or sources, and the methods, models, or frameworks it uses). creview refuses the whole
proposal if any quote is not verbatim or a first pass has no summary; fix it and submit again.

On a later pass of the same segment, look from a different angle and do not try to recall earlier
passes. Duplicates are merged afterwards. Check every concern against the confirmed profiles'
false alarms before writing it.

Between passes, report progress only as segments monitored and remaining. Do not mention
candidates, their number, or their content until the scan is screened.

## 3. Synthesis, screening, and overview

```bash
creview scan synthesize SCAN
creview scan screen SCAN SCREENING_PATH
```

`synthesize` merges candidates that quote the same passage and returns the pool. The same concern
raised in different segments, or with different quotes, still appears as separate entries. In the
screening file, decide for every entry:

- `merge`, with `into` set to another entry's id, when it is the same concern as that entry. Keep
  the clearest entry and merge the rest into it; their evidence is combined.
- `drop`, with a reason, when it matches a profile's false alarms, fails the rubric's checks before
  keeping a candidate, or its quotes do not support it. Screen as the authors' advocate; expect to
  drop many entries.
- `keep` otherwise, with `author_reply` (the strongest reply the authors could give from their own
  manuscript, citing where; search the whole manuscript) and `survives` (why the concern still
  stands). If the reply answers the concern, drop it instead. Set the severity: `major` only when
  you can name `affected_conclusion`, the paper's specific conclusion that would not follow.
  creview refuses a kept entry without these fields. If useful, give one `potential_issue` wording that covers the
  entry's members. The pool is private working context: never show it, list it, or count it to the reviewer.

`screen` returns the segment summaries and an overview file. Write the article overview described
in the development contract from those summaries, reading the manuscript again where they leave
something unclear, and store it:

```bash
creview scan overview SCAN OVERVIEW_PATH
```

The file holds `summary`, `analysis`, and `considerations` (a list of at most five open questions).
`creview scan candidate` refuses to start until the overview is stored.

## 4. Conversation

```bash
creview scan candidate SCAN
```

The first call also returns the `overview`. Present it to the reviewer before the first candidate,
then present the candidate.

Each call returns one kept candidate, majors first, in segment order, with `context`: the summaries
of the segments it cites. Open the candidate with one or two sentences of that context, then
present it as the current issue record under the development contract, ask for the reviewer's
view, and record the response before asking for the next one. The reviewer's own issues take priority over the pool; test them
against the manuscript first.

When the next candidate is minor, the majors are done. Say so, and ask whether the reviewer wants
the scan's minor points now, later, or not at all; do not say how many there are. If they want
them, show related minor candidates together, at most three at a time.

`more_available` says only whether another candidate exists. Do not tell the reviewer how many
remain. When none remain, say the deep scan's candidates are exhausted and continue the review as
usual.

`creview scan status SCAN` reports segment progress and how many candidates have been surfaced; it
is safe to show. Compile and export exactly as in a direct review. When the review is finished,
offer to delete the scan's private records with `creview scan purge SCAN --confirm SCAN`.
