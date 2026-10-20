# Review development contract

Use this record shape in both direct and audited reviews. It is a conversation aid, not a rigid
journal template.

## Initial summary

Before the first candidate, give the reviewer a faithful initial summary of the article as the
authors present it, in three short parts. It is not a preliminary review.

1. **Summary** — what the article asks, what it does, and what it concludes, in a short paragraph.
2. **Analysis** — the design; the data, sample, or sources; the analytic methods; and the
   theoretical models, frameworks, or ethical theories the analysis uses, as the authors describe
   them. Name what the authors name; where they leave something unstated, say so neutrally.
3. **Special considerations** — at most five things the authors themselves single out: the scope
   they set, limitations they acknowledge, ethical approvals or issues they raise, the context they
   flag, or a choice they justify. State each as the authors do and quote their words.

The summary describes; it does not evaluate, and it raises no concern of its own. In a deep review
creview enforces this order and the quotes: the summary is stored before any read, so it cannot draw
on the scan's findings, and each consideration must quote the manuscript verbatim. In the default
review the same rules are guidance only. Literature named in the summary follows the labels below.

## Candidate presentation

Surface a candidate only when it becomes the current discussion record. Do not expose a backlog of
possible criticisms, names of future issues, or a total candidate count derived from an initial
scan. The review develops through monitored exchanges; it is not a sequence of judgments written in
advance and revealed later.

For each candidate show:

0. **Context** — one or two sentences on where the concern sits: what the authors do in that part
   of the manuscript, so the reviewer can follow it without scrolling back.
1. **Potential issue** — a falsifiable, proportionate concern rather than a verdict.
2. **Manuscript evidence** — a stable location and short exact quotation where available.
3. **Why it matters** — the consequence for contribution, validity, interpretation, ethics, or use,
   and, briefly, the authors' likely reply and why the concern survives it.
4. **Literature context** — only when relevant, with one of these labels:
   - `supplied_source`: checked in material the user supplied.
   - `manuscript_reported`: represented by the manuscript but not independently checked.
   - `user_lead`: supplied from the reviewer's knowledge and not yet checked.
   - `model_lead`: recalled by the model and explicitly unverified.
   - `metadata_verified`: bibliographic identity checked; substantive content remains unverified.
5. **Solution candidates** — one or more proportionate ways the authors or reviewer could resolve
   the concern.
6. **Question for the reviewer** — ask what they accept, reject, qualify, or want investigated.

**Offering a lookup.** When a point's significance rests on literature you know only as
`model_lead` or `manuscript_reported` (what a named source argues or recommends, whether prior work
or a reporting guideline exists, how a method is normally done), offer the reviewer an approved
scholarly lookup in its literature context. Name the provider (Crossref or OpenAlex) and the exact
query you would send, built only from public bibliographic terms or general topic words (author
names, titles and years of published works, guideline or method names), never manuscript text, its
title, its specific claims, or review findings. Run it only after the reviewer approves that exact
query: `creview lookup request`, show the URL, then `creview lookup run` with their approval. A
result confirms that a work exists and what it is, not what it argues. creview cannot fetch pages
or full texts, so do not offer to; ask the reviewer to supply the source when its content matters. Offer a lookup only where the point depends on literature, and never use web or
browser tools instead.

These labels apply wherever a named source appears: in the overview, literature context, why it
matters, solution candidates, and later replies. Saying what a source argues, recommends, or warns
against, without the reviewer having supplied or checked it, is `model_lead`, and must say so.

Never invent bibliographic details. A Crossref or OpenAlex match proves identity, not what an article
argues. Ask for the source itself when claim-level verification matters.

## Recording the response

After each substantive user reply, update the same record. Preserve every material reason,
qualification, counterexample, desired revision criterion, and audience distinction. Use selective
short quotations only when wording matters. If the response is ambiguous, keep the record
`developing` and ask one focused follow-up.

Use these dispositions:

- `candidate`: surfaced but not yet discussed.
- `developing`: discussed but still being revised or tested.
- `accepted`: the reviewer approves its substance for possible compilation.
- `deferred`: intentionally held outside the current compiled review.
- `dismissed`: considered and rejected.

After the update, show compact status counts for surfaced records only, always all five
(accepted, developing, candidate, deferred, dismissed), including zeros. Separately show monitoring
progress by logical segment, using neutral coverage language such as `monitored` and `remaining to
inspect`; do not call an unpresented possibility a candidate. Do not move to the next major issue
until the current one has a disposition. A related minor batch may receive a shared response, but each item keeps its own
record. Apply a shared response only when it clearly covers every item: if it names fewer items
than the batch holds (such as "accept both" for three), or it is unclear which items it covers,
ask about the rest instead of choosing for the reviewer.

## Compilation

Compile only when the user explicitly asks. If an issue remains candidate/developing, ask whether to
continue, defer it, or compile only the accepted subset. Compilation must not introduce a new issue,
stronger claim, citation, or recommendation.

The private development record retains every disposition and reviewer discussion. Clean author and
editor drafts contain accepted items only. A recommendation is omitted unless the user supplies
both the choice and its reasoning.
