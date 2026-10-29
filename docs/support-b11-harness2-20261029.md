# B11 checkpoint-aware evaluator — 2026-10-29 KST

Times below are UTC on October 28. The b11 wheel/runner is unchanged. A new evaluator bundle
corrects checkpoint setup, not medical criteria, source matching or numerical acceptance.
731 local tests passed at staging. The full suite has now finished: **11/12 engineering jobs
passed; the genuine-compression job failed exact-quote checks**. The chronological running
observations below remain historical. No release or medical-quality qualification is implied.

## Preserved failure and bounded correction

B10's turn-limit test failed in 27.34 seconds before any forced interruption: the model stopped
after `support start` without issuing the first task. The saved run had cursor zero, no answers,
facts, provided blocks or refusals, and statistics pending. It correctly failed the old test.
The original eight-file record and failed result are preserved; no recovery event was inferred.

The evaluator now permits one explicit same-session request for `support next` only while the
run is untouched. It rejects a second premature stop, any saved analysis/refusal/note, written
answer, advanced cursor or changed run. That continuation consumes one of the existing six
actual invocations; no new run or larger budget is allowed. Initial state and request count
remain visible in the result.

Turn-limit/compression settings and deliberate module-failure injection now wait for an issued
first checkpoint on a resumed session. A bootstrap setup call is not the analysis invocation.
The actual forced event, same-run/session checks, genuine export, source quotes and receipt
still must pass. The code does not retry failed module answers or reclassify old failed tests.

Eighty focused adapter/recovery/scope/evaluation checks pass. The full installed-candidate suite
passes 731 tests in 66.91 seconds; Ruff, lock and diff checks pass. Twenty-nine added cases cover
early-stop continuation, repeated stops, written answers, advanced/refused state, six-call cap,
and settings/fault injection after a delayed checkpoint. These are not medical human judgments.

## Immutable candidate and evaluator artifacts

- Package `0.9.0b11`, answer contract 8, persisted schema 1 and `medical-methods-v1` unchanged.
- Wheel SHA256 `07d1c1abc21393bdb28be683dc73b6a60c32f2fc2a0c172b62ca4e3b06ba0590`.
- Runner `5a37d154ee4efa99b6d7fdbe995507de45df142dc1a8ccad27a09371411e55da`.
- New local/workstation bundle `/tmp/creview-support-b11-harness2.50TRVAiO`, 37 listed files,
  manifest SHA256 `664bc73ad8e50516214a599bb207c781109c52cefdfdfb873c77df70db8a085f`.
- All file hashes independently verified on both hosts. Relative to the original b11 bundle,
  only `test-support-hermes.py`, `probe-support-recovery.py` and `probe-support-scope.py` change.
  The wheel, source corpora, key-free manifests, dependencies and baseline checker are unchanged.
- New runtime `/tmp/creview-support-runtime.tm9ClpRZ`, Python 3.14.2, same 25 hash-pinned
  dependencies installed offline. Exact installed identity and strict live preflight passed
  without generation. Its preflight runtime was `not_in_hermes`; real workflow jobs still
  validate their actual recorded custom model/provider/endpoint.

The original b11 controller `2389253` was canceled at 14:52:24 before inference, after checking
its process start identity, waiting state, no children and no suite file. Its queue-state bytes,
bundle and logs remain; `queue-cancellation.json` records the action. No unrun job is a pass.
The new controller verifies that cancellation and its checksum before it can begin.

## Fresh live suite and first regression

Controller `2461652` queued at 15:05:30 UTC and started at 15:06:00, after all b10 controller/job
processes exited and model slots were idle. Controller SHA256
`b25d65192efa6c31eb085784d86451fa38bcfdde5006dd607da901a7d9f197e5`.
It verifies the bundle/runner before each job and existing 21-file runtime stat/process
continuity before/after the suite. A new ten-second sampler, PID `2461967`, started before first
inference. This is whole-window warm/shared-process sampling, not an exclusive/cold-start or
minimum-hardware benchmark. Regular profiles and model services were not changed.

