# Medical support b11 development — 2026-10-28

B11 addresses source/task boundaries found during b10 and an eight-page native-format fixture.
Its original wheel passed 690 local tests. The unchanged wheel now passes 731 tests including
checkpoint-aware evaluator regressions. The original queue was canceled before inference and
preserved. A new harness-2 suite is running with a fresh live forced-interruption/recovery pass;
broader checks and medical qualification remain incomplete. See
[current harness-2 status](support-b11-harness2-20261029.md).

## Preserved failures and changes

B10's six full-length pairs finished at 13:56:41 UTC. Statistics, qualitative study, scoping
review, narrative review and logic completed; systematic review failed extraction. All six
ordinary-Hermes baselines passed their engineering checks. These outcomes are not human judgments.

In SR task-0005, row 9 of Table 1 was split at its third cell. Both rejected submissions cited
`table-1-r9-c1` and `table-1-r9-c2`, which belonged to the preceding chunk. B11 keeps consecutive
native cells of one row together without changing source bytes, order or block IDs. An intact
row exceeding the source budget is refused rather than truncated. Extraction instructions now
distinguish current-chunk facts from later cross-chunk appraisal; refusals identify the offending
fact/evidence field without printing private values. Exact source matching, two-refusal failure,
preserved rejected payloads and atomic state writes remain in force.

The failed case and its matched baseline are copied to
`/tmp/creview-support-b10-s43-results.Rxkvle9B`: 31 regular allowlisted files, 991,685 bytes,
archive SHA256 `91affbd4cc1becbce3f790fb43cad245dc438feab544386e51793e73371bb23a`.
The failed receipt verified against independent b10 sums; both source copies and the actual
baseline output hash verified. The incomplete overall suite was not relabelled complete.

The 3,777-word r17 source also exposed PDF text-alignment fallback constructing five spurious
tables on prose pages, in addition to its three real ruled tables. B11 no longer promotes such
alignment guesses into numeric-eligible geometry. Original page text remains intact. Automatic
PDF table geometry is explicitly limited to visible ruled grids; borderless tables require human
layout review. Native DOCX/Markdown is the alternative when reliable table geometry is required.
This is a capability boundary, not evidence that a borderless table or article is defective.
Actual ambiguous geometry/images/scans/math and other processing limits remain conservative.

## Native-format evidence and its limits

The docx skill required rendering and visual inspection. The first eight-page fixture retained
orphaned headings and failed format checks; those artifacts remain unchanged. The revised render
keeps headings with following content and tables intact. All eight pages were inspected by the
agent, not an independent human. It is one invented article in three formats, not three studies.

Evaluator directory: `/tmp/creview-support-ordinary-native-v2.VPwlOef2`. The same copied Markdown
bytes, ordered paragraphs and all three cell grids pass the documented comparison. PDF now has
three tables and 240 blocks rather than eight tables and 2,085 blocks in the first render under
b10. These counts alone do not establish completeness or scientific fidelity.

Strict whitespace-only comparison still records differences where the render wraps after a
printed hyphen, e.g. `internal-` followed by a newline and `medicine`. A separate evaluator-only
comparison joins raw-extracted newline whitespace after a **retained** hyphen between letters.
It does not drop hyphens, join digits, fix spelling/punctuation, rewrite source snapshots or
normalize submitted answers. Both the strict results and the explicit comparison policy remain
in the report. Numeric/word-repair refusal tests pass. Historical failed reports remain false.
The runtime's `pdf-layout-whitespace-v1` exact-quotation policy is unchanged.

See `evals/deployment/ordinary-native-fixture-20261028.json` for all source/page/checker hashes,
retained strict differences and original failures. Its key-free manifest SHA256 is
`902fa05904b98d3edf618ba22180485ec517529d6c89272f05226f14912caa67`;
`independently_reviewed` remains false. Build/render/comparison metadata stays on the evaluator.

## Exact candidate and local verification

- Version `0.9.0b11`; answer contract 8, persisted schema 1 and `medical-methods-v1` unchanged.
- Wheel `/tmp/creview-support-b11-development.MzzeEH9l/closed_review-0.9.0b11-py3-none-any.whl`.
- Wheel SHA256 `07d1c1abc21393bdb28be683dc73b6a60c32f2fc2a0c172b62ca4e3b06ba0590`.
- Runner `5a37d154ee4efa99b6d7fdbe995507de45df142dc1a8ccad27a09371411e55da`.
- Installed wheel bytes independently match the wheel archive. Relative to frozen b10, only
  `__init__.py`, `support/sources.py` and `support/workflow.py` change. Calculator, contract,
  route/privacy guards and packaged Hermes skill are byte-identical.
