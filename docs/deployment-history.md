# Deployment history — b2 through b15

This is the preserved development tracker, not the current release status. Entries below were
written at different checkpoints and include interim failures, missing evidence and subsequently
completed attempts. Later dated records take precedence for their own exact identities; they do
not erase earlier failures or qualify another build. See [current development readiness](deployment-readiness.md)
for `0.9.0.dev7`. The b15 engineering results below must not be relabeled as dev7 results.

Objective: fix/revise every medical support branch and its routes until the agreed local-model
review-support deployment is ready. This is not an automatic full review, an authoring agent,
a publication decision or a certification of medical correctness.

The target under active verification is jkworkstation's existing Hermes/Qwen private stack.
Other operating systems/model configurations must not be called qualified by inference from it.
The regular workstation profiles and model services remain untouched; current runs are isolated.

Latest attempt: [b15 persistent post-reboot retest](support-b15-restored-20261029.md).
That suite finished with five of six public support cases passing, all public baselines,
all native-format pairs and all recovery tests passing. Qualitative stopped before run creation;
a driver-only bounded startup fix now passes 995 local tests. The separate targeted qualitative
pair finished successfully at 09:34 UTC, with independent source/quote/receipt/export/baseline
readback verified. Its live startup completed normally; fallback recovery is deterministic-test
coverage, not a newly observed live recovery. The full batch's failure is not replaced by this
new attempt, and medical-quality/release qualification remains unestablished.
Implementation: [b15 limit/edit/rejection fixes and interrupted first retest](support-b15-recovery-20261029.md).
Previous real-paper result: b14 finished with three support passes and three failures;
all six baselines passed. The original failures are preserved and verified in the b15 record.
Last completed targeted suite: [b13 precision-safe comparisons and regressions](support-b13-development-20261029.md).
Previous exact-build evidence: [b11 six full-length pairs and broader engineering suite](support-b11-harness2-20261029.md).
Latest evaluator-only check: [six saved sources and 29 calculations reproduced](support-replay-checks-20261029.md).
Historical format evidence: [three finished b13 native-format pairs, 53 calculations reproduced](support-b13-native-20261029.md).
Earlier format evidence: [b11 native-format pairs and 40 calculations](support-b11-ordinary-native-20261029.md).
Additional format diagnostic: [short native pairs and strict cross-Python PDF mismatch](support-b11-short-native-20261029.md).

The targeted b13 engineering run is complete. On October 29 the user explicitly waived
approval of engineering test inputs: autonomous synthetic selection and public-article discovery
may proceed. The earlier source-only packet is optional, not a prerequisite or blocker.
The b14 revision separates real published articles from synthetic fixtures, removes mandatory
pre-run source approval, and retains genuine offline audits for medical-quality claims.
Real articles are not presumed error-free controls or known-error recall cases. Human medical/
fidelity/usefulness/translation, checking-time and hardware judgments remain missing; neither
engineering passes nor old F1–F10 decisions fill them. No new Tailscale server has been started.

## Current b15 engineering evidence

The frozen b15 candidate is **not deployment-ready or release-qualified**. Its latest installed-wheel
run passed 946 tests (including four new outer-controller tests), and its first attempt's four
actual-Hermes recovery jobs passed; copied evidence independently reproduces four
source snapshots, four receipts and 19 calculations. Those recovery jobs exercise one synthetic
article repeatedly, not all six medical branches.

The workstation is reachable again after a reboot. The original temporary test root and
processes are absent, so the first attempt is interrupted with public/native outputs unverified.
A new exact-b15 attempt started at 03:58:04 UTC in persistent private storage after runtime
and strict preflight checks; it does not replace or upgrade the old attempt. At 04:00:49 UTC,
statistics had accepted 3/23 tasks, with no gaps or module failures; one exact-quote refusal
was repaired within the existing refusal bound. See the latest-attempt record above.

The last observed real-statistics run reached task 23/23 with status `partial`, 179 facts,
13 calculations, four unjudged observations and no recorded task failures. Its final case result,
export and coverage-gap explanation have not been retrieved. No all-six public-pair or three-format
native-pair pass has been established for b15. Earlier candidates do not qualify this identity.

Previously, on October 29 at 02:54–02:57 UTC, SSH connections, Tailscale ping and gateway reads failed;
the local Tailscale daemon reported the workstation offline, last seen at 02:50 UTC. This is lost
observation, **not evidence that the remote jobs stopped**. No job, service or regular profile was
restarted or changed. Later reboot/path/PID checks, not those timeouts, establish the original
attempt's interruption. Its lost coverage-gap detail remains unknown.

An offline exact-b15 audit revalidated the 23-file bundle and all six unchanged public manuscripts.
All 2,252 source blocks are scheduled exactly once in source-snapshot order; all 1,048 native table
cells, 181 intact rows and original extracted table text are retained. All six sources have no
parser warnings. This rules out a reproducible parser-warning explanation for the statistics
`partial` status under these inputs, but **does not identify its actual recorded coverage gap**
or prove the model reconstructed the delivered content. Eight focused scope/coverage-status tests
also passed against the installed wheel. See
[`b15-offline-boundaries-20261029.json`](../evals/deployment/b15-offline-boundaries-20261029.json).

The next required evidence is the original saved statistics gap/rejection records, completed
real-paper/native pairs, and exact-build source/receipt/calculation readback. Preserve the frozen
b15 inputs, wheel, harness and any unsuccessful results; a further implementation change needs
a new candidate identity. Human medical-quality, fidelity, translation and usefulness judgments
remain unassessed, and the release gate remains closed.

## Requirements and historical authoritative evidence

The table below records earlier qualification evidence and outstanding gates. It is not a
current-candidate pass table; use the b15 section above for the current engineering status.

