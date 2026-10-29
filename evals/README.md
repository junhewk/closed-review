# Evaluation fixtures and historical evidence

This directory contains reproducible engineering inputs and sanitized development records,
not a medical-quality certification or a store for live review data.

| Directory | Purpose |
| --- | --- |
| `support-pilot/` | Twelve short, explicitly synthetic branch fixtures. |
| `support-ordinary-candidates/` | Synthetic support-versus-ordinary-Hermes inputs. |
| `support-ordinary-draft/` | Six longer synthetic manuscripts and source-review notes. |
| `support-numeric-regression/` | Synthetic numeric boundary/regression fixture. |
| `support-public-articles/` | Published-article selection, provenance, hashes and conversion manifest; full texts are stored separately. |
| `deployment/` | Key-free manifests, synthetic controls, historical evidence and frozen launchers; current publication gate. |

The `b*` filenames identify historical experimental candidates. Preserve their versions,
hashes, failed outcomes and launcher contents: they are not results for the current dev7 wheel.
Historical absolute paths describe the machines used and may no longer exist. In particular,
scripts under `deployment/` can depend on old wheels and host paths; use current scripts under
`scripts/` for new work, not an archived controller without inspecting it.

Keep raw Hermes transcripts, profile configurations, credentials, private manuscripts, answer
keys, completed human audits and generated dossiers outside the checkout in private storage.
`runs/`, `results/` and `private/` are ignored as a precaution, not an access control. Only commit
intentionally reviewed, key-free fixtures and summaries. No output may be automatically labeled
a human-approved concern merely because a calculation, quotation or engineering check passes.

For current status see [development readiness](../docs/deployment-readiness.md); for running
the branch pilot see [the pilot guide](../docs/support-pilot.md).
