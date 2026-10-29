# B15 limit/edit/rejection fixes — active retest

Objective: fix the real-paper limit/edit/rejection failures and retest the complete local
review-support workflow for deployment readiness. This objective is not complete. Input
selection requires no further approval; actual human medical judgments are not invented.

Later status: the workstation rebooted and this attempt's temporary runtime is absent.
Its copied four-job recovery evidence remains valid, but public/native outcomes are unverified.
See the [separate persistent post-reboot retest](support-b15-restored-20261029.md).
The observations below are historical, not a claim that this original controller remains live.

## Reproduced causes and changes

1. **Large Markdown table rejected before SR could start.** B14 scheduled each recognized
   Markdown table as one indivisible text block and again as native cells. The real SR table's
   full block exceeded 12,000 characters, although individual rows fit. B15 schedules every
   header/data cell in intact rows, retains the whole extracted table text in immutable snapshot
   metadata, and excludes that duplicate from task delivery. No manuscript is edited, no cell
   silently omitted, and no task/output limit increased. Genuine overbudget indivisible content
   still stops explicitly; this is not a claim to support unlimited inputs.
2. **Existing answer files refused after resume/compaction.** Hermes protects files whose full
   current contents were not read in the current task. Reissuing `support next` now retains an
   existing draft and supplies a fresh `answer_path`, with the prior path for optional readback.
   Submission is bound to the newly issued path. Accepted/rejected archives remain; source and
   quote/numeric checks and the per-task two-refusal stop are unchanged. A draft reissue does not
   reset refusals. The skill explicitly describes these paths and preserves file-tool guards.
3. **Resumable iteration boundary treated as fatal.** The evaluator now distinguishes an actual
   host-recorded iteration handoff from an arbitrary exit 1. It requires a new foreground host
   event matching the original session/model and bounded call count, committed task progress,
   unchanged source/build/routes/task list, and retained refusal history. Model prose is never
   the evidence. Tracebacks, host errors and unresolved file-mutation-verifier failures remain
   fatal. It resumes the same session/run within the existing six-invocation/time bounds; it
   neither restarts a failed case nor claims success from the handoff.

New deterministic coverage includes real-table-sized source scheduling, fresh-draft preservation,
symlinks, refusal accounting, actual-workflow continuation/export, and adverse handoff cases
(including fabricated summaries, changed source/session/model, fork events and edit failures).
Old fixture helpers were updated to use issued paths; required read/fragments and rejection
archive checks remain. The skill-creator guidance was used for the narrow recovery instructions,
and both skill copies validate/match; the maintained privacy block is unchanged.

## Frozen candidate

- Version `0.9.0b15`, answer contract 10, persisted schema 1, `medical-methods-v1` unchanged.
- Build `/tmp/creview-support-b15-development.lnZyr4W9`.
- Wheel SHA256 `f3f0ba77dd8709db3094226af382e0e63b94a486a41074a106517bac4cff7b76`.
- Runner `aad45258aa8dd462a448e19f184e2dafa0edf3c582e70ec51f734a64fa8d3708`.
- All 52 package files equal source and independently wheel-derived sums. Compared with b14,
  version, packaged skill, answer contract, support source snapshot and workflow change;
  `support/continuation.py` is added. Calculators, medical criteria, privacy/routes and renderer
  do not change. No old run is migrated or upgraded.
- Clean Python 3.11.15 wheel install, 31 hash-pinned dependencies installed offline, source
  `pythonpath` disabled: **942 tests pass in 100.55 seconds**. Ruff, lock, shell syntax, diff,
  skill validation and exact skill-copy checks pass. Earlier fixture-path test failures remain
  recorded as development failures, not silently counted as passes.
- Both-host frozen bundle `/tmp/creview-support-b15-candidate.pf8uua67`, 23 listed regular files,
  manifest SHA256 `939cd9f1f7942fa4a37b88d8a5a58108b7472558c2e82e8534227cb8995d8b85`.
- Public corpus SHA256 remains
  `12b799d631cf60050078d1af7ba4acaf1c74e44d3345264abfe026e49d57def1`.
  All six real manuscripts and the three native-format fixture files are unchanged. No private
  issue keys, human judgments or original XML/public peer-review subarticles are transferred.

## Real workstation verification — running

Fresh runtime `/tmp/creview-support-runtime._z4usy4r`, Python 3.14.2, 25 hash-pinned dependencies
installed offline. Strict live preflight passed outside Hermes without generation
(`not_in_hermes`); exact installed runner matches. The original 21-file runtime identity's
stat/process continuity passed before the suite. Existing services and ordinary profiles are
untouched. Model `qwen3.8-flash-next`, explicit context 262144, private gateway unchanged.

Controller `2903288`, start ticks `125681069`, started **02:17:09 UTC October 29**.
Controller SHA256 `19d895f047eb5a0e102709d44b0481cccf3889117a92fe5b823e088e8677282d`.
It checks idle slots and bundle/runner identity before each serial job, writes progress
heartbeats every 15 seconds, and runs a ten-second per-process memory sampler. Transient
observation errors never restart a live job. Memory is warm/shared, not cold/exclusive/minimum.

Serial jobs: genuine iteration handoff; existing unsubmitted draft; pristine-checkpoint/forced
turn-limit recovery; actual compression; six public support/ordinary-Hermes pairs; three full-length
Markdown/DOCX/PDF pairs. Public/native dossier responses are Korean. These are engineering tests,
not seeded-error precision/recall or human translation/fidelity/usefulness judgments.

**First regression passed:** real Hermes reached the imposed 20-call analysis-turn limit and
returned exit 1 after committed progress from task 0 to 3. The evaluator preserved the nonzero
log/event, resumed the same session/run, and finished in three invocations. Four tasks completed,
five calculations and one unjudged model proposal, receipt integrity passed. No profile budget
was raised. The smaller turn bound is an explicit regression setting, not a deployment default.

