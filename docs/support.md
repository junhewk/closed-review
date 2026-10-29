# Medical methodological review support

The `medical-methods-v1` workflow is for a human reviewer examining one submitted manuscript.
All model inference stays in Hermes on the configured local/private gateway. Python performs
source access, calculations, validation, persistence and rendering; it never calls a model.
No datasets, transcripts, code, supplements, or separately acquired cited papers are inputs.

This implementation is a candidate, not a qualified medical reviewer. Unit tests establish
contracts, not scientific reliability. No cloud fallback or automatic external lookup is used.
Hermes terminal/network isolation remains the operator's responsibility: profile guardrails
alone cannot guarantee confidentiality. Keep journal-specific permission requirements.

For a bounded real-Hermes synthetic pilot of these modules, see
[support-pilot.md](support-pilot.md). The earlier scan smoke is not a substitute.

## Selecting modules

Use `/journal-article-review` and state your focus. There are three families and six independent
branch IDs. `creview support modules` prints their packaged criteria and applicability limits:

| Family | Branch IDs | Deliverable |
|---|---|---|
| Statistical | `statistics` | Tables, population/outcome/analysis reconstruction, numerical checks, test-fit appraisal |
| Qualitative/review methodology | `qualitative-study` | Sampling, participant composition, generation, coding/theme development, displayed evidence |
| Qualitative/review methodology | `systematic-review`, `scoping-review`, `narrative-review` | Type-specific methods, selection/charting/synthesis and question/content correspondence |
| Logic | `logic` | Premises, definitions, approach, evidence roles, objections/replies and conclusions |

Selection is explicit; “all” is not an implicit full review. A meta-analysis can combine
`systematic-review` and `statistics`; an empirical ethics paper can add `logic`. The user’s
language setting governs explanations/navigation; original quotations and numbers stay intact.
Pass `--language` when that preference is available to Hermes, otherwise inherit its user setting.
Do not infer the preference from server locale or manuscript language.

`creview support route ARTICLE_TYPE` is an advisory map, not an automatic review. For example,
`meta-analysis` suggests systematic-review plus statistics, while `normative-perspective`
suggests logic. The reviewer still selects the focus explicitly. No route runs every branch.

## Agent/tool contract

Create a dedicated profile with an explicit verified context length (at least 65536), then use
`creview hermes doctor --profile NAME --support`. Inside Hermes run
`creview session start --support` before opening a manuscript. The stricter gate checks the
actual recorded session model/provider/endpoint, all auxiliary pins, launcher integrity, local
terminal/toolsets, ambient credentials and proxy bypass. An unverifiable runtime is refused,
not assumed safe. Basic legacy doctor readiness alone is not support eligibility.

After the privacy check, start a run:

```text
creview support start MANUSCRIPT --module statistics --module logic
creview support next RUN
creview support submit RUN ANSWER_PATH
creview support status RUN
creview support report RUN
creview support export RUN
```

Outside Hermes, pass the preflight's `--session` to `start`. Each task supplies its instructions,
template, task ID and answer path. Use file tools to write JSON at that exact path; never put
manuscript text in shell arguments. Tasks perform bounded source extraction, criterion-specific
appraisal, then consolidation that may group or withdraw weak concerns. Two refused answers stop
that module visibly; there is no automatic new run. Other selected modules remain independent.
The default maximum is 96 tasks (explicitly configurable, at most 256). Context overflow is a
visible module failure, never silent source omission. Hermes context compression is not certified
by these size limits. Resume the same run after an interruption; changed source/build/routes
require a new run. Old reports can still be exported from their saved snapshots.

The explicit `answer_schema`, introduced in contract 7 and retained in contract 9, supplies
filled criterion IDs and calculator
output identifiers. Every evidence field—including `method_evidence`—is a list of
`{block_id, quote}` objects. Shape errors identify up to twelve field paths without echoing the
confidential values, so one repair can address several format mistakes. Evidence is never coerced
from a string into invented citations. Keep `scope_limits` (normal manuscript-only boundaries)
separate from `coverage_gaps` (actual processing/cap/coverage failures). Each gap now requires
`kind` (`unreadable_content`, `ambiguous_structure`, `unreconstructed_content`, `fact_cap`),
nonempty distinct `block_ids` from the assigned extraction chunk, an affected guide `role` and
`detail` stating what could not be reconstructed and why. A `fact_cap` gap requires reaching
24 facts. General uncertainty about author intent or absence of a formal/moral/legal certificate
belongs in scope limits; internal argument reconstruction does not certify truth or validity.
Free-form gap strings and the obsolete `limits` field are refused in new answers, not silently
reclassified. Historical extraction limits remain unchanged and conservative. Source extractor
warnings and any actual declared gap still prevent complete coverage. Typed provenance is not
proof that a model's classification is correct; it remains subject to human coverage review.
`ambiguous_structure` is reserved for extractor-flagged physical geometry; use the task's
`ambiguous_structure_block_ids`. Readable conflicting numbers remain separate printed facts for
later appraisal, not a structure failure. Genuine semantic reconstruction failures can still be
declared as `unreconstructed_content`. No flag certifies correct interpretation or completeness.

