# closed-review

closed-review is confidential journal peer review on a model you control, for Hermes Agent.
"Closed" is meant as in closed peer review: the manuscript and your reasoning stay private, and the
manuscript never goes to a cloud model. It is a local-first workflow for collaboratively developing
reviews of confidential journal manuscripts with a self-hosted model. The Hermes skill surfaces evidence-grounded candidate
issues, preserves the reviewer's reasoning, and compiles accepted comments only on explicit request.
For an audited review, `creview` adds durable coverage, issue history, and exports; approved literature
lookups work in every mode.

closed-review is an independent project. [Hermes Agent](https://github.com/NousResearch/hermes-agent)
and Hermes Desktop are made by Nous Research, which does not maintain or endorse this project.

## Before you use it

- **You need permission to use AI in a review.** Many journals and funders restrict or forbid
  generative AI in peer review, and some forbid it even when the model runs on your own hardware;
  NIH, for example, prohibits generative AI in grant peer review. Running a model locally does not
  make a use permitted. Before reading a manuscript, the skill asks you to confirm that the journal
  allows this assistance and records your answer, but it cannot check the policy for you.
- **Know what is enforced.** `creview` never sends manuscript text to a model itself, checks every
  model route in the Hermes profile before a review starts, and runs external lookups only after you
  approve the exact request. Everything else the agent does follows instructions, not enforcement:
  its terminal can reach whatever the operating system allows, and only network isolation of the
  Hermes host stops that. See [What the profile check covers](https://github.com/junhewk/closed-review/blob/main/docs/privacy.md#what-the-profile-check-covers) and
  [Skill self-improvement](https://github.com/junhewk/closed-review/blob/main/docs/privacy.md#skill-self-improvement-and-the-privacy-block).
- **You need your own model server.** Any OpenAI-compatible server you control works (Ollama, LM
  Studio, llama.cpp, vLLM, or similar). There is no built-in default; `creview` refuses to run a
  review until you name it.

## Quick start

1. Run a model server you control that serves `/v1/chat/completions` with tool calling, reachable
   only from this computer or a private network, and select it as the main model in your Hermes
   profile. See [Set up a model server](https://github.com/junhewk/closed-review/blob/main/docs/model-server.md).
2. Install the runner and store the trusted gateway:

   ```bash
   git clone https://github.com/junhewk/closed-review.git ~/src/closed-review
   uv tool install ~/src/closed-review
   creview config detect --apply
   ```

3. Load the skill, either by adding `~/src/closed-review/skills` to `skills.external_dirs` in the
   profile's `config.yaml` or with `creview hermes install --apply`, then check the profile:

   ```bash
   creview hermes doctor
   ```

   The install scripts (`scripts/install.sh`, `scripts\install-windows.ps1` for Hermes Desktop on
   Windows) do steps 2 and 3 and keep both up to date. See [Install](https://github.com/junhewk/closed-review/blob/main/docs/install.md).
4. In Hermes, start a review:

   ```text
   /journal-article-review          # discuss one candidate issue at a time
   /journal-article-review deep     # search the whole manuscript segment by segment first
   /journal-article-review audit    # a resumable, audited case with a durable evidence ledger
   ```

## Documentation

- [Set up a model server](https://github.com/junhewk/closed-review/blob/main/docs/model-server.md): server requirements, common setups, and the Hermes
  model setting.
- [Install](https://github.com/junhewk/closed-review/blob/main/docs/install.md): `creview config detect`, the external skill directory, the install
  scripts for macOS, Linux, and Hermes Desktop on Windows, and upgrade notes.
- [Privacy checks](https://github.com/junhewk/closed-review/blob/main/docs/privacy.md): what the profile check covers, and how the privacy block
  survives Hermes's skill self-improvement.
- [Review workflows](https://github.com/junhewk/closed-review/blob/main/docs/workflow.md): the default review, design profiles, logical segments,
  compiling and exporting, audited cases, literature lookups, and reference checks.
- [Deep review](https://github.com/junhewk/closed-review/blob/main/docs/deep-review.md): the segment-by-segment scan, grouping by
  concern key, the sweep, and how candidates reach the reviewer.
- [Export receipts](https://github.com/junhewk/closed-review/blob/main/docs/receipts.md): what a receipt records and how to verify one.
- [References](https://github.com/junhewk/closed-review/blob/main/docs/references.md): the Deep Review work this
  builds on, and the methods and reporting guidance the design profiles name, with DOIs.

## Development

```bash
uv sync --extra dev
uv run creview --help
```
