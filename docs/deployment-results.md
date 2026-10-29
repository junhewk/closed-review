# Deployment checks — 2026-10-27 and 2026-10-28

These are synthetic engineering checks, not model-quality qualification. No configuration is
approved for release. Tests used disposable profiles and isolated tool installations; the regular
workstation installation and model-server configuration were not changed.

## Host and candidates

Linux workstation with RTX 4090 and RTX 3090 GPUs (24 GB each). Hermes 0.21.5,
commit `ebadb5462e`, config schema 49. The private gateway advertised Qwen3.8-Flash-Next at
262144 tokens and Gemma-4-31B at 65536 tokens.

Qwen ran through the existing Strata runtime with IQ3_S weights and int8 KV cache. Gemma used the
existing llama.cpp server with QAT Q4_0 weights, q8 KV cache, one parallel slot, and a configured
65536-token context. This records observed settings, not a reproducible hardware recommendation:
exact runtime revisions, weight hashes, memory placement, and peak memory remain to be recorded.

## Real Hermes smoke tests

Each run used the same 362-word synthetic arithmetic-contradiction manuscript. The harness
checked the runner from inside Hermes, deliberately stopped and resumed the scan, and sent a
scripted reviewer acceptance through Hermes's normal user-message path. Wall time includes
fresh-profile runtime preparation, model work, and tools; it is not pure inference time.
Server load was not controlled for a comparative benchmark, so these timings do not establish
a general speed ranking between the models.

| Candidate package identity (`sums_sha256`) | Model | Result |
|---|---|---|
| `845dbc1f832a40367031d324a2fe4cf61bbaa0a0d2f2155d6dc2936c291361f5` | Qwen | Failed: scan reached the first finding at 898.68 seconds; the 900-second total limit stopped the workflow before export. |
| `8fa191a31758b49ebc66edbbc3272615489d05392fe2d0fff4c5d88762050ffd` | Gemma | Failed: scan completed in 364.72 seconds and acceptance was verified; after 459.79 seconds the agent claimed export completion, but only the prepared directory metadata existed. No drafts or receipt. |
| `deda49df70870b00965b8017bdab066f759bf31401668fb61e4b210021e27dea` | Gemma | Failed: scan completed in 435.14 seconds; total 582.20 seconds. Verified acceptance, author/editor drafts, receipt, and preflight, but no development record. |
| `b30f0718741dfb6bd679e7f56cdc995fa113951a826da7012b7ef02905d89cf1` | Gemma | Failed: scan completed in 348.61 seconds; total 455.55 seconds. Runner identity, scan resumption, and reviewer acceptance passed. The agent stopped after preparing the export directory; no drafts or receipt existed. |

The Gemma failure led to explicit skill instructions that preparing an export does not write it:
write all three drafts, finalize, and verify the receipt before reporting success. The harness
was not relaxed to accept the agent's claim. The next failure led to a deterministic completion
check: managed profiles cannot finalize until all three drafts exist and are nonempty. Legacy
unmanaged-profile partial exports remain compatible. Failed runs are not erased or counted as
passes. A valid receipt proves integrity of the files it lists, not completeness of the workflow.

## Package verification

The 2026-10-27 `0.9.0b1` candidate had package identity
`b30f0718741dfb6bd679e7f56cdc995fa113951a826da7012b7ef02905d89cf1`.
A clean wheel installation matched the source-package identity. All 163 local tests passed;
Ruff, Bash syntax, PowerShell parsing, and patch-whitespace checks passed. The real Linux
installer created an isolated profile whose doctor check passed, with no deployment problems.
Native Windows/macOS runtime behavior has not been established by those checks.

At the end of the 2026-10-27 tests, the candidate had not passed the workflow smoke test, so the
full qualification batch was not started.

## Gateway rerun — 2026-10-28

With the gateway responding, the same `b30f0718…` package and Hermes commit `ebadb5462e` were
tested sequentially on the same 362-word synthetic manuscript. Each used a fresh disposable profile
and the 900-second total timeout. Both passed every automated workflow check: runner identity,
resumption, completed scan, verified scripted acceptance, three export files, receipt integrity,
and a recorded preflight.

| Model | Scan time | Total smoke time | Automated result |
|---|---:|---:|---|
| Gemma-4-31B | 354.72 seconds | 514.92 seconds | Passed |
| Qwen3.8-Flash-Next | 143.82 seconds | 188.12 seconds | Passed |