In the b8 implementation, general PDF extractor cautions are explicit source/module scope
limits, not evidence that a particular block was unreadable. They remain visible in the dossier.
Detected ambiguous table geometry, embedded images, scanned/unreadable text, Office Math and
other actual processing warnings remain conservative coverage limits. A readable PDF is not
automatically partial merely because its format is PDF, but an actual omission still prevents
complete coverage. Historical warnings/statuses are never migrated or promoted by this change.
Repeated schema definitions use standard `$ref` / `$defs` references, not extra answer fields.
This retains the exact calculator/evidence restrictions while reducing printed task size.
The full pretty-printed task is limited to 45,000 characters, below the managed Hermes terminal
capture of at least 50,000. The initial fact index contains twelve entries with explicit
continuation. Run each `next`/`read` separately, not concatenated with other payloads. Strict
doctor requires explicit `tool_output` limits (50,000 terminal characters, 2,000 file lines,
20,000 characters per file line); they are frozen into each run's route. Legacy profile defaults
are not enough: create a fresh candidate profile without overwriting an existing configuration.

Consolidation accounts for every candidate criterion and mismatch calculation once. A group can
attach `calculations: [ID]` to its `criteria: [ID]`; do not create a second observation for the
same discrepancy. A calculation-only group uses `criteria: []`. A weak input-role interpretation
can be withdrawn using `calculation_id`, a reason and any counterevidence; the arithmetic record
stays visible in the dossier. Navigation for English/Korean is deterministic; other languages
can supply their labels. Status/report/render operations do not advance saved tasks.

Answer contract 8 exposes `candidate_criterion_ids` and `mismatch_calculation_ids` in each
consolidation task and binds its schema to those existing records. Groups are actionable
observations, not positive-check summaries. Supported criteria, matching/conditional calculations,
fact IDs and titles are not grouping or priority references. When both lists are empty,
`groups`, `withdrawn` and `priority` must all be `[]`; positive checks and ordinary limits can
still be summarized, and all facts, assessments and calculations remain visible. Invalid answers
are refused, not automatically stripped or converted into a no-concern result. Existing failed
runs remain failed; this development change needs fresh exact-build live verification.

For more context, use `support read RUN --module NAME` with one of:

- `--block-id ID` or `--fact-id ID`, repeatable;
- `--facts --offset N`, to page through the module's facts;
- `--assessments` or `--calculations`, to page through that module's full appraisal records;
- `--query-file FILE`, for a confidential search string; `--query` is for general headings only.

Results expose `total`, `next_offset` and `next_fragment_offset`. Pass the latter cursors as
`--offset N --fragment-offset N`; null `next_offset` means finished. Each read's pretty-printed
JSON is bounded to 12,000 characters. A single oversized record is returned in consecutive
`fragments` of serialized JSON, with character offsets; concatenate those texts unchanged and
parse the result to reconstruct the full record. No quotes, counterevidence or assumptions are
silently shortened. Large consolidations switch from inline records to indices plus read commands.
All their assessment/calculation pages and fragments must have been supplied within the current
consolidation task before submission. Missing context does not spend a repair attempt. This is a
delivery check, not proof of model attention or understanding. Other task-context overflows still
stop the affected module visibly.
Evidence uses `{block_id, quote}` with exact substring matching. Source matching and provided-block
counts do not prove semantic correctness or attention. Hermes conversation history is not a hard
module-isolation boundary; task payloads exclude other modules' criticisms.

Extraction chunks keep consecutive native table cells from the same row together. An intact
row larger than the source-task budget is refused explicitly, not truncated. Each extraction
fact must cite only the current task's block IDs; earlier/adjacent chunks remain available for
their own extraction tasks and later appraisal. A refusal names the fact/evidence field without
printing its private content. The two-refusal stop and preserved rejected submissions remain.

For new PDF snapshots, `pdf-layout-whitespace-v1` collapses extracted layout whitespace in
`block.text` before it is saved. Exact quotes must match that immutable text. Changed blocks
also retain `extracted_text`, the original extracted layout, shown separately in the dossier.
This is not PDF-byte reconstruction, OCR, dehyphenation or word/punctuation/numeric-token repair.
Submitted answers are never normalized or fuzzy-matched. Other formats and existing snapshots
retain their original quote policy; old failures are not reclassified by this change.

