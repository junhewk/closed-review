# B15 post-reboot retest — separate persistent attempt

The workstation became reachable again on October 29. Read-only checks found a new boot at
03:48:15 UTC (12:48:15 KST), boot ID `9abf0082-4cfe-4b35-8bbd-a1dea5722ace`, no original
controller/driver/sampler PIDs, and no `/tmp/creview-support-runtime._z4usy4r` directory.
The old attempt cannot be resumed from that location. Its public/native results are unverified,
not passes. Its four already copied recovery jobs and independent 19-calculation readback remain
preserved locally. The earlier statistics `partial` detail was not recovered or silently cleared.

No service or regular Hermes profile was changed or restarted. The existing Strata and gateway
services were active, the gateway advertised the original Qwen model/context, and its native slot
was idle before the new attempt. Other GPU/model workloads were left untouched.

## Exact candidate and runtime checks

The **same b15 wheel and 23-file bundle** are used, not a rebuilt candidate or edited harness:

- Wheel SHA256: `f3f0ba77dd8709db3094226af382e0e63b94a486a41074a106517bac4cff7b76`.
- Runner: `aad45258aa8dd462a448e19f184e2dafa0edf3c582e70ec51f734a64fa8d3708`.
- Bundle manifest: `939cd9f1f7942fa4a37b88d8a5a58108b7472558c2e82e8534227cb8995d8b85`.
- All six real-paper and three native fixture files are unchanged; private keys are not copied.
- All 21 runtime-file paths/stat records still match the earlier hash-bound identity. Those prior
  hashes are reused with explicit unchanged-stat provenance, not falsely described as a new 86 GB
  rehash. The current native executable was also independently hashed through `/proc/3746/exe`;
  it matches the earlier Strata binary. Native pack/weight/MTP/profile/prefill/context arguments
  match. This is not an attestation of loaded-memory contents.
- Hermes remains `0.21.5+7498.gebadb54`, HEAD
  `ebadb5462e46c168a7eb097895faa647493e0a26`. Its current launcher is a shell wrapper rather
  than the earlier reported symlink. The wrapper, target entry point, conversation loop,
  compression and write-guard files have new explicit start-of-attempt hash/stat pins.
- Native PID `3746` / ticks `17832`; server PID `3353` / ticks `17763`; gateway PID `4576` /
  ticks `20270`. No continuity with pre-reboot process identities is claimed.
- Runtime identity SHA256: `7c6d71899851282f3882f8608878ef1e107f4c7a71992e66bc41e835c91f7da2`.
  Raw copied record: `evals/deployment/b15-restored-runtime-identity-20261029.json`.
- Fresh Python 3.14.2 environment: 25 hash-pinned dependencies and the exact wheel installed
  offline. Strict live preflight passed without generation (`not_in_hermes`).

## New attempt, not a repair of old results

Persistent private root:
`/home/jk/.local/state/creview-evaluations/b15-restored.w0fNUWyl`.
The eight frozen evaluator scripts are unchanged. The outer bootstrap/controller have new,
explicit identities because the old controller's pre-reboot PID and `/tmp` preconditions no
longer apply:

- Bootstrap: `evals/deployment/b15-restored-bootstrap.py`, SHA256
  `732a7a48320587a0682350a61e1c44876963204e58f15a0e81c7787ca54604c0`.
- Controller: `evals/deployment/b15-restored-controller.py`, SHA256
  `dc67ef135f09e513318c3fb28c8d9eef6f1adac26c069b6a6c5b0212ab1e2789`.
- Controller PID `9424` / ticks `58880`; memory sampler PID `9426` / ticks `58888`.
- Started **03:58:04 UTC**; public-pair driver PID `9432` / ticks `58889`.
- Order: six real-paper pairs first, three native-format pairs, iteration handoff, stale draft,
  pristine-checkpoint/forced-limit recovery, actual compression. The unchanged case, invocation
  and total time bounds remain. All inference jobs are serial; no extra model/provider is used.
- Controller writes 15-second heartbeats, now including stored gap details and extraction limits.
  A read-only terminal monitor polls every 30 seconds. Transient observation errors do not
  restart cases. Runtime boot/PID/stat and bundle identities are checked between jobs and at end.
- A 10-second native-process memory sampler records a warm/shared window, not cold/exclusive
  measurements or portable minimum hardware. Sampling is incomplete until the attempt ends.