The exports were also inspected for this one case. Both drafts describe the accepted arithmetic
concern. Gemma's editor draft calls it a **major** issue, although the saved finding's severity
is **minor** and the scripted reviewer did not rate its severity. Its automated smoke pass does
not detect that wording discrepancy. Qwen's drafts correctly attribute the supplied acceptance
and request; this single inspection is not a broader semantic-quality assessment.

These are individual synthetic runs, not controlled model benchmarks. The Qwen server invocation
on this rerun did not include the `--batch 2` option observed on 2026-10-27, and host load was
not controlled. The earlier runs and failures remain part of the evidence; the gateway and model
also served requests during those runs. A smoke pass does not qualify a configuration for release.

## Fidelity and qualification work — 2026-10-28

After the rerun, a scan-linked export check was added for explicit severity conflicts and certain
explicit references to unpresented findings. These are narrow checks; they do not establish that
all wording is faithful. The current candidate's package identity is
`7dab865a256117b02dcdb09c056dd12ddbe5ded4245cb0943311ecb9aa5e3605`.
Qwen passed the expanded synthetic smoke on this build in 167.33 seconds, including 122.58 seconds
to complete the scan. The check also verified the scan link and found no explicit severity or
unpresented-finding phrases. The exported wording still needs an independent human assessment.

The extended batch was started with 24 quality runs and nine timing-only runs. The three timing
manuscripts are approximately 6,500 words and are derived from existing cases with additional
model-authored discussion. They have not been independently reviewed for naturalness; their
repeated planted material is excluded from the quality score. Results and sampled hardware peaks
remain pending until the batch and its audits finish. The evaluator's answer keys remain local.

The first quality run, `ms1-r1`, completed its scan in 424.13 seconds for a 4,459-word synthetic
manuscript; it is too short to contribute to the ordinary-length latency gate. Its ten retained
concerns require independent review. The local audit interface was revised after feedback that
raw finding records were hard to assess: it now offers the hash-checked manuscript and linked
passages, and permits an explicit undecided response. Readability does not establish validity or
replace domain expertise.

## Still required

The 24-run semantic assessment, ordinary-length latency measurements and corpus realism review,
hardware measurements, compression and turn-limit recovery, long-document/poor-PDF audits, and
reviewer beta remain pending. The original six private papers are too short to establish the
6,000–10,000-word timing target.
Answer keys remain outside this repository and outside Hermes. See
[deployment qualification](deployment.md) for the protocol and blocked publication gate.

## Medical-methods pilot preparation — 2026-10-28

The new support workflow has twelve short synthetic pilot manuscripts across six branches and
a bounded real-Hermes runner, separate from the historical scan batch above. The runner creates
isolated profiles, requests a deliberate pause/resume, checks actual exports and receipts, and
retains failures without attributing any scientific decision to the reviewer. It does not
automatically score concern validity. Pilot comparison cases and intended issues are not
independently validated qualification cases.

The initial SSH connection to `jkworkstation` (`100.122.169.13`) was refused by the execution
environment with `socket: Operation not permitted`, before connection. At that point no new
workstation inference, installation, service operation or remote test was performed. A bundle was
prepared with the candidate wheel, hash-pinned requirements, allowlisted manuscripts and runner;
the evaluator-only intended issues remain outside that bundle and the repository.

Local verification: 246 tests passed, including ten pilot/harness tests and deterministic
replays of the paired table percentages. The successful end-to-end adapter test substitutes
deterministic task answers for Hermes; it is not a live model result. The existing HTTP audit
server test was excluded because this sandbox prohibits sockets. Ruff, Bash syntax and whitespace
checks passed; the candidate wheel built successfully. The locked scientific dependency stack
and the bundle launcher still need execution on the workstation. See
[synthetic support pilot](support-pilot.md) for commands and interpretation limits.

## Medical-methods real-Hermes pilot — 2026-10-28

After SSH access became available, the locked candidate was installed in a disposable workstation
environment. A corrected twelve-case serial pilot completed on Hermes/Qwen in about 30 minutes:
five modules stopped on structured-submission errors; seven completed appraisal/export but were
marked partial. No case passed strict completeness. All twelve receipts were verified after
copying artifacts back locally. The earlier interrupted batch remains preserved and separate.

Local regression verification with locked runtime dependencies and the installed wheel now
passes all 248 tests, including the previously blocked socket test. Only a test-runner terminal
partial-state bug was fixed; the candidate product code was not changed to improve the outcome.
The runner/tool contract, coverage/snapshot handling and duplicate arithmetic observations need
correction before deployment. No module is qualified and no release gate was opened. See the
[full pilot results](support-pilot-results-20261028.md) for identities, per-branch results,
artifact locations, the interrupted-batch audit trail and required next work.
