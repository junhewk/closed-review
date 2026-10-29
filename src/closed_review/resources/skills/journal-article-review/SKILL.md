---
name: journal-article-review
description: Manuscript-only medical methodological support on the verified local model. Select statistical, qualitative/review-methodology, or logic modules and receive source-linked reconstructions, bounded appraisal, and a readable dossier; never a full review or publication verdict.
metadata:
  hermes:
    requires_toolsets: [terminal, file]
---

# Medical methodological review support

For human reviewers, not authors. Input is one manuscript (including its own tables and reference
list), not datasets, code, transcripts, supplements, or separately acquired cited papers. Perform
substantive, evidence-backed methodological appraisal within selected modules. Do not begin with
a complete verdict or a publication recommendation. The reviewer owns every scientific judgment,
the recommendation, final wording, and submission.

## Privacy gate

<!-- creview:privacy-gate:begin -->
<!-- Maintained by creview. `creview hermes doctor` compares this block with the installed creview
and stops reviews when it differs, so record lessons in other sections or reference files. -->
Before reading any manuscript, run `creview session start --support` and follow the privacy rules it returns.
If it fails, stop and report its error; do not work around it. Those rules come from the installed
creview package, not from this skill.
<!-- creview:privacy-gate:end -->

## Workflow

1. Run the privacy gate before reading the manuscript. Ask once whether this specific journal
   permits this local assistance, unless the conversation explicitly establishes it. If a question
   is undelivered or unanswered, stop; never manufacture consent.
2. Run `creview support modules`. Confirm the desired module(s) only when the request is
   ambiguous. Never automatically run all modules. Available independent branches:
   - `statistics`: tables, source-bound recalculation, test/design compatibility, interpretation.
   - `qualitative-study`: approach, participant selection, coding/theme development and evidence.
   - `systematic-review`, `scoping-review`, `narrative-review`: distinct methodology and content
     appraisal. A meta-analysis may explicitly combine its review branch and statistics.
   - `logic`: empirical/legal/normative premises, approach, inference, objections and replies.
   `creview support route ARTICLE_TYPE` is advisory only: it suggests type-appropriate branches
   without starting a run. A meta-analysis may combine review methods and statistics; do not
   silently add modules outside the reviewer's requested focus.
3. Start `creview support start MANUSCRIPT --module NAME [--module NAME] [--language LANGUAGE]`.
   Pass the user's configured response language when available; otherwise use the inherited
   Hermes user preference. Never choose a language from server locale or manuscript language.
   Preserve original quotations, numbers and statistical notation.
4. Run `creview support next RUN`. For each issued task, write the JSON template at its
   `answer_path` using file tools, then run `creview support submit RUN ANSWER_PATH`. Follow
   task-specific criteria rather than legacy major-flaw profiles. Exact quotes must cite the
   specified source block. Never put confidential text in shell arguments. Search source text
   using `creview support read RUN --module NAME --query-file FILE`; IDs and general headings
   may be used as command arguments. Read additional facts/source as needed; respect pagination.
   Follow both `next_offset` and `next_fragment_offset` with `--offset` and `--fragment-offset`.
   Large records are returned as consecutive JSON-text fragments; join them in character-offset
   order without rewriting the text. When consolidation says `records_paged`, read every page of
   `--assessments` and `--calculations`, including counterevidence and assumptions, before grouping.
   An incomplete-read error requests more context; it is not an answer-repair refusal.
   Run each `next`/`read` command separately so combined output cannot exceed Hermes's capture
   budget. Schema `$ref` entries refer to `$defs` inside `answer_schema`; they are not answer fields.
   Python calculates; do not fabricate calculator outputs or fill missing numerical inputs.
   Follow `answer_schema` and the supplied template. Evidence, including `method_evidence`, is
   always a list of `{block_id, quote}` objects; calculator output IDs are not formula strings.
   Quote each block's `text` exactly. PDF snapshots may collapse layout whitespace only;
   their separate `extracted_text` retains the extracted line layout for inspection. Do not
   reflow a quote yourself, repair hyphenation, change punctuation or normalize numeric tokens.
   Calculator inputs must preserve printed literal numeric tokens. Written-out numbers,
   expressions and unprinted derived totals are unsupported: omit that calculation and state
   the limit in its assessment. Do not convert words to digits or invent a reported total.
   Do not supply `reported.relation` or `source_operator`. Preserve any printed qualifier in
   its exact quote (e.g. `p<0.05`); Python reads it and determines matches/mismatches. Use
   narrower quotes when ambiguous. Never salvage a replay by dropping unavailable terms.
   Keep ordinary manuscript-only boundaries in `scope_limits`; only actual processing/coverage
   failures go in `coverage_gaps`. Do not demand out-of-scope raw data as a prerequisite.
   Each gap must give `kind`, assigned `block_ids`, an affected guide `role`, and `detail` of
   what could not be reconstructed. Use `[]` when none; a `fact_cap` gap requires 24 facts.
   `ambiguous_structure` requires extractor-flagged physical geometry (see the task's
   `ambiguous_structure_block_ids`). Contradictory legible numbers are not unreadable structure:
   extract each printed value unchanged, without calculating, and appraise their discrepancy
   later. An actual semantic reconstruction failure is `unreconstructed_content`; lack of
   an extractor flag does not certify that the interpretation is correct.
   Provisional meaning, unverifiable external sources and lack of formal validity/moral/legal
   certification are scope limits, not processing gaps. Do not use the obsolete `limits` field.
