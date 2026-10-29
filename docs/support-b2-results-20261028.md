# Medical support b2 engineering results — 2026-10-28

Nine of twelve short synthetic cases passed the engineering checks on real jkworkstation
Hermes/Qwen. Three stopped after two refused task submissions. This candidate is **not qualified**;
these counts are neither medical accuracy measurements nor release approval.

## Exact candidate and scope

- Package `0.9.0b2`; protocol `medical-methods-v1`; answer contract 2.
- Runner sums `fbffd1c858852cd88ff34657b3422a3f2d9c467d6866eec728cca324f08f53ac`.
- Wheel SHA256 `6101e72c76e84db2a711b160c7ca2a36a351db443212934a71ad521ae1dd2ffe`.
- Harness SHA256 `a9f0a6b83e2439050ef7a0379ceabc652a23248c79698cc8e147cc5a571f3075`.
- Existing Hermes `0.21.5+7498.gebadb54`; Qwen alias `qwen3.8-flash-next` through the private
  gateway; existing Strata IQ3_S/int8 KV, configured maximum context 262144.
- New isolated Python 3.14.2 environment and one disposable profile per article. Existing
  profiles, installed tools, gateways and model services were not changed or restarted.
- Twelve invented 313–371-word English Markdown manuscripts, one selected branch each.
  These are not independently validated controls or representative full-length papers.
- Serial run: 2026-10-28 04:20:47–04:47:43 UTC (13:20:47–13:47:43 KST).
  Times include profile setup, inference, tools, deliberate pause/resume and export.

## Results

| Branch | Cases | Status | Observations | Calculations | Seconds |
| --- | --- | --- | --- | --- | --- |
| Statistics | 01 / 02 | complete / complete | 0 / 1 | 5 / 5 | 168.36 / 143.67 |
| Qualitative study | 03 / 04 | complete / complete | 0 / 2 | 0 / 0 | 120.27 / 143.31 |
| Systematic review | 05 / 06 | failed / complete | 0 / 1 | 0 / 2 | 127.03 / 176.33 |
| Scoping review | 07 / 08 | failed / failed | 0 / 0 | 0 / 2 | 100.68 / 135.70 |
| Narrative review | 09 / 10 | complete / complete | 0 / 1 | 0 / 0 | 97.03 / 134.85 |
| Logic | 11 / 12 | complete / complete | 0 / 1 | 0 / 0 | 130.60 / 138.56 |

All twelve passed recorded runner identity, exact source-quote binding, unchanged manuscript,
selected-module scope, same-run resumption, no invented reviewer decisions, no legacy scans,
export-file existence, receipt integrity and saved/exported snapshot equality. Only module
completion failed in the three stopped cases. These checks do not establish scientific meaning,
completeness of model attention, absence of false alerts or detection of the intended issues.

The earlier focused b2 statistics smoke independently completed in 167.68 seconds with five
calculations and one linked, nonduplicated observation. It is a separate run, not a replacement
for any failed matrix case.

## Failures preserved and corrective work

- Case 05: a counterevidence quotation replaced a source semicolon with a period. The quote
  rejection was correct; the generic diagnostic failed to identify that field clearly.
- Case 07: extraction evidence failed exact quotation binding twice. No clean-review inference
  is permitted from its zero observations.
- Case 08: calculator submissions used incorrect count-sum input names and then written-out
  counts, which are outside the literal numeric-token registry. These must not be silently
  converted or substituted with invented totals.

The b3 revision adds field-specific reference diagnostics, archives the actual rejected JSON,
requires method-specific calculator input/parameter names and output identifiers, exposes
numeric-binding errors together, and instructs the agent to omit unsupported arithmetic with
an explicit assessment limit. Exact quotation/token checks and the two-refusal cap are retained.
Those changes require fresh live evidence; b2 results cannot certify b3.

## Evaluator artifacts

The allowlisted copied archive is
`/tmp/creview-support-b2-results.sOg4iaWK/creview-support-b2-matrix-20261028.tar.gz`, SHA256
`4ab080cba7698a42f6e720672a33faefd9f2cf0246d0e0b382d61c677c397fb4`.
It contains synthetic sources, runner records, task answers, logs and dossiers, not profile
credentials, config files or session databases. All twelve receipts were verified locally
against a fresh installation of the original b2 wheel, not the current b3 implementation.

Private static packet: `/tmp/creview-support-b2-results.sOg4iaWK/matrix-audit`.
It includes the original manuscripts, dossiers and six globally labeled observations; all
reviewer judgments, coverage decisions, expected issues, checking times and hardware fields
remain blank. No evaluator keys were imported or transferred to the model host. No server
was started. The previous b1 failures remain documented separately.

Remaining evidence includes independently reviewed realistic cases, three repetitions per
branch, same-model baselines, long/poor-extraction and recovery probes, module-independence and
language/fidelity audits, runtime/weight reproducibility, and the human qualification gate.
