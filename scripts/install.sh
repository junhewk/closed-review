#!/usr/bin/env bash
# Install or update closed-review for Hermes Agent and Hermes Desktop on macOS and Linux.
#
# Installs or updates the creview runner with uv, installs or updates the managed
# journal-article-review skill in the Hermes profile, stores the trusted model gateway, and runs
# `creview hermes doctor`. Use the same command to install and to update.
#
# Usage: scripts/install.sh [options]
#   --source SRC          Any source `uv tool install` accepts: a git+https:// or git+ssh:// URL, or
#                         a local folder. Default on the first run: the public GitHub repository.
#                         Later runs without --source upgrade from the source uv recorded.
#   --profile NAME        The Hermes profile (default: HERMES_SESSION_PROFILE, else "default" under
#                         HERMES_HOME or ~/.hermes).
#   --gateway-url URL     The trusted model server's OpenAI-compatible URL. Optional: when no
#                         gateway is stored, the script runs `creview config detect --apply`.
#   --model NAME          The review model on that server. Required with --gateway-url.
#   --trusted-model NAME  Another model on the same server that Hermes routes may use (repeatable).
#   --replace-unmanaged   Move a hand-copied skill folder to a backup without asking.
#   --no-git-pull         Do not update the Git checkout this script runs from.
#   -h, --help            Show this help.
#
# Run from a Git clone, the script first fast-forwards that clone (setting local edits aside with
# `git stash` and restoring them), so the script and skill files match what it installs.
#
# Written for the bash 3.2 that macOS ships.

set -euo pipefail

DEFAULT_SOURCE="git+https://github.com/junhewk/closed-review.git"
source_arg=""
profile=""
gateway_url=""
model=""
trusted_models=()
replace_unmanaged=0

no_git_pull=0
original_args=("$@")

usage() { sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
    case "$1" in
        --source) source_arg="${2:?--source needs a value}"; shift 2 ;;
        --profile) profile="${2:?--profile needs a value}"; shift 2 ;;
        --gateway-url) gateway_url="${2:?--gateway-url needs a value}"; shift 2 ;;
        --model) model="${2:?--model needs a value}"; shift 2 ;;
        --trusted-model) trusted_models+=("${2:?--trusted-model needs a value}"); shift 2 ;;
        --replace-unmanaged) replace_unmanaged=1; shift ;;
        --no-git-pull) no_git_pull=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1 (see --help)" >&2; exit 2 ;;
    esac
done

if { [ -n "$gateway_url" ] && [ -z "$model" ]; } || { [ -z "$gateway_url" ] && [ -n "$model" ]; }; then
    echo "Pass --gateway-url and --model together." >&2
    exit 2
fi

# 0. This checkout. An old copy of the script would install the newest runner but skip whatever
# the old copy did not know about, so bring the clone up to date first.
script_path="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
if [ "$no_git_pull" -eq 1 ] || [ "${CREVIEW_INSTALLER_UPDATED:-0}" = 1 ]; then
    :
elif ! command -v git >/dev/null 2>&1 ||
    ! git -C "$repo_root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "==> $repo_root is not a Git checkout; not updating it"
elif ! git -C "$repo_root" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
    echo "==> $repo_root has no upstream branch; not updating it"
else
    echo "==> Updating this checkout ($repo_root)"
    before="$(git -C "$repo_root" rev-parse HEAD)"
    script_before="$(git -C "$repo_root" hash-object "$script_path")"
    stashed=0
    if [ -n "$(git -C "$repo_root" status --porcelain)" ]; then
        git -C "$repo_root" stash push --include-untracked -m "creview installer" >/dev/null
        stashed=1
        echo "    Set local edits aside with git stash"
    fi
    if ! git -C "$repo_root" pull --ff-only; then
        if [ "$stashed" -eq 1 ]; then
            git -C "$repo_root" stash pop >/dev/null || true
        fi
        echo "Could not fast-forward $repo_root (it has diverged from its upstream)." >&2
        echo "Resolve it with git, or rerun with --no-git-pull." >&2
        exit 1
    fi
    if [ "$stashed" -eq 1 ]; then
        if git -C "$repo_root" stash pop >/dev/null; then
            echo "    Restored local edits"
        else
            echo "Your local edits conflict with the update. They are kept in \`git stash list\`" >&2
            echo "and the conflicting files are marked in $repo_root; resolve them, then rerun." >&2
            exit 1
        fi
    fi
    after="$(git -C "$repo_root" rev-parse HEAD)"
    if [ "$before" = "$after" ]; then
        echo "    Already up to date at ${after:0:12}"
    else
        echo "    Updated ${before:0:12} -> ${after:0:12}"
        if [ "$(git -C "$repo_root" hash-object "$script_path")" != "$script_before" ]; then
            echo "==> The script itself changed; running the updated version"
            CREVIEW_INSTALLER_UPDATED=1 exec "$script_path" ${original_args[@]+"${original_args[@]}"}
        fi
    fi
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is not installed. Install it, open a new terminal, and rerun this script:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 1. The creview runner.
tool_dir="$(uv tool dir)"
if [ -d "$tool_dir/hermes-review" ]; then
    # The package was called hermes-review (command hreview) before it was renamed.
    echo "==> Removing hermes-review, the old name of closed-review"
    uv tool uninstall hermes-review
