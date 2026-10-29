# Install

You need a model server you control (see [Set up a model server](model-server.md)),
[uv](https://docs.astral.sh/uv/getting-started/installation/), and Git (on Windows, Hermes's
installer already provides Git).

## Dedicated review profile (recommended)

Use a wheel and installer from the same tagged release. The installers now pin the release wheel
and do not update a checkout unless you explicitly pass `--git-pull` / `-UpdateCheckout`.
This checkout is **0.9.0.dev7**, a development build for supervised local pilots, not a qualified
release. Tagged development builds are distributed through
[TestPyPI](https://test.pypi.org/project/closed-review/0.9.0.dev7/) and
[GitHub prereleases](https://github.com/junhewk/closed-review/releases/tag/v0.9.0.dev7), not PyPI.
For a local checkout, build and install your own wheel:

```bash
uv build
./scripts/install.sh --source ./dist/closed_review-0.9.0.dev7-py3-none-any.whl \
  --review-profile closed-review --gateway-url http://127.0.0.1:8080/v1 --model MODEL \
  --context-length 131072
```

On Windows, use `-Source`, `-ReviewProfile`, `-GatewayUrl`, `-Model`, and `-ContextLength` with the PowerShell
installer. Omit the source override only when the pinned release is published. Developer checkouts
remain available through `--source` / `-Source`.

To preview profile creation separately after installing the runner:

```bash
creview hermes setup-profile --profile closed-review \
  --gateway-url http://127.0.0.1:8080/v1 --model MODEL --context-length 131072
```

Add `--apply` to create it. Replace `131072` with the actual configured server context.
Medical support requires this explicit value; it does not resize the model server.
Values below 65536 are not eligible for the current support profile.
An advertised 64k window is an eligibility floor, not a qualification result.

The fresh profile enables only terminal, file, skills, and clarification toolsets. Persistent
memory, background self-improvement, delegation, explicitly enabled user plugins, and configured
MCP servers are disabled. Hermes 0.21.5 can still auto-load bundled backend plugins even when
`plugins.enabled` is empty; the doctor checks the configured allow-list, not every loaded module.
Enabled model side tasks use the trusted endpoint. It hides inline diffs/tool previews and permits
one active review. It never clones your personal configuration or credentials.

An unmanaged profile is never overwritten. Repeating setup with identical model settings updates
the skill and launcher while preserving configuration and records; modified managed launchers are
refused. Use a new name when changing model or context settings. On Unix, a profile-local launcher
selects the intended runner through Hermes's terminal initialization. Native Windows relies on
the installed command being on PATH and must pass the runtime smoke check.

```bash
creview hermes doctor --profile closed-review --support
hermes -p closed-review
```

Restart Hermes after installation. Start a fresh conversation per manuscript. `doctor` retains
its legacy `ready` result and adds `support_readiness` for the stricter medical support contract.
`--support` refuses unsafe toolsets, unpinned auxiliary routes, cloud credentials, unverified
context, altered launchers and incompatible live-session routes. The tool does not run inference
or certify review quality. The skill runs `creview session start --support` inside Hermes before
reading the manuscript. Test these new modules with [the synthetic pilot](support-pilot.md),
then complete the offline qualification audits. Receipts certify file integrity, not correctness.

Each managed profile has its own `review-data` store. Hermes transcripts remain in its `state.db`.
Module outputs are private static dossiers, not author/editor decision drafts. Journal permission
and host-level data/network controls remain required; profile settings are not an OS sandbox.

### Legacy interfaces (not the support deployment gate)

`creview hermes smoke --profile NAME --keep` uses disposable synthetic session storage, checks
the runner from inside Hermes, resumes a saved scan, sends a scripted acceptance through the
normal user-message path, and verifies the three exports and receipt. Its default total timeout
is 900 seconds (`--timeout` changes it); the first run may include Hermes runtime preparation.
Use `--hermes PATH` if needed. `--keep` retains synthetic artifacts; otherwise they are removed.
Passing does not establish scientific accuracy, faithful draft wording, compression recovery, or
network isolation. See [deployment qualification](deployment.md).

Legacy direct-export finalization requires all three nonempty drafts before writing a receipt.
For a scan, `creview direct prepare-export --scan SCAN` links the accepted records and checks
explicit severity labels in the author and editor drafts before finalization. The check flags an
unambiguous conflict when accepted ratings agree. Mixed ratings or reviewer severity wording need
manual review. A second narrow check catches certain explicit mentions of unseen findings in any
draft. Neither check establishes that the rest of a draft is faithful or free of unseen material.
Purging a scan does not purge transcripts, attachments, logs, or exports. Confidential use depends
on journal permission and the host's data/network controls. Profile settings are not an OS sandbox.

## Installing into an existing profile

This is legacy/development compatibility, not the medical-support installation path. It does
not create a managed, support-eligible profile, and a legacy `doctor` result does not qualify
the redesigned modules. For medical support use the dedicated profile above and require
`creview hermes doctor --profile NAME --support` before attaching a manuscript. Unmanaged
profiles, personal credentials and external skill directories must not be assumed eligible.

The same command installs and updates. On macOS and Linux, for Hermes Agent and Hermes Desktop:

```bash
git clone https://github.com/junhewk/closed-review.git ~/src/closed-review
~/src/closed-review/scripts/install.sh
```

On Windows, for Hermes Desktop, from a clone or a downloaded copy of this repository:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1
```

The script:

1. Leaves the checkout unchanged by default. The developer-only `--git-pull` / `-UpdateCheckout`
   option fast-forwards it, stashing/restoring local edits. `--no-git-pull` / `-NoGitPull` skips it.
2. Installs the pinned release wheel with uv (`--source` / `-Source` overrides it) and puts uv's tool folder on your
   `PATH`. This candidate is unpublished; the local-wheel override above is required here too.
3. Installs or updates the skill in the Hermes profile (`--profile NAME` / `-HermesProfile NAME`
   for a named one). Updates keep what Hermes's self-improvement added: unedited files are
   replaced, edited ones merged, and a conflicting edit is kept while the new version is saved to
   `creview-skill-updates/` for review. A skill folder copied by hand is moved to
   `creview-skill-backups/` after you agree (`--replace-unmanaged` / `-ReplaceUnmanaged` skips the
   question). If the profile loads the skill from a Git checkout (below), the script leaves it
   there and tells you to update the checkout.
4. Stores the trusted gateway: `--gateway-url URL --model NAME` (`-GatewayUrl`, `-Model`), or else
   `creview config detect --apply` when none is stored yet.
5. Runs `creview hermes doctor` and reports whether the profile is ready.

Fully quit and restart Hermes (or Hermes Desktop) after compatibility updates. These steps do
not make an existing unmanaged profile eligible for medical support. For the current slash
command, use the dedicated managed profile above and pass its strict `--support` doctor before
attaching a manuscript. Do not supply confidential material to an unmanaged profile on the
strength of a legacy doctor result. The skill's strict support gate will refuse it.

The following display notes describe legacy profiles; managed support profiles already set the
required values. Do not edit a frozen support configuration to work around a failed check.
In Hermes's terminal interface, file edits are displayed as inline diffs by default. During a scan
these can show unfinished findings before the agent presents them. To hide the diffs, add this to
the review profile's `config.yaml` before restarting Hermes (merge it into `display` if that
section already exists):

```yaml
display:
  inline_diffs: false
```

Do not use `tool_progress: verbose` for this workflow: it can display tool arguments and results.
These are display settings, not access controls; the reviewer's session still contains tool output.
`creview hermes doctor` and `creview session start` warn when the profile uses the default inline
diffs or verbose progress. A session-level `/verbose` change can override the configured progress.

The skill runs `creview session start --support` before reading a manuscript, and it fails if the skill's
privacy block does not match the installed runner: always update both with the script. Do not
supply confidential material until the check passes, and do not bypass a failed check.

If Desktop connects to a remote Hermes gateway, install on that host, in its active profile.

## The model server

`creview config detect` finds the server. It looks at the Hermes profile's main model first, then
at the usual local ports (Ollama 11434, LM Studio 1234, llama.cpp 8080, vLLM 8000), and adopts a
server only when it is on this computer or a private network (a host name counts only if every
address it resolves to is private) and it answers `/v1/models` listing the model. It never adopts
a cloud endpoint. Other models the profile routes to on the same server, such as a delegation
model, join the trusted list. Pass `--model NAME` when the server lists several, and
`--profile NAME` for a named profile. To name a server yourself:

```bash
creview config gateway --url http://GATEWAY_HOST:PORT/v1 --model MODEL_NAME [--trusted-model NAME]
```

Both store the gateway in creview's private data directory (`gateway.json`).
`CREVIEW_TRUSTED_MODEL_URL`, `CREVIEW_MODEL`, and `CREVIEW_TRUSTED_MODELS` override it,
`CREVIEW_MODEL_API_KEY` supplies a bearer token, and `creview config show` prints the settings in
effect. For what `creview hermes doctor` checks, see
[Privacy checks](privacy.md#what-the-profile-check-covers).

## The private store

For unmanaged profiles, creview keeps the gateway setting, scans, lookups, reference checks, and exports in
`$XDG_DATA_HOME/closed-review` (by default `~/.local/share/closed-review`); set `CREVIEW_HOME` for
another private location. On Windows the store must be inside your user profile folder,
`C:\Users\YOU`: Windows ignores the Unix permissions creview sets, and the profile folder's default
access list admits only you, SYSTEM, and administrators. creview checks that the store is inside
it but does not read access lists, so it cannot notice a profile folder you shared by hand.

## For developers: load the skill from a checkout

Instead of the managed copy, a profile can load the skill straight from a Git checkout:

This is legacy/development compatibility, not an eligible medical-support profile. Medical support
requires the dedicated profile's packaged skill, without external directories or personal credentials.

```bash
git clone https://github.com/junhewk/closed-review.git ~/src/closed-review
uv tool install ~/src/closed-review
creview config detect --apply
```

```yaml
# the profile's config.yaml
skills:
  external_dirs:
    - ~/src/closed-review/skills
```

Update with `git -C ~/src/closed-review pull --ff-only`, `uv tool install --force
~/src/closed-review`, and `creview hermes doctor`. Hermes's self-improvement edits skills in
place, so its lessons appear as uncommitted changes in the checkout: read them
(`git -C ~/src/closed-review diff`) before committing or pushing. The privacy rules ask for
generic lessons only, but nothing checks that.

Do not use `/learn` to install this repository: it writes a new local skill from the source instead
of loading this one. If that has happened, remove the generated skill from the profile and start a
new Hermes session.

## From hermes-review

Up to 0.9.0.dev1 the project was called hermes-review, with the command `hreview`. Nothing carries
over: delete the old `journal-article-review` skill folder from the profile and run the install
script, which removes the old tool. The old store, `~/.local/share/hermes-review`, is not read.
