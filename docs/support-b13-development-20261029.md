# B13 precision-safe numerical comparisons — 2026-10-29 KST

Frozen, unpublished local-model **review-support** candidate, not medical qualification.
Times below are UTC on October 28. The deployment goal remains incomplete.

**Final engineering status:** all six targeted jobs finished exit 0 at 18:08:09 UTC, including
three full-length format pairs. Eight receipts, twelve source copies and four actual baseline
outputs verify; eight saved snapshots and 68 calculations reproduce. This is not all-six-branch
medical qualification. Earlier running observations below are chronological, not current status.

## Corrected arithmetic boundary

A deterministic regression exposed a real comparison bug in b12: a two-sided normal replay
from `z=7.2` computes `6.021255962234844e-13`, but the fixed absolute `1e-12` allowance marked
it numerically matching a printed `p=1e-30`. Its statistical status was still conditional;
nevertheless the agreement flag was wrong. The original diagnostic and old wheel are preserved.

B13 removes that fixed allowance. Comparisons use the exact printed decimal token and precision:
integer sums compare exactly, percentages compare integer count ratios by cross multiplication,
and statistical methods compare the decimal representation of their saved floating-point result.
Statistical arithmetic is not arbitrary-precision inference and remains conditional, whether
matching or differing. Source-derived inequality rules, literal input binding and two-refusal
stops are unchanged. No calculated mismatch automatically establishes a manuscript error.

Count sums now accumulate integers and reject totals above `2**53`, rather than losing units
while adding individually admissible counts. Reported decimal exponents outside -324 through
308 are refused. Records retain approximate float `rounding_tolerance` and add its exact decimal
string plus a named comparison basis. Existing calculations, exports and failures are not migrated.

Twenty-eight new deterministic cases cover tiny p-values, underflow, precise bounds, inequalities,
exact integer sums, percentage rounding boundaries and extreme exponents. The workstation's
installed b13 runner also directly reproduces the tiny-p correction without a model call:
agreement false, status conditional, exact rounding tolerance `5E-31`.

## Exact candidate

- Version `0.9.0b13`, answer contract 9, persisted schema 1, `medical-methods-v1` unchanged.
- Local build `/tmp/creview-support-b13-development.omi50M86`.
- Wheel SHA256 `9bbb442968c34f06b1a1b683b157d2e8dfbe8820f0b3a27c63422e899fc72b5e`.
- Runner `60995d277fb664ea7d27eeec00c0d300210a9721486e1d46639c723c2a18c119`.
- All 51 package files match source and independent wheel-derived sums. Relative to frozen b12,
  only `__init__.py` and `support/calculators.py` differ. Renderer, medical criteria, extraction,
  workflow, profile/routes and skill bytes are unchanged. Earlier runs do not qualify b13.
- Clean Python 3.11.15 wheel install, 31 hash-pinned dependencies installed offline, source
  `pythonpath` disabled: **868 tests pass in 79.58 seconds**. Ruff and lock checks pass.
- Both-host bundle `/tmp/creview-support-b13-candidate.7f6nx7tl`, 40 listed files, manifest
  SHA256 `30f62591fd8198ecd33886c38d1d2a10a122e354bacaa985b9ffbacf9e1935b4`.
  The evaluator-only saved-replay checker, reviewer proposals and private keys are not transferred.

## Serial workstation regression

Fresh runtime `/tmp/creview-support-runtime.t54as132`, Python 3.14.2, 25 hash-pinned dependencies
installed offline. Exact installed identity and strict preflight passed without generation.
Preflight was outside Hermes (`not_in_hermes`); actual jobs must validate recorded session routes.

Controller `2612316`, start ticks `122454198`, SHA256
`2a0bea12e66a1b7ec4413f8bbcc6efe0bf1ed3f3af6940855f5f42f3af34eae7`, queued at 17:19:21.
It verified the b12 cancellation, then waited for b11 controller/jobs/sampler termination and
idle slots. Released at 17:23:21; its separate warm/shared ten-second sampler starts before
inference. Bundle/runner hashes are checked before each job and the existing 21-file runtime
stat/process continuity before/after. This is not cold-start, exclusive or minimum-memory evidence.

