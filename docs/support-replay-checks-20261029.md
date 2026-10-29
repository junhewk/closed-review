# Evaluator-only record reproduction — 2026-10-29 KST

This continuation does not change the frozen b11/b12 wheels, live suites, module criteria,
source matching, model settings, human judgments or release gate. The checker adds no model
job; the pre-existing serial workstation suite continues independently.

Current continuation: b11 is now terminal, b12 was canceled before inference and the separate
[b13 precision candidate](support-b13-development-20261029.md) is running targeted regressions.
The staging/running observations below are historical, not current queue status.

## Gap and check

The ordinary pilot checks exported receipts and ordinary evidence quotes. Those checks alone
do not re-extract the source from the copied manuscript or reproduce every saved calculation.
`scripts/check-support-replays.py` adds a separate offline check of prepared evaluator packets:

- Match the original manuscript, batch, saved run and receipt to independent trusted wheel sums.
- Require identical calculator/parser implementation hashes before interpreting old records.
- Recreate the source snapshot; exclude only its relocated `path`. Do not fix quotes, numbers,
  table geometry, paragraph ordering, warnings or source policies.
- Recalculate every stored replay using its original inputs, method variant, source-derived
  reported relation and assumptions. Compare the entire saved result, including outputs and
  comparison flags. JSON comparison distinguishes booleans from integers.
- Save a NEW report outside the original packet. Read no private answer key or audit template;
  create no findings or human judgments. Existing exports, pass/failure records and reports stay
  intact. The exported reviewer-notes file is hashed as a receipt subject, not interpreted.

The result is **record reproduction, not numerical agreement**, independent mathematical
validation, proof of extraction completeness, input-role correctness or medical validity. A
conditional difference can reproduce correctly. A failed module stays failed even if its saved
records reproduce. Dependencies are recorded as observed; their versions are not an attestation
about the historical execution. This check cannot qualify a release or replace human inspection.

## Verified ordinary-length packet

All six saved source snapshots and **29 calculations** reproduced in the completed b11
ordinary-length packet `/tmp/creview-support-b11-ordinary-results.59Ok30n0/ordinary-audit`.
The original six receipts, twelve manuscript copies and six baseline hashes had already been
independently verified. No baseline/human result was filled by the new checker.

- Artifact runner `5a37d154ee4efa99b6d7fdbe995507de45df142dc1a8ccad27a09371411e55da`.
- Evaluator runner `e95934c9e2be05d432fefb964a1b9beb5728a34ebd781f4df928bdf8daabfe2a`;
  all required replay/parser implementation hashes match the original b11 sums.
- Checker SHA256 `599a9f9bc2b73c077e15ba825c8bf37fccb482d337a0c544de8ffd490dbc2c9e`.
- Report `/tmp/creview-support-b11-ordinary-results.59Ok30n0/replay-checks-v2.json`, SHA256
  `ed97fc700e05aa0ca429d2e764c694140ecfbe9dd38463eee576931ce43bbce9`.
- The earlier development report remains preserved separately, not overwritten or reclassified.

Twenty-nine new unit cases cover all 13 actual workflow-saved calculators, changed but
self-resealed outputs/flags/statuses, source edits, invalid variants/evidence, unchanged input
trees, unsafe paths/symlinks, wrong implementation hashes, no private-audit reads, failed-module
nonpromotion, new-report/no-overwrite rules and mismatch-report preservation. The full suite
passes **831 tests in 75.54 seconds** against the same frozen installed b12 wheel, with source
`pythonpath` disabled. Ruff, lock and diff checks pass. This adds evaluator coverage, not a new
candidate identity or medical qualification.

At 16:18:08 UTC the live b11 native worker `2513422` was confirmed alive with its original start
ticks. Full-length Markdown and DOCX support/baseline pairs had passed; PDF was still running at
the final task, with all 240 source blocks provided, 70 facts, six appraisals and 11 calculations.
That unfinished run is not a pass. Its full native-format results and saved-source comparisons
must still be collected after completion. B12 remains queued behind the entire b11 suite and
sampler. Independent source/test-role approval and formal repeated human audits remain missing.

Usage is documented in [the pilot guide](support-pilot.md#reproduce-saved-source-and-calculation-records).
Machine record: `evals/deployment/replay-checks-evidence-20261029.json`.

Subsequently, all [three full-length native-format pairs](support-b11-ordinary-native-20261029.md)
finished. Their three snapshots and 40 saved calculations also reproduced. This adds finished
format-specific evidence without reclassifying the earlier running observation or human fields.

The [short native-format diagnostic](support-b11-short-native-20261029.md) subsequently exposed
one strict cross-Python PDF bounding-coordinate mismatch. The checker now reports differing
JSON fields and a bbox-only inspection hint, with no tolerance or acceptance change. Nine added
cases bring this evaluator test file to 38 and the unchanged installed b12 suite to 840 checks.
Current script SHA256:
`127285d36f9177c0fd260ee55be092a528c71f4a84296421f2551f94d276d966`.
Earlier checker/report hashes above remain historical. New b13 calculator bytes differ, so use
the preserved b12 evaluator for b11 records; the code-identity guard must not be bypassed. New
b13 precision readback uses its exact new implementation and is not a migration of old results.
