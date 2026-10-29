# Synthetic Hermes pilot

This pilot tests the new `medical-methods-v1` workflow, not legacy `creview hermes smoke`.
It uses twelve short, invented medical manuscripts: two per branch across all six branches.
They include paired comparison/seeded material but are not independently validated clean
controls or representative full-length papers. There is no automatic scientific-quality score,
no human acceptance scripted into Hermes, and no release qualification from a successful run.

The [2026-10-28 real-Hermes results](support-pilot-results-20261028.md) record the completed pilot,
its failures and the test-runner correction. They do not qualify the current candidate.
The subsequent [b2 matrix](support-b2-results-20261028.md) passed nine of twelve engineering
checks, retaining three failures. Neither matrix is medical-quality qualification.
The [b3 matrix](support-b3-results-20261028.md) passed eleven, retaining a different calculator
failure, and records the first ordinary-Hermes baseline and image-only PDF probe.
The [b4 diagnostic](support-b4-results-20261028.md) also passed eleven cases, but exposed a real
Hermes task-output capture limit as well as a different SR refusal. Its successor is being
tested with bounded task delivery; earlier-build passes do not qualify that successor.
The [b5 matrix](support-b5-results-20261028.md) also finished at eleven engineering passes:
one logic case misclassified ordinary caveats as coverage gaps. The current revision requires
localized gap declarations and is undergoing a fresh exact-build matrix and serial probes.

The runner creates a new disposable profile for every article, pins main and auxiliary inference
to the selected private gateway/model, installs the current packaged skill in that new profile,
deliberately pauses/resumes the same support run, and requests an actual static dossier. Each
article gets at most six Hermes invocations and 900 seconds by default; the whole batch is capped
at three hours. Runs are serial. Existing profiles, review stores, gateways and services are not
modified or restarted. Ensure that the shared gateway is available before starting.

The checkpoint-aware evaluator permits one explicit same-session continuation only when the
agent stopped immediately after `support start`: cursor zero, no issued task, all selected
modules pending, no provided blocks, saved analysis, refusals, notes or answer files. It asks
only for the first `support next`, then stops again. A second premature stop, progressed state,
changed run or written answer is not repaired automatically. The request consumes one of the
same six invocations; it does not raise the cap or restart a run. Initial checkpoint state and
the number of completion requests remain in the result. Old failed checkpoint tests stay failed.

## Run on jkworkstation

From an installation containing this candidate and its dependencies, with Hermes on PATH:

```bash
python scripts/test-support-hermes.py --profile closed-review --output /tmp/new-support-pilot
```

The profile is read only for its private endpoint/model/context settings; a fresh standard review
configuration is generated for each case. It need not already contain the new support skill.
If the named profile is not available, supply the actual private endpoint and advertised model:

```bash
python scripts/test-support-hermes.py \
  --gateway-url http://127.0.0.1:PORT/v1 --model EXACT_MODEL_ID --context-length 262144 \
  --output /tmp/new-support-pilot
```

Add `--hermes /absolute/path/to/hermes` if it is not on PATH. Add `--case case-02` to start with
one article. The pilot explicitly requests English by default; set `--language ko` or another
preferred language when desired. No language is inferred from the server or manuscript.
Use a NEW output directory. The runner never deletes old failures or restarts a failed case.

A prepared transfer bundle additionally provides `run-support-pilot.sh`, the candidate wheel,
hash-pinned runtime requirements and just the allowlisted manuscripts. After extracting it:

```bash
bash run-support-pilot.sh --profile closed-review
```

This launcher requires `uv`, creates a new temporary Python environment and installs the pinned
dependencies there. It may need package-index access to download missing dependencies before
inference starts; it does not install into the regular Hermes or creview environment. It never
copies evaluator keys. A separately held evaluator key must remain off the inference host.

## Inspect results

`batch.json` records the candidate identity, harness hash, model settings, per-case status,
timings and dossier locations. Every case retains its `result.json`, Hermes logs, source snapshot,
task answers and exported HTML/Markdown. Evidence checks verify exact quoted substrings, not
their interpretation. Receipt checks verify exported file integrity, not scientific support.
The runner rejects restarts, legacy scans, invented reviewer decisions, incomplete modules,
missing exports and changed runner/source identities. No server or browser is started.

