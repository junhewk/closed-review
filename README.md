# closed-review

closed-review provides **medical methodological review support** for human reviewers using a
local model through Hermes Agent. Input is the submitted manuscript only, not the authors' data,
code, or interview transcripts. It does not provide a full review or publication recommendation.

**0.9.0.dev7 is a development build for supervised local pilots**, not a production or medically
qualified release. It replaces the earlier agent-based full-review promise with focused support:
make the reported methods, numbers and arguments easier for a person to inspect.

Attach the manuscript and type `/journal-article-review`, specifying the support you want:

- **Statistics:** reconstruct tables and analyses, recalculate supported quantities, and assess
  test/design compatibility and numerical interpretations.
- **Qualitative and review methodology:** separate branches for qualitative studies, systematic
  reviews, scoping reviews, and narrative reviews; examine the reported approach and evidence.
- **Logic:** reconstruct empirical, legal and normative premises, inferential connections,
  objections and conclusions.

Modules run only when selected and can be combined. Results include a compact summary and a
source-linked HTML/Markdown dossier, in the user's chosen language with original quotations.
Reviewer decisions are optional; there is no mandatory one-finding-at-a-time queue.

Model judgments, reporting gaps, calculated discrepancies and unassessable material remain
distinct. A verified calculation or exact quotation is not scientific validation. These new
modules are **not yet model-qualified**. See [the workflow and limits](docs/support.md).

closed-review is an independent project. [Hermes Agent](https://github.com/NousResearch/hermes-agent)
and Hermes Desktop are made by Nous Research, which does not maintain or endorse this project.

## Before you use it

- **It supports your review, not replaces it.** Methodological assessments are provisional.
  Manuscript-only input cannot reproduce original coding, inspect statistical diagnostics, or
  verify the content of unread references. Different runs can produce different interpretations.
- **You need permission to use AI in a review.** Many journals and funders restrict or forbid
  generative AI in peer review, and some forbid it even when the model runs on your own hardware;
  running a model locally does not make a use permitted. The skill asks you to confirm that the
  journal allows this assistance, but it cannot check the policy for you.
- **Know what is enforced.** `creview` never sends manuscript text to a model itself, checks every
  model route in the Hermes profile before a review starts, runs external lookups only after you
  approve the exact request, and records your decisions only with words you wrote. Everything else
  the agent does follows instructions, not enforcement: its terminal can reach whatever the
  operating system allows, and only network isolation of the Hermes host stops that. See
  [Privacy checks](docs/privacy.md).
- **You need your own model server.** An OpenAI-compatible server with tool calling and at least
  64k context is a candidate, not automatically a qualified setup. Run the module pilot and
  offline human audits in [the support workflow](docs/support.md). The legacy scan smoke does
  not qualify these modules. There is no built-in model default.

## Quick start

You need Hermes Agent, [uv](https://docs.astral.sh/uv/getting-started/installation/), and your own
tool-capable model server. There is no bundled model or cloud fallback.

1. Run a model server you control, reachable only from this computer or a private network.
   See [Set up a model server](docs/model-server.md). Its actual configured context must be at
   least 65,536 tokens; the setting below must match the server, not merely its advertised maximum.
2. From this checkout, build and install the development wheel (macOS/Linux):

   ```bash
   uv build
   ./scripts/install.sh --source ./dist/closed_review-0.9.0.dev7-py3-none-any.whl \
     --review-profile closed-review \
     --gateway-url http://127.0.0.1:8080/v1 --model MODEL --context-length 131072
   ```

   Dev7 is not published: keep `--source`; the installer's default release URL is unavailable.
   On Windows use `scripts\install-windows.ps1` with `-Source` and the equivalent profile/model
   arguments; see [Install](docs/install.md). The installer creates an isolated managed profile
   and runs its doctor check. Use a new profile name for different model/context settings.
3. Run `creview hermes doctor --profile closed-review --support`, then launch
   `hermes -p closed-review`. Start a fresh conversation, attach a manuscript, and type:

   ```text
   /journal-article-review Check the statistics and tables in this manuscript.
   ```

   Select only the modules you need. For Korean explanations, say so in the request; original
   quotations stay unchanged. Read the resulting dossier as a working aid, not a final verdict.

## Tested scope and remaining limits

Historical b15 testing completed every branch across separate attempts, ordinary-Hermes
baselines, native-format pairs and recovery checks. A driver-only startup fix passed 995 local
tests and a targeted qualitative rerun. The original failed full batch remains recorded.
Those runs identify b15, **not this new dev7 wheel**, and do not establish medical accuracy,
useful prioritization, or acceptable false-alert rates.

The bounded premature-stop recovery is in the evaluation driver, not stock Hermes's interactive
loop. Normal interactive sessions may still stop early. A clean exact-build six-branch batch,
interactive-path verification and independent human quality audits remain before production
claims. The automated publication gate stays closed. See [current readiness](docs/deployment-readiness.md).

## Documentation

- [Medical support workflow](docs/support.md): modules, calculations, dossiers, limits, and new
  qualification requirements.
- [Current development readiness](docs/deployment-readiness.md): pilot scope, historical
  engineering evidence and remaining qualification work.
- [Development history](docs/deployment-history.md): preserved candidate identities, failures
  and dated retest records.
- [Evaluation data](evals/README.md): synthetic fixtures, public-article provenance and what
  must stay outside Git.
- [Legacy deployment qualification](docs/deployment.md): historical scan testing. Its scores do
  not qualify the redesigned modules; publication remains blocked pending new human audits.
- [Historical scan workflow](docs/review.md): explicitly invoked legacy commands and records.
- [Set up a model server](docs/model-server.md):
  server requirements, common setups, and the Hermes model setting.
- [Install](docs/install.md): the install scripts,
  the model server setting, the private store, and loading the skill from a checkout.
- [Privacy checks](docs/privacy.md): what the
  profile check covers, and how the privacy block survives Hermes's skill self-improvement.
- [Export receipts](docs/receipts.md): what a
  receipt records and how to verify one.
- [References](docs/references.md): the Deep
  Review work this builds on, and the methods and reporting guidance the design profiles name.

## Development

```bash
uv sync --locked --extra dev
uv run --locked ruff check src tests scripts
uv run --locked pytest
uv build
```

The tests use synthetic fixtures/mocks and do not establish model quality. For an actual
local-Hermes pilot use [the pilot guide](docs/support-pilot.md). Keep raw transcripts, profile
credentials, private manuscripts, answer keys and generated dossiers outside this checkout;
commit only reviewed, key-free fixtures and evidence summaries.
