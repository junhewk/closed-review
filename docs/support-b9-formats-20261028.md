# Medical support b9 native-format regression — 2026-10-28

All three support runs completed and passed their engineering checks, including the PDF that
failed b8 quotation copying. The original paired batch nevertheless failed: its PDF baseline
used ordinary local file discovery, but the frozen baseline checker omitted that Hermes tool
from its allowlist. This failure remains recorded; a later checker correction does not rewrite
the batch or establish medical quality.

## Exact candidate and completed runs

- Package `0.9.0b9`, answer contract 7, protocol `medical-methods-v1`.
- Runner `02d047cef7658cb5c1290723743f8e0b6b68344a9cc546e6f35a4f3603f7f3b8`.
- Wheel SHA256 `5e628d579a43b1955164f60742fdedb175bcbd33d2a81c920a6ce0100761331e`.
- Dedicated workstation runtime `/tmp/creview-support-runtime.jwiCD2vE`, Python 3.14.2,
  existing private Hermes/Qwen stack, configured context 262144.
- Batch 11:01:30–11:13:20 UTC; one engineering repetition, same short invented article in three
  formats, manifest independently reviewed false. Not three independent medical studies.

| Format | Support status | Support seconds | Observations / calculations | Baseline seconds / engineering |
| --- | --- | --- | --- | --- |
| Markdown | complete | 176.07 | 1 / 5 | 56.40 / passed |
| Native DOCX | complete | 162.70 | 1 / 5 | 60.45 / passed |
| Rendered PDF | complete | 190.89 | 1 / 4 | 64.01 / failed tool-name check |

Different replay counts are not a correctness or completeness score. The PDF's successful exact
quotes demonstrate this fixture's execution regression, not reliable geometry interpretation,
clinical usefulness, full coverage or a universal PDF guarantee. B8's failed source/answers and
export remain unchanged. B9's original extracted PDF layout remains available in its dossier.

## Baseline checker diagnosis and separate correction

The failed baseline's only false recorded check is `ordinary_tools_only`. Its structured trace
uses `search_files` with pattern `manuscript.pdf`, target `files`, and its own disposable work
directory. The installed Hermes implementation registers `search_files` in the ordinary `file`
toolset; the profile already allowed that toolset. There is no detected support/legacy execution,
auto-loaded review skill or route mismatch. Trace signals alone do not prove semantic independence.

The evaluator-only revised checker now recognizes local `search_files`, limited to the baseline's
work directory, while refusing outside/symlink-escaping discovery and packaged review criteria.
Unknown/external tools remain refused. Twenty new regressions cover ordinary discovery, content
search, defaults, malformed fields, criteria paths/patterns, outside paths and unknown tools.
The baseline-specific test file passes all 39 tests. Revised harness SHA256:
`f75d6d0428b4e40f05872020a6f9b6ec290614c2c028ae2cb1941e7a18b175bb`.
The full updated repository suite passes 609 tests in 67.03 seconds against the same installed
b9 identity; no new packaged runner was created for this evaluator-only correction.

A read-only check of the actual completed PDF session returns the original false trace check
under the original harness and true under the revised harness; its saved `result.json` hash is
unchanged. The installed wheel and running suite's harness bundle were not replaced in place.
This is a separate diagnosis, not a new baseline inference or a promoted original batch.

## Preserved evaluator packet

Archive SHA256:
`de7de5bb7c2c93020bd772991410f732bd04b7900609daea8efff1655c6429fc`.
Local directory `/tmp/creview-support-b9-native-results.H2xe9T4a` contains 80 regular allowlisted
files, 1,189,751 unpacked bytes, excluding credentials, configuration and session databases.
All three export receipts independently verified against the original wheel reference sums.

The `audit` packet retains all original formats, three O-labeled proposals and three actual paired
baselines, including the failed baseline record. Human judgments, expected issues, checking times
and independent medical approval remain blank. No evaluator keys were imported, no server was
started and release remains closed. The separate b9 branch/recovery/full-length suite continues;
see [deployment readiness](deployment-readiness.md).
