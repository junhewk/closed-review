# Deployment qualification

> Historical full-scan qualification. The redesigned default uses `medical-methods-v1`; its
> branch-level human audits and release requirements are described in [support.md](support.md).
> Legacy scan scores and smoke tests cannot qualify or release the new workflow.

The target is a Hermes add-on for capable personal computers, supporting a human reviewer with
an initial scan of about 10–15 minutes. The beta provides profile guardrails, not OS network
isolation. A configuration is the exact runner, Hermes version, model weights/quantization,
inference runtime, hardware, and context setting—not just a model name.

## Release gates

- Pass the real Hermes smoke test: runner identity, resumption, verified scripted acceptance,
  a link to the scan, three exports, explicit severity consistency, and receipt integrity.
- Run six synthetic design-profile manuscripts and two clean controls three times each.
- Evaluate each retained finding's meaning and evidence: at least 80% aggregate recall of
  planted majors, at least 90% validity of retained major concerns, and no unsupported confirmed
  finding. Recall counts each planted issue once per run.
- Inspect accepted-only exports, faithful reviewer attribution, and absence of unsurfaced
  findings. Verify compression recovery, the Hermes turn limit, long documents, and poor PDF
  extraction. Images and unextractable material remain for human inspection.
- At least 90% of measured 6,000–10,000-word scans must complete within 900 seconds, excluding
  reviewer waiting. Short controls cannot satisfy that gate.
- Record exact runtime/model provenance and measured peak memory before recommending hardware.

## Running and scoring

Keep the private evaluation set outside the public repository. Only `msN/manuscript.md` files
go to the inference host. **Never copy its `keys/` directory to Hermes.** Public controls and the
run manifest are in `evals/deployment/`. After installing the candidate and creating its profile:

```bash
python scripts/qualify.py run --profile closed-review \
  --corpus /path/to/manuscripts-only --output /path/to/private/batch
```

The harness runs the smoke test first and scans serially. It saves after each run and resumes
with the same command. Changed build/config/manifest/manuscript hashes require a new output
directory. Completed failures remain in the batch; successful retries cannot silently replace
them. Per-scan timeout defaults to 1800 seconds. Synthetic runtime artifacts are retained at
the reported paths; they may be removed after collecting the evidence you need.

Bring results to the evaluator's machine. Each successful run has `scan.json` and `audit.json`.
Read the complete finding alongside its evidence and private key; fill in `valid`, matched planted
IDs in `matches`, `confirmed_supported` where applicable, and a specific `rationale`. Name the
evaluator in `reviewer`. Shared quotations are navigation aids, never automatic credit. Additional
valid concerns can have an empty `matches` list. Screened/dismissed candidates are excluded.

On the evaluator's machine, `scripts/audit-qualification.py` prepares a readable, offline view
of the concerns, their cited passages, the full synthetic manuscript, and a separate private
answer-key page. The source manuscript is checked against the executed batch's hash. The helper
then saves the human's answers as they are entered. For example:

```bash
python scripts/audit-qualification.py --output /path/to/private/batch \
  --keys /path/to/private/creview-eval/keys --corpus /path/to/private/creview-eval \
  --manifest evals/deployment/manifest-ordinary.json \
  --run ms1-r1 --reviewer "Evaluator name"
```

This helper does not call a model or send data over a network. Run it on the evaluator's machine,
not in Hermes or on the inference host. The separate `answer-key.html` contains private key
material and is stored with private file permissions; keep it local and do not share it with a
model. The finding view's quotation links check exact text only, not whether an interpretation or
claim of absence is justified. Select `unsure` whenever you cannot judge; no decision is saved.
`--revisit` permits an evaluator to reconsider their own saved decisions. If a scan retained no
findings, the helper asks for explicit sign-off after the evaluator has inspected the scan and
manuscript; it does not silently mark an empty result as reviewed.

To prepare the finding view without running an interactive audit, use
`scripts/prepare-audit-packet.py` with `--output`, `--corpus`, `--manifest`, and `--run`. An
optional `--keys` creates the private key view, and must only be used on the evaluator's machine.
These scripts never replace an existing packet file whose contents differ.

Use `--run all` to walk all currently completed quality runs in manifest order; timing-only
runs are excluded. Enter `quit` to stop, and rerun the command later to continue with saved
decisions. Runs that have not completed successfully remain outside this walk and keep the
qualification gate pending.

