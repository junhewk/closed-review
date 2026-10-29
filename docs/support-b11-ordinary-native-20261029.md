# B11 full-length native-format results — 2026-10-29 KST

Historical exact-build evidence. See [b13](support-b13-development-20261029.md) for the current
candidate; b11 format passes do not qualify that new identity.

All three support/baseline pairs finished engineering-passed at 16:20:43 UTC on October 28.
These are three formats of the **same one invented 3,777-word article**, not three independent
medical studies or a formal repeated qualification. Native Word/PDF fixtures span eight pages
and contain the same three tables. All medical judgments and human checking times remain blank.

| Format | Support seconds | Observations / calculations | Baseline seconds | Source blocks supplied |
| --- | ---: | ---: | ---: | ---: |
| Markdown | 426.79 | 0 / 16 | 104.38 | 154 / 154 |
| DOCX | 415.24 | 0 / 13 | 80.34 | 151 / 151 |
| PDF | 455.43 | 0 / 11 | 105.09 | 240 / 240 |

Every module completed without module failure; PDF had one repaired refused task. The zero
observation counts do not prove absence of issues. Inference timings are not human checking
times, evidence of usefulness or exclusive-load/minimum-hardware benchmarks.

## Exact identity and preserved artifacts

- Version `0.9.0b11`, runner
  `5a37d154ee4efa99b6d7fdbe995507de45df142dc1a8ccad27a09371411e55da`.
- Wheel SHA256 `07d1c1abc21393bdb28be683dc73b6a60c32f2fc2a0c172b62ca4e3b06ba0590`;
  checkpoint-aware harness-2 bundle and source files unchanged.
- Local `/tmp/creview-support-b11-ordinary-native-results.OUBhPpIl`, 108 regular allowlisted
  archive files, 3,898,064 bytes; archive SHA256
  `f4f01208e1360985a2d49421aa444ecbe12814c375d55929ef3ef4c11638c003`.
- Three export receipts independently verified against original b11 wheel sums. All six
  support/baseline manuscript copies and three actual baseline output hashes verified.
  `native-audit` retains original files, dossiers and baselines with blank human fields.
  No private keys, configurations or state databases were transferred; no server started.

## Reproduction and source preservation

The evaluator-only checker reproduced all three saved snapshots and **40 calculations** using
byte-matched parser/calculator code. Report `replay-checks.json`, SHA256
`d20cbc6a6c4b037f68ea5418d202d13ec0250593affd12ea582c5ff8257e9372`.
This verifies saved-record consistency, not numerical agreement, semantic input roles or validity.

Comparing the actual saved snapshots with the original Markdown fixture found every expected
paragraph in order and all three table grids equal under the predeclared fixture comparison
policy. Strict whitespace-only checks pass for Markdown/DOCX. For PDF they remain **false**:
its raw extraction wraps some letter-hyphen-letter text across lines. The separate evaluator-only
`fixture-pdf-retained-hyphen-layout-v1` comparison joins just those raw line wraps while retaining
the printed hyphen. It does not join digits, rewrite words/numbers/headers, change saved snapshots
or repair submitted quotes. Both comparison results remain recorded. This does not certify all
PDF extraction, invisible content or borderless-table geometry.

Native verification `native-verification.json`, SHA256
`dc3d841c42724125b62de492c92ab1c0132b58d8aa0625be2e12ea6bdda57d9d`.
The original sources, old strict failures and earlier candidate failures stay preserved.

The docx read-only guidance also prompted a separate Pandoc 3.1.3 check. Its structured AST
retains the manuscript title as metadata and matches all **62 paragraph texts in order and
three table grids**, without word/punctuation/numeric repair. Word bytes remain unchanged.
A raw GFM readback comparison failed because nonstandalone output omits title metadata and
encodes bold table headers/brackets as Markdown syntax. That failed diagnostic remains alongside
the separate AST comparison; it is not relabeled as a passed source check or a manuscript defect.

## Analytical coverage is not established

The runs selected 16, 13 and 11 value-only replay signatures, with no repeats of those signatures
within a run; ten signatures are shared by all three and the union contains nineteen. These
signatures omit provenance and semantic input roles: identical values do not prove the same
quantity, and differing signatures are not automatically missed checks or errors. One stochastic
run per format cannot establish that format caused the difference. Human content/coverage review
and formal repeated cases are still required; block delivery and arithmetic reproduction cannot
substitute for them.

At the time of this format result, the controller advanced to short native fixtures at 16:20:43,
PID `2540958`, while the broader suite/sampler remained active. That suite subsequently
[finished with one compression failure](support-b11-harness2-20261029.md). The unstarted b12
queue was canceled before inference; b13 is a new arithmetic candidate. No release is authorized.

Machine record: `evals/deployment/b11-ordinary-native-evidence-20261029.json`.
