# Medical-methods pilot results — 2026-10-28

The current build is **not deployment-ready**. On jkworkstation's real Hermes/Qwen stack,
five of twelve modules stopped on structured-submission errors. Seven finished appraisal and
export, but were marked `partial`. None passed the strict engineering-completeness gate.
These results do not qualify a module or establish scientific concern precision/recall.

## Configuration and scope

- Protocol: `medical-methods-v1`, package `0.9.0b1`.
- Candidate sums: `edb814c8bbb9285c3acbf37387c1e08af4db49090295c881ad4a55015e1f97d0`.
- Wheel SHA256: `be5bf208526d1db3eb042796accc1f126d7af2821b94bcebde9650aff3ec9c14`.
- Corrected harness SHA256: `856190f3be57d760512213ac6f9a7fb09b89457e3b7f58b7818b8ea5a2ae1286`.
- Hermes `0.21.5+7498.gebadb54`, upstream `ebadb546`; Hermes Python 3.14.7.
- Qwen3.8-Flash-Next, existing Strata IQ3_S engine, int8 KV; gateway model alias
  `qwen3.8-flash-next`. Main and auxiliary inference pinned to the private gateway.
- Configured/advertised context: 262144 tokens. No model-server settings changed.
- Isolated creview runtime: Python 3.14.2, locked NumPy 2.3.5 / SciPy 1.16.3 /
  pdfplumber 0.11.9. Dependency installation succeeded.
- Twelve invented Markdown manuscripts, 313–371 words each, one selected branch per case,
  fresh private profiles, explicit English response setting, no reviewer decisions scripted.
- Cases ran serially from 12:20:49 to 12:50:52 KST, approximately 30 minutes total.
  Individual times include profile/runtime preparation, inference, tools, pause/resume and export;
  they are not pure inference timings or a full-length-paper latency benchmark.

The manuscripts have comparison and seeded variants, but comparison cases are not independently
validated error-free controls. The evaluator-only intended issues were not transferred to
jkworkstation, included in prompts, or added to this repository. No external literature lookup
or direct model API inference was used by the harness; Hermes performed the model work.

## Corrected batch

`partial` below means the appraisal reached its terminal state and a dossier was exported;
it is not an engineering pass. Zero observations in a stopped module is not a clean review.

| Branch | Cases | Terminal states | Retained observations | Seconds |
| --- | --- | --- | --- | --- |
| Statistics | 01 / 02 | failed / failed | 0 / 0 | 156.00 / 128.70 |
| Qualitative study | 03 / 04 | partial / partial | 2 / 1 | 158.96 / 167.72 |
| Systematic review | 05 / 06 | failed / failed | 0 / 0 | 175.62 / 125.88 |
| Scoping review | 07 / 08 | failed / partial | 0 / 1 | 145.13 / 210.90 |
| Narrative review | 09 / 10 | partial / partial | 0 / 1 | 148.93 / 115.27 |
| Logic | 11 / 12 | partial / partial | 0 / 1 | 137.00 / 132.94 |

All twelve cases passed runner identity, source hash/quote binding, same-session resumption,
selected-module scope, absence of invented reviewer decisions, absence of legacy scans,
export-file existence and receipt verification. All twelve receipts were also verified after
copying the artifacts back to the evaluator machine. These checks do not validate meanings.

All source blocks were issued, with no extraction warnings for these Markdown cases. Issuing
blocks does not prove that the model attended to or interpreted every passage correctly.

No case reached the 900-second timeout. The five module stops followed schema refusals, not
gateway unavailability or a switch of provider. Failed-run dossiers differ from saved `run.json`
in the task cursor only, so their exact-snapshot-equality check fails despite valid file receipts.

## What the outputs show—and do not show

Qualitative, scoping, narrative and logic outputs include localized internal-contradiction
observations, grounded in the supplied manuscript rather than claims to have inspected raw
interviews, external studies or real law. Related narrative/logic concerns were grouped rather
than emitted once per criterion. The narrative and logic comparison cases retained no concerns.