The first turn-limit probe completed at 15:10:39 in 279.08 seconds: an actual three-turn
interruption, expected CLI exit recovered, same session/run resumed, complete statistics export
in three invocations, one unjudged proposal and three calculations. Initial checkpoint state was
`issued`, with **zero** extra completion requests. It proves this normal-checkpoint recovery path,
not a live execution of the new extra-continuation branch. That branch has deterministic
real-workflow adapter coverage; a forced-early-checkpoint real-Hermes demonstration remains pending.

The finished probe is copied to `/tmp/creview-support-b11-h2-regression-results.zYEwAeF6`:
23 regular allowlisted files, 381,107 bytes, archive SHA256
`85e5e7690838c20a51add46c1f284ee93a653f4717836056cf93a9525224ce71`. Its receipt and original
source independently verified against original b11 wheel sums. No human validity was inferred.

The full-length SR case ran first among the six paired cases and passed in 480.04 seconds:
all 214 source blocks supplied, 71 facts, seven appraisals, two unjudged proposals and five
calculations. Its actual ordinary-Hermes baseline also passed in 60.30 seconds. One extraction
quote refusal was repaired within the allowed retry; there was no module failure. This is a
fresh exact-build engineering result, not a migrated b10 failure or medical validity judgment.
The pair is copied at `/tmp/creview-support-b11-h2-sr-results.oPlcWsBt`: 42 regular allowlisted
files, 1,456,282 bytes, archive SHA256
`f9bdd867f754d8e2243d79f7329b5a58747a752e86791365d85e67556a796f92`. The export receipt,
both original source copies and actual baseline output hash independently verified. The running
six-case global batch was not copied/relabelled as a finished batch. Human judgments stay blank.
The remaining native/matrix/recovery/scope/language/traversal/baseline jobs stay
serial in fresh profiles; unexecuted work is not a pass.

## Finished six-case ordinary-length pairs

Finished at 15:54:15 UTC, exit 0: six support runs and six actual same-model baselines passed
engineering checks in one unreviewed diagnostic repetition.

| Case / branch | Support seconds | Observations / calculations | Baseline seconds |
| --- | ---: | ---: | ---: |
| s43 / systematic review | 480.04 | 2 / 5 | 60.30 |
| r17 / statistics | 356.73 | 0 / 20 | 94.81 |
| q28 / qualitative study | 291.02 | 0 / 0 | 47.68 |
| h36 / scoping review | 417.59 | 0 / 4 | 57.60 |
| n54 / narrative review | 340.48 | 0 / 0 | 48.89 |
| l62 / logic | 340.50 | 0 / 0 | 80.23 |

Every module completed with all source blocks provided and no module failure. Delivery does not
prove attention or correct interpretation. The two SR proposals remain unjudged; zero elsewhere
is not proof of no issue. Inference elapsed times are not human checking times or quality rankings.
The unreviewed corpus cannot be retroactively qualified.

Copied to `/tmp/creview-support-b11-ordinary-results.59Ok30n0`: 230 regular allowlisted files,
7,025,858 bytes, archive SHA256
`098a299124309d19bc72855cd710fc1bd31d9abb9a188e275291e236743213e9`. Six receipts independently
verified against original b11 wheel sums; twelve support/baseline source copies and six actual
baseline output hashes verified. The local `ordinary-audit` includes all original manuscripts,
both proposals and actual baselines. All human judgments, roles and checking times stay blank.
No new server or key transfer. Machine record: `evals/deployment/b11-ordinary-evidence-20261029.json`.

The controller moved to the eight-page native-format pairs at 15:54:15, PID `2513422`. The wider
suite and sampler remain active; no global terminal suite/memory claim is made.

