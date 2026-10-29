# B12 numerical-comparison view — 2026-10-29 KST

Frozen, unpublished local-model **review-support** candidate, not medical qualification.
Times below are UTC on October 28. The active deployment goal remains incomplete.

**Superseded by [b13](support-b13-development-20261029.md).** A verified fixed-epsilon arithmetic
comparison bug required a new candidate. The unstarted b12 controller was canceled at
16:53:59.443188 UTC, before inference and with no child jobs. Original queue-state bytes, bundle,
controller and logs are preserved; a separate cancellation record records the action. The queued
sections below describe historical setup, not current activity. None of the four unrun b12 jobs
is a pass. The renderer remains in b13 unchanged; earlier browser checks are not fresh b13
workflow or human approval.

## Deliverable

The static HTML/Markdown dossier now starts each calculation-bearing module with a compact
comparison table: calculation ID/method, compared output, original reported token and
source-derived relation, saved computed value, numerical agreement on selected inputs, and
comparison status. Conditional comparisons can agree **or differ**; neither result establishes
input-role correctness, scientific validity or an error. No new observation, priority or
reviewer decision is created. All replays remain in saved order, without ranking or quotas.

Computed values use their saved representation rather than another display-rounding step;
original reported tokens are preserved. Missing historical agreement flags are shown as
unrecorded, never inferred from status strings or coerced from nonboolean values. Links target
visible calculation headings; full inputs, outputs, evidence, assumptions and JSON remain in
expandable details. English/Korean navigation is deterministic. Contract 9 extends custom-language
labels. Historical custom-language snapshots missing these labels retain the detailed view;
English/Korean can use display-only defaults. Saved data and earlier exports are not migrated.

Narrow tables scroll horizontally with keyboard focus; metadata wraps without page-wide overflow.
No dossier JavaScript, external assets, browser app, model call or server was added.

## Exact candidate and local evidence

- Version `0.9.0b12`, answer contract 9, persisted schema 1, `medical-methods-v1` unchanged.
- Wheel `/tmp/creview-support-b12-final.xlQrkYcZ/closed_review-0.9.0b12-py3-none-any.whl`,
  SHA256 `51086c03754259961912db7a67db76d98fd313e0ff612083429bad530cf37993`.
- Runner `e95934c9e2be05d432fefb964a1b9beb5728a34ebd781f4df928bdf8daabfe2a`.
- All 51 package files match source and independent wheel-derived sums. Only four differ from
  b11: version, contract-version constant, localization and renderer. Arithmetic, extraction,
  workflow, medical criteria, profile/routes and skill bytes are unchanged. Earlier b11 passes
  do not qualify this new identity. The earlier b12 development wheel is preserved separately;
  only the final identity above was staged for workstation inference.
- Clean isolated Python 3.11.15 install, 31 hash-pinned test dependencies installed offline:
  **802 tests pass in 66.96 seconds**, with source `pythonpath` disabled. Ruff, lock consistency,
  shell installer syntax and diff checks pass. Exact-build release verification correctly
  refuses the empty gate. No publication, tag, push or regular installation was performed.
- 62 new comparison cases cover all 13 real calculators, conditional true/false, inequalities,
  literal notation, saved precision, absent/nonboolean flags, uncompared outputs, record order,
  localized/historical snapshots, hostile strings, unchanged data and export receipts.
- Local synthetic browser checks passed English/Korean at 1360×1400 and Korean at 390×1100:
  calculation links, expandable inputs/JSON, source targets, keyboard-scrolling and no page-wide
  horizontal overflow. The agent inspected screenshots. This is not independent human usability
  or translation approval. Browser record `/tmp/creview-support-b12-final.xlQrkYcZ/browser-qa.json`,
  SHA256 `e2b074f234b612014b7fd21e75c0cc4c6265cfb9cc645da0798e92ff0a090d58`.

## Separate checkpoint regression and serial queue

Evaluator-only `scripts/probe-support-bootstrap.py` wraps the unchanged recovery driver. It saves
a distinct first prompt requesting a stop immediately after `support start`, leaving the ordinary
prompt and manuscript intact. Passing requires an actual pristine `unissued` checkpoint, exactly
one same-session completion request, an issued checkpoint, a genuine three-turn interruption on
invocation 3, and completion within four to six actual invocations. Ordinary recovery cannot
substitute for this extra branch. Prompt/wrapper hashes remain explicit. Nine new unit cases and
30 focused recovery checks pass; this extra branch has not yet executed live.

- Bundle on both hosts `/tmp/creview-support-b12-candidate.0rq7fd6d`: 38 verified files,
  manifest SHA256 `408aa0a6d9fdcba488a3c0422d1ab590b9981d5b99013a4a9c4c87ebcee4af95`.
  Corpora, key-free manifests, existing evaluators and 25 locked runtime dependencies are unchanged
  from b11 harness 2. New source-review candidates, author proposals and private keys are not in
  the bundle. All source manifests remain independently reviewed **false**.
- Runtime `/tmp/creview-support-runtime.wzz1l14s`, Python 3.14.2, offline install, exact installed
  identity and strict live preflight passed without generation. Preflight was outside Hermes
  (`not_in_hermes`); actual workflow/session route checks still must pass.
- Controller `2513917`, start ticks `121944614`, queued at 15:54:25 UTC; SHA256
  `cd724e90d4e8960a04cf298f7dca95b4e332ad2428bce54347757b54ce943a2c`.
  Observed alive waiting for b11, no b12 suite/inference started. It requires the exact prior
  controller, jobs and sampler to exit, terminal records, then idle slots; it never stops or
  patches them. The existing 21-file runtime stat/process continuity is checked before/after;
  a new whole-window warm/shared sampler starts before inference. This is not a minimum-memory,
  exclusive-load or cold-start benchmark.
- Four targeted jobs: forced early-checkpoint/turn-limit recovery, Korean, explicit multi-module
  scope, and three paired eight-page Markdown/DOCX/PDF cases. Not a full qualification matrix;
  unexecuted jobs are not passes.

## Remaining work

Use the new b13 identity for regressions; do not restart the canceled b12 queue. Approve
independent source/test roles **before** formal runs; diagnostic corpora cannot be retro-approved.
Three paired repetitions, human precision/recall, coverage, numerical-claim fidelity, usefulness,
translation, baseline checking times and hardware review remain incomplete. Keys stay off the
model host and no judgments are fabricated. The source-only packet stays local while its Tailscale
sharing question is unanswered; no new server was started.

Machine record: `evals/deployment/b12-evidence-20261029.json`. Release gate remains closed.

Evaluator-only continuation: [source/calculation record reproduction](support-replay-checks-20261029.md)
adds 29 tests and verifies the completed b11 packet without changing this frozen wheel, bundle,
controller or queued jobs. The full installed-b12 suite now passes 831 tests in 75.54 seconds.