| Requirement | Evidence needed | Historical evidence / remaining work |
| --- | --- | --- |
| Local main and auxiliary inference; no hidden cloud route | Strict configuration tests plus actual-session provider/endpoint checks and live preflight | Fresh b13 strict preflight and all six route-bound targeted jobs passed. Actual main-session metadata was verified; profile checks cover auxiliary pins. Not an OS network-isolation or gateway-forwarding guarantee. |
| All six branches: statistics, qualitative study, SR, ScR, narrative, logic | Unit contracts plus real Hermes cases per branch; qualified human judgments | B11's six full-length pairs and twelve-case matrix passed engineering checks; whole suite failed its genuine-compression job on exact quotes. B13 is a new identity with six targeted jobs, not qualified by earlier passes. No branch medically qualified. |
| Type-appropriate module routing, explicit user scope | Advisory routing tests, multi-module tests and live scope checks | Fresh b13 statistics+logic export, receipt/source readback, calculation reproduction and per-module record-ID scope checks passed. This does not prove semantic independence in a shared model conversation. Deliberate failure isolation has separate preserved b11 evidence. Human audit remains required. |
| Manuscript only, exact provenance, no invented raw-data/citation validation | Source-binding, malformed evidence, extraction tests and human dossier audit | Exact checks retained, including rejection of double-escaped table line breaks. Saved-source/calculation readback covers b11 full-length, native and twelve-case matrix plus the live b13 precision replay; a cross-Python PDF bbox failure remains recorded separately. No source/answer repair or medical certification. Human audit pending. |
| Honest workflow status; stable snapshots | Scope-versus-coverage tests, failure exports and receipt/snapshot checks | All 31 b11 receipts (including failed/not-assessable modules) and all eight b13 receipts verify against independent sums. Eight b13 snapshots and 68 calculations reproduce without upgrading failures or filling judgments. The three full-length native-format pairs are finished. |
| Useful, nonduplicated observations, not a criticism quota | Grouped calculation tests and readable exports; human false-alert/miss assessment | B13 displays calculations separately from model proposals and preserves conditional differences. Native runs proposed zero observations; that does not prove no issue or adequate coverage. Precision, recall and useful prioritization remain unestablished without human review. |
| User language, static headless dossier, optional genuine reviewer decisions | Locale, HTML safety, attribution, export tests plus live language/UX checks | B13 retains b12's EN/KO comparison overview and corrects comparison boundaries. Its Korean workflow passed and copied source/calculation records reproduce. Historical synthetic browser checks remain separate; human fidelity/usability/translation unapproved. No automatic reviewer decisions. |
| Normal-length and difficult manuscripts within local/Hermes limits | Full-length, DOCX/PDF/ambiguous extraction, context and interruption/compression evidence | All three b13 eight-page fixture pairs passed: receipts/sources/actual baselines verified, three saved snapshots and 53 calculations reproduced. Expected paragraphs/grids match under explicit fixture policy; separate strict PDF cross-format differences remain. One invented article, not independent medical qualification. No source/quote repair; analytical coverage and human fidelity unverified. |
| Repeated medical qualification and same-model baseline | Independent audited cases and three repetitions, offline human judgments/checking times, exact build/model | Hash-bound corpus, original evaluation batch and actual paired baselines are required by the offline scorer. Actual source/medical audits remain incomplete; b14 no longer requires input preapproval. Real-paper engineering batches are not seeded-recall qualification. Keys stay off the model host. |
| Hardware/runtime reproducibility | Model/weight/quantization/runtime/context identity and memory observations tied to the candidate | 21 runtime files hashed; b13 final stat/process continuity passed. Its complete warm/shared window has 268 GPU/RSS samples, sampled peaks 23,682 MiB GPU and 60,910,832 KiB RSS. Not exclusive/cold-start/minimum-memory or loaded-memory attestation. Human hardware audit missing. |
| Release/install readiness | Clean locked wheel installation, correct installer flags, strict doctor, exact-build gate and complete audits | 868 tests pass against installed b13; 40-file bundle verified on both hosts and strict preflight passed. All six targeted jobs completed, eight receipts/twelve source copies/four baselines verify, 68 calculations reproduce. B12 was canceled before inference, not passed. Formal all-branch evaluation and human gates incomplete; release correctly refused. |

Do not mark this objective complete from unit tests, one smoke, or a twelve-case pilot alone.
The qualification target remains 90% concern precision, 80% seeded recall per branch, no
unsupported computed-error verdicts, three repetitions, human coverage/usefulness review,
baseline checking times and workflow/hardware audits. Failing modules and missing judgments
must keep qualification false. Publication is not authorized merely by building a candidate.

## Preserved b2 candidate

- Version `0.9.0b2`, protocol `medical-methods-v1`, answer contract version 2.
- Runner sums: `fbffd1c858852cd88ff34657b3422a3f2d9c467d6866eec728cca324f08f53ac`.
- Wheel SHA256: `6101e72c76e84db2a711b160c7ca2a36a351db443212934a71ad521ae1dd2ffe`.
- Workstation bundle: `/tmp/creview-support-b2.afTeOvLC`.
- Isolated runtime: `/tmp/creview-support-runtime.xcbRvbOc`.
- Focused statistics result: `results/batch.json` under that runtime. Engineering passed in
  167.68 seconds, five calculations, one observation, no refusals, one verified export.
- Full matrix: `matrix/batch.json` under that runtime. Finished: 9/12 engineering passes.
  See [b2 results and failures](support-b2-results-20261028.md).
- Local verification: 308 tests passed on the locked runtime dependencies and installed candidate,
  including installer context/strict-doctor tests and PowerShell syntax parsing. Ruff and lock
  consistency checks pass. Native Windows/macOS Hermes behavior is not qualified by this.
- The focused statistics artifacts were copied back and receipt-verified locally at
  `/tmp/creview-support-b2-results.sOg4iaWK/statistics-smoke`; the archive hash is
  `6932cddffb91961c4a1b5d243f3eda4724d797a918a0783cbe06b543917e142f`.

Only results tied to this exact runner count for this candidate. Changing packaged code or
the skill requires a new identity and fresh qualification evidence; preserve earlier failures.

### Frozen b3 results

- Package `0.9.0b3`, answer contract 3, protocol unchanged.
- Runner sums: `a81c219d65334c60730acc81322aa94d85f51b032662e9007e8b7633df59145f`.
- Wheel SHA256: `461fc0793348484782b9bac3b0a03275a23ec149c9d0d11f34207c47b99a0b4d`.
- Bundle `/tmp/creview-support-b3.xldit8wu`; isolated runtime
  `/tmp/creview-support-runtime.rodzYY64`; live matrix `results/batch.json`.
- 352 local tests pass with the installed candidate; Ruff passes. Evaluator-only audit-reference
  tests are additional checks, not changes to the frozen installed candidate.
- Field-specific quote/numeric diagnostics and preserved rejected submissions; exact calculator
  keys/parameters/outputs; no coercion of written-out numbers, expressions or derived totals.
- The image-only PDF probe passed its distinct not-assessable engineering checks in 36.05s.
  Forced turn-limit recovery resumed the same run after a harness correction, but its statistics
  appraisal then failed on the ambiguous model-supplied comparison field. That probe remains failed.
- Additional standalone scope probes cover explicitly selected statistics+logic, injected
  single-module failure, Korean output and deterministic 6,500-word traversal stress. Their
  ten local tests pass, including real workflow failure isolation. They are not live evidence
  yet and do not establish corpus realism, clinical accuracy or translation fidelity.
- The completed matrix passed 11/12 engineering cases. All b2 stops completed, but case 06
  introduced a new calculator failure; this is not proof of repeatability. Case 05 retains
  two unjudged proposals, not two established problems. See [b3 evidence](support-b3-results-20261028.md).
- One real ordinary-Hermes case-02 baseline passed route/preflight/tool-trace/output checks in
  66.91s. It is not a medical-quality, semantic-independence or speed-ranking result.
- 403 local tests passed before the b4 development edits. The serial paired-repetition scheduler,
  key-free manifest and offline paired/repeated-case packet are implemented and tested, not
  a substitute for running independently reviewed cases. Human judgments/checking times stay blank.
- Both b2 and b3 are unpublished candidates, not qualified releases. Installer defaults name
  the candidate version but require an explicit built wheel until a release is authorized.

Read-only host checks confirmed gateway Qwen upstream `http://127.0.0.1:1919`, backed by the
existing Strata service. Native settings include IQ3_S pack, int8 KV, maximum context 262144,
resident KV 32768, conversation cache 8192 MiB and speculative/MTP configuration. Strata HEAD is
`7f783d192e4e1562c8830f4cd6f09de80cc9561c`. Gateway repository HEAD is
`959b9a36aa558e20689b597e1fed7a234715caee`, with local source modifications: HEAD alone is not
its runtime identity. Weight hashes and attributable peak-memory measurements remain
pending. Observed total GPU usage includes concurrently loaded services and is not a model
memory requirement or peak. No services/configurations were modified for these checks.
Observed source/binary hashes and deliberately missing hardware fields are recorded in
`evals/deployment/b3-runtime-observations.json`; this record is not a qualification approval.

### Continuation handles

