# B11 short native-format pairs — 2026-10-29 KST

One short invented manuscript, three formats, one paired repetition; not three independent
medical studies. All three support runs and actual same-model baselines passed engineering
checks at 16:31:45 UTC on October 28. Human judgments remain blank.

| Format | Support seconds | Observations / calculations | Baseline seconds |
| --- | ---: | ---: | ---: |
| Markdown | 141.92 | 1 / 4 | 55.09 |
| DOCX | 183.79 | 1 / 6 | 48.49 |
| PDF | 179.83 | 1 / 5 | 53.54 |

All source blocks were supplied, six appraisals completed, one 5×3 grid preserved and no module
failures or refused answers occurred. Each proposal remains unjudged. Fifteen saved calculations
reproduce. Value-only signatures vary (4/6/5; three common, eight in union); these omit input
roles/provenance and cannot measure misses or establish format causation from stochastic runs.

Copied packet `/tmp/creview-support-b11-short-native-results.dFPcYg1w`, 80 regular allowlisted
files, 1,228,633 bytes, archive SHA256
`51d951cbb79f13f522c2222b3392243e54050ac7ca1433a03ab22c66b3a6c075`.
Three receipts, six source copies and three actual baseline output hashes independently verify.
Expected paragraphs, order and grid match in every format. Read-only Pandoc Word AST also
matches eleven paragraphs and one grid, including title metadata; the source was unchanged.
No source translation or private answer key was created/transferred and no server was started.

## Strict PDF mismatch retained, runtime cause diagnosed

The local Python 3.11.15 saved-source comparison passes Markdown/DOCX but **fails PDF** at exactly
`/tables/0/bbox/1`: saved `403.93571428571425`, fresh `403.9357142857143`, adjacent binary64 values.
No text, cell or other field differs. The same pdfplumber 0.11.9 function source and seven input
edges produce the difference using ordinary `sum`. Python changed its float summation algorithm
in 3.12. [Primary Python documentation](https://docs.python.org/3/library/functions.html#sum)

Read-only parsing three times in the original frozen Python 3.14.2 runtime reproduces the strict
canonical JSON snapshot exactly, ignoring only the relocated root file path. This is separate
runtime-matched evidence, not a reclassification of the local strict failures. No coordinate
tolerance, source rewrite, quote normalization, model call or service/profile change was applied.
The failed report and subsequent diagnostic report both remain exit-1 artifacts.

Evaluator-only checker diagnostics now list differing JSON pointers and flag bbox-only differences
for inspection, without accepting them. They examine all differences even when the printed list
is capped, distinguish boolean/numeric JSON and do not expose manuscript values. Nine added unit
tests pass; 840 tests passed against the unchanged b12 wheel before the separate b13 arithmetic
change. This evaluator script is not transferred to the model host.

Diagnostic record SHA256
`9ca4e10498ecd466cab9aa9a97a1581687fe5405dd5b1ff46f9ba89cfdf1337c`.
Initial failed report SHA256
`2ac12b82dd6bfb3a09f134540c84c9c771f2e1a0f4a51f4fd2e959289f487b7b`;
field-diagnostic report SHA256
`c063ddb05d9871f43dce641035bebbecf46eb0e63c85d00d32f598b44faa1d8d`.

Machine record: `evals/deployment/b11-short-native-evidence-20261029.json`. Source-role approval,
medical fidelity, useful prioritization, repeated coverage and human checking times remain
unestablished. Record reproduction is not mathematical or clinical validation; release stays closed.