The stale-draft regression subsequently passed: an actual existing incomplete draft was
preserved byte-for-byte, a fresh answer was written, and the same run completed in two
invocations with five calculations and one unjudged proposal. Both finished regressions'
receipts/source copies verify against independent b15 sums; neither CLI output has an unresolved
file-mutation footer. These are original-host checks, not yet copied-source/calculation replay.

At 02:27:25 UTC, the pristine-checkpoint/forced-limit job had also exited 0 and actual compression
was running (driver `2916072`, start ticks `125739802`). Public/native pairs had not started.
Machine snapshot: `evals/deployment/b15-evidence-20261029.json`.
By 02:32:24 UTC all four recovery jobs had exited 0, including actual compression. The
six-article public-pair job was running (driver `2920163`, start ticks `125763888`), with the
statistics source at task 1/23, 17 facts and no recorded refusal. Native pairs remain queued.
This is a later progress observation, not a final suite or clinical-quality result.
Read `suite-state.json`, `latest-observation.json`, `controller.log`, and each
job's result/driver files under the runtime for current status. A live terminal monitor is
attached. Final source/receipt/calculation readback and all-branch results remain required.
No deployment-ready, release-qualified or whole-suite-pass claim is made yet.

### Independent copied recovery readback

The four completed recovery subtrees are now copied separately to
`/tmp/creview-support-b15-recovery-results.7tKkPlsX/copied-verified`: 101 regular allowlisted files,
1,375,581 bytes, archive SHA256
`54f1974285e78f999ed5cdb4c0ee378e5669c523635d7a0cbb8fd67b44ef62bf`.
The new verified extraction followed archive digest, exact-file-set, path/type, size and every
member-hash checks. An initial copy/extraction raced the SCP index transfer; that unverified
diagnostic copy is retained separately and excluded from verification. No original job files
were changed. Live public/native outputs, memory logs, configs, environments, private keys and
transcript databases are not in this slice.

The exact installed b15 wheel reproduces all four source snapshots and all **19 saved
calculations**; all four receipts/exports and original manuscript copies match. Copied host
events independently show the 20-call same-session handoff, pristine bootstrap plus forced
three-call handoff, old draft hash/fresh path, and an actual same-session compression commit.
The compression evidence also preserves two aborted attempts, not three successful commits.
The completed workflow passed; no claim is made that every compression attempt succeeded.

Readback record SHA256
`4eaa638225588275d49ea9b345063f6ae689e6131491160149aaea9f1508e6bc`.
Details: `evals/deployment/b15-recovery-readback-20261029.json`. This used no model/network calls,
private keys, human judgments or source/answer repairs. The five model observations across
these repetitions of one synthetic article remain unjudged. Public/native pairs and final
deployment/medical readiness are not established by this recovery subset.

### Observation loss and offline boundary check

The last buffered workstation heartbeat, at **02:49:22 UTC**, showed the real-statistics run
at task 23/23, status `partial`, with 179 facts, 13 calculations, four unjudged observations
and zero recorded failures. This is not a verified final case/export or a pass. The actual
`coverage_gaps`/`extraction_limits` and later public/native outcomes remain unread.

Read-only retries at 02:54–02:57 UTC found SSH and the gateway timing out, no Tailscale ping
reply, and the workstation peer reported offline (last seen 02:50 UTC). The existing monitor
produced no new records. Observation loss does not establish whether the remote processes
are still running; no suite restart, timeout-based repair or service change was performed.

While the host was unreachable, the original b15 installed wheel revalidated all 23 local
bundle members and all six public manuscripts against their frozen hashes. An offline audit
found every source block scheduled once in snapshot order, every native cell retained, every
table row kept intact and every original extracted table string retained. Across the six
sources this covers 2,252 blocks, eight tables, 1,048 cells and 181 rows. All parser warning
lists are empty. Under this exact source/build, consolidation marks `partial` when stored
coverage gaps exist; the actual gap kind/detail still requires the original remote run.
No gap has been suppressed, answered or repaired from inference about its cause.

Eight focused installed-wheel tests passed in 1.71 seconds (108 deselected), covering ordinary
scope boundaries versus genuine gaps, readable conflicts requiring explicit repair, malformed
gap refusals and the retained `partial` result when the 24-fact cap is reached. The check does
not replace the earlier full 942-test run or the missing live result. Machine record:
`evals/deployment/b15-offline-boundaries-20261029.json`.

## Preserved b14 failure evidence

The original batch finished at 00:27:57 UTC: three support passes (qualitative, narrative,
logic), three failures (statistics 22/24, SR before start, ScR 19/20), all six ordinary baselines
passing their recorded engineering checks. Source permission requests are not treated as
approval, and input preapproval is not reintroduced as a prerequisite.

Its full allowlisted copy is `/tmp/creview-support-b14-results.zpxAQ7E2/copied`: 258 regular files,
6,506,212 bytes, archive SHA256
`840c330d0d8fee97228364b1712e85dce6760574d4a63c7515a8371f9263bb04`.
Archive paths/types, every member's hash and exact file set were validated before extraction;
configurations, environment files and transcript databases were excluded.

The original installed b14 wheel independently verifies 12 source copies, five saved source
snapshots, all three completed receipts/exports and six actual baseline source/output files.
All 11 calculations retained in the **failed** statistics run reproduce; that failure is not
upgraded. Readback record SHA256
`10390bcf050b78c55b6f16ab0bc40791fd3fca49a52f5d5583e9d98c6fc00b32`.
No model/network calls, original-artifact edits, source/answer repairs or human judgments were
used in this readback. Numerical reproduction does not establish correct input roles or medical
concern validity.