At **04:00:49 UTC**, the new statistics run
`support-9308ad68c464a57f0b71e805d564459f` had accepted 3/23 tasks, with 48 facts and no coverage
gaps or module failures. Its actual session route was verified as `custom`,
`qwen3.8-flash-next`, `http://100.122.169.13:8091/v1`. One source-punctuation mismatch was
refused at task 3 and subsequently accepted using a fresh draft; the original refusal and its
counter remain. A host guard also blocked an attempted script-execution command; it was not
executed or bypassed. Neither event is erased or described as a zero-error run.

Four new local orchestration tests pass: existing attempts cannot be overwritten, a wrong
bundle is refused before service inspection, partial/gap observation leaves the saved run
unchanged, and a malformed observation is recorded without spawning/restarting anything.
These tests are not medical inference or final suite results. A full installed-wheel rerun
completed with **946 tests passed in 83.76 seconds**, including these four tests, with source
`pythonpath` disabled. JUnit confirms zero failures, errors or skips. Logs, exit record and an
exact copy of the executed supervisor are preserved under
`/home/jk/.local/state/creview-evaluations/b15-installed-tests-20261029-0404`.
The first foreground rerun had ended with signal 15 / exit 143 before a summary; it remains
an interrupted attempt, not a pass. The successful rerun used a separate supervisor/session;
the cause of the earlier signal has not been established. Lint and compilation checks pass
after development-only style fixes; the active remote launchers have not been changed.

At **04:05:21 UTC**, controller, sampler and driver PID/start ticks verified live. Statistics
had accepted 12/23 tasks, 114 facts, no gaps and no failures. Machine evidence:
`evals/deployment/b15-restored-evidence-20261029.json`. This later progress observation is not
an exported-dossier or all-branch pass.

At **04:11:07 UTC**, all 20 statistics extraction tasks had been accepted: 163 facts, no
coverage gaps, no extraction warnings and no module failures. Appraisal/consolidation was
still running (20/23 tasks). This new attempt has not reproduced the earlier coverage gap;
its absence does not explain or repair the lost predecessor's `partial` result.

Authoritative current files are `suite-state.json`, `latest-observation.json`, `controller.log`,
`public-pairs/batch.json` and each original case's `result.json`/saved run under the root above.
This attempt is **not yet deployment-ready, medically qualified or release-qualified**.
Completed all-branch/native/recovery results, exact-build copied source/receipt/calculation
readback, and the outstanding qualification gates remain required.

## Finished first persistent suite and bounded startup fix

The persistent suite finished at **06:05:46 UTC**, with overall engineering status **failed**:
five of six real-article support cases passed, all six public ordinary-Hermes baselines passed,
all three native-format pairs passed, and all four recovery regressions passed. Runtime
continuity passed at the end. The sole failed public support case was qualitative: privacy
preflight passed, but Hermes stopped after three of twelve calls with its host-recorded
`Reasoning-only clean stop`. No support run existed. This was a startup failure, not a
qualitative appraisal or context-limit failure. The driver only recovered untouched runs
that already existed and therefore rejected the missing startup checkpoint.

The user requested a fix and rerun. The run driver now permits exactly **one** pre-start
continuation when its new host-log suffix contains the matching clean-stop and turn-end
events, the session/model/counters match, the same session has passed the support privacy
preflight, its actual route is verified local, the exact runner probe and source/configuration/
skill pins match, and no run/draft/export/legacy scan exists. Model prose never establishes
eligibility or journal approval. Errors, changed state, and a second premature stop remain
failures. The continuation consumes an existing invocation: six invocations, twelve-call
startup turns, appraisal bounds and the original time deadline are unchanged.

This is a **driver-only change**, not a change to the b15 package, skill, medical criteria,
calculators, privacy rules or ordinary Hermes chat implementation. It is not a claim that
every local-model stall is recoverable. Original failures remain failed and are not edited.
There are 49 new startup tests, including full deterministic workflow/export adapters for
all six modules and adverse host/state cases. The focused 105-test suite passes. A complete
installed-b15-wheel run with source `pythonpath` disabled passed **995 tests in 105.68 seconds**,
with zero JUnit failures/errors/skips. Lint, compilation and diff checks pass.

### Separate startup-h3 qualitative rerun