Six serial engineering jobs: numerical precision pair, forced pristine-checkpoint/turn-limit
recovery, genuine compression, Korean, explicit statistics+logic scope, and three paired eight-page
Markdown/DOCX/PDF cases. These are not a full new medical qualification matrix. The precision
pair and bootstrap recovery finished exit 0; compression was running at 17:33 UTC. The short
precision fixture is key-free, invented, unreviewed and not a medical gold case or clean control.

The first two jobs are copied to `/tmp/creview-support-b13-first-results.RnE2o3Ik`: 56 regular
allowlisted files, 604,218 bytes, archive SHA256
`fdfada66f93f781491ac5367558dfa736076a1456ee70a0ce5baf19f247cec2b`. Both receipts and support
source copies, the actual baseline source/output and both bootstrap prompt hashes independently
verify. The precision case really saved `p_from_z`, two-sided, `7.2` and original `1e-30`, with
false agreement and conditional status. Its saved source and one calculation reproduce offline;
the dossier overview shows both values, “Differs on selected inputs” and “Conditional statistical
comparison.” Support/baseline elapsed times were 143.83/36.47 seconds, not human checking times.
Its one model proposal is a population/reporting limitation, not a numerical-error observation;
it remains unjudged and does not establish useful prioritization or medical coverage.

Bootstrap recovery passed in 207.32 seconds: actual pristine `unissued` checkpoint, exactly one
same-session completion request, genuine three-turn interruption on invocation 3, then complete
export in four actual invocations. One unjudged proposal, five calculations. This is the first
live execution of that bounded extra-continuation branch, not a retroactive b11 pass.

Compression subsequently passed in 267.40 seconds with the actual event recorded; Korean passed
in 185.53 seconds with explicit `ko` and Korean-prose smoke checks. Each exported one unjudged
proposal and three calculations, with no module failure. The separate copied slice contains
42 regular allowlisted files, 668,095 bytes, archive SHA256
`4caf33bab46da174d759896cb7b5550afe0bcc652a4c625667b65d0ce9d7e27c`.
Both receipts, all subject byte hashes and both original source hashes independently verify;
both snapshots and all six calculations reproduce offline. Verification record SHA256
`499aebd0f1fae253fb91fb7b125debb03912e95c6bfec5d4ff48923cba4472a2`.
This does not approve translation, meaningful attention or concern validity. At 17:42 UTC the
multi-module driver also finished exit 0: five targeted jobs finished, with the full-length
format-pair job still outstanding. There is no final whole-suite or peak-memory claim yet.

The finished multi-module slice is now copied and independently verified: 31 regular allowlisted
files, 549,359 bytes, archive SHA256
`ec3c53d4c43d38d278e0ed3ba0bc4ddf7e7d4710e62f8f5ffdcdcf191df5fc44`.
Statistics and logic both completed, with separate fact/record references and connections
between each module's own facts; one unjudged proposal each, three statistics calculations
and none for logic.
This checks record scope, not semantic independence of reasoning in a shared model conversation.

Across all five finished jobs, five receipts/all subject byte hashes, five original source
snapshots and **15 saved calculations** independently reproduce. All six module records completed
with their source blocks supplied, no saved coverage/extraction gap and no module failure. Delivery
is not proof of attention or completeness. The offline readback did not read audit templates or
keys, invent judgments, modify exports, or make model/network calls. Record SHA256
`4e3134cf3d3ffca5544e614e72306dd82342a1f45ba493c8795f5860a0b05e9f`.

The full-length format worker `2638242`, start ticks `122598310`, started at 17:43:22 and is
confirmed live. Its pairs remain unfinished. A fresh read-only Pandoc 3.1.3 readback of the exact
Word fixture yields the same AST as the independently interpreted fixture check: 62 paragraphs
and three grids, with title metadata included. Source bytes are unchanged. This proves fixture
content continuity, not completion of the running b13 extraction/analysis or human fidelity.
Word-source readback record SHA256
`97407c5d69b737fcdb8e570f37e8b9a71c62565f2b96854cddd575379feb48a0`.

