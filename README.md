# closed-review

closed-review is confidential journal peer review on a model you control, for Hermes Agent.
"Closed" is meant as in closed peer review: the manuscript and your reasoning stay private, and the
manuscript never goes to a cloud model. It is a local-first workflow for collaboratively developing
reviews of confidential journal manuscripts with a self-hosted model. The Hermes skill surfaces evidence-grounded candidate
issues, preserves the reviewer's reasoning, and compiles accepted comments only on explicit request.
For an audited review, `creview` adds durable coverage, issue history, approved lookups, and exports.

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
  Hermes host stops that. See [What the profile check covers](https://github.com/junhewk/closed-review#what-the-profile-check-covers) and
  [Skill self-improvement](https://github.com/junhewk/closed-review#skill-self-improvement-and-the-privacy-block).
- **You need your own model server.** Any OpenAI-compatible server you control works (Ollama, LM
  Studio, llama.cpp, vLLM, or similar). There is no built-in default; `creview` refuses to run a
  review until you name it.

## Set up a model server

In this README the *gateway* is simply the OpenAI-compatible address of whatever serves your model.
Ollama or LM Studio on the same computer counts; no separate gateway software is needed. The server
must:

- serve `/v1/chat/completions` and `/v1/models`;
- support tool calling, because Hermes runs the skill's commands through tools;
- give the model a context window large enough for a manuscript and the conversation (64k tokens or
  more is a sensible floor);
- be reachable only from this computer or a private network. Never expose it to the internet:
  Ollama, for example, has no authentication of its own.

Common setups (check your server's documentation for current flags):

| Server | Start | Gateway URL |
|---|---|---|
| Ollama | `ollama pull MODEL`; the app or `ollama serve` runs the server | `http://localhost:11434/v1` |
| LM Studio | load a model and start the local server | `http://127.0.0.1:1234/v1` |
| llama.cpp | `llama-server -m MODEL.gguf --jinja --port 8080` (`--jinja` enables tool calling) | `http://localhost:8080/v1` |
| vLLM | `vllm serve MODEL --enable-auto-tool-choice --tool-call-parser PARSER` (the parser depends on the model family) | `http://localhost:8000/v1` |

Pick a model that supports tool calling (Ollama lists this as the `tools` capability). Check that the
server answers before going further:

```bash
curl http://localhost:11434/v1/models
```

Then select the same server as the main model in the Hermes profile you review from, with a named
provider rather than `auto`. For Ollama:

```yaml
model:
  provider: custom
  base_url: http://localhost:11434/v1
  default: MODEL
```

`hermes model` writes the same thing when you choose a custom or local endpoint. Hermes sends
Ollama the model's full context window automatically; set `model.ollama_num_ctx` to fix a smaller
value, for example to limit memory use. For LM
Studio, `provider: lmstudio` without a `base_url` is fine: Hermes and `creview` both use
`http://127.0.0.1:1234/v1`, or `LM_BASE_URL` if set. `localhost`, `127.0.0.1`, and `::1` count as
the same address. If the server runs on another machine, use that machine's private address
everywhere instead.

## Install

```bash
git clone https://github.com/junhewk/closed-review.git ~/src/closed-review
uv tool install ~/src/closed-review
creview config detect            # shows what it found; nothing is saved yet
creview config detect --apply    # stores it
```

`creview config detect` finds the model server for you. It looks at the Hermes profile's main model
first, then at the usual local ports (Ollama 11434, LM Studio 1234, llama.cpp 8080, vLLM 8000), and
adopts a server only when:

- it is on this computer or a private network (a host name counts only if every address it
  resolves to is private), and
- it answers `/v1/models`, listing the model.

It never adopts a cloud endpoint, even one the Hermes profile uses. Other models the profile already
routes to on the same server, such as a delegation model, are added to the trusted list. If the
server lists several models and the profile does not name one, pass `--model NAME`; use
`--profile NAME` for a named Hermes profile.

To name the server yourself instead, for example a server Hermes does not use yet:

```bash
creview config gateway --url http://GATEWAY_HOST:PORT/v1 --model MODEL_NAME [--trusted-model NAME]
```

Both commands store the trusted gateway in the private data directory (`gateway.json`).
`CREVIEW_TRUSTED_MODEL_URL`, `CREVIEW_MODEL`, and `CREVIEW_TRUSTED_MODELS` override the stored
values, `CREVIEW_MODEL_API_KEY` supplies a bearer token if the server requires one, and
`creview config show` prints the settings in effect. Then run `creview hermes doctor` to check the
Hermes profile.

Register the checkout as an external skill directory in the active Hermes profile's `config.yaml`:

```yaml
skills:
  external_dirs:
    - ~/src/closed-review/skills
```

Hermes then discovers `journal-article-review` directly from the Git checkout. Updates are explicit:

```bash
git -C ~/src/closed-review pull --ff-only
uv tool install --force ~/src/closed-review
creview hermes doctor
```

Hermes's self-improvement edits skills in place, so its lessons appear as uncommitted changes in the
checkout. `git pull --ff-only` refuses when an update touches the same files: stash the edits, pull,
and reapply them (`git stash`, `git pull --ff-only`, `git stash pop`), or use the managed installer
below, which merges them automatically.

Read Hermes's skill edits (`git -C ~/src/closed-review diff`) before committing or pushing them. The
privacy rules tell the agent to record only generic lessons, but that is an instruction, not a
check: an edit that mentions a manuscript's topic, wording, or findings would leave the machine with
the commit.

Do not use `/learn` to install this repository. `/learn` authors a new local skill from the source
material instead of loading the maintained skill, and may create an overlapping skill such as
`creview-manuscript-review`. If that has already happened, remove the generated skill from the
active profile to avoid ambiguous activation, then start a new Hermes session. Verify that the
maintained skill is visible with:

```bash
hermes skills list | rg journal-article-review
```

`creview hermes install --profile PROFILE --apply` remains available as a fallback
installer when an external skill directory is unsuitable. It copies the packaged skill into that
profile; updates must be applied again with the same command, which keeps Hermes's edits (see
[Skill self-improvement](https://github.com/junhewk/closed-review#skill-self-improvement-and-the-privacy-block)).

Hermes can instead install and track the skill through its native hub command:

```bash
hermes skills install junhewk/closed-review/skills/journal-article-review
```

That command installs only the skill documents. Install the `creview` runner separately with
`uv tool install`, because the skill invokes it for privacy validation and optional private cases.

Case data defaults to `$XDG_DATA_HOME/closed-review`, falling back to `~/.local/share/closed-review`;
set `CREVIEW_HOME` to use another private local store.

### What the profile check covers

Hermes sends conversation content to more than the main model. `creview hermes doctor` and
`creview session start` check every route in the active profile's `config.yaml`, and a review
cannot start while any of them leaves the trusted gateway:

- The main model: `model.provider` must name the trusted gateway (`custom` with its `base_url`, or a
  named provider pointing at it). An unset or `auto` provider is refused, because Hermes then lets
  side tasks fall back to OpenRouter or Nous.
- Auxiliary tasks (`auxiliary.*`, such as context compression, title generation, the
  self-improvement review, and vision) and their `fallback_chain`, plus `AUXILIARY_*` environment
  overrides. `auto`, `main`, or an empty provider means the main model and is accepted.
- `delegation`, `fallback_providers`, `fallback_model`, and `curator.auxiliary`.
- Routes a session can switch to: `model_aliases`, `providers`, `custom_providers`, mixture-of-agents
  presets (`moa`), and gateway model routes.
- `memory.provider`, which must be empty: external memory services receive conversation content.
- Vision: when credentials for OpenRouter, Nous, or DeepInfra exist, `auxiliary.vision` must be
  pinned to the trusted gateway, because Hermes sends images there when it treats the main model
  as text-only.

Every model a route names must be in the trusted list: the gateway's model plus any
`--trusted-model` names (or `CREVIEW_TRUSTED_MODELS`). When the live check runs, the gateway must
advertise each of them.

The route rules follow Hermes's own routing code and were verified against Hermes Agent v0.21.5
(config schema 49) and upstream commit `acc3cad` (schema 51). Hermes changes quickly: when the
profile's `_config_version` is outside 49-51, the doctor adds a warning that routes added or changed
since may not be checked.

Other cloud credentials (in the environment, the profile's `.env`, or `auth.json`) are listed as
warnings, by name only. They do not route anything on their own, but they let someone switch the
session with `/model` or let an API-server client choose a provider per request, and `creview`
cannot see either. Voice transcription and speech (`stt`, `tts`), Kanban workers (which run under
other profiles), and memory plugins configured outside `config.yaml` are not checked.

Toolsets that send text to outside services (`web`, `browser`) and configured MCP servers are also
listed as warnings. Only the privacy rules keep the agent from using them on a manuscript; disable
the toolsets in the review profile (`agent.disabled_toolsets: [web, browser]`) to make that a
setting rather than an instruction.

Upgrading from 0.7.0: run `creview hermes doctor` after updating. Profiles that passed before may
now be refused. The usual fixes are to set `model.provider` to `custom` (with the trusted
`base_url`) or to the trusted provider's name instead of `auto`, and to remove or repoint any
auxiliary, delegation, or alias route to a cloud provider. To route a side task to another model on
the trusted gateway, add the route and rerun `creview config detect --apply`, which trusts models
the profile routes to on that server.

Upgrading from 0.8.0: there is no built-in gateway any more. Run `creview config detect --apply`
once after updating, or name the server with `creview config gateway`, or keep setting
`CREVIEW_TRUSTED_MODEL_URL` and `CREVIEW_MODEL`. Until then the doctor refuses every profile.

Upgrading from hermes-review: up to 0.9.0.dev1 the project was called hermes-review, with the
command `hreview`. Nothing carries over. Delete the old `journal-article-review` skill folder from
the Hermes profile, then run the install script, which removes the old `hermes-review` tool and
installs `closed-review` (or run `uv tool uninstall hermes-review` yourself). Set the gateway again
with `creview config detect --apply`; the old data store, `~/.local/share/hermes-review`, is not
read and can be deleted once you no longer need its exports.

## Install script for macOS and Linux

`scripts/install.sh` does the same as the Windows script below, for Hermes Agent and Hermes Desktop
on macOS and Linux. Run it from a clone or a downloaded copy of this repository; the same command
installs and updates:

```bash
scripts/install.sh
```

Run from a Git clone, it first fast-forwards that clone (`git pull --ff-only`), setting any local
edits aside with `git stash` and restoring them afterwards, and re-runs itself if the update changed
the script; if the edits conflict with the update it stops and leaves them in the stash. Pass
`--no-git-pull` to skip this. It then installs `creview` with uv (from the GitHub repository on the
first run, `uv tool upgrade` later;
`--source` installs from somewhere else), makes sure uv's tool folder is on your `PATH`, installs
or updates the managed skill in the Hermes profile (`--profile NAME` for a named one), stores the
trusted gateway (`--gateway-url URL --model NAME`, otherwise `creview config detect --apply` when
none is stored yet), and runs `creview hermes doctor`. If the profile already loads the skill from
a Git checkout through `skills.external_dirs`, the script leaves that in place and tells you to
update the checkout instead, so Hermes never sees two copies. It needs only the bash that macOS
ships.

## Install in Hermes Desktop on Windows

The official [Hermes Desktop](https://github.com/NousResearch/hermes-agent/blob/main/apps/desktop/README.md)
uses the same skill directories as Hermes Agent, which on native Windows live under
`%LOCALAPPDATA%\hermes` (see the [Windows guide](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/windows-native.md)).
`scripts\install-windows.ps1` installs and updates both the `creview` runner and the managed
`journal-article-review` skill, so nothing needs to be copied by hand.

Prerequisites: [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git for Windows.
Hermes's Windows installer already provides Git.

Install and update with the same command, from a clone or a downloaded copy of this repository:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1
```

On the first run the script finds the model server with `creview config detect --apply`, so select
the local model in Hermes Desktop (or start the server) before running it. To name the server
yourself, add `-GatewayUrl http://GATEWAY_HOST:PORT/v1 -Model MODEL_NAME`.

The script:

1. Updates the clone it runs from, as the macOS and Linux script does: `git pull --ff-only`, with
   local edits set aside by `git stash` and restored, and a re-run when the script itself changed.
   Pass `-NoGitPull` to skip it.
2. Runs `uv tool install` from `git+https://github.com/junhewk/closed-review.git` on the first run,
   then `uv tool upgrade closed-review` on later runs, which fetches the newest commit. Pass
   `-Source git+https://…` or `-Source C:\path\to\checkout` to install from somewhere else.
   If `creview` was installed from a local folder, the script moves it to the Git source.
3. Adds uv's tool directory to the user PATH if needed, so Desktop can run `creview`.
4. Runs `creview hermes install --apply`, which writes the skill into the active profile's `skills`
   folder with a manifest. Later updates keep what Hermes's self-improvement added: unedited files
   are replaced, edited ones are merged, and a conflicting edit is kept while the new version is
   saved to `creview-skill-updates\` for review. If the folder was copied by hand earlier, the script asks before moving it to
   `creview-skill-backups\` in the profile, outside `skills\`, so Hermes does not load it twice.
   Pass `-ReplaceUnmanaged` to skip that prompt.
5. Stores the trusted gateway: with `creview config gateway` when `-GatewayUrl` and `-Model` are
   given (add `-TrustedModel NAME` for other models on it), otherwise with
   `creview config detect --apply` if none is stored yet.
6. Runs `creview hermes doctor` and reports whether the profile is ready.

On Windows, creview's private store (the gateway setting, deep-review pools, audited cases, and
exports) must be inside your user profile folder, `C:\Users\YOU`. Windows ignores the Unix
permissions creview sets on macOS and Linux; instead, the profile folder's default access list
admits only you, SYSTEM, and administrators. creview checks that the store is inside it but does not
read Windows access lists, so it cannot notice a profile folder you have shared by hand.

Use `-HermesProfile NAME` for a named profile. `HERMES_HOME` overrides the profile location, as on
other platforms. After installing or updating, fully quit and restart Desktop. In Desktop, enable
the terminal and file tools, select the trusted self-hosted endpoint and model described above,
and start a new chat with:

```text
/journal-article-review
```

The skill runs `creview session start` before reading a manuscript. It fails if the skill's privacy
block does not match the installed runner, so always update both with the script. Do not supply
confidential material until the check passes, and do not bypass a failed privacy check. Do not use `/learn` to
install or update the maintained skill.

If Desktop connects to a remote Hermes gateway, install both the skill and `creview` on that host,
in its active profile, rather than in the Windows client's local directories.

## Skill self-improvement and the privacy block

Hermes improves skills from experience: after a task it may patch `SKILL.md` or add reference
files. That is expected, and `creview` does not try to stop it. Nothing in Hermes can make a skill
read-only, so this project does not claim the skill text stays as shipped.

What `creview` does instead:

- **Privacy rules come from the package.** `creview session start` runs the profile check and
  returns the privacy rules from the installed `creview`, which skill self-improvement cannot
  edit. The skill keeps only a short marked block telling the agent to run it.
- **The privacy block is checked, everything else is not.** Every doctor run compares the block
  between `<!-- creview:privacy-gate:begin -->` and `<!-- creview:privacy-gate:end -->` with the
  installed release. Other edits are listed under `skill_changes` for information. If the block
  changed, reviews stop until you look at `creview hermes skill-diff` and run
  `creview hermes skill-restore --apply`, which restores only that block and keeps Hermes's other
  edits.
- **Receipts record whether the check ran.** `creview session start` records a preflight for the
  Hermes session (`HERMES_SESSION_ID`, stored hashed). An export receipt states `passed`, `failed`,
  or `none`. Audited cases record `audited_case`, because `review start` refuses to run without a
  passing check.

Upgrading from 0.6.0 or earlier: run `creview hermes install --apply` (or the Windows script) once.
Those releases kept no baseline, so an edited `SKILL.md` cannot be merged that first time: the
update keeps Hermes's version, replaces its old privacy section with the new block, and saves the
full new `SKILL.md` to `creview-skill-updates/` in the profile for you to compare. Later updates
merge automatically.

The limits: these checks run only when `creview` runs. A session that never calls `creview`, and
never exports through it, leaves no trace, and the privacy rules are instructions to the agent,
not enforcement. The agent's terminal can reach anything the operating system allows; only network
isolation of the Hermes host stops that.

## Basic workflow

Open the configured Hermes profile and invoke `journal-article-review`. After the privacy and policy
checks, the default workflow reads the supplied material and first gives an article overview: what
the article asks, does, and concludes; the design, data, methods, and models or frameworks its
analysis uses; and a few open considerations about the article as a whole. It then discusses one
major candidate—or a small related minor batch—at a time. Each issue opens with where it sits in
the manuscript and carries manuscript evidence, its significance,
tiered literature context, solution candidates, and the reviewer's full substantive response. The
skill shows progress after every exchange and never selects a recommendation for the reviewer.
Before the first issue, the skill proposes design profiles for the manuscript (qualitative research,
systematic review, scoping review, normative argument including empirical bioethics, legal analysis) and
waits for the reviewer to confirm them. A profile lists where that kind of work usually fails and
which concerns are common false alarms; it guides inspection and contains no prepared comments.

Every mode then works through **logical segments**: theme-level parts of the manuscript such as the
sampling description, the analysis, or the main argument. `creview segments propose` drafts them
from the headings; the agent refines them (one theme each, overlapping where a theme spans parts),
tags them with the confirmed profiles' areas, and gives each a scrutiny tier (light, medium, high).
A stored plan must cover every part of the manuscript. Segments organize where the review looks and
how progress is reported; they are not findings.

Progress counts include only issues already surfaced in the conversation. The skill does not expose
or count a precomputed queue of future criticisms; whole-manuscript progress is reported separately
by segment, as monitored or still to inspect.

### Deep review

```text
/journal-article-review deep
```

A deep review, modelled on the segment-based structure of Google's
[Deep Review](https://research.google/blog/analyzing-technical-documents-with-deep-review/) but run
entirely on the trusted local model, searches the manuscript before the conversation starts:

1. `creview scan start` reads the attached file in place and drafts a segment plan; the agent
   refines it and `creview scan plan` stores it.
2. Each segment is reviewed in sequence, in independent passes: light 1, medium 2, high 3. Every
   candidate must quote the manuscript verbatim at a real location, or `creview scan submit`
   refuses it.
3. `creview scan synthesize` merges candidates that quote the same passage, and the agent screens
   the merged pool against the profiles' false alarms (`creview scan screen`).
4. From the summaries each segment's first pass recorded, the agent writes an article overview:
   what the article asks, does, and concludes; the methods, models, and frameworks its analysis
   uses; and a few open considerations (`creview scan overview`). The conversation opens with it.
5. The conversation then draws one kept candidate at a time (`creview scan candidate`), majors
   first, and develops it with the reviewer exactly as in the default review.

The pool is private: the reviewer sees segment progress and the candidates surfaced so far, never the
size or content of what remains. The scan stores only its plan, the segment summaries and overview,
and the pool, re-reads the file each step, and stops if the file changes; `creview scan purge` deletes it. Segments run one after
another, so a deep review takes several times longer than the default one.

When the reviewer explicitly asks to compile, accepted records become separate author and editor
drafts while the private development record retains deferred and dismissed issues. Direct exports
use `creview direct prepare-export` to create private paths for all three artifacts, then
`creview direct finalize EXPORT_ID` to record an [export receipt](https://github.com/junhewk/closed-review#export-receipts) beside them.

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

External Crossref or OpenAlex queries are disabled by default. Each exact query must be proposed,
shown to the user, and approved before `creview lookup run` will execute it.

An explicitly requested mechanical reference check is available through `creview references check`.
It checks local citation/bibliography consistency without network access. Optional metadata
verification uses a frozen manifest containing every exact Crossref or OpenAlex query and URL; the
runner executes it only after approval of that immutable set.

The checker normalizes common extraction artifacts—dense line numbers, split author tokens,
organization-authored entries, and DOI wrapping—before matching. Successful repairs are retained as
private normalization diagnostics, not surfaced as manuscript issues.

## Export receipts

Every export writes a `receipt.json` beside the drafts: automatically for audited exports, and through
`creview direct finalize EXPORT_ID` after the agent writes a direct export. Each receipt is also
appended to the private local log `receipts.jsonl` in the case-data directory. Nothing is sent
anywhere.

A receipt records the creview version, a SHA-256 of the installed package's file list
(`sha256sum` format, excluding `__pycache__`), the model name, the endpoint as a category
(`loopback`, `private-network`, `hostname`, or `public`) rather than its address, the profile check
result, and for each exported draft both the file's SHA-256 and a `text_sha256`. The text hash is
computed after NFKC normalization and collapsing all whitespace, so text pasted into and copied back
out of a journal's submission system still matches while any change of wording does not. The
`receipt_id` is the SHA-256 of the receipt's sorted, compact JSON without that field.

Receipts also record the profile check's view of the skill's privacy block and a `preflight`:
whether `creview session start` passed in the session that exported (see
[Skill self-improvement](https://github.com/junhewk/closed-review#skill-self-improvement-and-the-privacy-block)).

Receipts are self-reported (`"attestations": [{"type": "self"}]`). They detect accidental change to
the exported text or the installed tool; they are not signed, so they do not prove that the tool was
unmodified or that no other AI tool was used.

### Verifying a receipt

Hermes's skill self-improvement never writes to the `creview` installation, but the agent's terminal
could, and a modified `creview` could also fake its own checks. Verify a receipt with a copy of
`creview` that did not run on the reviewed machine, installed fresh from the release named in the
receipt:

```bash
uvx --from git+https://github.com/junhewk/closed-review.git@vVERSION creview receipts verify receipt.json
```

The verifier checks the `receipt_id`, compares each exported file beside the receipt (an exact
match, or `text_match` after normalization), and compares the receipt's `tool.sums_sha256` with its
own installed files. A receipt from another version reports the tool as `not_checked`.

To compare against a saved reference instead, pass `--sums FILE`. Each release on the
[releases page](https://github.com/junhewk/closed-review/releases) attaches `creview-sums-VERSION.txt`, the package hashes of a clean install of that
release; it is the `sums` field of `creview receipts sums`, byte for byte.

## Development

```bash
uv sync --extra dev
uv run creview --help
```