fi
receipt="$tool_dir/closed-review/uv-receipt.toml"
from_git=0
if [ -f "$receipt" ] && grep -Eq '\bgit[[:space:]]*=' "$receipt"; then
    from_git=1
fi
install_from=""
if [ -n "$source_arg" ]; then
    install_from="$source_arg"
elif [ "$from_git" -eq 0 ]; then
    if [ -f "$receipt" ]; then
        echo "creview was installed from a local folder; switching to $DEFAULT_SOURCE."
    fi
    install_from="$DEFAULT_SOURCE"
fi
case "$install_from" in
    git+*)
        if ! command -v git >/dev/null 2>&1; then
            echo "git is required to install from a Git URL. Install git, or pass --source with"
            echo "the path of a downloaded copy of the repository."
            exit 1
        fi ;;
esac
if [ -n "$install_from" ]; then
    echo "==> Installing creview from $install_from"
    uv tool install --force "$install_from"
else
    echo "==> Updating creview"
    uv tool upgrade closed-review
fi

bin_dir="$(uv tool dir --bin)"
creview="$bin_dir/creview"
if [ ! -x "$creview" ]; then
    echo "creview was not found at $creview after installation" >&2
    exit 1
fi
case ":$PATH:" in
    *":$bin_dir:"*) ;;
    *)
        echo "==> Adding $bin_dir to your shell PATH"
        uv tool update-shell || true
        echo "    Open a new terminal (and restart Hermes Desktop) for the change to apply." ;;
esac
"$creview" --version

profile_args=()
if [ -n "$profile" ]; then
    profile_args=(--profile "$profile")
fi

# 2. The managed skill in the Hermes profile.
set +e
dry_run="$("$creview" hermes install ${profile_args[@]+"${profile_args[@]}"} 2>&1)"
dry_code=$?
set -e
install_args=(hermes install --apply ${profile_args[@]+"${profile_args[@]}"})
skip_skill=0
if [ "$dry_code" -ne 0 ]; then
    case "$dry_run" in
        *"external directory"*)
            echo ""
            echo "The profile loads the skill from a Git checkout (skills.external_dirs), so this"
            echo "script leaves it there. Update that checkout to the same release as creview:"
            echo "  $dry_run"
            skip_skill=1 ;;
        *"unmanaged skill"*)
            if [ "$replace_unmanaged" -eq 0 ]; then
                echo ""
                echo "The journal-article-review skill folder was copied by hand, so creview cannot"
                echo "update it safely. It can be moved to a backup folder (outside skills/, so Hermes"
                echo "will not load it) and replaced with a managed copy that future runs update."
                answer=""
                if [ -r /dev/tty ]; then
                    printf 'Move it to a backup and install the managed copy? [y/N] '
                    read -r answer < /dev/tty || answer=""
                fi
                case "$answer" in
                    y|Y|yes|YES) replace_unmanaged=1 ;;
                    *) echo "Skill left unchanged. Rerun with --replace-unmanaged when ready."; exit 1 ;;
                esac
            fi ;;
        *)
            echo "creview hermes install failed: $dry_run" >&2
            exit 1 ;;
    esac
fi
if [ "$skip_skill" -eq 0 ]; then
    if [ "$replace_unmanaged" -eq 1 ]; then
        install_args+=(--replace-unmanaged)
    fi
    echo "==> Installing the journal-article-review skill"
    "$creview" "${install_args[@]}"
fi

# 3. The trusted gateway: the only endpoint confidential material may reach. There is no default.
if [ -n "$gateway_url" ]; then
    gateway_args=(config gateway --url "$gateway_url" --model "$model")
    for name in ${trusted_models[@]+"${trusted_models[@]}"}; do
        gateway_args+=(--trusted-model "$name")
    done
    echo "==> Storing the trusted model gateway"
    "$creview" "${gateway_args[@]}"
elif "$creview" config show | grep -Eq '"url":[[:space:]]*null'; then
    echo "==> Trusted gateway: none stored; looking for a local model server"
    if ! "$creview" config detect --apply ${profile_args[@]+"${profile_args[@]}"}; then
        echo "No model server was adopted. Start it, or rerun with --gateway-url URL --model MODEL."
    fi
else
    stored="$("$creview" config show | sed -n 's/^  "url": "\(.*\)",$/\1/p')"
    echo "==> Trusted gateway: ${stored:-set by environment} (stored; pass --gateway-url to change it)"
fi

# 4. Doctor. A failure here usually means the profile still needs the trusted model settings.
echo "==> Checking the Hermes profile"
set +e
"$creview" hermes doctor ${profile_args[@]+"${profile_args[@]}"}
doctor_code=$?
set -e
echo ""
if [ "$doctor_code" -eq 0 ]; then
    echo "Done. Restart Hermes (fully quit Hermes Desktop), then start a new chat."
else
    echo "Installed, but the doctor check failed (see above). Fix the reported problems in the"
    echo "Hermes profile, restart Hermes, and let the skill rerun the check. Do not supply"
    echo "confidential material until it passes."
    exit 3
fi
