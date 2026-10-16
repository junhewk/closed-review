---
name: journal-article-review
description: Collaboratively develop a confidential journal review in Hermes with the verified self-hosted model; surface evidence-grounded candidate issues, preserve the reviewer's reasoning, and compile only on explicit request.
metadata:
  hermes:
    requires_toolsets: [terminal, file]
---

# Journal article review development

Help the human reviewer develop their review. Do not begin with a complete verdict, fixed list of
major/minor comments, or model-selected recommendation. Rubrics and mechanical checks discover
candidates; they are not pre-written review items.

## Privacy gate

<!-- creview:privacy-gate:begin -->
<!-- Maintained by creview. `creview hermes doctor` compares this block with the installed creview
and stops reviews when it differs, so record lessons in other sections or reference files. -->
Before reading any manuscript, run `creview session start` and follow the privacy rules it returns.
If it fails, stop and report its error; do not work around it. Those rules come from the installed
creview package, not from this skill.
<!-- creview:privacy-gate:end -->

## Development loop

Read [references/development.md](references/development.md) and use its issue-record contract.

After reading the manuscript and before the first candidate, give the reviewer the article
overview described in [references/development.md](references/development.md): what the article
asks, does, and concludes; what its analysis uses (design, data or sources, methods, and models or
frameworks); and a few open considerations about the article as a whole. In a deep review, the
overview comes after the scan instead, just before its first candidate.

Then choose design profiles as described in
[references/designs/index.md](references/designs/index.md): propose the profiles that fit, with a
one-line reason each, wait for the reviewer to confirm or correct them, then read only the confirmed
profiles. They guide where to look and which concerns are false alarms; they are not review items.

Then plan the review by logical segments, in every mode. Run `creview segments propose MANUSCRIPT`
for an attached file (in an audited case, use the case commands in the workflow reference). It
drafts segments from the headings; when the manuscript was pasted rather than attached, draft them
yourself from its headings. Refine them so each holds one theme (overlap is allowed where a
theme spans parts), tag each with the confirmed profiles' monitoring areas, and set its tier:
`light`, `medium`, or `high` scrutiny. Show the reviewer the segment titles, themes, and tiers in
one short list; this plan names where you will look, never what you expect to find.

Read the supplied manuscript as a whole, but reveal candidates adaptively:

- Discuss one major candidate at a time.
- Closely related minor candidates may be grouped in batches of at most three.
- Do not announce, enumerate, summarize, or count possible future issues. A whole-manuscript scan may
  guide what to inspect next, but it is private working context—not a precomputed review queue.
- Open each candidate with its context (what the authors do in that part), then give its
  manuscript anchor, why it matters, tiered literature context when relevant, and proportionate
  solution candidates.
- Ask for the reviewer's view before treating it as an accepted comment.
- After every substantive reply, show the revised issue record and compact counts for records already
  surfaced to the reviewer: accepted, developing, candidate, deferred, and dismissed. Never include
  undisclosed possibilities in those counts. Report whole-manuscript progress separately by
  segment, as monitored or still to inspect, without turning segments into findings.
- Preserve every substantive qualification in a faithful structured account. Quote selectively;
  do not replace the record with a raw transcript.
- When the user introduces an issue, prioritize and test that issue against the manuscript instead
  of returning to a predefined checklist.

Continue developing the same records when the user supplies corrections, sources, supplements, or a
review form. Do not restart the review.

## Deep review

Use a deep review only when the user asks for it, for example with
`/journal-article-review deep`. Read [references/deep.md](references/deep.md) and follow it. It
reviews every segment in sequence, several times for high-scrutiny segments, and builds a private
pool of candidates before the conversation starts. The conversation then follows the development
loop above, drawing one candidate at a time from the pool.

## Default: direct conversation

Use attached or injected material directly. Do not create an audited case unless the user requests
an audited, exhaustive, checkpointed, or resumable workflow. Do not use `execute_code` for general
reading or criticism.

Track the issue records in the conversation. When the user explicitly asks to compile, use accepted
records only. Keep deferred, dismissed, and unresolved candidates in the private development record,
not the journal-facing prose. Do not introduce new criticism during compilation.

A recommendation is optional and belongs to the user. Discuss implications if asked, but do not
select a recommendation. Include one only after the user states their choice and reasoning.

When the user asks to save or export, run `creview direct prepare-export` (with the
`--session` value that `creview session start` returned, if it returned one) and write the private
development record plus separate author and editor drafts to the returned `output_paths`. Keep
author-facing and confidential material separate. The legacy `output_path` is only a compatibility
fallback. After writing the files, run the returned `finalize_command` once; it records
`receipt.json` beside them. Tell the user the receipt exists. It is self-reported: it records the
creview build, model settings, and hashes of the exported text, but it does not prove that no other
AI tool was used. Never edit the receipt; if the files change, run `finalize_command` again.

## Mechanical reference check

Run a reference check only when the user requests it. For an attached file, use
`creview references check MANUSCRIPT`; for an audited case, use
`creview references check --case CASE`. Treat only entries in `issues` as possible candidates.
`normalizations` records extraction repairs and `warnings` records parser limitations; neither is a
manuscript defect or a review candidate. If normalization resolves a mismatch, report it only as a
private method note. When parsing remains unresolved, state that the checker could not decide—do not
ask the reviewer to disposition extraction artifacts and do not create author-facing prose.

Metadata verification is a second, optional step. Prepare an immutable request with
`creview references request-metadata CHECK --provider crossref|openalex`, show every exact query
and URL, and wait for explicit approval of that exact manifest. Then record the reply in a file and
run `creview references run-metadata CHECK REQUEST --approval-file FILE`. Metadata verifies
bibliographic identity only, never substantive support.

## Optional audited review

Use the durable case only when explicitly requested or when continuing an existing case. Read
[references/workflow.md](references/workflow.md) and follow its bounded commands. Internal coverage
tasks may be predefined, but every resulting issue remains a candidate until the reviewer develops
or disposes it. Existing cases migrate in place.

The human reviewer owns all scientific judgments, final wording, disclosure decisions, and
submission.