The b3 matrix PID `1870011` has finished; authoritative results are
`/tmp/creview-support-runtime.rodzYY64/results/batch.json`. Its baseline and image-only probe
also finished. The initial turn-limit result at `probe-turn-limit/probe.json` is a preserved
harness failure (expected CLI exit incorrectly treated as fatal). Corrected harness bundle:
`/tmp/creview-support-b3-probes-v2.Wl1lMKVV`. Its `probe-turn-limit-v2/probe.json` confirms real
same-run recovery but a later calculator refusal; it remains failed. Do not erase or restart
these results to count them as passes. Use a new explicit candidate/harness identity for revisions.

Verified b3 packet: `/tmp/creview-support-b3-results.l5cPPJY4/comparison-audit` includes all twelve
original manuscripts, nine observations and the paired case-02 baseline. Human judgments,
expected issues and checking times remain blank. Independent original-build sums are saved at
`/tmp/creview-support-b3-results.l5cPPJY4/independent-runner.sums` for historical verification.

Verified b2 evaluator packet revision with headless-readable `OBSERVATIONS.md`:
`/tmp/creview-support-b2-results.sOg4iaWK/matrix-audit-v2`. It retains all original manuscripts;
all reviewer judgments remain blank. Nothing from this evaluator packet belongs on the model
host. Do not request semantic approval for a new candidate before its diagnostics are complete.

### Preserved b4 numeric diagnostic

Source version is now `0.9.0b4`, answer contract 4. Models no longer supply a comparison
operator. Python derives the qualifier from complete numeric tokens in the original source
block, not a possibly clipped quote. It refuses ambiguous qualifiers, bound-valued operands
and numbers that would lose fractional precision, then computes the comparison. The
repair path instructs omission of an unavailable replay, never changed quantities or invented
inequalities. All 423 tests passed against the second development wheel. Its two-case live
diagnostic completed successfully; none of this is medical-quality qualification.

Development test wheel only: `/tmp/creview-support-b4-dev.aOD0tmKM`, wheel SHA256
`9d37c3fb61ef1e1ca02681724fb4a8dacd87b3ee583ffb4e30624e6c68a88f2e`, runner sums
`49dc67b0b5756cad704b1a6c003e532b96f32a4d9fb54d7ed31329f62ffa6c2f`.
That first wheel is preserved, not deployed. The newer development wheel is
`/tmp/creview-support-b4-dev2.kVhk1mG5`, SHA256
`cb503b70cd0930d1412ee65e540842e929b78ce045eed0fd6b8f2cadc1420f66`, runner sums
`4fcec1e1d222c6811f7ea9a0dcfa7a49e595034a33f74eee50005cb8fd7ec627`.
It remains in its isolated workstation diagnostic environment, not a regular Hermes/review
installation. This is not the final b4 candidate; subsequent packaged changes have a new identity.

Two-case b4 diagnostic: bundle `/tmp/creview-support-b4-diagnostic.KDriMH0x`, runtime
`/tmp/creview-support-runtime.JRDtLPRg`, results `results/batch.json`, remote PID `1930917`.
It finished cases 02 and 06 serially: complete in 182.79s / 178.62s, one / two observations,
five / one calculations. The SR replay did not invent a subtotal comparison when a source
count was written out. Both dossiers/receipts verified after evaluator transfer. One exact-quote
refusal in case 06 was repaired. Human validity/recall judgments are still blank.

Evaluator archive SHA256: `40e7a983d23861131e550af1c9b801313406d24bfce8bbc3a58ca62d935bee93`.
Verified static/headless packet: `/tmp/creview-support-b4-numeric-results.jI3nUNWw/audit`,
two original manuscripts and three O-labeled proposals; no human judgments, key import or server.

### Frozen b4 diagnostic — completed, not deployment-ready

- Version `0.9.0b4`, answer contract 4, protocol unchanged.
- Runner sums: `becf7ad4a5d77f1fc2fb500923ba8eeba1da822d0852d6a7511837b87ffdf1fb`.
- Wheel SHA256: `a2a2b01946c06c799bcfcff7c747bdc2ebb5e100315dbe365b7b7b151e365393`.
- Bundle `/tmp/creview-support-b4-candidate.94SJuVLo`; new workstation runtime
  `/tmp/creview-support-runtime.fIobqKL4`, Python 3.14.2, hash-pinned dependencies.
- 463 local tests pass against the installed frozen wheel. Ruff, lock consistency and diff
  checks pass. Workstation bundle hashes and installed identity match; strict live doctor
  passes in a separate disposable preflight profile without generating text.
- Matrix harness: `7739fd82a9c2398d06106c995b2ede466cb1aa18567590599015c525727811ce`.
  PID `1966320` has finished, results `matrix/batch.json` under that runtime. The twelve-case
  serial matrix ran 07:11:16–07:38:59 UTC and passed 11/12 engineering cases. Case 05 failed;
  all failures are preserved. See [the complete b4 result](support-b4-results-20261028.md).

The first seven recorded cases contain six engineering passes and one preserved SR failure
(case 05). That failure first reported an inexact quote, then an unprinted numeric token on
the repair. Both rejected payloads remain. A further read-only Hermes inspection also found
that statistics task output is about 145,489 pretty-printed characters before a fact index,
against this runtime's default 50,000-character terminal capture. Overflow is saved by Hermes,
but direct task delivery is incomplete. These observations disqualify b4 as a deployment
candidate even if its remaining short cases complete. It is not upgraded in place.
A read-only case-01 session trace confirms one spill/truncation event in its five recorded
next/read terminal results, with largest captured output 49,864 characters. Whether the model
subsequently recovered that content is not certified by the count. The associated metadata,
per-process hardware snapshot and deliberately missing weight/peak identities are recorded in
`evals/deployment/b4-runtime-observations.json` without copying the session database.

New scoring checks bind all three repetitions to the unchanged original evaluation batch,
source/build/model/context and actual paired baseline outputs/traces. Earlier builds required
independent input approval before evaluation; b14 removes this unnecessary timing restriction.
An actual offline audit of frozen synthetic sources and representativeness is still required
for quality claims, and recorded input-review labels cannot be rewritten. Numerical-error
claims are checked regardless of observation kind,
and human review must cover claims in summaries/appraisals as well as final observations.
All human judgments, corpus/baseline reviews and checking times remain blank in generated packets.

The valid-length verbose-record regression exceeded the old consolidation budget. Large
consolidations now provide indices and bounded reads instead of stopping simply because of their
combined record size. Individual oversized records are delivered in lossless JSON-text fragments;
all required records/fragments must be supplied in the current task before submission. Every read
is at most 12,000 pretty-printed JSON characters, including escaping. Missing pages do not consume
a repair attempt. Tests cover Korean/Unicode/escaping, gaps, prior-task reads, full calculation
assumptions and module scope. Delivery is not proof of attention, understanding or clinical validity.
Other unhandled task-context/source-block limits still stop visibly, not by silent truncation.

Actual recovery/scope/language/long-source checks on this exact candidate remain pending, as do
independently validated realistic cases, three repeated paired evaluations, expert audits and
candidate-attributable hardware measurements. The release gate remains closed.

### Frozen b5 diagnostic — completed, one partial logic case

- Version `0.9.0b5`, answer contract 5, protocol unchanged.
- Runner sums: `06fdb81157279615424b5b67e88e3fad3f7b3e9c152e5d978e831d5838c7ed0f`.
- Wheel SHA256: `75e77406ae89671533bdb569f8418e16afcf04e2649486fd8179c16b8d42b0b0`.
- Bundle `/tmp/creview-support-b5-final.kaWTwR2E`; new isolated workstation runtime
  `/tmp/creview-support-runtime.KrdIdTxe`. Independent evaluator reference sums are in the
  bundle. No ordinary profile or service was changed.
