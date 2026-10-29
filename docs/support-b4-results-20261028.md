# Medical support b4 diagnostic — 2026-10-28

The frozen b4 matrix finished at **11/12 engineering passes**, retaining one SR failure.
A separate inspection confirmed actual statistics-task output truncation. This build is not
deployment-ready or medically qualified; completion counts are not precision/recall scores.

## Exact candidate

- Version `0.9.0b4`, protocol `medical-methods-v1`, answer contract 4.
- Runner `becf7ad4a5d77f1fc2fb500923ba8eeba1da822d0852d6a7511837b87ffdf1fb`.
- Wheel SHA256 `a2a2b01946c06c799bcfcff7c747bdc2ebb5e100315dbe365b7b7b151e365393`.
- Harness `7739fd82a9c2398d06106c995b2ede466cb1aa18567590599015c525727811ce`.
- Existing jkworkstation Hermes/Qwen private stack, context 262144, disposable Python 3.14.2
  runtime `/tmp/creview-support-runtime.fIobqKL4`. No regular profile or service was changed.
- Serial run: 07:11:16–07:38:59 UTC (16:11:16–16:38:59 KST), twelve short invented English
  Markdown papers. These are neither independently validated controls nor full-length cases.

## Results

| Branch | Cases | Status | Observations | Calculations | Seconds |
| --- | --- | --- | --- | --- | --- |
| Statistics | 01 / 02 | complete / complete | 0 / 1 | 3 / 3 | 125.74 / 176.63 |
| Qualitative study | 03 / 04 | complete / complete | 1 / 1 | 0 / 0 | 133.39 / 136.25 |
| Systematic review | 05 / 06 | failed / complete | 0 / 1 | 0 / 1 | 144.76 / 171.77 |
| Scoping review | 07 / 08 | complete / complete | 0 / 1 | 2 / 2 | 149.69 / 138.27 |
| Narrative review | 09 / 10 | complete / complete | 0 / 1 | 0 / 0 | 100.75 / 125.18 |
| Logic | 11 / 12 | complete / complete | 0 / 1 | 0 / 0 | 122.73 / 138.21 |

All twelve passed recorded runner/source identity, exact quotation binding, same-run resumption,
explicit module scope, no invented reviewer dispositions, no legacy scan, export/receipt checks
and equality of the saved/exported snapshot. Only case 05 failed module completion. These are
necessary integrity signals, not proof of attention, appropriate inference or full source review.
Wall times include setup, tools, inference, pause/resume and export, not pure model latency.

Case 05's first refusal identified a calculation's inexact quote. The repair then failed because
its numeric value was not literally printed in the bound quote. Both rejected submissions and
diagnostics are preserved; no unsupported calculation was committed. The successor diagnoses
independently detectable source/numeric problems together, without adding retries or silently
removing calculations. Whether this helps the model is a new-build live question.

Case 06 completes here after failing b3, while case 05 now fails. Observation counts also vary
between builds. This is not evidence of stable medical accuracy or a basis for labeling the
toy comparison papers clean. Every validity/coverage judgment remains for independent review.

## Confirmed delivery limit

The b4 statistics appraisal prints approximately 145,489 characters even without a fact index.
The inspected Hermes runtime captures 50,000 terminal characters by default. A read-only actual
case-01 session trace contains one spill/truncation event in five next/read terminal results;
the largest captured result is 49,864 characters. Hermes saved the overflow, but direct delivery
was incomplete. The trace count does not establish whether the model recovered every omitted
part. The old engineering harness did not certify complete tool-output delivery.

The successor factors repeated schema definitions, bounds the entire printed task and requires
explicit compatible capture limits. It has a new runner identity and disposable environment;
these b4 results cannot qualify it. See [the readiness tracker](deployment-readiness.md).

## Preserved evaluator evidence

- Archive SHA256 `e9b6b6b43033d076c4e1de14fa8b37a8cae10e3f3a94cc306c8b8d7c7db92b19`.
- Evaluator directory `/tmp/creview-support-b4-results.ZRfqQzXp`: 270 allowlisted regular files,
  excluding credentials, profile configuration and session databases. Original manuscripts,
  task answers/refusals, run snapshots, exports and logs are retained.
- All twelve export receipts verified against independently installed original-wheel sums.
  Static/headless packet `audit` contains twelve originals and seven O-labeled proposals.
  Human judgments, private-key fields and checking times remain blank; no keys were imported,
  sent to the model host or served over a network.
- Read-only runtime/capture observations: `evals/deployment/b4-runtime-observations.json`.
  Weight hashes and attributable peak memory remain missing; process snapshots are not model
  hardware recommendations or isolated peaks.

Normal-length/format/recovery/scope/language testing on the exact successor, independent realistic
corpus validation, three paired repetitions, baselines and human audits are still required.