Those [three full-length format pairs](support-b11-ordinary-native-20261029.md) finished
engineering-passed at 16:20:43. Three receipts, six manuscript copies and three actual baseline
hashes independently verified; all three snapshots and 40 calculations reproduce. Explicit
PDF layout comparison passes while strict differences stay recorded; analytical coverage and
human validity remain unjudged. The next short-native worker is `2540958`; the broader suite
is still running, not a complete or medically qualified suite.

## Complete broader suite and preserved compression failure

Finished 17:23:00.330326 UTC, global engineering result **false**. The controller, all twelve
drivers and sampler were confirmed terminated before the whole-suite archive was collected.
The twelve-case matrix completed 12/12 at 17:01:32; it contains 11 unjudged proposals and 16
calculations across the six branches. Twelve original source snapshots and all 16 calculations
reproduce offline against byte-matched historical calculator/parser code. The audit packet's
human judgments, roles and checking times remain blank; it is not medical-quality qualification.

Genuine compression completed on invocation 2, but statistics stopped after two refusals in
210.15 seconds. Both rejected answers used literal backslash-plus-`n` characters between three
table rows where the original block contained line breaks, at
`$.assessments[1].evidence[6]` and `$.connections[0].evidence[0]`. The same invalid quotes were
resubmitted. Exact matching correctly refused them; no fuzzy repair, refusal reset, extra retry
or old-result promotion was applied. This diagnoses the observed encoding failure, not proof
that compression caused it. The failed module exported zero observations/calculations and its
valid receipt does not turn failure into success.

Unreadable-PDF, explicit multi-module, deliberate one-module failure isolation, Korean,
long-source traversal and the actual ordinary-Hermes baseline all passed their distinct
engineering checks. The deliberate failure test correctly keeps statistics failed while logic
completes; the unreadable image-only PDF stays not-assessable, not a successful medical appraisal.

Whole-suite copy: `/tmp/creview-support-b11-h2-suite-results.SbMkRonO`, 878 regular allowlisted
files, 18,583,656 bytes, archive SHA256
`df0614d439b3a544846e170a282f0bbba8ac0d0fd4ae29bbca7dde3832d07742`.
All 31 receipts and their four subject byte hashes independently verify against original wheel
sums, including both failed-module exports and the not-assessable export. Thirty-one support
source copies, thirteen baseline source copies and thirteen actual baseline output hashes verify.
The first matrix-packet attempt used the wrong artifact root and was refused before packet
creation; the correct module subtree produced `matrix-audit-v2`, without changing raw results.
Local verification record SHA256
`53a5e663ed1c1da6f81d657dafb3ed440b1b73394fd1900e45323fa2c2bf2568`;
matrix replay report SHA256
`7fe1645c4046ea561a08b1b5a4ed58416d07ae9314b61fc21bb908006dc05d30`.

The complete warm/shared ten-second window ended 17:23:07 with 818 GPU and 818 RSS samples:
sampled per-model peaks 23,682 MiB GPU and 61,649,100 KiB RSS. The controller's final 21-file
stat/process continuity check passed. These are not instantaneous/exclusive peaks, loaded-memory
attestation, minimum hardware requirements or cold-start measurements.

The [short format packet](support-b11-short-native-20261029.md) separately records a one-ULP
cross-Python PDF coordinate mismatch without relaxing source checks. The newer b13 arithmetic
candidate is not qualified by any b11 result; its separate compression pass does not erase this
failure.

## Remaining gates

The broader b11 execution is terminal and failed. A forced early-checkpoint live demonstration
passed on the separate b13 identity, not retroactively on b11. Independent source/test-role approval before
formal runs, three paired repetitions, human precision/recall/coverage/translation/baseline
checking-time judgments and final hardware review remain incomplete. The release gate remains
closed. The source-only packet stays local pending Tailscale sharing preference; no server or
private-key transfer was performed. Machine record:
`evals/deployment/b11-harness2-evidence-20261029.json`.

The compact conditional/numerical-comparison view is implemented and browser-tested in a separate
[b12 candidate](support-b12-development-20261029.md), queued after this suite exits. It does not
change b11's running wheel, artifacts or medical qualification status.