- 541 local tests pass against the installed exact wheel; Ruff, lock/diff checks and packaged
  skill equality pass. The workstation independently verified every bundle hash, installed
  hash-pinned dependencies and passed strict live doctor without text generation. Explicit
  capture limits are 50,000 terminal characters, 2,000 file lines and 20,000 characters per line.

Standard JSON Schema `$defs` / `$ref` and a factored calculator base remove repeated contract
text without relaxing calculator inputs, parameters, output enums or evidence rules. A generated
comparison of 1,404 answers against the b4/b5 wheels found no acceptance differences; this is a
finite contract regression check, not proof of scientific validity. A full test fact index now
produces about 39,400 statistics-task characters, rather than over 150,000. The initial index
contains twelve entries and explicit continuation. Every complete printed task is bounded at
45,000 characters, including its paths and commands. Other oversized payloads stop visibly.

Managed profiles explicitly configure Hermes capture limits; strict support preflight refuses
missing/lower/malformed limits and freezes them into each run's route. Each next/read must run
separately; concatenated tool outputs could still exceed the combined capture budget. This is
not an OS sandbox or a guarantee of attention. Existing profiles are preserved, not silently edited.

Source-reference and numeric-binding problems are now diagnosed together before any semantic
write. A missing numeric token is identified even if its quote also has a punctuation error,
so a single repair can address both. Calculations are never dropped or rewritten automatically,
and two refused answers still stop the module. The initial b5 development wheel at
`/tmp/creview-support-b5-candidate.mwwxWO5a` is preserved separately and is not this candidate.

The b5 matrix finished at 11/12 engineering passes, with case 12 partial. It had no extractor
warning or execution failure, but declared general uncertainty/no-certification statements as
free-form coverage gaps. The original result remains partial; it is not promoted by a later
implementation change. See [the full b5 results](support-b5-results-20261028.md).

The bounded b5 launcher in local tool session `78935` observed b4's completed twelve-case result,
checked an idle model slot and verified the installed b5/harness identities. It started the
new b5 matrix at 07:39:09 UTC, PID `2000184`; it finished at 08:08:47 UTC. Queue state is
`/tmp/creview-support-runtime.KrdIdTxe/queue.json`; output is `matrix/batch.json` in that runtime.
Case order is 05, 06, 02, 01, 03, 04, 07, 08, 09, 10, 11, 12, prioritizing the diagnostics without
omitting comparison cases. The first three cases (05, 06, 02) passed engineering checks in
167.12s / 174.92s / 148.87s. A read-only actual-session statistics trace contains four direct
next/read terminal results, largest 39,402 characters, without spill handles or truncation
markers. This is delivery metadata, not proof of model attention or semantic review. The
completed matrix does not qualify a successor. The evaluator packet at
`/tmp/creview-support-b5-results.QqS3ppwx/audit` retains all twelve originals and eleven proposals;
all twelve receipts verified. No independent human judgments or quality metrics have been supplied.

### Frozen b6 candidate — completed, broader suite failed

- Version `0.9.0b6`, answer contract 6, persisted schema/protocol unchanged.
- Runner sums: `af326686c57ad42b2d932176bed9dca46067981905b26dd426781e3e704b6622`.
- Wheel SHA256: `e8998d8e62557548d332551d984d83d03c47e56da9b7b87542efdd1ff03a49bb`.
- Bundle `/tmp/creview-support-b6-candidate.soQ6AXJt`; isolated workstation runtime
  `/tmp/creview-support-runtime.1s3lCpTe`. Exact bundle hashes, installed identity and strict live
  preflight passed. Existing Hermes remains `0.21.5+7498.gebadb54`; no service/profile upgrade.
- 549 local tests pass against the frozen installed wheel, including a source-draft integrity
  check. Ruff, lock/diff checks and packaged skill equality pass. Source parsing/hash checks
  do not certify medical correctness or change the frozen package.

Coverage gaps now require a kind, assigned source-block IDs, an affected guide role and a concrete
description of what could not be reconstructed. A fact-cap declaration requires 24 extracted
facts. Free-form gap strings and obsolete extraction `limits` are refused in new answers;
normal scope caveats require explicit correction, never an automatic keyword-based waiver.
Historical reports remain unchanged/readable. Genuine structured gaps still make processing
partial and block qualification, even if a status is incorrectly labelled complete. Their
dossier entries link affected source blocks; duplicated extractor warnings are displayed once.
Typed provenance is not a certificate of correct semantic classification.

Live suite tool session `78914` owns the current work. Matrix PID `2046243` started at
08:34:40 UTC; inspect `suite-state.json` and `matrix/batch.json` under the runtime before
launching anything else. Case order: 12, 11, 01, 02, 03, 04, 05, 06, 07, 08, 09, 10.
All twelve cases passed engineering checks. The logic regression (12) completed in 172.18s
without refusals, preserving four scope caveats and declaring no processing gaps. This is an
execution/classification observation, not adjudication of its two proposed concerns.

The controller ran only one inference job at a time and checked for an idle model slot before
each next job. After the full matrix passed, it proceeded serially to forced turn-limit, forced
compression, unreadable-PDF, explicit multi-module, injected single-module failure, Korean and
6,500-word traversal probes, followed by one ordinary-Hermes case-02 baseline. Every job uses
new profiles/output directories. Independent probe failures are retained; no job is restarted.
The suite finished at 09:26:18 UTC with overall engineering failure: the interruption module was
partial, compression commits went unrecognized by an outdated event detector, and the fault
harness was stopped by its environment route mismatch before injection. The other probes and
baseline passed their engineering checks. Originals remain unchanged. See [b6 results and
corrections](support-b6-results-20261028.md), including all eighteen verified export receipts.

The new [ordinary-length draft corpus](../evals/support-ordinary-draft/README.md) now covers all
six branches with connected 3,746–4,278-word manuscripts. Each has three tables, no parser
warnings and five to seven extraction chunks. Its manifest is key-free and explicitly
unreviewed. Source/hash/traversal integrity passed; the sources were copied into the b9 bundle
for one engineering support/baseline pair per case. No realism, clinical quality or checking-time
result is established. Independent source approval, control/seeded variants, three formal paired
repetitions and expert coverage/validity/checking-time audits remain required. No release is approved.

### Frozen b7 candidate — engineering suite passed, not medically qualified

- Version `0.9.0b7`, answer contract 7, persisted schema/protocol unchanged.
- Runner `40b4b825d7a1a4a2d23865cdbde4640ace44e254f0be81e0fb24f0aa1852cd1e`.
- Wheel SHA256 `7b50794106a5c0dcc73419f48a91275207a07f0d051dd0426bf3f6760f3a9186`.
- Bundle `/tmp/creview-support-b7-candidate.E7TJrlTM`; isolated Python 3.14.2 runtime
  `/tmp/creview-support-runtime.keFl4Rdl`. All bundle hashes, installed runner identity and strict
  live preflight passed without changing services or regular profiles. 560 local tests passed
  against the installed candidate; Ruff, lock consistency and diff checks passed.

Physical `ambiguous_structure` declarations must cite extractor-flagged blocks; legible
contradictory values must be preserved for appraisal rather than reconciled at extraction.
Actual semantic reconstruction failures can still be declared and remain partial. The check
does not automatically remove gaps or certify source understanding. Ambiguous Markdown native
geometry now also taints its retained flattened table evidence, including historical snapshot
locators, so numeric replay cannot bypass a flag by selecting the old table block. PDF ambiguous
page restrictions remain conservative; no OCR or automatic geometry repair was introduced.

