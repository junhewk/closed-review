# Review record

The shape of what you show the reviewer. It is a conversation aid, not a journal template.

## Initial summary

Before the first finding, a faithful account of the article as the authors present it, in three
short parts. It describes; it does not evaluate or raise a concern.

1. **Summary**: what the article asks, does, and concludes.
2. **Analysis**: the design; the data, sample, or sources; the analytic methods; and the models,
   frameworks, or ethical theories the analysis uses, as the authors name them.
3. **Special considerations**: at most five things the authors single out (scope, acknowledged
   limitations, ethics, context, a justified choice), each quoted.

In a scan, creview stores this summary before any read and returns it as `overview`.

## Issue record

Show one major issue at a time, or up to three closely related minor ones. Never expose a backlog,
the names of future issues, or how many remain.

0. **Context**: what the authors do in that part, in one or two sentences.
1. **Potential issue**: a falsifiable, proportionate concern, not a verdict.
2. **Manuscript evidence**: a stable location and a short exact quotation.
3. **Why it matters**: the consequence for the contribution, validity, interpretation, ethics, or
   use, the strongest reply the authors could make from their own manuscript, and why the concern
   survives it. If the reply answers it, say so.
4. **Literature context**, only when relevant, each source labelled:
   `supplied_source` (checked in material the reviewer supplied), `manuscript_reported` (as the
   manuscript represents it), `user_lead` (from the reviewer, unchecked), `model_lead` (recalled by
   the model, unverified), or `metadata_verified` (bibliographic identity checked, content not).
   Saying what a source argues without the reviewer having supplied it is `model_lead`, and must
   say so. A source quotation found in the manuscript is `manuscript_reported`, not independent
   verification of the source. An uncited claim alone does not establish a misreading. Never invent
   bibliographic details.
5. **Solution candidates**: one or more proportionate ways to resolve it.
6. **Question for the reviewer**: what they accept, reject, qualify, or want investigated.

When a point rests on literature you know only as `model_lead` or `manuscript_reported`, offer an
approved lookup: name the provider and the exact query, built only from public bibliographic terms
(author names, titles and years of published works, guideline or method names), never manuscript
text, its title, its claims, or review findings.

## Responses

After each reply, update the same record and keep every reason, qualification, and counterexample
the reviewer gives; quote them only where the wording matters. Dispositions:

- `candidate`: surfaced, not yet discussed.
- `developing`: discussed, still being revised or tested.
- `accepted`: the reviewer approves its substance for the review.
- `deferred`: held outside the current review.
- `dismissed`: considered and rejected.

If a reply is ambiguous, record `developing` and ask one focused question. Then show the status
counts for surfaced records only, all five, including zeros. Do not move to the next major issue
until the current one has a disposition. A reply to a batch applies only to the items it clearly
covers; if it names fewer items than the batch holds, ask about the rest.

In a scan, when a major comes back with `next_severity: minor`, it is the last major: once it has a
response, say the majors are done and ask whether the reviewer wants the minor points now, later,
or not at all, without saying how many. When none remain, say so; if `reserve_available` is true,
say that lower-priority minor points exist, and call `creview scan candidate SCAN --reserve` only
if the reviewer asks. `creview scan status SCAN` gives the counts and is safe to show.

## Compilation

Compile only when the reviewer explicitly asks. If an issue is still `candidate` or `developing`,
ask whether to continue, defer it, or compile only the accepted ones. Compilation adds no new issue,
stronger claim, citation, or recommendation. The private development record keeps every
disposition and the reasoning the reviewer actually supplied; the author and editor drafts hold
accepted items only. Do not attribute the agent's analysis or a suggested remedy to the reviewer
as their own reasoning merely because they accepted the issue. When they gave no reason, say so;
the agent's analysis may be recorded separately and labelled as such. The private record covers
surfaced issues only: do not list, name, or count unsurfaced scan findings there or in the drafts.
Those findings remain in the private scan until they are surfaced. Do not claim the preflight
proves that no manuscript content left the machine; it checks settings, not everything the host
does. A recommendation appears only when the reviewer gives both the choice and the reasoning.