The first full-length pair (Markdown) subsequently completed: support 403.65 seconds, actual
same-model baseline 70.48 seconds. Its 154 source blocks were supplied, 58 facts and six appraisals
saved, with three tables, 19 calculations, zero proposals and no refusal or module failure.
Zero proposals is not proof of no issue; these elapsed times are not human checking times.
The finished pair alone is copied to `/tmp/creview-support-b13-native-md-results.D0nWJq2c`,
34 regular allowlisted files, 1,259,168 bytes, archive SHA256
`028d562a83ed1db31e8612822d421146da9cbc45622ae2fe5be243376956e1de`.
Its receipt/all subject byte hashes, both source copies and actual baseline output verify;
the saved source snapshot and all 19 calculations reproduce against exact b13 code. The running
global batch was not copied or relabeled as finished. Verification record SHA256
`d821cc6174c0389cb72dd18e88dea9a2e35562afedfb29038a0dc9c63ef07d43`.
At 17:55 UTC the DOCX run remained live at task cursor 5/8 with all 151 source blocks supplied,
63 facts and no refusal/failure. The DOCX/PDF pairs and whole-suite evidence remain outstanding.

The DOCX pair then finished engineering-passed: support 380.50 seconds, baseline 91.65 seconds,
all 151 source blocks supplied, 63 facts, six appraisals, three tables and 19 calculations. One
consolidation-task refusal was repaired within the existing limit; zero module failures and
zero proposals, not proof of no issue. The completed pair is copied to
`/tmp/creview-support-b13-native-docx-results.9Beyo4dt`, 36 regular allowlisted files,
1,326,100 bytes, archive SHA256
`31f2c35f9d9c73fa00ad39e1245e5909ccf33a41bfe8c5d0f0ba4c6870589cf5`.
Its receipt/all subject byte hashes, both original Word copies and actual baseline output verify;
the saved source snapshot and all 19 calculations reproduce. Word bytes match the independently
read fixture exactly. Verification record SHA256
`21bfa928dfa7adac28c218a46b89f35328763b50d8ad6f1292ccd785e9d9a52e`.
At 18:04 UTC the same PDF worker was live, with all 240 blocks supplied and one refused task;
its final module result, actual baseline and whole-suite records were still unfinished.

The unstarted b12 controller was canceled at **16:53:59.443188 UTC**, before inference. Its
original queue bytes, wheel and logs remain unchanged, with a separate cancellation record.
None of its four unrun jobs count as passes. B11 finished 11/12 jobs: the genuine compression
event occurred, but exact-quote refusals stopped statistics. That failure remains a failure;
b13's separate compression pass does not erase it or establish repeatability.

## Terminal suite and complete sampling window

The controller, all six drivers and sampler were confirmed terminated before the complete archive
was collected. Global engineering result true, finished `2026-10-28T18:08:09.418406+00:00`.
The complete source-bound copy is `/tmp/creview-support-b13-suite-results.B9NEpb5E`: 261 regular
allowlisted files, 6,205,161 bytes, archive SHA256
`95f7316af828455714fd74d4f4e01452a68fab9f998c384c559f35076bb8dd62`.
All eight receipts and four subject byte hashes per receipt independently verify; eight support
source copies, four baseline source copies and four actual baseline outputs verify. The earlier
five completed-job exports are byte-identical in this full copy. Verification record SHA256
`af5be31b36ea643b59549bce8871be47ea7860825eec73fe88994e13b50ea19a`.

All [three full-length format pairs](support-b13-native-20261029.md) finished, with 53 saved
calculations and three snapshots reproduced in addition to the earlier 15 calculations/five
snapshots. No reviewer judgments were filled. Passing mechanics and zero native proposals do
not establish medical validity or absence of issues.

The warm/shared ten-second sampling window ended 18:08:16 UTC: 268 GPU and 268 RSS samples,
sampled per-model peaks 23,682 MiB GPU and 60,910,832 KiB RSS. The controller's final 21-file
runtime stat/process continuity check passed. This is not instantaneous/exclusive peak usage,
loaded-memory attestation, minimum hardware, a cold-start benchmark or human hardware approval.
Regular profiles/services and model configuration were untouched.

## Gates still closed

The targeted regressions and artifact checks are complete. They do not replace exact-build
medical coverage of all six branches, formal paired repetitions or human qualification.
Independent source/test-role approval must precede formal runs; diagnostic corpora cannot be
retro-approved. Three paired repetitions, human precision/recall, coverage, numeric-claim fidelity,
usefulness, translation, baseline checking times and hardware review remain incomplete. Keys remain
off the model host. No reviewer judgments, publication, regular-profile changes or new server.

Machine record: `evals/deployment/b13-evidence-20261029.json`. Release remains refused.