The compression harness recognizes same-session committed, non-fallback structured attempt
telemetry as well as the older completion event. The injected-failure harness mirrors only the
managed vision provider/model selectors; route guards are unchanged and regressions verify real
changes still fail closed. Both received new live evidence; neither promotes b6's old failures.

Suite session `49528` started at 09:28:20 UTC after b6 finished. The forced turn-limit probe
(PID `2107966`) finished successfully at 09:31:27 UTC: actual interruption, same-run recovery,
complete statistics module, one observation, three calculations, no execution failures and all
recorded integrity checks passed. Compression (PID `2111646`) finished successfully at
09:36:53 UTC, with a real committed compression and complete statistics result. The injected
failure probe (PID `2116444`) passed at 09:39:41 UTC: two deliberate schema refusals stopped only
statistics; logic completed and its context remained isolated. These are not medical-validity
judgments. The full matrix finished 12/12, with nine observations and fourteen calculations.
The suite finished at 10:22:13 UTC with all nine engineering jobs passing; controller `2107963`
and matrix `2119287` are terminal. The unreadable-PDF, explicit multi-module, Korean, repetitive
traversal and ordinary-Hermes baseline checks also passed. Each job used a new profile/output.
See [complete b7 results](support-b7-results-20261028.md). The suite remains engineering-only
and `not_qualified`; realistic native-format cases, approved all-branch corpora, three paired
repetitions, expert audits and exact hardware evidence remain.

The three completed priority probes were copied back to
`/tmp/creview-support-b7-priority-results.OJqQD6Z6`: 75 regular allowlisted files, 994,256 unpacked
bytes, no credentials/configuration/session database. Archive SHA256
`b206e02e39bb7938ee68893de0aca65f12fb27ed1b48a14928a23c2ef11e8d3e`.
All three export receipts independently verified against the original b7 wheel sums. This
preserves the intentional statistics-failure dossier as such, not an ordinary completed review.
Human fidelity/validity judgments remain absent. After the suite finished, all results were
collected at `/tmp/creview-support-b7-suite-results.b4Icjyiv`: 455 regular allowlisted files,
6,353,274 bytes, archive SHA256
`345ee3f56e3c4cde1da214f2670e4f0503576c575188054a845f707ee9885d7a`.
All nineteen receipts verified independently. Its `matrix-audit` contains twelve originals
and nine O-labeled proposals; human judgments and checking times remain blank.

### Frozen b8 native-format diagnostic — PDF quotation failed

- Version `0.9.0b8`, answer contract 7, protocol unchanged. Development runner
  `fc7e7ee468171179c8bcc160f6251399903d528879ca87d89fe8d9017e03c9ac`.
- Wheel `/tmp/creview-support-b8-development.D4EFOigC/closed_review-0.9.0b8-py3-none-any.whl`,
  SHA256 `4afa0716836f65c0c9a58598ee11fac8c882bd31d08e4abf88ab338861bdb1c5`.
- 571 local tests passed against this installed wheel; Ruff, lock/diff and Node syntax checks
  passed. It is not an all-branch-qualified build and does not replace b7's historical evidence.

One invented article was converted to native Word tables and rendered PDF. Its one-page output
was visually inspected by the agent; this is not independent human medical review. All expected
paragraphs and the 5-by-3 table grid survive unchanged in Markdown, DOCX and PDF. The fixtures,
checker report and render are in `/tmp/creview-support-native-formats.siGXEe71`. Hashes, generator
versions, visual-check scope and deliberately absent human approval are recorded in
`evals/deployment/native-format-fixture-20261028.json`. They are three formats of one short
synthetic article, not three independent medical cases or approved controls.

This reproduced a format-status defect: b7's readable unambiguous PDF receives a generic caution
as a warning, making every such result partial. B8 preserves that caution in explicit source
and module scope limits. Actual detected geometry ambiguity now produces a localized warning
for every supported table format and still makes processing partial. Images, scanned/unreadable
text, Office Math, real semantic reconstruction gaps and historical partial results remain
conservative. No existing report was reclassified; no absence-of-flags completeness certificate
was added. Expected-content/grid tests are not proof of no hidden or omitted content.

Native diagnostic bundle `/tmp/creview-support-b8-format-diagnostic.TFfH0Tvx` contains only the
development wheel, hash-pinned dependencies, three harnesses, independent runner sums, the
key-free unreviewed manifest and its three source files. Build/render/checker metadata remains
on the evaluator. Workstation runtime `/tmp/creview-support-runtime.t5MkgBGS` independently
verified bundle/runner hashes and passed strict live preflight without inference.

Queue session `90254`, controller PID `2131296`, ran only after b7 finished and is now terminal.
The diagnostic finished at 10:32:28 UTC, exit 1. Markdown and DOCX support completed; PDF stopped
after two exact-quote refusals because extracted layout line breaks were reflowed in answers.
All three ordinary-Hermes baselines passed their engineering checks. Original failures remain.
See [b8 format results](support-b8-formats-20261028.md). Its evaluator directory
`/tmp/creview-support-b8-format-results.nWRQ0VAH` contains 78 allowlisted files, 989,616 bytes,
archive SHA256 `efe69e1c55da68d912d5543dc30eb3ff31f8981a4fa16aa9c13533467cfc73f4`.
All three receipts verified. Its `audit` retains originals, two proposals and actual paired
baselines with all human judgments/times blank. This was one engineering repetition, not formal
qualification; no regular profile, model service or human judgment was changed to count a pass.

### Frozen b9 candidate — short engineering checks passed; full-length failure preserved

- Version `0.9.0b9`, answer contract 7, persisted schema 1 and protocol unchanged.
- Runner `02d047cef7658cb5c1290723743f8e0b6b68344a9cc546e6f35a4f3603f7f3b8`.
- Wheel SHA256 `5e628d579a43b1955164f60742fdedb175bcbd33d2a81c920a6ce0100761331e`.
- Bundle `/tmp/creview-support-b9-candidate.Lp4XBGE0`; isolated Python 3.14.2 workstation
  runtime `/tmp/creview-support-runtime.jwiCD2vE`. All hashes, installed identity, hash-pinned
  dependencies and strict live preflight passed. Existing profiles/services are untouched.
- 589 local tests passed against the installed wheel before freezing. An evaluator-only baseline
  checker correction adds twenty regressions without changing the packaged runner or live bundle.
  The last b9 local suite passed 631 tests in 63.05 seconds, including evaluator-only source
  candidate tests; its installed runner identity was unchanged. Subsequent b10 packaged changes
  have a different identity and do not replace this evidence.

New PDF snapshots use `pdf-layout-whitespace-v1`: `block.text` canonicalizes whitespace only,
while changed blocks retain original extracted layout as `extracted_text`. Raw layout is visible
in exports, not duplicated in the default extraction task. No answer is automatically corrected;
words, punctuation, hyphenation and numeric tokens are unchanged, and exact substring matching
remains mandatory. Historical snapshots/results are untouched. Fourteen focused regressions
include token preservation, wrong-number/punctuation/hyphenation refusals, old-source behavior
and inert escaped layout rendering. The original b8 answer passes reference checks only against
a fresh b9 snapshot; this mechanical replay is not live model or medical-quality evidence.