5. On a refused answer, call `support next RUN` again. It preserves the old draft and issues
   a fresh `answer_path` when that file already exists. Read the earlier draft if useful, then
   write the complete corrected JSON to the new path; do not patch or overwrite old drafts or
   accepted answers. Use paths exactly as returned, without embedding Markdown backticks.
   Repair all reported format paths and retry once. Reissuing a draft does not reset refusals.
   Two refusals stop
   that module visibly; do not restart automatically. Other selected modules can continue via
   `support next`. After Hermes interruption, use `support status` then `support next` on the
   same run. A turn ending at its iteration limit is not completion: preserve the checkpoint
   and continue the same session/run within the existing limits. If a file-tool edit fails,
   inspect the actual saved state before continuing; do not claim it landed or disable file
   guards. Use the freshly issued answer path, not a stale conversation copy.
   Do not alter profiles, budgets or providers to work around a failure.
6. When no tasks remain, run `creview support report RUN` and `creview support export RUN`.
   During consolidation, account for each candidate and each mismatch calculation exactly once.
   Attach related calculations to the same observation rather than creating duplicate concerns;
   withdraw indefensible input-role interpretations with a reason, preserving the calculation.
   Groups are actionable observations, not positive-check summaries. Use only the task's
   `candidate_criterion_ids` and `mismatch_calculation_ids`; supported criteria, matching or
   conditional calculations, fact IDs and titles are not grouping/priority references. When
   both lists are empty, `groups`, `withdrawn` and `priority` must all be `[]`. Summarize normal
   checks and ordinary limits in `summary`; the facts, assessments and calculations stay visible
   without creating an observation. Never invent a concern to fill an array.
   English/Korean navigation is supplied by the tool; do not regenerate its labels.
   Present the actual coverage/status and up to three priority observations, disclose totals,
   and provide the HTML/Markdown dossier paths. A partial or failed module is not a clean review.
   Do not force the reviewer through one finding per turn. Start no server automatically.
7. Follow-ups and decisions are optional. For a decision, write the reviewer's exact words into
   a private file and use `creview support record RUN ID accepted|edited|rejected|deferred
   --words-file FILE`. Use ID `run` and disposition `note` for a general note. Do not infer
   adoption from silence, or attribute model reasoning to someone who only accepted an item.
   Export a new dossier revision when asked; never overwrite an earlier export.

## Interpretation boundaries

Distinguish calculated discrepancies, reporting gaps, methodological concerns and not-assessable
items. Arithmetic verification is not verification of extracted roles, scientific interpretation
or source authenticity. A reporting gap is not proof a procedure was omitted. Keep normal
results, methodological alternatives, author qualifications, and counterevidence visible.
No criticism quota, automatic severity, model-confirmed validity badge, or automatic moral/legal
verdict. Follow [dossier guidance](references/review.md).

No transcript re-coding, raw-data replay, full citation validation, external literature retrieval,
or universal checklist quality score. Guidance is packaged locally and applicability-bound.
References named in the manuscript remain unread external sources unless their content is
actually present in it. Existing mechanical reference checks are available only on explicit
request; they do not validate substantive support.

## Legacy compatibility

`creview scan`, the earlier design profiles, and direct author/editor draft exports are legacy
interfaces. Do not invoke them as part of this support workflow, upgrade their records, or
claim their qualification scores certify these modules. Keep existing records/services intact.
