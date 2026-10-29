# B13 full-length native-format results — 2026-10-29 KST

All three support/baseline pairs finished engineering-passed at 18:08:09 UTC on October 28.
These are three formats of the **same invented 3,777-word article**, not three independent
medical studies or a formal repeated qualification. Word/PDF fixtures span eight pages with
the same three tables. Medical judgments and human checking times remain blank.

| Format | Support seconds | Calculations | Baseline seconds | Source blocks supplied |
| --- | ---: | ---: | ---: | ---: |
| Markdown | 403.65 | 19 | 70.48 | 154 / 154 |
| DOCX | 380.50 | 19 | 91.65 | 151 / 151 |
| PDF | 460.28 | 15 | 80.53 | 240 / 240 |

Every module completed without module failure. DOCX and PDF each had one repaired refused
task; those rejected payloads remain. Every run proposed zero observations, which does not
prove absence of issues, complete coverage or useful prioritization. Timings are inference
elapsed times, not human checking times or quality rankings.

## Exact build and archive

- Version `0.9.0b13`, runner
  `60995d277fb664ea7d27eeec00c0d300210a9721486e1d46639c723c2a18c119`.
- Wheel SHA256 `9bbb442968c34f06b1a1b683b157d2e8dfbe8820f0b3a27c63422e899fc72b5e`.
- Complete suite copy `/tmp/creview-support-b13-suite-results.B9NEpb5E`: 261 regular allowlisted
  files, 6,205,161 bytes, archive SHA256
  `95f7316af828455714fd74d4f4e01452a68fab9f998c384c559f35076bb8dd62`.
- The native subset's three receipts, six manuscript copies and three actual baseline output
  hashes independently verify. `native-audit` retains original sources, dossiers and baselines
  with blank human fields. No private keys, profile configurations or session databases were
  transferred; no server was started.

## Source and calculation reproduction

All three saved source snapshots and **53 calculations** reproduce with the exact b13
calculator/parser implementation. Strict saved-versus-fresh source comparisons show zero
differing fields, ignoring only each relocated root file path. This checks record consistency,
not independent formula validation, numerical agreement, semantic input roles or medical validity.
Replay report SHA256:
`5bb5a81a79123eb4a15dc02dff822d838536b7ad2c7dff0f09dbe51b5409de71`.

Against the original Markdown fixture, all expected paragraphs/order and three table grids
match under the predeclared `fixture-pdf-retained-hyphen-layout-v1` comparison. The separate
strict whitespace-only cross-format comparison remains false for PDF because raw extraction
wraps some retained hyphens across lines. The evaluator policy joins just that letter-hyphen
line wrap without deleting the hyphen. It never rewrites manuscript bytes, saved snapshots,
submitted quotations, numeric tokens or input bindings. This cross-format comparison is
distinct from the exact saved-snapshot reproduction above, and does not certify all PDF content.
Native verification report SHA256:
`40b6bef2abc2e550c14af3cff141577620e3c8b92680fcc11a3038565607378a`.

The DOCX skill's read-only guidance prompted a separate Pandoc check of the exact Word fixture.
Its fresh AST matches the independently interpreted 62 paragraphs and three grids, including
title metadata; source bytes remain unchanged. Both actual Word copies match that fixture's
hash. This is source-content continuity, not human fidelity or medical approval.

## Coverage remains unestablished

Value-only replay signatures number 19/19/15, with ten common and 28 in the union. They exclude
provenance and input roles: equal counts or values do not prove equal analytical coverage,
and differing signatures are not automatically missed issues. One stochastic run per format
cannot establish format causation. Human coverage/usefulness review and formal repetitions
remain required. Earlier b11/b12 failures and cross-Python strict diagnostics are preserved,
not upgraded by these passes.

Machine record: `evals/deployment/b13-native-evidence-20261029.json`.
See [the complete b13 candidate record](support-b13-development-20261029.md) for the five other
targeted jobs, complete sampling window and remaining release gates.