Suite session `59898`, controller `2196301`, started at 11:01:30 UTC. The native-format job
finished at 11:13:20 UTC: all three support runs passed, but the PDF baseline failed the frozen
checker's omitted ordinary `search_files` tool. Its failed record remains. A separate read-only
revised-checker diagnosis passes without changing its original result. See [b9 format evidence](support-b9-formats-20261028.md).
The full matrix finished at 11:46:12 UTC, 12/12 engineering passes, thirteen observations and
fifteen calculations. PID `2210675` is terminal. The turn-limit probe, PID `2251801`, also
finished successfully at 11:49:07 UTC: an actual forced interruption, same-run recovery and a
complete statistics result in 174.56 seconds, with one observation and two calculations.
Compression PID `2255634` finished successfully at 11:56:24 UTC in 436.98 seconds, with three
actual committed non-fallback compressions and a complete statistics dossier. Two other attempts
were aborted; starts/aborts do not count as commits. The image-only PDF probe also passed at
11:56:59 UTC in 34.55 seconds, retaining `not_assessable`, no extracted text/tasks/calculations/
observations and visible extraction warnings. The explicit statistics+logic probe passed at
12:01:48 UTC in 288.83 seconds. Injected failure isolation passed at 12:04:43 UTC in 175.32
seconds, keeping statistics failed and logic complete after two deliberate refusals. Korean
smoke passed at 12:07:33 UTC in 169.56 case seconds. Repetitive long-source traversal passed
at 12:13:32 UTC (253.59 case seconds), followed by an ordinary-Hermes baseline pass in 64.81
seconds. These are not semantic-independence, translation-fidelity or medical-validity judgments.
The ordinary-length batch and suite finished at 12:58:57 UTC; controller `2196301` and job
`2283916` are terminal. Overall engineering remains false because native paired and ordinary-
length jobs failed. Five of six full-length support cases and all six baselines passed. See
[the b9 matrix result](support-b9-results-20261028.md). The evaluator copy at
`/tmp/creview-support-b9-matrix-results.EbcnWNag` contains 273 allowlisted files, 3,848,829 bytes,
archive SHA256 `5f253e20490b6e1a5233f7aa0b803a8b04b58df6b2be0665cf90f1280d41e4de`.
All twelve receipts independently verified. Its audit retains all originals and thirteen proposals;
human judgments, expected issues, baseline reviews and checking times remain blank.
Eleven jobs run serially, checking the model slot before each: the three-format paired regression,
full short-case matrix, turn-limit, compression, unreadable PDF, explicit multi-module, injected
module failure, Korean, repetitive traversal, one short baseline, then six full-length paired
drafts. Independent failed jobs remain recorded while subsequent diagnostics continue.

Both new format and full-length batches use one engineering repetition and manifests with
`independently_reviewed: false`. They cannot become the required independently approved,
three-repetition formal qualification through retroactive approval. No private expected issues,
approved control assignments or human judgments were generated or transferred for these batches.
Separate unapproved author proposals now exist only on the evaluator, not as ground-truth keys.
`not_qualified` and the
closed release gate remain authoritative until the outstanding live/human/hardware work is done.

Read-only model-process memory sampling started at 11:11:48 UTC in
`/tmp/creview-support-b9-telemetry.jtPF7Itv`, controller `2208244`, with ten-second samples tied to
the model and suite process start identities. It stops when the suite/model ends or its bounded
observation window expires. This starts partway through the suite, can include other users of
the shared model, and is not a whole-candidate peak, instantaneous peak or hardware minimum.
Full weight file identities were subsequently collected below; formal candidate-attributable
measurement interpretation remains outstanding.

A separate read-only file-identity collector is queued at
`/tmp/creview-support-b9-runtime-identity.6QEVVf1C`, PID `2230275`, queued 11:26:58 UTC.
Its dry plan resolves 21 explicit runtime files (86,130,739,641 bytes), including both GGUF
shards, native dense/tokenizer/metadata files, MTP files, expert profile, native executable
and server/gateway sources. Script SHA256:
`9aba817133a9a47020b2be6519f487b1c5fc529a8b55031ae455a0e173472ad3`.
It waits for the authoritative suite terminal state, controller/unfinished job exit and an idle
model, uses idle I/O priority and checks for busy model slots during hashing. Runtime process
start identities and file stat fingerprints must stay unchanged; any mismatch fails visibly.
At queue verification it was alive and had hashed zero files. This is planned collection, not
completed weight identity, loaded-memory attestation or model authenticity/quality qualification.
The collector subsequently finished at 13:00:06 UTC after hashing all 21 files. Its exact record,
including large integer fingerprints preserved byte-for-byte, is saved in
`evals/deployment/b9-runtime-identity-completed.json`, SHA256
`496f43a38f6d6c76cbb469fe7c0d1a6bb7e97ef8763af129429da1953fc4d8af`.
This closes file-hash collection, not vendor authenticity or loaded-memory attestation.
The separate 11:30:15 UTC read-only process/source/hardware snapshot is saved in
`evals/deployment/b9-runtime-observations.json`. It confirms the existing native executable,
server/gateway source hashes and specific model-process GPU allocation; it explicitly leaves
full weight hashes and candidate-attributable peaks null. Total host RAM and process-lifetime
high-water figures are observations, not recommended minimums.

Install guidance names the current development wheel, with version-consistency regressions covering
the Unix installer, Windows installer and documented local-wheel command. Server/privacy/install
guidance explicitly separates strict medical support from default legacy doctor/smoke behavior;
the latter cannot qualify these modules. The 73 focused install/profile/deployment checks pass.
These are evaluator/documentation updates, not edits to the frozen workstation bundle.

Six additional payload regressions exercise every actual full-length draft extraction chunk,
including the complete source/table metadata and answer/submit paths. All source blocks are
delivered unchanged and each full payload stays within the 45,000-character delivery budget;
the 71 focused draft/payload tests pass. This is delivery evidence only, not model attention,
reconstruction accuracy, normal-length inference completion or independent source approval.

The three completed turn-limit/compression/unreadable-PDF probes were copied to
`/tmp/creview-support-b9-recovery-results.V1oBvyG0`: 59 regular allowlisted files, 746,927 bytes,
archive SHA256 `0c3a857a55eab79bf83b8675ae879f8bd81a33204babab78e03786a28282672e`.
All three receipts and copied source bytes independently verified against the original wheel
reference sums. The unreadable-PDF final chat explicitly says no clean review/content inference;
this agent inspection is not an independent human audit or a filled reviewer judgment.

The remaining explicit multi-module/failure/Korean/traversal probes and short baseline were
collected at `/tmp/creview-support-b9-scope-results.xXiyOtAU`: 126 regular allowlisted files,
1,892,848 bytes, archive SHA256
`850af898ec023c740dbfc29db29d31f009a71198a81c6dc7137cfc9d733501ce`.
All four receipts, copied source bytes and the ordinary-baseline original/output hashes verified.
The deliberate failed-module export remains failed, not an ordinary completed statistics review.

