# Medical support b8 native-format diagnostic — 2026-10-28

The diagnostic failed overall: Markdown and DOCX support completed, but PDF extraction stopped
after two exact-quotation refusals. All three ordinary-Hermes baseline runs passed their
engineering checks. The failed support result is preserved, not promoted by a later fix.

## Exact input and candidate

- Package `0.9.0b8`, answer contract 7, runner
  `fc7e7ee468171179c8bcc160f6251399903d528879ca87d89fe8d9017e03c9ac`.
- Wheel SHA256 `4afa0716836f65c0c9a58598ee11fac8c882bd31d08e4abf88ab338861bdb1c5`.
- Isolated workstation runtime `/tmp/creview-support-runtime.t5MkgBGS`, Python 3.14.2,
  existing private Hermes/Qwen stack and configured context 262144.
- Three formats of the same invented short article, not three independent studies. One
  engineering repetition with actual paired baselines; corpus approval remains false.
- Queue started the diagnostic only after b7 ended. It finished at 10:32:28 UTC, exit 1.

| Format | Support status | Support seconds | Baseline seconds | Observations / calculations |
| --- | --- | --- | --- | --- |
| Markdown | complete | 151.59 | 80.94 | 1 / 5 |
| DOCX native table | complete | 181.44 | 66.11 | 1 / 5 |
| Rendered PDF | failed during extraction | 84.91 | 46.98 | 0 / 0 |

The source files preserve the expected paragraphs and 5-by-3 table grid. The Word/PDF render
received an agent visual layout check, not independent medical review. All original bytes,
generator versions and hashes are recorded in `evals/deployment/native-format-fixture-20261028.json`.
The baselines' trace checks are necessary signals, not proof of semantic independence or quality.
A failed early support run cannot be compared with a completed baseline as reviewer time saved.

## PDF failure and targeted successor change

The PDF had 37 source blocks, all issued, with no detected geometry warning or declared gap.
Its general PDF caution correctly remained a scope limit after the b8 status fix. The new
failure was quotation copying: extracted paragraphs retained layout line breaks while the
model supplied reflowed text. The first answer had nine exact-substring mismatches. The repair
fixed eight but left `All 200 patients...` without the extracted break after `200`, so the second
refusal stopped the module. Both rejected payloads and the failed export remain unchanged.

B9 creates new PDF snapshots with whitespace-only canonical block text and retains original
extracted layout separately. It does not normalize submitted answers, relocate quotes, repair
hyphenation or alter words, punctuation or numeric tokens. Exact matching still uses the saved
block text. A read-only replay of the first rejected payload against a fresh canonical snapshot
passes reference checks with the same IDs; the old source still rejects it and its run hash
is unchanged. This is a targeted mechanical check, not model or medical-quality qualification.

## Evaluator evidence

Archive SHA256:
`efe69e1c55da68d912d5543dc30eb3ff31f8981a4fa16aa9c13533467cfc73f4`.
Local directory `/tmp/creview-support-b8-format-results.nWRQ0VAH` contains 78 regular allowlisted
files, 989,616 unpacked bytes, excluding credentials/configuration/session databases. All three
export receipts verified against independent original-wheel reference sums, including the
failed PDF dossier.

Its `audit` packet preserves all three original formats, two O-labeled proposals and the three
actual paired baseline outputs. Human judgments, expected issues, independent corpus approval
and checking times remain blank. No keys were imported, no server was started and no release
was approved. See [deployment readiness](deployment-readiness.md) for the exact b9 follow-up.
