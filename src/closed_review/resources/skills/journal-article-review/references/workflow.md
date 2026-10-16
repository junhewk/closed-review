# Optional audited CLI workflow

Use this workflow only for an explicitly audited, exhaustive, checkpointed, or resumable review.
Direct review must not create a case. All commands return JSON, and manuscript text must never be
placed in shell arguments.

## Intake

```bash
creview session start
creview case create MANUSCRIPT --journal JOURNAL \
  [--supplement FILE] [--guideline FILE] [--review-form FILE]
creview case attest CASE --statement-file ATTESTATION_FILE
creview segments propose --case CASE
creview segments set --case CASE PLAN_PATH
creview review start CASE
```

`segments propose` writes a draft plan of logical segments. Refine it as the skill describes (one
theme per segment, overlaps where useful, profile areas, tiers), then store it with `segments set`.
creview refuses a plan that leaves any part of the manuscript or supplements uncovered, and the plan
cannot change once the review starts. Each segment becomes one coverage task; its task includes the
outline of all segments, so read neighbouring segments when a claim depends on them.

Stop after intake. Report the case id and the exact continue command.

## Coverage and candidate discovery

```bash
creview review status CASE
creview review batch-start CASE --limit 3
creview review next CASE
creview finding submit CASE PROPOSAL_PATH
```

Coverage and rubric tasks are internal discovery prompts, not final review items. A submitted
finding begins as `candidate`. Ground it in a verbatim source quote and include the potential issue,
why it matters, audience, verification status, literature evidence tiers when relevant, and
solution candidates.

A batch contains at most three coverage items. Stop when the batch closes. The existing Hermes
session boundary between intake, batches, and compilation remains mandatory.

## Issue development

Candidate discussion takes priority over additional coverage:

```bash
creview finding next CASE
creview finding prepare-response CASE FINDING_ID
creview finding respond CASE FINDING_ID RESPONSE_PROPOSAL
creview finding list CASE [--status candidate|developing|accepted|deferred|dismissed]
```

The response proposal requires:

```json
{
  "disposition": "developing | accepted | deferred | dismissed",
  "reviewer_reasoning": "faithful account of every substantive point and qualification",
  "agent_synthesis": "how the response changed or confirmed the issue"
}
```

It also carries the editable finding fields. Do not proceed to another major issue until the current
one is accepted, deferred, or dismissed. `finding next` returns one major issue or up to three
related minor issues. Existing `prepare-revision`, `revise`, and `dismiss` commands remain
compatibility operations; normal development uses response proposals.

After every response, show the returned status counts and resume the coverage batch only when no
candidate/developing issue remains.

## Requested reference check

Run only when the user asks:

```bash
creview references check --case CASE [--source-id manuscript]
creview references request-metadata CHECK --provider crossref|openalex
creview references run-metadata CHECK REQUEST --approval-file APPROVAL
```

The local check imports only its `issues` as candidate findings. Its `normalizations` are private
method notes and its `warnings` are parser limitations, not manuscript defects; never turn either
into a finding. Before metadata execution, show the complete immutable query manifest and wait for
explicit approval. Metadata results establish bibliographic identity only.

## Compilation and export

Compilation is explicit and requires complete coverage plus no candidate/developing issues:

```bash
creview draft prepare CASE
creview draft submit CASE PROPOSAL_PATH
creview export CASE --out OUTPUT_DIRECTORY
```

The recommendation may be `null`. If included, the draft requires the user's chosen recommendation,
rationale, and recorded reasoning. Export produces a private development record and clean author and
editor drafts. Only accepted findings enter clean drafts; deferred and dismissed records remain in
the development ledger and review JSON. Export also writes a self-reported `receipt.json`; tell the
user it exists and that it does not prove that no other AI tool was used.

Existing cases migrate in place. Legacy active findings become accepted with an explicit marker
that historical reviewer reasoning was not recorded; no reasoning is invented. Existing submitted
legacy drafts remain exportable until they are changed.