The first full-length case `r17` stopped at consolidation after all 154 source blocks, 65 facts,
six supported appraisals and fourteen matching/conditional replays were retained. It tried to
group positive checks and ordinary limits as observations even though both actionable-ID sets
were empty, then repeated that error on repair. Its failed result is preserved at
`/tmp/creview-support-b9-r17-results.JRWntIj0`: 52 allowlisted files, 1,420,082 bytes, archive
SHA256 `93e8a2a469081999d77c3e513821773f2c40cc09bfa830cf01dfdc2231114f1d`.
The failed export receipt and source/baseline hashes verified independently. Qualitative study
`q28` completed in 306.41 seconds with no proposals, and SR `s43` in 480.54 seconds with one
proposal and three calculations; both paired baselines passed. ScR, narrative and logic support
also completed, and all six baselines passed. The suite is terminal. The complete evaluator
copy at `/tmp/creview-support-b9-suite-results.L1pTFCbx` contains 785 allowlisted files,
14,909,921 bytes, archive SHA256
`b309205cea8af3012d088c44a1e0a47c4fc297714e8284337e4df8bc8db00eb8`.
All 28 receipts and copied original sources verified independently. Its six-case `ordinary-audit`
preserves the failed statistics case, two unjudged proposals and all actual baselines; all human
judgments, expected issues and checking times remain blank. No server was started.

### Frozen b10 candidate — terminal with engineering failure

- Version `0.9.0b10`, answer contract 8, persisted schema/protocol unchanged.
- Development wheel `/tmp/creview-support-b10-development.EjN5Zwxi/closed_review-0.9.0b10-py3-none-any.whl`.
- Wheel SHA256 `9165e9ad617ab1350b419d455cc89c3dd2e01bc1ec3e1ad5830fb8fd5ff67229`.
- Runner `bed5cfcee482492f4b44e5fe98313235bce787ce46d03790e3e3dd94bcd73f46`.
- 668 local tests passed in 61.82 seconds against the installed development wheel. Ruff, lock,
  diff and skill-copy checks passed. Thirty-seven new reference/consolidation regressions pass.

Consolidation now declares eligible candidate and mismatch-calculation IDs and binds its task
schema to them. If neither exists, groups/withdrawals/priorities must be empty; positive checks
and normal limits belong in the summary and existing dossier records. Wrong IDs get field-level
diagnostics. There is no automatic dropping, answer repair, concern creation or old-run promotion.
Calculator, parser and route-guard files are unchanged; all eighteen generic schema objects from
the b9/b10 wheels compare exactly equal before the new task-specific reference binding.
See [b10 development evidence](support-b10-development-20261028.md).

The same wheel is frozen in local/workstation bundle `/tmp/creview-support-b10-candidate.3KcqndQF`.
Its 33-file checksum-manifest SHA256 is
`b24512f13953cfcf724ac93fbb9c8e7e390ee332fc24c8bf5589bdef3904ed5f`; every file verified on
both hosts. Fresh workstation runtime `/tmp/creview-support-runtime.BxOpwf8V`, Python 3.14.2,
installed 25 hash-pinned dependencies offline and passed exact installed-identity and strict live
preflight checks. B9 and its weight collector were terminal before any new inference.

Detached controller `2337386` started at 13:17:05 UTC; ordinary-length job `2337398` runs first.
Both were confirmed alive. The fresh same-source statistics `r17` regression passed in 355.84
seconds, zero observations and twelve calculations, followed by an ordinary baseline pass in
138.28 seconds. This is a new run, not fourteen old calculations repaired/migrated or proof of
coverage, medical correctness or time savings. The qualitative support run also completed in
330.68 seconds with zero observations. The six-case job finished at 13:56:41 UTC: five support
passes, SR failed twice citing two cells outside its task, all six baselines passed. B11 fixes
row packing and refusal guidance without changing this result. The whole b10 suite is now
terminal; original failed results must not be restarted/relabelled as passes.

Its terminal full-length job is copied at `/tmp/creview-support-b10-ordinary-results.cW91glcz`:
215 regular allowlisted files, 6,664,077 bytes, archive SHA256
`28b1bf5947d8e9874f7bb11ebc517230a724ab11d711d0538643494d22231e58`. All six receipts,
original manuscripts and actual baseline output hashes verified. The six-case `audit` retains
one unjudged ScR proposal and the failed SR case, with all human fields blank. The scorer refuses
the blank template; no private keys or reviewer decisions were supplied.

The short native-format paired job subsequently passed at 14:11:36 UTC: Markdown 156.90 seconds,
DOCX 195.27, PDF 261.25, each with one proposal/three calculations, and all three ordinary-Hermes
baselines passed (87.10/111.69/67.41 seconds). This is one short article in three formats, not
three studies or the queued eight-page b11 case. Evaluator copy
`/tmp/creview-support-b10-native-results.LaVpF7mS`, 80 files, 1,171,278 bytes, archive SHA256
`617f5ad62dec3850997df0e30fa5b6e45259a4dc751de40fd378a46ecd732a19`; all three receipts and
source/baseline hashes verified. Its three-case audit has all human judgments blank. The short
matrix subsequently passed 12/12 at 14:46:09 UTC. See
`evals/deployment/b10-ordinary-evidence-20261028.json` and
`evals/deployment/b10-native-evidence-20261028.json`.

Eleven jobs ran serially with idle-slot checks and bundle/runner revalidation: full-length pairs,
native-format pairs, all short branch cases, recovery, scope/failure, Korean and repetitive-source
probes and a short baseline. A ten-second per-model-process sampler, PID `2337387`, started
before the first job and finished at 15:05:52 UTC, after the suite finished at 15:05:45. It covers
the whole warm/shared suite window, not
exclusive load, cold starts, instantaneous peaks or minimum hardware. All sources remain
unreviewed, all human decisions remain blank and release stays closed. Realistic multi-page
native-format checks, independent corpus/clinical review and three formal paired repetitions
are still required beyond this engineering suite.

Full verified copy `/tmp/creview-support-b10-suite-results.Oet64XtA`: 738 allowlisted files,
13,963,389 bytes, archive SHA256
`f5b14c13488db194f80a59c40fe225542f0373aab26dd6fdca682e12cd811a30`. All 27 receipts/source
copies and ten actual baseline outputs verified. Two jobs failed: full-length SR and a turn-limit
probe that stopped before its initial issued checkpoint, never reaching the intended forced
interruption. The other nine jobs passed their recorded checks. The matrix has ten unjudged
proposals and sixteen calculations; no quality score or role assignment follows from those counts.

Warm/shared whole-suite sampling recorded 649 GPU and RSS samples, sampled peaks 23,682 MiB GPU
and 60,985,572 KiB RSS. These are not instantaneous/exclusive/cold-start peaks or hardware minima.
The raw 21-file identity record was copied without reserialization; its hash remains
`496f43a38f6d6c76cbb469fe7c0d1a6bb7e97ef8763af129429da1953fc4d8af`. Human hardware audit is
still pending. See `evals/deployment/b10-suite-evidence-20261029.json`.

The new [twelve-source candidate set](../evals/support-ordinary-candidates/README.md) contains two
full-length drafts per branch, each with three tables and passing source/payload integrity tests.
Its manifest SHA256 is `e7263ab2e8c828d893efae656fc768f1df74cd45bf12f26dd3e1bfb0ce9541d0`;
`independently_reviewed` remains false. Original six files are byte-identical; author-proposed
changes/roles remain unapproved evaluator-only material outside the repository and model host.
This new set has not been transferred or run for inference and is not a representative/approved
corpus merely because it supplies two files per branch. Independent source/test-role approval,
new frozen approved inputs and three formal paired repetitions are still required.

### Frozen b11 candidate — original queue superseded; harness 2 running

- Version `0.9.0b11`, answer contract 8, persisted schema/protocol unchanged.
- Wheel SHA256 `07d1c1abc21393bdb28be683dc73b6a60c32f2fc2a0c172b62ca4e3b06ba0590`.
- Runner `5a37d154ee4efa99b6d7fdbe995507de45df142dc1a8ccad27a09371411e55da`.
- 690 tests passed in 63.54 seconds against the installed wheel; Ruff, lock, Node syntax,
  diff and skill-copy checks pass. Only package version, source snapshot and workflow files
  differ from b10; calculator/contract/route/skill bytes remain unchanged.