Add `hardware.json` with `hardware`, `model_weights`, `quantization`, `runtime_version`,
`context_length`, `peak_memory`, and `reviewer`. Add `workflow-audit.json` with `reviewer` and
explicit boolean results for `accepted_only`, `reviewer_attribution`, `unsurfaced_hidden`,
`compression_resume`, `turn_limit_resume`, `long_document`, and `poor_pdf_extraction`.

```bash
python scripts/qualify.py score --output /path/to/private/batch \
  --keys /path/to/private/creview-eval/keys --manifest evals/deployment/manifest-ordinary.json
```

Missing judgments or evidence leave qualification false. Evaluator assertions are self-reported,
not authenticated. Nothing is uploaded automatically.

The existing six private papers are about 1,600–5,000 words. They cover semantic regressions but
cannot establish ordinary-length latency. Add a synthetic 6,000–10,000-word set and privately held
keys to an extended manifest, retaining three repetitions. Do not pad papers with repeated text
to manufacture a performance result.

For long manuscripts derived from the six quality cases, mark the new cases `"timing_only": true`
in the extended manifest. Their scans must complete and count toward the latency gate, but their
findings do not enter the quality metrics a second time and need no answer key on the test host.
An independent evaluator still needs to confirm that the longer documents are realistic and that
the generated scans are appropriate for timing. Keep the original quality cases in the same batch.
The provided `manifest-ordinary.json` expects the separate `deployment-ordinary-v1` directory in
the private corpus. It specifies 24 quality runs and nine derived timing runs.

After the timed batch, `scripts/probe-hermes-recovery.py` can run separate disposable synthetic
probes for `turn-limit`, `compression`, and `unreadable-pdf`. The compression probe uses a low
token cap to force a test event; it does not change the deployment profile. A passing automated
PDF warning check still requires a person to inspect the model's answer for invented content.
In the inspected Hermes commit `ebadb5462e`, the percentage compression trigger for a context
window below 512k tokens has a 75% floor, so the profile's `threshold: 0.5` is not by itself a
guarantee of compression at 50%. Absolute token caps and other runtime limits may trigger it
earlier. Verify the actual trigger and recovery on the installed Hermes version.
For hardware observation, `bash scripts/monitor-qualification.sh MODEL_PID 5` reports sampled
GPU-memory and resident-memory high-water marks when stopped. Sampling can miss brief peaks and
resident memory may include shared or mapped pages.

## Candidate configuration matrix

| Configuration | Evidence | Status |
|---|---|---|
| Linux; Hermes 0.21.5 / ebadb5462e; Qwen3.8-Flash-Next IQ3_S via Strata; advertised 262144 context | Expanded synthetic smoke passed on the current build; qualification batch in progress | Not qualified |
| Linux; Gemma-4-31B QAT Q4_0 via llama.cpp; configured 65536 context | One synthetic smoke pass on 2026-10-28; severity discrepancy in editor draft and earlier export failures | Not qualified |
| macOS / Apple Silicon | Package CI is separate from local inference qualification | Hardware unqualified |
| Native Windows | Installer/package checks are separate from Hermes runtime compatibility | Workflow unqualified |

The workstation has an RTX 4090 and RTX 3090, each with 24 GB VRAM; this does not imply both are
required by either model. Qwen uses a custom Strata runtime. Record memory placement and peak
usage before recommending equivalent hardware. Test 64k and 128k where supported by the server.
Changing the Hermes setting does not resize the server.

The tested Hermes build auto-loads bundled backend plugins despite an empty `plugins.enabled`
list. The profile disables external toolsets and configures trusted model routes, but the doctor
does not establish that no bundled plugin code loads. Review that boundary before a reviewer beta.

See [dated deployment results](deployment-results.md) for measured runs and exact package
identities. A tiny smoke manuscript cannot establish ordinary-manuscript performance.

## Rollout

Prepare a tagged prerelease only after its gates pass. Publish the exact configuration matrix,
limitations, wheel, installer, and checksums together. Until then, local candidate wheels are for
synthetic qualification. Begin a small reviewer beta after journal permission and host data
handling are established. Collect setup failures, checking time, valid added concerns, and false
alarms; manuscripts and transcripts remain local unless explicitly shared. Requalify after
changing Hermes, runtime, model weights, or quantization.

The release workflow enforces this through `evals/deployment/release-gate.json`: it needs a
labelled configuration with a complete score tied to the built wheel's package checksum. The
candidate's empty configuration list deliberately blocks publication. Package CI alone cannot
open that gate.
