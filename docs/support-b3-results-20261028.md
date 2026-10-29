# Medical support b3 results — 2026-10-28

The frozen b3 matrix passed 11/12 short synthetic engineering cases. One systematic-review
case stopped on calculator submissions. This candidate is **not deployment-ready or qualified**.
Observation counts are not medical precision, recall or usefulness scores.

## Exact build and run

- `0.9.0b3`, protocol `medical-methods-v1`, answer contract 3.
- Runner: `a81c219d65334c60730acc81322aa94d85f51b032662e9007e8b7633df59145f`.
- Wheel SHA256: `461fc0793348484782b9bac3b0a03275a23ec149c9d0d11f34207c47b99a0b4d`.
- Matrix harness: `a9f0a6b83e2439050ef7a0379ceabc652a23248c79698cc8e147cc5a571f3075`.
- Existing jkworkstation Hermes `0.21.5+7498.gebadb54`, private Qwen gateway to loopback
  Strata, IQ3_S pack, int8 KV, maximum context 262144. Dedicated Python 3.14.2 environment.
- Serial matrix: 04:47:58–05:19:26 UTC (13:47:58–14:19:26 KST). Wall times include
  setup, tools, inference, deliberate pause/resume and export, not pure inference.
- Twelve invented 313–371-word English Markdown manuscripts, fresh profiles, one branch
  selected per article. They are not independently validated controls or full-length cases.
  No normal installation, profile, gateway or model service was changed or restarted.

## Matrix

| Branch | Cases | Status | Observations | Calculations | Seconds |
| --- | --- | --- | --- | --- | --- |
| Statistics | 01 / 02 | complete / complete | 0 / 1 | 5 / 5 | 130.91 / 174.78 |
| Qualitative study | 03 / 04 | complete / complete | 0 / 3 | 0 / 0 | 168.87 / 149.73 |
| Systematic review | 05 / 06 | complete / failed | 2 / 0 | 9 / 1 | 176.36 / 174.31 |
| Scoping review | 07 / 08 | complete / complete | 0 / 1 | 2 / 2 | 173.93 / 204.48 |
| Narrative review | 09 / 10 | complete / complete | 0 / 1 | 0 / 0 | 107.85 / 141.52 |
| Logic | 11 / 12 | complete / complete | 0 / 1 | 0 / 0 | 147.86 / 137.65 |

All twelve passed recorded runner/source identity, exact quotation binding, same-run resumption,
explicit module scope, no invented reviewer decisions, no legacy scan, export-file/receipt
integrity and saved/exported snapshot equality. Only module completion failed in case 06.
All twelve receipts were also verified after copying to the evaluator machine. These checks
do not establish interpretation, attention, scientific validity or complete issue detection.

All three b2 stops (05, 07, 08) complete under b3. However, case 06 passed b2 and failed b3:
11/12 is not proof of repeatable reliability. The two case-05 and three case-04 observations
remain unjudged proposals, not established problems or automatically measured false alerts.

## Failure retained

Case 06 supplied numeric `4` bound to printed `four`. The validator correctly identified
`$.calculations[1].inputs.part_4` as lacking its exact source token. The agent then dropped
that term and changed the incomplete subtotal's reported comparison to `< 120`; no `<` occurs
in the quote. This changed the calculation's meaning rather than repairing the missing input.
Both rejected payloads and diagnostics are preserved; neither invalid proposal was committed.

Next revision: make the fallback explicit—omit an unavailable calculation and explain its
limit, never salvage it by dropping terms, changing quantities or inventing inequalities.
Keep exact source/operator checks and bounded refusals. That packaged fix is not claimed here.

## Baseline and poor-source evidence

An ordinary-Hermes case-02 baseline on the same model/context/language/private profile defaults
completed in one invocation, 66.91 seconds. Checks passed for actual local runtime and strict
preflight, unchanged source, real output, structured tool trace, no detected auto-loaded skill,
no support/legacy workflow, and requested model/endpoint/context. Harness:
`97725fa2004b7b0aafd149b45f7401ea4c1e26cdfede7637d65688e336bb226f`.
Output SHA256: `43158d543bc08d075b7ba7e894afee9c978520a1099e2e37e2c63de72e47f8ca`.
This is not a speed ranking or semantic-independence proof. Baseline statements, quotations,
calculations and usefulness need human review; checking times remain blank.

The image-only PDF probe passed in 36.05 seconds: empty extracted text, zero tasks/findings/
calculations, visible warnings, honest `not_assessable` state, one actual dossier and verified
receipt. Its final chat explicitly disclosed unread content and no OCR/vision, not a clean
manuscript. One probe is not general PDF/DOCX extraction or human fidelity qualification.

The initial turn-limit probe observed the deliberate three-turn limit but the harness treated
Hermes's expected status-1 exit as fatal before trying continuation. Its drafted answer, saved
run, logs and failed result remain unchanged. A revised harness narrowly permits this expected
exit only with the new recorded limit event, unchanged run/session and no Python traceback.
Five regression cases cover expected exit, missing event, changed run, traceback and other exit.
New probe results use a new directory; never overwrite the initial failure.

The corrected turn-limit probe finished in 116.89 seconds. It recovered the expected forced
exit and resumed the same saved run; all source/export/receipt checks passed. The statistics
module then stopped on model-proposed `>` operators absent from the quoted numbers. Thus
the overall probe is still failed. Its two rejected payloads show the same ambiguous
`reported.relation` input problem in a second branch; the unfrozen b4 development removes
model-supplied operators entirely. This b3 evidence cannot qualify that new build.

Original probe harness: `3998a7e0136799dda0268b66500d0335bbc038856cca05bd7ebc52de9c99ffde`.
Revised harness: `59301646ce4245ae54658c0601142cfb8d25c3cd8559a53d5220bbf8cdcd8694`.
Compression, scope, injected module failure, Korean and long-source live evidence is still pending.

The new serial evaluation scheduler and offline packet builder support distinct paired
repetitions and hash-bound sources/baselines. Their tests pass; repeated live evaluation has
not run. The short-pilot manifest says `independently_reviewed: false`. Scheduler success on
it is not medical-quality qualification and must not silently relabel it as an approved corpus.

## Preserved evaluator artifacts

- Matrix archive `/tmp/creview-support-b3-matrix-20261028.tar.gz`, SHA256
  `b1b134d889690216317309d3aa558485de5410e38ee734d9a21e841dad3437dd`.
- Baseline/image archive under `/tmp/creview-support-b3-results.l5cPPJY4`, SHA256
  `9cd3b836dc0dd3c4246156b12de575fbea08f888957bbe10f1b1a37ce1a37ca7`.
- Original failed turn-limit archive in that directory, SHA256
  `09ae1b530af2133465d48d8ab37ab8d94b738c8c8e101fe4db19b1f649c29019`.
- Verified packet `/tmp/creview-support-b3-results.l5cPPJY4/comparison-audit`: twelve originals,
  nine O-labeled proposals, full dossiers and the case-02 baseline. All validity judgments,
  private-key fields and checking times remain blank. No evaluator keys were sent to the model
  host and no server started. Collectors exclude credentials, configs and session databases.

The [readiness tracker](deployment-readiness.md) preserves all remaining requirements: calculator
repair, realistic independently reviewed cases, human audits, repetitions, baseline comparisons,
format/long-source/recovery/fidelity tests and model/hardware reproducibility. No release is approved.
