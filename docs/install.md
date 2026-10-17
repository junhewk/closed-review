# Install

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
[Skill self-improvement](privacy.md#skill-self-improvement-and-the-privacy-block)).

Hermes can instead install and track the skill through its native hub command:

```bash
hermes skills install junhewk/closed-review/skills/journal-article-review
```

That command installs only the skill documents. Install the `creview` runner separately with
`uv tool install`, because the skill invokes it for privacy validation and optional private cases.

Case data defaults to `$XDG_DATA_HOME/closed-review`, falling back to `~/.local/share/closed-review`;
set `CREVIEW_HOME` to use another private local store.

For what `creview hermes doctor` checks, see [Privacy checks](privacy.md#what-the-profile-check-covers).

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
the terminal and file tools, select the trusted self-hosted endpoint and model (see
[Set up a model server](model-server.md)), and start a new chat with:

```text
/journal-article-review
```

The skill runs `creview session start` before reading a manuscript. It fails if the skill's privacy
block does not match the installed runner, so always update both with the script. Do not supply
confidential material until the check passes, and do not bypass a failed privacy check. Do not use `/learn` to
install or update the maintained skill.

If Desktop connects to a remote Hermes gateway, install both the skill and `creview` on that host,
in its active profile, rather than in the Windows client's local directories.

## Upgrading

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