- Frozen local/workstation bundle `/tmp/creview-support-b11-candidate.3PiIPNee`, all 37 listed
  files verified. Manifest SHA256
  `0b6797dc6aad7770ba184b1e8de55f5040be91bf31ee7c39f637387e8c588b72`.
- Fresh isolated runtime `/tmp/creview-support-runtime.qr67IZVN`, Python 3.14.2; same 25
  hash-pinned dependencies installed after online metadata resolution, exact identity and
  strict live preflight passed without generation. This is not called a fully offline install.
- Original controller `2389253` queued at 14:03:16 UTC was deliberately canceled before
  inference at 14:52:24 UTC to replace the evaluator's fragile checkpoint setup. Its process
  identity/no-child/no-suite state were verified; original queue records are unchanged and
  `queue-cancellation.json` records the action. No unrun job counts as a pass.

B11 keeps native table rows intact within extraction chunks and gives field-level, private
guidance for outside-chunk evidence. It does not admit cross-chunk extraction, remove bad facts,
raise refusal limits or change numeric acceptance. The failed b10 SR case/baseline are preserved
locally with an independently verified receipt and source/output hashes.

Automatic PDF table geometry uses visible ruled grids only: the prior fallback cut prose into
spurious cells. Borderless tables remain extracted text and require human layout review; native
DOCX/Markdown is the alternative for reliable geometry. The same 3,777-word r17 source now has
an eight-page Word/PDF fixture with three tables, rendered and inspected on every page using the
docx workflow. The evaluator-only comparison records strict failures alongside narrow retained-
hyphen line-wrap comparison; no saved source/quote/number is repaired. All input/control/medical
judgments remain unreviewed. The new twelve-job suite adds full-length native-format pairs,
with a recovery regression first and SR first among the six-source pairs. See
[b11 evidence and limitations](support-b11-development-20261028.md) and
`evals/deployment/ordinary-native-fixture-20261028.json`.

Harness 2 permits one bounded same-session request to finish an untouched initial checkpoint,
then applies recovery/fault settings only after an issued first task. It does not increase six
actual invocations, change source/refusal checks or restart failed work. All 731 local tests pass
in 66.91 seconds. The exact b11 wheel/runner is unchanged; only three evaluator scripts differ.

Frozen bundle `/tmp/creview-support-b11-harness2.50TRVAiO`, 37 verified files, manifest SHA256
`664bc73ad8e50516214a599bb207c781109c52cefdfdfb873c77df70db8a085f`. Fresh runtime
`/tmp/creview-support-runtime.tm9ClpRZ`, Python 3.14.2, installed the same 25 hash-pinned dependencies
offline and passed strict preflight. Controller `2461652` queued at 15:05:30 UTC and started at
15:06:00 after all b10 processes exited. Sampler `2461967` started before first inference; shared/
warm caveats still apply. Read this runtime's current `suite-state.json`, not the canceled queue.

Its first turn-limit regression passed at 15:10:39 UTC in 279.08 seconds: actual three-turn
interruption, expected CLI exit recovered, same-session/run completion in three invocations,
one proposal/three calculations. Receipt/source independently verified; initial checkpoint was
issued normally with zero extra completion requests. The extra-continuation branch is covered
by deterministic real-workflow tests, not yet by a forced early-checkpoint real-Hermes test.
The fresh full-length SR support case completed in 480.04 seconds: all 214 blocks supplied,
71 facts, seven appraisals, two unjudged proposals and five calculations. Its ordinary-Hermes
baseline passed in 60.30 seconds. One extraction quote refusal was repaired within the allowed
retry; no module failure occurred. Old b10 failures are unchanged. Other full-length/native and
broader checks remain live/pending. See
`evals/deployment/b11-harness2-evidence-20261029.json`.

### Independent source approval — private readable packet prepared

The twelve-source candidate set now has a source-only packet at
`/tmp/creview-support-source-review-v2.mdVh6DWD/packet/source-review-ko.html`, with Korean/English
instructions, original English articles, all 36 tables and optional raw Markdown views. It has
no model findings, author proposals, private issue maps or inferred decisions. Every source copy
matches the unchanged unreviewed manifest; a separate evaluator template leaves reviewer,
expertise, source decisions and representativeness blank. The HTML has no forms/scripts or
external assets, and the new renderer checks preserve exact table grids and unique anchors.

An initial local packet displayed spaced Markdown separator rows as table data. It remains
unpublished and preserved; the renderer was fixed, a NEW packet generated and all 36 grids
verified. Ten new evaluator-only tests plus existing audit tests pass; the full local suite now
passes 700 tests in 97.05 seconds against the same frozen b11 runner. This does not add medical
approval or alter b11's wheel, installed workstation runner or queued suite.

The packet is private/local only. Tailscale publication preference was requested separately;
no server was started, existing view was not replaced and no private judgments were transferred.
At preparation time independent suitability approval had been treated as a prerequisite;
the user removed that prerequisite on October 29. The readable packet remains an optional
audit aid, not evidence of approval. Details: `evals/deployment/source-only-review-packet-20261028.json`.

The public legacy guide no longer tells users that the current slash command starts the old
one-finding-at-a-time scan. Existing-profile install instructions now direct medical support to
the managed profile and strict doctor before attaching a manuscript, rather than suggesting an
unmanaged profile is usable. These match the already-enforced skill/profile behavior; packaged
files and old records are unchanged. Two new documentation regressions pass, 58 focused install/
skill/profile tests pass, and the full installed-b11 suite now passes 702 tests in 62.84 seconds.

Read-only release verification of the exact installed b11 identity refuses the empty gate with
`no fully qualified configuration`; all nine qualification tests pass, including legacy-protocol
rejection. This is a gate check, not authorization to publish. Calculator/dossier inspection also
confirmed that conditional records retain numerical differences without automatic error verdicts;
the reading guidance now explicitly distinguishes `conditional` from `numerical_match` and
requires inspecting outputs/reported values even with zero observations. A clearer conditional
comparison overview remains a UX item for a later exact-build revision and human usability review;
the current technical JSON flag alone is not proof that readers can find differences easily.

## Implemented revisions

The source now provides explicit answer schemas/output enums and multi-path shape diagnostics;
keeps normal `scope_limits` separate from real `coverage_gaps`; makes scheduler reads/rendering
non-mutating; consolidates calculated and model concerns into one observation; supplies fixed
English/Korean navigation; checks live model routes as well as profile defaults; rejects unsafe
terminal/toolsets, cloud credentials and unbypassed proxies; and adds strict support preflight.
Installers now require verified context values and no longer send medical support users to the
legacy scan smoke. Legacy commands/records are preserved, not repurposed as qualification.

## Public guidance scope checks

Only public methodological guidance was looked up; no manuscript, source excerpt or evaluator
key was sent to a web service. The [authors' reflexive-TA reviewer guide](https://www.thematicanalysis.net/editor-checklist/)
supports approach-specific appraisal rather than universal coding-reliability demands.
[PRISMA-ScR](https://www.prisma-statement.org/scoping) distinguishes scoping reporting from an
effectiveness conclusion. The original [SANRA paper](https://link.springer.com/article/10.1186/s41073-019-0064-8)
describes narrative-review appraisal, not a universal automated reporting score. These sources
inform applicability boundaries; they do not qualify this implementation or any model output.