A finished `partial` module is terminal: export and audit it once, then move to the next case.
It still fails the engineering-completeness check. A runner regression now covers this case;
requesting further continuations of a finished partial result is not a recovery test.

Human review must compare the dossier with its included manuscript and the privately held
intended issues, checking both false alerts and misses. Intended comparison cases can contain
legitimate limitations; do not treat every alert on them as automatically false. Do not score
cases using the obsolete private legacy-scan answer keys. Before release, use independently
audited cases, full-length and poor-extraction cases, three repetitions, same-model baselines,
hardware/workflow measurements and the offline `creview support score` gate described in
[support.md](support.md).

## Prepare the offline human packet

Copy only allowlisted synthetic manuscripts, exported dossiers, run records and test logs back
to the evaluator machine. Never copy private evaluator keys in the other direction. Then run:

```bash
python scripts/prepare-support-audit.py \
  --batch /path/to/copied/batch.json --artifacts /path/to/copied \
  --output /path/to/NEW-private-audit-packet
```

Use the exact candidate installed independently on the evaluator machine. Alternatively supply
`--runner-sums /path/to/independent-candidate.sums` when auditing an older candidate; obtain that
reference from its trusted wheel/release, never the audited batch. The script verifies build,
receipt and manuscript hashes and preserves original manuscripts beside the static dossier.
It does not import keys, make validity judgments, start a server or require browser widgets.
Judgments and missing metadata stay blank until the human supplies them.
The template also leaves numerical-claim review, independent corpus approval and baseline review
blank. Those fields require actual offline inspection, including summaries/appraisals outside
the O-labels. For formal evaluations the packet preserves the frozen manifest and original batch;
the scorer binds each repeated output and baseline to those records. A corpus that was unreviewed
when a batch started cannot be approved retroactively by editing the audit. See the audit fields
in [support.md](support.md#qualification-and-legacy-compatibility).

### Reproduce saved source and calculation records

After preparing a copied packet, run this optional evaluator-only check:

```bash
python scripts/check-support-replays.py \
  --packet /path/to/private-audit-packet \
  --runner-sums /path/to/independent-candidate.sums \
  --output /path/to/NEW-reproduction-report.json
```

The checker verifies the original manuscript/receipt/build bindings, recreates the source snapshot
from the copied manuscript, and replays every saved calculation with unchanged inputs, variant,
reported token and evidence. Only the relocated source `path` is excluded from snapshot comparison;
quotes, numbers, ordering, table geometry and warnings are not repaired or normalized. Calculator,
parser and required implementation hashes must match the trusted build; observed dependency
versions are recorded, not treated as historical attestation.

`all_checks_passed` means record reproduction, **not** numerical agreement with the manuscript,
independent formula validation, correct input roles, extraction completeness or concern validity.
An accurately reproduced conditional difference is still conditional. A failed module remains
failed even when its saved records reproduce. Exit 0 means reproduction passed; exit 1 keeps a
new mismatch report; exit 2 refuses unsuitable input/provenance. No existing artifact or judgment
is changed, no model/network call occurs, and private keys/the audit template are not read. The
four exported files, including reviewer notes, are hashed for receipt integrity. Use a NEW report
outside the packet; this checker cannot replace the offline human audit or qualify a release.

## Recovery probes

After the shared model is idle, run `scripts/probe-support-recovery.py` separately with mode
`compression`, `turn-limit` or `unreadable-pdf`, the same explicit gateway/model/context/Hermes
options and a new `--output` directory. Each probe uses its own disposable profile; it does
not change model services or regular profiles. Compression and turn limits are deliberately
forced test settings, not recommended deployment defaults. A probe only passes when its actual
event and workflow checks both pass. The unreadable probe requires an honest not-assessable
export, not fabricated content. Human final-chat/dossier fidelity review is still required.
Current Hermes compression is detected from same-session committed, non-fallback attempt
telemetry; a start, abort, no-op or another session does not count. The legacy numbered
completion message is also supported. Original failed probes are never rewritten after a
detector change; preserve them and use a new harness/output directory.
The forced turn limit/compression setting now starts at the first resumed invocation after a
verified issued checkpoint, not a hardcoded invocation number. Deliberate module-failure
injection follows the same boundary. A bootstrap continuation must never consume the intended
interruption/fault test. A normal-checkpoint live recovery pass does not prove that the extra
checkpoint-continuation path has also occurred in real Hermes.

To test that extra branch deliberately, run `scripts/probe-support-bootstrap.py` with the same
explicit gateway/model/context/Hermes options and a NEW output directory, without a mode argument.
Its separate saved first prompt asks the model to stop after start, then requires the actual
unissued-to-issued checkpoint continuation before the forced turn limit on invocation 3. A normal
checkpoint/recovery pass cannot substitute for this regression. All six-invocation/source/route/
receipt checks still apply; do not run it alongside another model job or restart an old failure.

`scripts/probe-support-scope.py` similarly accepts modes `multi-module`, `module-failure`,
`korean` and `long-source`. The first explicitly selects statistics and logic. The fault probe
deliberately submits two invalid statistics answers after the initial pause, then requires
that statistics remain failed while logic completes in the same run. This is not an ordinary
engineering pass. Korean-character detection is only a necessary smoke signal, not a translation
quality verdict. The deterministic 6,500-word source is repetitive traversal-stress material,
not independently authored medical-quality or realistic-latency evidence. Original quotations,
scope isolation, attention and usefulness still require human inspection.
For the existing verified Hermes runtime, evaluator-side fault submission mirrors the managed
config's non-secret vision provider/model selectors, just as its terminal does. It never edits
the saved route or bypasses the guard; actual route changes must still stop the probe.

## Same-model baselines and repetitions

Run `scripts/test-support-baseline.py --case case-02` with the same explicit gateway, model,
context, Hermes executable, corpus and NEW output options. It shares strict local privacy
preflight, but does not activate the review skill or use its appraisal workflow. Trace checks
reject detected skill loading, support/legacy commands and copied packaged criteria. They are
necessary signals, not proof of semantic independence. The actual baseline Markdown and its
hash are retained; validity and reviewer checking times are never filled automatically.

### Native-format engineering fixtures

`scripts/build-support-format-fixture.cjs NEW_DIRECTORY [case02|r17]` creates native Word tables
from either the short invented case-02 source (default) or the fixed 3,777-word r17 manuscript
with three tables. Arbitrary/private source paths are not accepted. It needs `docx` in the
evaluator's Node module path,
not on the model host or as a plugin runtime dependency. The checked build used docx 9.15.0,
Node 22.22.2 and LibreOffice 24.2.7.2. Render the Word file to PDF locally, inspect every page,
then run `scripts/check-support-format-fixtures.py --inputs DIRECTORY --manifest NEW_JSON
--report NEW_REPORT_JSON`, adding `--fixture r17` for the full-length source. The checker requires
the original copied Markdown bytes, ordered paragraphs and native table grids without
numerical/header correction. For PDF format comparison only, raw-extracted line wraps after a
retained hyphen between letters may be joined; the hyphen remains and digit joins, ordinary
spaces, spelling and punctuation repairs are refused. Strict whitespace-only checks are recorded
alongside this comparison. This does not normalize model answers or change any source snapshot,
saved quotation or calculator binding. It does not infer
clinical correctness, absence of hidden content or independent corpus approval.

The generated key-free manifest has three files representing the **same one** selected invented
article, not three independent studies. `independently_reviewed` stays false. Only those source
files and the manifest may go to the model host; keep build metadata, render inspection and
checker reports on the evaluator machine. The existing paired scheduler accepts these native
formats with `--repetitions 1` for an engineering diagnostic. This does not satisfy the formal
three-repetition, all-branch, independently approved medical corpus or human-audit requirements.

The b8 diagnostic completed Markdown/DOCX but failed PDF exact quotations when answers reflowed
extracted line breaks. New b9 PDF snapshots canonicalize layout whitespace only, retaining the
original extracted layout separately. Quotes still match saved `block.text` exactly; answers,
words, punctuation, numeric tokens and historical snapshots are not repaired. See
[the preserved format failure](support-b8-formats-20261028.md).

The new r17 Word/PDF render has eight pages, all inspected by the agent after correcting orphaned
headings; this is not independent human/medical approval. Initial failed format inspections are
preserved. B11 removes the prose-to-table fallback and keeps intact table rows within extraction
tasks. The new full-length native fixtures pass local format-preservation diagnostics but still
require fresh real-Hermes execution and independent source/finding audits. Borderless PDF table
geometry is explicitly outside automatic reconstruction; no OCR or word repair was added.

The [six ordinary-length development drafts](../evals/support-ordinary-draft/README.md) are also
unreviewed. A one-repetition paired engineering run can test traversal and execution, not satisfy
formal qualification. Use their [source-only worksheet](../evals/support-ordinary-draft/SOURCE-REVIEW.md)
to separate genuine independent source approval from later finding judgments; never relabel an
already-started diagnostic batch as approved.

A separate [twelve-source candidate set](../evals/support-ordinary-candidates/README.md) supplies
two unreviewed full-length sources per branch for later independent selection. Its manifest
remains false for independent approval. Author proposals are evaluator-only drafts, not private
ground-truth keys or human decisions, and are not sent to the model host. Neither parser success
nor an author's intended edit establishes a clean comparison case or a valid seeded issue.

### Readable source-only approval packet

Before formal runs, the evaluator can prepare the unreviewed twelve-source candidate set without
model findings, baseline outputs, author proposals or private keys:

```bash
uv run --locked python scripts/prepare-support-source-review.py \
  --manifest evals/support-ordinary-candidates/manifest.json \
  --corpus evals/support-ordinary-candidates/manuscripts \
  --output /tmp/NEW-source-only-review
```

This creates one self-contained `source-review-ko.html`, original hash-verified Markdown copies,
Korean/English instructions and a blank evaluator-only `source-review-template.json`. The articles
and tables remain original English, not translated/approved medical evidence. All 36 table grids
are checked in regression tests, including spaced Markdown header separators; source HTML is
escaped and line anchors are unique across papers. The optional original Markdown view keeps
the full source available. No model/network call or server is started, and no forms are required.

Read the originals before consulting model findings or author suggestions. Record actual reviewer
identity/date/expertise, suitability/revision/exclusion reasons and domain representativeness.
Test-role/private issue adjudication is separate and stays offline. This utility does not approve
or modify the input manifest, infer controls/seeds or qualify old diagnostic runs. Publishing a
new packet on Tailscale needs the user's sharing approval; never expose a filled audit template
or private keys. See [deployment readiness](deployment-readiness.md).

For serial repetitions paired with baselines:

```bash
python scripts/evaluate-support-hermes.py \
  --manifest evals/support-pilot/manifest.json --corpus evals/support-pilot/manuscripts \
  --gateway-url http://127.0.0.1:PORT/v1 --model EXACT_MODEL_ID --context-length 262144 \
  --output /tmp/NEW-support-evaluation
```

Defaults are three repetitions, 900 seconds per phase and a six-hour total cap. Every support
and matched baseline gets a distinct disposable profile. Budgets, failed cases and unexecuted
work remain visible. Source copies preserve exact bytes and extension, including native PDF/
DOCX; copying-format tests are not proof that those formats were correctly read in live cases.

The manifest has only protocol, corpus ID, synthetic/reviewed flags and case ID/module/file/hash
entries. Private expected issues and control assignments are refused. The bundled short corpus
is explicitly **not independently reviewed**, so successful repetitions on it are diagnostic,
not qualification. Formal qualification still needs independently validated realistic cases,
human false-alert/miss and corpus audits, and all other release gates.

Copy the resulting `support`, `baselines`, key-free manifest and batch records to the evaluator
machine before preparing the offline packet. Repetition folders stay distinct while the audit
keeps their original logical case IDs. Original manuscripts, dossiers and any matched baseline
are linked for headless review; all human judgments and checking times remain blank.