The qualitative comparison retained two reporting questions about sample-adequacy reasoning
and the sparse display of quotations. Its abbreviated form makes automatic false-positive
classification inappropriate; a human must judge applicability, usefulness and importance.
Observation counts in the table are not precision estimates.

The stopped statistics/systematic-review cases do not establish that the local model cannot
reason about those subjects: they did not complete the tool contract needed to assess that.
The original diagnostic batch successfully calculated a table percentage in one attempt, but
that is neither a reliable traversal nor medical-quality qualification.

## Three corrective work areas

1. **Make the submission contract usable by the local model.** Four final stops report
   `evidence must be a list of {block_id, quote}`; one reports an invalid calculator output.
   The final answers show `method_evidence` supplied as a string, or formulas such as
   `sum(parts)` used as output names. The calculator catalogue currently supplies formulas but
   does not enumerate output keys. Supply complete typed examples/output enums and field-path
   errors. Keep exact-source validation; increasing retries alone would mask the defect.
2. **Separate scope limitations from incomplete coverage, and make snapshots consistent.**
   Every finished module became partial because extraction `limits` included ordinary caveats
   such as absent raw interviews/external originals. This is distinct from an extractor or
   context-budget failure. Preserve such caveats visibly without conflating them with missing
   manuscript coverage. Also fix cursor mutation during phase calculation/rendering: the five
   failed-run exports advance the cursor while saved state retains its earlier value. Do not
   resolve this by claiming receipt integrity proves snapshot equality.
3. **Deduplicate the reviewer-facing presentation.** In the original diagnostic statistics
   dossier, a model observation and an automatically appended calculated-discrepancy observation
   describe the same percentage mismatch. Consolidation currently appends each arithmetic
   mismatch after grouping model concerns, without attaching it to an existing observation.
   Present one issue with its calculation evidence. One diagnostic dossier also retains the
   literal navigation token `calculation_note`, which needs a meaningful user-facing label.

Relevant implementation locations: `support/calculators.py` (catalogue/validation),
`support/workflow.py` (`_phase`, consolidation and status assignment), and `support/render.py`
(snapshot export). Product code was **not** changed to make these test results pass.

Fix these contracts and rerun the same pilot before expanding features or claiming readiness.
After that, independently reviewed, full-length cases, poor extraction, repeated runs,
same-model baselines, hardware/workflow audits and human semantic judgments are still required.

## Interrupted batch and harness correction

The first batch uncovered a runner defect: its terminal-state set omitted `partial`, so it
requested extra continuations/exports for an already finished case. That batch was stopped
during its third case, terminating only its own runner and child process group. Its artifacts
and an interruption record were retained. Its second-case missing-dossier claim is a harness
error and must not be attributed to the model; its third case is censored.

The corrected runner treats partial as terminal while still failing completeness. A regression
test covers this distinction. The fresh twelve-case batch used the identical candidate wheel,
model settings, manuscripts, prompts and criteria. Only the test harness changed. Earlier
failures were not deleted or converted into passes.

Local verification with the locked runtime dependencies and installed candidate wheel:
**248 tests passed**, including the HTTP/socket test previously blocked by sandbox policy.
Ruff passed. The initial fresh-environment launcher check failed before the candidate wheel
was installed there; installing that wheel and rerunning resolved the environment setup issue.

## Artifacts

- Readable local index (manuscript + HTML/Markdown links):
  `/tmp/creview-support-results.U24CpP6o/README.md`.
- Corrected remote batch:
  `/tmp/creview-support-runtime.ZziaUxWi/results-v2/batch.json` on jkworkstation.
- Corrected artifact archive, copied locally and hash-matched:
  `/tmp/creview-support-results.U24CpP6o/results-v2-artifacts.tar.gz`.
- Archive SHA256: `ed5a67fc769478a435fff6488a701d87ab07b8d7c28a11fc91c7404d7db3a205`.
- Original diagnostic artifacts and interruption record remain beside the local index.

The regular Hermes installation, existing review profiles/stores and existing services were
not replaced or restarted. Existing gateway/model process IDs were unchanged at the final
check. No browser service was started. Profile checks are guardrails, not an OS-enforced
network-isolation certificate. All branches remain `not_qualified`; the release gate stays closed.
