# Privacy checks

## What the profile check covers

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
- Vision: an `auxiliary.vision` route that names a cloud provider is refused like any auxiliary task.
  Leaving vision unpinned is your Hermes setting and only draws a warning, but note what it means:
  when credentials for OpenRouter, Nous, or DeepInfra exist, Hermes may send images there when it
  treats the main model as text-only. Do not give the agent figures or page images from
  confidential material unless `auxiliary.vision` is pinned to the trusted gateway.

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
