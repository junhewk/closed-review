# Deep review

```text
/journal-article-review deep
```

A deep review, modelled on the segment-based structure of Google's
[Deep Review](https://research.google/blog/analyzing-technical-documents-with-deep-review/) but run
entirely on the trusted local model (see [References](references.md)), searches the manuscript before
the conversation starts:

1. `creview scan start` takes the design profiles the reviewer confirmed, with their words
   confirming them, reads the attached file in place, and drafts a segment plan; the agent refines
   it and `creview scan plan` proposes it. The reviewer sees each segment's tier and the number of
   passes, and confirms or changes the tiers; the plan is stored only with their words, sent after
   the proposal. Profile areas must be the confirmed profiles' own.
2. Before any pass, the agent writes the initial summary (`creview scan overview`): a faithful
   account of the article, with the authors' own special considerations and main conclusions
   quoted verbatim. Written before any candidate exists, it cannot preview one.
3. Each segment is reviewed in sequence, in independent passes: light 1, medium 2, high 3. Each pass
   receives the confirmed profiles' common false alarms and major flaws from creview's own package
   copy, and the register of concerns raised so far (keys and labels only). Every candidate must
   quote the manuscript verbatim, name its type, tag the listed major flaw it shows (or none), and
   carry a concern key, reusing the key of a concern already raised; an inconsistency must quote
   both statements. The agent states the arithmetic a segment implies (`112 - 74` against a stated
   `42`) and creview computes it, recording a candidate for any mismatch; a number-heavy segment is
   refused without these checks.
4. `creview scan synthesize` groups the candidates in code by concern key, since independent passes
   quote different sentences for one concern; a computed check keeps its own group with its
   restatements. One sweep over
   the whole pool (`creview scan sweep`) then names the entries to drop, sorts every preliminary
   major into the concern it raises (creview merges each concern's entries into one, so a flaw
   raised in several places becomes one major comment), merges other duplicates, and looks up
   each listed major flaw across every entry, so a narrowly worded entry, or one showing two flaws,
   is still matched. creview sets the severity in code: an entry is major when a pass or the sweep
   found a listed major flaw in it, or when at least half the passes over its segment rated it
   major; a computed mismatch is major only when the manuscript reuses the figure.
5. The conversation then draws one kept candidate at a time (`creview scan candidate`): majors first
   (majors on the same main conclusion together), then minors three at a time, in an order creview
   sets: entries the manuscript verifiably shows (computed mismatches, quoted inconsistencies)
   first, then by how many independent passes raised them. The agent gives the authors' strongest
   reply and why the concern survives it as it presents each one. Only nine minors are surfaced
   unless the reviewer asks for more, and verifiable ones are never held back. creview labels each
   work a candidate cites (`manuscript_reported` or `model_lead`, with claims about a work's content
   always `model_lead`) and prepares a Crossref lookup for it, which runs only with the reviewer's
   approval. The reviewer's response is recorded with `creview scan record`; further candidates are
   refused until every surfaced one has a response.

Inside Hermes, every statement creview records as the reviewer's (the profile confirmation, each
disposition, each lookup approval) must quote one of the reviewer's own messages in the session,
which creview reads from the profile's `state.db`; a disposition or approval must come from a
message sent after the item was shown. creview refuses words the reviewer did not write.

The pool is private: the reviewer sees segment progress and the candidates surfaced so far, never the
size or content of what remains. The scan stores only its plan, the initial summary, the segment
summaries, and the pool, re-reads the file each step, and stops if the file changes; `creview scan
purge` deletes it, with the lookup requests it prepared. Segments run one after another, so a deep
review takes several times longer than the default one. A scan needs about three tool calls per
pass; when that exceeds the profile's `agent.max_turns`, `creview scan plan` warns, and Hermes
pauses the scan until the reviewer replies "continue".