Started **09:24:29 UTC** under
`/home/jk/.local/state/creview-evaluations/b15-startup-h3.ObgFm7kw`.
It uses the same exact b15 wheel/runner and unchanged qualitative manuscript
`46b3dcdb949f822309eb67b9c7f44102ef619e5e1959d3e0962ca322ff0ad3a0`.
The newly frozen 25-member bundle changes only `test-support-hermes.py` among the original
23 members; it additionally retains the old manifest and a clearly labeled one-case manifest.
It is a targeted new pair, not a replacement pass for the failed full batch.

- Driver SHA256: `84d03286e3527ab78c0ef101f095c785f4a7c445f80cb68d4ad1257ce650cda5`.
- Bundle manifest SHA256: `f8d64e381e3ee1b5ea8260a25b89931055e8f2648b6ce060ac9c6183de1dafa6`.
- Controller SHA256: `a6a415bf3cc02327bcec8374fafcd3f95b1e24a235b8ced64087c00fdc5b91c1`.
- Controller PID/ticks `215169` / `2017367`; driver `215172` / `2017375`;
  sampler `215171` / `2017375`. Terminal observation polls every 30 seconds.
- Full-test JUnit SHA256: `6d26cb2670ffa29db15167a3036a58048b78e1087d9b3e549617ea0b3119fc2d`.
- Local full-test artifacts:
  `/home/jk/.local/state/creview-evaluations/b15-startup-h3-tests-20261029`.

At **09:31:01 UTC** the new qualitative run
`support-7c62894367e91bbbba0d21bb48b103c2` had accepted all nine extraction tasks (9/13 tasks
overall), 105 facts, no refusals, no gaps and no failures, with the actual local route verified.
Startup completed normally on this attempt; the new pre-start fallback was not needed.
Its guard/recovery coverage is deterministic test evidence, not a claim of a newly observed
live premature-stop recovery. Final appraisal, export and baseline checks remain pending.

### Startup-h3 final result and independent readback

The targeted pair **finished successfully at 09:34:02 UTC (18:34 KST)**. Qualitative support
completed in 491.20 seconds, the actual ordinary-Hermes baseline in 70.22 seconds. These timings
do not establish comparative review quality. All recorded engineering checks passed: one requested
module, same session/run continuation, unchanged source, source-bound quotes, final dossier/export
and receipt, no legacy scan or invented reviewer decisions. The module accepted all 13 tasks,
105 facts and one **unjudged model observation**, with zero refusals, gaps or module failures.
The baseline's actual source/output/tool trace and local route checks also passed. Runtime
continuity passed at the end; the controller, driver and sampler are finished.

This live startup succeeded normally (`startup_completion_requests: 0`), so the new fallback
was **not invoked on this run**. Its one-stop recovery and refusal behavior are covered by
the deterministic tests, not a claim that a new real premature stop was observed and recovered.
The previous failed qualitative record and first-turn log retain their original hashes and
failure status; the previous six-case batch is not relabeled as passed.

An allowlisted 55-file, 1,549,608-byte copy was checked for archive digest, exact member set,
regular-file/path safety, every member size/hash and total bytes **before extraction**.
Archive SHA256: `5d0e5d97d57fae8d20fa966b23d4cfd7dd80252319c4f06f65e7df27d622aa81`.
No configurations, environment files, transcript databases or private keys were included.
With the original installed b15 wheel and independent wheel-derived sums, evaluator readback
reproduced the full source snapshot exactly (only the relocated path is excluded), verified
all retained source quotations, receipt/export/saved-run identity, and the actual paired
baseline source/output hashes. No source/answer repairs, model calls, network calls or human
judgments were used in that readback. There are no calculations in this qualitative module.

- Verified copy:
  `/home/jk/.local/state/creview-evaluations/b15-startup-h3-results.7vrLbhWA/copied-verified`.
- Readback report SHA256:
  `b6a5aa31a72bcbd3065e0ccf0b445f940c130dc9794508065a31403e33e08202`.
- Machine record: `evals/deployment/b15-startup-h3-evidence-20261029.json`.

All 52 packaged source files still equal the original b15 wheel. No service, regular profile,
model/provider, manuscript, source-validation rule, refusal limit or iteration/time budget
was changed. This completes the requested targeted startup fix/rerun, **not medical-quality
qualification, a new full-six-case pass, or release approval**.