## Statistical checks

DOCX tables preserve empty cells, spans and merge origins. Markdown tables preserve cell positions.
PDF automatic table geometry now uses visible ruled grids only. Text alignment is not promoted
into native cells: on ordinary prose pages it can cut printed words into spurious table columns.
Borderless tables remain in extracted page text and require human layout review; prefer native
DOCX/Markdown tables when reliable table geometry is needed. This limitation remains explicit
in each PDF's source/module scope and does not certify the remaining prose or infer a defect.
PDF table extraction retains page/geometry, but is not certified; ambiguous tables block dependent
numeric inputs, including flattened text on their page. Scans/figures are not read and no OCR runs.
The source snapshot and extraction warnings remain in the dossier.

`conditional` is not a numerical-agreement verdict. Declared tests, ratios/intervals and inequality
comparisons remain conditional even when the selected-input calculation differs from the printed
value. Inspect the displayed outputs, reported value/relation, assumptions and exact source
bindings; the full calculation JSON records `comparison.numerical_match` separately. A false
numerical-match value is not automatically a confirmed manuscript error, and a conditional label
is not a successful check. These records remain available even with no final observation. Human
numerical-claim/coverage review must not be limited to the observation list.

The calculator registry is deliberately closed: exclusive count sums, unweighted percentages,
unadjusted 2×2 ratios, declared Pearson/Yates or Fisher variants, independent Student/Welch tests,
p-values from declared z/t/chi-square/F statistics, and normal/t intervals from sufficient inputs.
See the task's calculator catalogue for required names and parameters. Every input must bind an
exact numeric token to manuscript evidence; method/population evidence and assumptions are required.
For example, a numeric input is `{"value":"20","evidence":[{"block_id":"ID","quote":"20"}]}`.
In answer contract 4, models do not supply `reported.relation` or `source_operator`. Python
reads literal qualifiers from the original source block and decides comparisons. Shortening
a quote cannot hide a printed inequality or turn part of `150` into a supposed `50`. Operands
must be point values, not bounds; ambiguous source qualifiers or unrepresentable numbers are
refused. Missing literal inputs require omitting the entire replay with an explicit limit,
not dropping terms or changing the reported quantity to force a comparison.

Calculators record formulas, inputs, outputs, variants, assumptions and provenance. Since b13,
integer sums accumulate exactly and reject totals above `2**53`; percentages compare integer
count ratios by cross multiplication against the exact reported decimal and its precision.
Statistical comparisons use the decimal representation of the saved float result, not a fixed
absolute epsilon or an arbitrary-precision statistical calculation. Records name the comparison
basis and retain both approximate float `rounding_tolerance` and exact-string
`rounding_tolerance_decimal`; the latter can remain nonzero when the float metadata underflows.
Reported decimal exponents outside -324 through 308 are refused. Historical records/exports
are not recalculated or migrated. Statistical replays from summaries are conditional even
when their numbers differ. Undefined ratios, missing variances, unknown pairing, arbitrary
continuity corrections, weighted-percent replays and unsupported adjusted/pooled analyses are not
reconstructed. An arithmetic mismatch does not certify its input interpretation or scientific
importance. Test appropriateness and inferential interpretation remain reasoned model appraisals.

## Reading and recording results

For modules with calculations, the dossier starts with a compact numerical comparison table:
reported token and source-derived relation, saved computed value, numerical agreement on the
selected inputs, and comparison status. **Conditional does not mean matching**: conditional
replays can agree or differ, and neither outcome establishes input roles or scientific validity.
No finding, priority or reviewer decision is created by this display. All replays remain in
saved order, including agreements and uncompared calculations. Computed values are displayed as
saved rather than rounded again; reported numeric tokens are preserved. A missing historical
agreement flag is shown as unrecorded, never inferred from the status label.

Each calculation links to its full record, where inputs, outputs, source evidence, assumptions
and saved JSON remain available in expandable details. The Markdown export contains the same
overview and full records. English/Korean navigation is deterministic. Answer contract 9 adds
the overview labels for other user-selected languages; old custom-language snapshots without
these labels keep their detailed view, while old English/Korean snapshots can use display-only
defaults. Rendering does not migrate saved data, change source text or overwrite earlier exports.

The chat summary shows up to three priority observations and actual totals. The dossier includes
reconstructions, source-linked connections, criterion assessments, calculations, withdrawn concerns,
limits, original extracted source, and reviewer notes. It distinguishes:

