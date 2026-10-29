# B14: autonomous inputs and real-paper engineering pilot

**Final status:** finished 00:27:57 UTC October 29, overall engineering failure: three support
passes, three failures, all six baselines passed. The earlier running observations below are
historical. See [preserved b14 evidence and the active b15 fixes/retest](support-b15-recovery-20261029.md).

The unnecessary source-preapproval prerequisite is removed following the user's October 29
instruction. Engineering tests may use autonomously selected synthetic inputs or real public
articles. Genuine offline assessment of medical fidelity, concerns, coverage and usefulness
remains necessary before claiming those qualities; no human judgments are generated for them.

## Implementation

The corpus loader now requires an explicit boolean source-kind label rather than forcing every
manuscript to be synthetic. The serial scheduler propagates that label into support/baseline
results and prompts. Public-article prompts do not invent journal permission, seeded issues or
error-free controls. Static audit packets and the offline replay checker accept either source
kind without granting qualification.

For synthetic quality evaluation, actual source/representativeness auditing may happen after
the run. The frozen manifest and the batch's original review label must still agree; historical
labels cannot be rewritten to manufacture approval. All artifact hashes, exact-build bindings,
three-repetition/baseline requirements and human/numerical-claim gates remain. Real-article
batches cannot be passed off as seeded-recall/clean-control qualification.

A deterministic JATS-to-text fixture converter verifies identifiers/licensing, retains all table
header rows/cells and records merged geometry. This avoids an observed Pandoc JATS→GFM loss of a
second header row. The transformation, graphics/supplement limitations and source hashes are
explicit. Full details and original-publication links: [six public articles](../evals/support-public-articles/README.md).

## Frozen candidate and verification

- Version `0.9.0b14`; protocol `medical-methods-v1`, answer contract 9, persisted schema 1.
- Build `/tmp/creview-support-b14-candidate-build.UvShKtRd`.
- Wheel SHA256 `fa1ab9c4fcd892f656aa42ba3fd6d8598d8c5664e7c913be76386867581f0c72`.
- Runner `9bb338f55ac483492fc01acc22cedabae14b81f400736c8b6c4b4eb81610b2fa`.
- All 51 packaged files match source and independently wheel-derived sums. Relative to frozen
  b13, only version, corpus contracts, provenance and qualification files differ. Medical module
  criteria, calculators, source parsing, rendering, workflow/routes and the skill are unchanged.
- Clean isolated Python 3.11.15 wheel install, 31 hash-pinned dependencies installed offline,
  source `pythonpath` disabled: **899 tests passed in 81.87 seconds**. Ruff, lock, shell syntax
  and diff checks passed. An earlier development test run exposed a stale documentation wheel
  path; it was corrected before the final installed-wheel run, not called a pass.
- Both-host bundle `/tmp/creview-support-b14-public.8nleg2dz`, 14 manifest-listed regular files.
  Manifest SHA256 `c515e8fdff00fc52fdd3b8c2641761b00e55a3e326e78d903c56925f5782b619`.
- Six real sources, eight tables, `independently_reviewed: false`, no planted errors/control
  roles. Corpus manifest SHA256
  `12b799d631cf60050078d1af7ba4acaf1c74e44d3345264abfe026e49d57def1`.

## Workstation run — started, not completed

New disposable runtime `/tmp/creview-support-runtime.tn0y3x2p`, Python 3.14.2, 25 hash-pinned
dependencies installed offline. Installed runner equals the frozen identity. Strict live
preflight passed outside Hermes (`runtime_status: not_in_hermes`), without generation; it is
not yet proof of any actual job's session metadata.

The existing Hermes version is `0.21.5+7498.gebadb54`, with the unchanged private gateway
`http://100.122.169.13:8091/v1`, model `qwen3.8-flash-next`, explicit context 262144. The existing
21-file runtime record's exact stat/process continuity passed before the batch. This does not
attest to loaded memory or prove gateway/network isolation. No service or regular profile changed.

Controller `2790871`, start ticks `124615457`, began at **23:19:33 UTC October 28**.
Controller SHA256 `0fba95a318c783a85ffad246f30a96302c6bc10c407eaffa36445346a7ed7e18`.
Driver `2790883`, sampler `2790873`. Idle slots were checked before inference. The controller
started a ten-second per-model-process sampler before the first job; this is a warm/shared
window, not an exclusive/cold-start benchmark or hardware minimum.

The batch is serial: statistics, qualitative study, SR, ScR, narrative review, logic; one
support run plus one actual ordinary-Hermes baseline per article. Responses are Korean; original
quotations/numbers remain unchanged. Per-case bound 1800 seconds, whole batch 21600 seconds.
Failures remain in place and are not restarted into passes. No original XML/public peer-review
reports or private keys were copied to the workstation. Source selection requires no approval.

At 23:22:48 UTC the actual statistics session's recorded runtime was verified, with explicit
context 262144. It had progressed through four of 24 tasks, retaining 50 facts with no refusal
yet; this is progress, not completion, attention or semantic accuracy. Other branches and all
baselines remain pending at that observation. Machine-readable snapshot:
`evals/deployment/b14-public-evidence-20261029.json`.

Authoritative live state: `suite-state.json`, `public-pairs/batch.json` and
`public-pairs-driver.log` under that runtime. At initial observation, the statistics support
case was running; no finished report, all-six-branch pass, final memory peak or quality score is
claimed. Finished artifacts will need receipt/source/hash and saved-calculation verification
before they are described as verified reports. The release gate remains closed.