- 690 tests passed in 63.54 seconds against the installed Python 3.12.3 candidate, with checkout
  `pythonpath` injection disabled. Ruff, Node syntax, lock consistency, diff and skill-copy
  checks pass. Twelve new source-boundary tests and ten additional format tests cover intact
  rows, oversize refusal, actual six-source chunking, private atomic refusals, retained prose,
  no text-alignment table fallback, ordered paragraphs and narrow evaluator-only layout handling.

## Original workstation staging and serial queue (superseded before inference)

Frozen local/workstation bundle `/tmp/creview-support-b11-candidate.3PiIPNee` has 37 hash-listed
files, checksum-manifest SHA256
`0b6797dc6aad7770ba184b1e8de55f5040be91bf31ee7c39f637387e8c588b72`.
Every file independently verified on both hosts. Original short/native/six-source corpora are
unchanged; the six-case manifest explicitly places SR first for regression. It adds only the new
three-format full-length source and key-free manifest, not private proposals or answer keys.

Fresh runtime `/tmp/creview-support-runtime.qr67IZVN`, Python 3.14.2. Initial offline dependency
resolution could not find cached metadata; installation then resolved the same 25 hash-pinned
dependencies against explicit PyPI and installed the wheel locally. This was dependency setup,
not manuscript/model traffic; it is not represented as a fully offline install. Installed
identity and strict live preflight passed, without text generation. The non-Hermes preflight
reports runtime `not_in_hermes`; actual jobs still must verify their recorded Hermes sessions.
No regular profile or model service was modified.

Original controller `2389253` queued at 14:03:16 UTC, waiting for the b10 controller/jobs to exit.
It was canceled at 14:52:24 UTC before inference to replace the evaluator harness. The original
`queue-state.json` remains unchanged beside `queue-cancellation.json`; unrun jobs are not passes.
The new running controller/runtime is documented in [harness 2](support-b11-harness2-20261029.md).
Original controller SHA256
`4532d1c0e9a8994c767303c6d228c7de99e9e5bfb89499a76ed695945602bde0`.
Its planned checks validated the exact runner/bundle and 21-file runtime fingerprint continuity.
The replacement retains those checks. Twelve serial jobs cover full-length pairs (SR first), eight-page
native-format pairs, short native pairs, short branch matrix, recovery, scope/failure, Korean,
repetitive-source and baseline checks. New whole-suite warm/shared-process memory sampling starts
only after queue release; no exclusive/cold-start/minimum-memory claim is implied.

## Additional evaluator-only preparation

The completed b10 full-length and short-native paired batches were independently collected and
receipt/source/baseline verified. Their new audit packets preserve failed results and leave all
human fields blank; see [b10 evidence](support-b10-development-20261028.md). No old failure was
promoted and no private keys were imported.

`scripts/prepare-support-source-review.py` builds a private source-only packet from a key-free,
unreviewed synthetic Markdown manifest. The new twelve-source packet at
`/tmp/creview-support-source-review-v2.mdVh6DWD/packet` contains Korean/English instructions,
original English articles, all 36 exact table grids, unique line anchors and raw Markdown views.
It contains no model findings or author proposals and infers no human decisions/test roles.
The separate evaluator template leaves all source approval fields blank. The builder makes no
network/model calls or manifest changes and starts no server. Publishing preference was requested
separately; the packet remains private/local pending the user's response.

The reused read-only renderer initially displayed spaced Markdown header separators as data.
That first local packet remains unpublished; the helper was fixed and a NEW packet generated.
Ten new evaluator-only tests cover all 36 grids, exact source hashes, blank decisions, escaped
untrusted content, unique anchors, no private-key reads and no reviewer-work overwrite. The
complete installed-candidate suite now passes 700 tests in 97.05 seconds. Ruff and diff checks
pass. These script/test/documentation changes leave the frozen b11 runner/wheel and workstation
queue unchanged; no new medical or real-Hermes success is implied.

Subsequent documentation checks found the public legacy guide still presented the current
slash command as its old scan queue, while existing-profile installation suggested attaching a
manuscript even though strict support would refuse that unmanaged profile. Both are corrected
and linked to the managed selected-module path. Two new documentation regressions and 58 focused
install/skill/profile tests pass; the full suite now passes 702 tests in 62.84 seconds. This is
documentation/test work only: the installed and queued b11 runner identity remains unchanged.

## Still required

Fresh b11 inference, independent source/test-role approval before formal runs, three paired
repetitions, private human findings/coverage/usefulness/translation judgments, actual checking
times and final hardware audit remain outstanding. The release gate remains empty/closed. New
candidate source proposals remain unapproved and evaluator-only; no old private keys were read.
