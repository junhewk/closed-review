# Development readiness — 0.9.0.dev7

**Suitable for supervised local pilots; not a production or medically qualified release.**
This development build packages the medical methodological review-support redesign. It is not
an automatic reviewer, a publication recommendation, or a certification of medical correctness.
Install from a locally built wheel using [the development installation instructions](install.md).
No public package release is implied by the version or repository push.

## Current scope

- Explicitly selected statistics, qualitative-study, systematic-review, scoping-review,
  narrative-review and logic branches. Branches can be combined.
- Source-linked reconstruction, deterministic calculations where inputs permit, and provisional
  observations in a static HTML/Markdown dossier. Quotes retain the original language;
  English/Korean presentation and optional genuine reviewer decisions are supported.
- Managed Hermes profiles with strict local-route/context checks, bounded work, resumable
  state and integrity receipts. These controls are not an OS network sandbox or a quality audit.

The existing engineering target is jkworkstation's private Hermes/Qwen stack. Other models,
operating systems and contexts are not qualified by inference from it. Use only permitted
manuscripts, keep transcripts and review records private, and inspect the output yourself.

## Engineering evidence and its limits

Dev7 local verification on October 29, 2026: **999 tests passed**, with no failures, errors or
skips, against a fresh wheel installation on Linux x86_64 / Python 3.11.15. The source-tree
Python path was disabled. Ruff, lock consistency, Bash/PowerShell installer parsing, packaged
skill parity and archive-content checks passed; the exact-build publication gate refused this
unqualified identity as intended. See [the dev7 validation record](../evals/deployment/dev7-local-validation-20261029.json).
This is local engineering verification, not a new live-Hermes or medical-quality evaluation.

Historical candidates retain their original versions, hashes, failures and limitations:

- The b15 persistent suite completed five of six real-public-article support cases, all six
  ordinary-Hermes baselines, all three native-format pairs, and four recovery jobs. Its
  qualitative case stopped before creating a run, so that full batch remains failed.
- A subsequent driver-only bounded-startup fix passed **995 local tests** against the b15
  installed wheel. A separate real qualitative pair then completed, with source, quote,
  export, receipt and baseline readback independently verified. Live startup was normal;
  the new premature-stop fallback was exercised deterministically, not in that live case.
- Every branch therefore completed across attempts, but this is not one clean final-driver
  six-branch batch, a representative quality sample, or evidence of medical validity.

See [the final b15 retest record](support-b15-restored-20261029.md),
[the preserved tracker and earlier evidence](deployment-history.md), and
[the evaluation-data guide](../evals/README.md).

Dev7 is a new package identity. Historical Hermes results do not become exact-dev7 results.
The startup fallback belongs to `scripts/test-support-hermes.py`, the evaluation driver;
it does **not** patch stock Hermes's interactive conversation loop. A normal interactive launch
can still stop early and require user intervention.

## Remaining production/qualification work

1. Verify the user-facing interactive launch path, including premature stops, with the final
   installed wheel and intended Hermes/model configuration.
2. Run one clean six-branch engineering batch with that exact identity and final driver;
   preserve unsuccessful attempts and verify saved sources, calculations and exports.
3. Independently audit reconstruction/evidence fidelity, useful observations and false alerts,
   translation, coverage, checking time and hardware/runtime limits. Real published articles
   are not automatically clean controls; synthetic fixtures are not clinical validation.

These are not prerequisites for a supervised development pilot or committing the source.
They remain prerequisites for stronger deployment/quality claims. The exact-build
[`release-gate.json`](../evals/deployment/release-gate.json) intentionally has no qualified
configurations; automated publication remains blocked. Private answer keys and human audits
stay off the model host and out of Git.
