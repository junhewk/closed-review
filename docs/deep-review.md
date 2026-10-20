# Deep review

```text
/journal-article-review deep
```

A deep review, modelled on the segment-based structure of Google's
[Deep Review](https://research.google/blog/analyzing-technical-documents-with-deep-review/) but run
entirely on the trusted local model (see [References](references.md)), searches the manuscript before
the conversation starts. creview runs it as a sequence of tasks: `creview scan next` gives the
current task with its instructions and an answer template, and `creview scan submit` checks the
agent's answer, refuses one it cannot verify with what to fix, and returns the next task. Code does
the steps in between.

1. `creview scan start` takes the design profiles the reviewer confirmed, with their words
   confirming them, reads the attached file in place, and drafts segments from its headings.
2. **Orientation.** The agent writes the initial summary, a faithful account of the article with
   the authors' own special considerations and main conclusions quoted verbatim, and groups the
   segments into 4 to 5 reading units by the manuscript's structure (introduction, methods,
   results, discussion; or the parts of an argument or a legal analysis), the Abstract last. Each
   unit is broken into parts at the manuscript's own breaks, of 300 to 800 words; creview checks
   the shape. Written before any read, the summary cannot preview a finding.
3. **Reads**, one per part, in order. Each read sees the concerns found so far, each with the
   passage it is about. What a part adds to one of them is recorded as typed evidence (it restates
   the claim, relies on it, contradicts it, or is the authors' answer to it), quoting this part
   only; a new concern names its target passage, and a second concern about the same passage must
   say how it is a different problem. Every quote must be verbatim. The agent states the arithmetic
   a part implies (`112 - 74` against a stated `42`) and creview computes it, recording a finding
   for any mismatch.
4. **Checks.** Each listed major flaw a read flagged is checked once, on the whole manuscript,
   against the concerns found: an answer that shows the flaw quotes the passages that show it and
   names the concern it is an instance of.
5. **The sweep** sorts every finding into the distinct concerns a reviewer would report, each
   stated in one sentence with the passage it is about; creview checks that every item is placed
   exactly once and that a computed mismatch stays a concern of its own.
6. **Second checks.** A concern rated major on judgement that names a listed major flaw is asked
   that flaw's question about its own passage; if the check does not show it, the concern becomes
   minor.
7. **Screening** sets aside a concern whose only evidence is the authors' own statement of a
   limitation, or that asks for one of the confirmed profiles' common false alarms with no passage
   making it apply. It stays available to the reviewer.

creview sets each concern's severity in code: major when a check confirmed a listed major flaw with
verbatim quotes, or when a computed mismatch is in a figure the manuscript reuses; otherwise the
model's rating, labelled as judgement.

The conversation then draws one finding at a time (`creview scan candidate`): majors first (those a
check confirmed before those on judgement), then minors three at a time, findings the manuscript
verifiably shows (computed mismatches, inconsistencies quoting both statements) first. Each comes
with the passage it is about, what later parts of the manuscript added, the authors' own answers
to it, and what each check found; the agent gives the authors' strongest reply and why the concern
survives it. Only nine minors are surfaced unless the reviewer asks for more, and verifiable ones
are never held back. creview labels each work a finding cites (`manuscript_reported` or
`model_lead`, with claims about a work's content always `model_lead`) and prepares a Crossref
lookup for it, which runs only with the reviewer's approval. The reviewer's response is recorded
with `creview scan record`; further findings are refused until every surfaced one has a response.

Inside Hermes, every statement creview records as the reviewer's (the profile confirmation, each
disposition, each lookup approval) must quote one of the reviewer's own messages in the session,
which creview reads from the profile's `state.db`; a disposition or approval must come from a
message sent after the item was shown. creview refuses words the reviewer did not write.

The findings are private: the reviewer sees the stage and task number and the findings surfaced so
far, never the size or content of what remains. The scan stores its plan, units, initial summary,
and findings in its private directory, re-reads the file each step, and stops if the file changes;
`creview scan purge` deletes it, with the lookup requests it prepared. A scan needs about three
tool calls per task; when the whole scan would exceed the profile's `agent.max_turns`, creview warns
once orientation is done, and Hermes pauses the scan until the reviewer replies "continue". On the
test manuscripts a scan took 6 to 9 minutes on one local model.
