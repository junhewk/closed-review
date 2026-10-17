# Review workflows

## Basic workflow

Open the configured Hermes profile and invoke `journal-article-review`. After the privacy and policy
checks, the default workflow reads the supplied material and first gives a faithful initial summary:
what the article asks, does, and concludes; the design, data, methods, and models or frameworks its
analysis uses; and the article's own special considerations (the scope, limitations, ethics,
context, or choices the authors single out), quoted. It is not a preliminary review. It then discusses one
major candidate—or a small related minor batch—at a time. Each issue opens with where it sits in
the manuscript and carries manuscript evidence, its significance,
tiered literature context, solution candidates, and the reviewer's full substantive response. The
skill shows progress after every exchange and never selects a recommendation for the reviewer.
Before the first issue, the skill proposes design profiles for the manuscript (qualitative research,
quantitative research, systematic review, scoping review, normative argument including empirical
bioethics, legal analysis) and waits for the reviewer to confirm them. A profile lists where that kind
of work usually fails, which flaws are major in it, and which concerns are common false alarms; it
guides inspection and contains no prepared comments.

Every mode then works through **logical segments**: theme-level parts of the manuscript such as the
sampling description, the analysis, or the main argument. `creview segments propose` drafts them
(for an attached file it first records the reviewer's own words confirming the design profiles, and
`creview direct prepare-export` refuses a session without them)
from the headings; the agent refines them (one theme each, overlapping where a theme spans parts),
tags them with the confirmed profiles' areas, and gives each a scrutiny tier (light, medium, high).
A stored plan must cover every part of the manuscript. Segments organize where the review looks and
how progress is reported; they are not findings.

Progress counts include only issues already surfaced in the conversation. The skill does not expose
or count a precomputed queue of future criticisms; whole-manuscript progress is reported separately
by segment, as monitored or still to inspect.

For the deep review, see [Deep review](deep-review.md).

## Compiling and exporting

When the reviewer explicitly asks to compile, accepted records become separate author and editor
drafts while the private development record retains deferred and dismissed issues. Direct exports
use `creview direct prepare-export` to create private paths for all three artifacts, then
`creview direct finalize EXPORT_ID` to record an [export receipt](receipts.md) beside them.

## Audited review

The durable evidence ledger remains available when the user explicitly requests an audited,
exhaustive, checkpointed, or resumable review:

```text
/journal-article-review audit
```

Audited mode creates a private case and splits evidence coverage, appraisal, and finalization into
bounded sessions. Its coverage tasks are the case's logical segments, set with
`creview segments propose --case CASE` and `creview segments set --case CASE PLAN` before
`creview review start`. Discovered findings remain candidates until discussed and dispositioned by
the reviewer. Existing cases migrate in place; cases started before 0.9.0 keep their size-based
coverage units.

Resume an existing audited case in a new Hermes session with:

```text
/journal-article-review continue CASE
```

## Literature lookups and reference checks

External Crossref or OpenAlex queries are disabled by default. Each exact query must be proposed,
shown to the user, and approved before `creview lookup run` will execute it. Lookups work in every
mode: an audited review stores them in the case, and a direct or deep review stores them under the
Hermes session that passed `creview session start`. The skill offers one whenever a point rests on
literature the model knows only from memory or from the manuscript; web and browser tools are
never used.

An explicitly requested mechanical reference check is available through `creview references check`.
It checks local citation/bibliography consistency without network access. Optional metadata
verification uses a frozen manifest containing every exact Crossref or OpenAlex query and URL; the
runner executes it only after approval of that immutable set.

The checker normalizes common extraction artifacts—dense line numbers, split author tokens,
organization-authored entries, and DOI wrapping—before matching. Successful repairs are retained as
private normalization diagnostics, not surfaced as manuscript issues.