- `calculated_discrepancy`: calculator mismatch under explicit input selections;
- `reporting_gap`: important information not located, not proof a procedure was not performed;
- `methodological_concern`: evidence-backed but provisional interpretation;
- `not_assessable`: insufficient manuscript evidence, not a criticism or clean bill of health.

Do not apply reporting checklists as universal validity scores. SR, ScR and narrative reviews have
different purposes; qualitative validation practices depend on the approach. Citation identity is
not content validation, and ethics/legal disagreement is not itself a methodological defect.

Record decisions only if the reviewer supplies them:

```text
creview support record RUN OBSERVATION_ID accepted --words-file FILE
creview support record RUN run note --words-file FILE
```

Other dispositions are `edited`, `rejected`, and `deferred`. Hermes transcript checks verify the
quoted words, not their interpretation. Outside Hermes, records explicitly say they are unverified.
No model rationale is automatically attributed to a reviewer who merely accepted an observation.

Each export uses a new private directory, containing `dossier.html`, `dossier.md`, `reviewer-notes.md`,
`support.json`, and `receipt.json`. Existing directories are never overwritten. HTML is static,
escaped, self-contained and has no external assets. No browser application or server starts.
Verify integrity with `creview receipts verify RECEIPT`. Receipts are self-reported provenance,
not confidentiality or scientific-validity certificates. Share confidential dossiers only through
the reviewer's explicitly authorized private channel; existing services are not changed.

## Qualification and legacy compatibility

All branches remain `not_qualified` until repeated human audits are complete. Evaluate each branch
on medical cases with planted issues and clean controls, three repetitions each, comparing ordinary
Hermes on the same model. Measure unsupported alerts, missed issues, extraction fidelity, checking
time and run variability. The candidate targets are 90% concern precision, 80% seeded-issue recall
per branch, and zero unsupported computed-error verdicts. Do not tune against private keys in model
context or send those keys to the inference environment.

On the evaluator's machine, `creview support score AUDIT.json` scores human judgments. It is refused
inside a Hermes session. The audit names `protocol`, `identity.runner` (package sums), `reviewer`,
hardware details and workflow checks. Each run names `case_id`, `module`, `control`, `repetition`
(1–3), the exported `support.json` as `artifact`, its `artifact_sha256`, private-key
`expected_issue_ids`, `coverage_reviewed: true`, and judgments for every final observation.
Judgments contain `id`, `valid`, `matches`, `rationale` and `contains_computed_error_claim`.
Any numerical-error claim requires `computed_supported: true` as well as a valid judgment,
regardless of its observation kind. Calculated/linked observations cannot opt out of this check.
Each run also requires `numerical_claims_reviewed: true` and
`other_numerical_error_claims_supported: true`, covering summaries and appraisal text outside
the final observations. Leave unresolved fields null; never guess a negative answer.

The audit must reference the frozen key-free corpus manifest and original evaluation batch,
with their hashes. Selecting or running engineering inputs does not require human preapproval.
The original `independently_reviewed` label is descriptive and must not be rewritten later;
a genuine offline audit may happen after the run. A human must still record
`corpus.source_only_validated`, `corpus.representative_medical_cases` and
`corpus.validation_reviewer` after independent source review. Every corpus case must have all
three support and ordinary-Hermes baseline repetitions in that batch. Published-article batches
are engineering evidence only, not seeded-error/clean-control qualification. Outputs are bound to its
run IDs, hashes, manuscript, exact build, local model/endpoint and configured context length.

Record actual `checking_seconds` and `baseline_checking_seconds`, the same `baseline_model`,
`baseline_reviewed: true` and nonblank `baseline_review_notes`. Include hashed baseline output
and result files; the scorer checks them against the original batch, required runtime/trace
checks and distinct baseline sessions. Naming a model and entering a time is insufficient.
Use `tests/test_support_qualification.py` only as a schema example, never as qualification evidence.
Hardware keys: `hardware`, `weights`, `quantization`, `runtime`, `context_length`, `peak_memory`.
Workflow flags: `source_binding`, `local_routes`, `interruption_resume`, `module_independence`,
`poor_extraction`, `reviewer_attribution`, `dossier_fidelity`, `language_settings`.

Missing provenance/judgments, changed artifacts/builds, insufficient coverage/repetition, and failed modules
keep qualification false. Human assertions are not independently authenticated. Release gates
require the new protocol and exact wheel identity; old scan scores cannot open them.

`creview scan`, old design profiles, `creview hermes smoke`, and the earlier qualification scripts
remain explicitly invoked legacy interfaces. They are not the default workflow or evidence for
these new modules. No historical records, running services or closed-review-pi files are migrated.
