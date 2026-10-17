from __future__ import annotations

import difflib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import yaml

from . import __version__
from .cases import assert_private_store, now_iso
from .errors import ReviewError
from .io import atomic_write_json, ensure_private_dir, sha256_bytes, sha256_file
from .routes import VERIFIED_CONFIG_VERSIONS, check_routes, default_base_url, read_env_file
from .routes import normalized_endpoint as _normalized_endpoint
from .settings import NOT_CONFIGURED, trusted_gateway

SKILL_NAME = "journal-article-review"
MANIFEST_NAME = "creview-skill-managed.json"
BASELINE_DIR = "creview-skill-baseline"
UPDATES_DIR = "creview-skill-updates"
BACKUPS_DIR = "creview-skill-backups"
PRIVACY_HEADING = "## Privacy gate"
PRIVACY_BEGIN = "<!-- creview:privacy-gate:begin -->"
PRIVACY_END = "<!-- creview:privacy-gate:end -->"
REQUIRED_TOOLSETS = {"terminal", "file"}
MODEL_FALLBACK_KEYS = {
    "fallback",
    "fallback_model",
    "fallback_models",
    "fallback_provider",
    "fallback_providers",
    "model_fallback",
    "model_fallbacks",
    "provider_fallback",
    "provider_fallbacks",
}
TOOLSET_BUNDLES_WITH_REQUIRED_TOOLS = {"coding", "debugging", "hermes-acp", "hermes-cli"}
# Toolsets whose tools send text to outside services (web search and extraction, a browser).
OUTBOUND_TOOLSETS = {"web", "browser"}


def _windows() -> bool:
    return os.name == "nt"


def hermes_home() -> Path:
    override = os.environ.get("HERMES_HOME")
    if override:
        return Path(override).expanduser()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if _windows() and local_app_data:
        # Native Windows Hermes (installer and Desktop) keeps its data here, not in ~/.hermes.
        return Path(local_app_data) / "hermes"
    return Path.home() / ".hermes"


def selected_profile(explicit: str | None) -> str:
    profile = explicit or os.environ.get("HERMES_SESSION_PROFILE")
    override = os.environ.get("HERMES_HOME")
    if not profile and override:
        # `hermes -p NAME` sets HERMES_HOME to <home>/profiles/NAME but no profile variable.
        home = Path(override).expanduser()
        if home.parent.name == "profiles":
            profile = home.name
    profile = (profile or "default").strip()
    if "/" in profile or "\\" in profile or profile in {".", ".."}:
        raise ReviewError("invalid Hermes profile name")
    return profile


def profile_root(profile: str | None) -> Path:
    name = selected_profile(profile)
    root = hermes_home()
    session_profile = os.environ.get("HERMES_SESSION_PROFILE")
    if os.environ.get("HERMES_HOME") and (
        profile is None
        or (session_profile and name == session_profile)
        or (root.name == name and root.parent.name == "profiles")
    ):
        return root
    return root if name == "default" else root / "profiles" / name


def _models_url(value: str) -> str:
    base = value.rstrip("/")
    if not urlsplit(base).path.rstrip("/").endswith("/v1"):
        base += "/v1"
    return f"{base}/models"


def _skill_files() -> dict[str, bytes]:
    root = resources.files("closed_review").joinpath("resources", "skills", SKILL_NAME)
    files: dict[str, bytes] = {}
    pending = [(root, "")]
    while pending:
        directory, prefix = pending.pop()
        for item in directory.iterdir():
            if item.is_file():
                files[prefix + item.name] = item.read_bytes()
            elif item.is_dir() and item.name != "__pycache__":
                pending.append((item, f"{prefix}{item.name}/"))
    return files


def _manifest_for(files: dict[str, bytes], profile: str) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "package_version": __version__,
        "profile": profile,
        "skill": SKILL_NAME,
        "installed_at": now_iso(),
        "files": {name: sha256_bytes(value) for name, value in sorted(files.items())},
    }


def _existing_manifest(destination: Path) -> dict[str, Any] | None:
    path = destination / MANIFEST_NAME
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewError(f"invalid managed-skill manifest: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("files"), dict):
        raise ReviewError("invalid managed-skill manifest")
    return value


# Hermes's self-improvement edits skills in place, so the skill as a whole is mutable guidance.
# Only the marked privacy block must match this release; creview detects a changed block whenever
# it runs, but cannot prevent the change.


def _normalize_block(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip("\n")


def _block_span(text: str) -> tuple[int, int] | None:
    start = text.find(PRIVACY_BEGIN)
    end = text.rfind(PRIVACY_END)
    if start < 0 or end < start:
        return None
    return start, end + len(PRIVACY_END)


def _packaged_block() -> str:
    text = _skill_files()["SKILL.md"].decode("utf-8")
    span = _block_span(text)
    if span is None:
        raise ReviewError("packaged skill has no privacy block")
    return text[span[0] : span[1]]


def privacy_block_status(skill_text: str) -> str:
    span = _block_span(skill_text)
    if span is None:
        return "missing"
    installed = _normalize_block(skill_text[span[0] : span[1]])
    return "match" if installed == _normalize_block(_packaged_block()) else "changed"


def _restore_privacy_block(text: str) -> str:
    """Put this release's privacy block back without touching the rest of SKILL.md."""
    block = _packaged_block()
    span = _block_span(text)
    if span is not None:
        return text[: span[0]] + block + text[span[1] :]
    text = text.replace(PRIVACY_BEGIN, "").replace(PRIVACY_END, "")
    lines = text.splitlines(keepends=True)
    heading = next((i for i, line in enumerate(lines) if line.strip() == PRIVACY_HEADING), None)
    section = f"{PRIVACY_HEADING}\n\n{block}\n\n"
    if heading is not None:
        # A pre-marker release or an edit removed the markers: replace that whole section.
        following = next(
            (i for i in range(heading + 1, len(lines)) if lines[i].startswith("## ")), len(lines)
        )
        return "".join(lines[:heading]) + section + "".join(lines[following:])
    first_section = next((i for i, line in enumerate(lines) if line.startswith("## ")), None)
    if first_section is None:
        return text.rstrip("\n") + "\n\n" + section.rstrip("\n") + "\n"
    return "".join(lines[:first_section]) + section + "".join(lines[first_section:])


def _external_skill_dirs(config: dict[str, Any], root: Path) -> list[Path]:
    skills = config.get("skills") or {}
    if not isinstance(skills, dict):
        return []
    values = skills.get("external_dirs") or []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    result: list[Path] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        expanded = Path(os.path.expandvars(value)).expanduser()
        result.append((expanded if expanded.is_absolute() else root / expanded).resolve())
    return result


def _configured_skill(config: dict[str, Any], root: Path) -> tuple[Path | None, str | None]:
    local = root / "skills" / SKILL_NAME
    if local.is_dir():
        return local, "profile_local"
    for external_root in _external_skill_dirs(config, root):
        candidate = external_root / SKILL_NAME
        if candidate.is_dir():
            return candidate, "external_dir"
    return None, None


def _relative_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != MANIFEST_NAME and "__pycache__" not in path.parts
    }


def skill_changes(destination: Path) -> list[dict[str, str]]:
    """Informational drift from this release's skill; Hermes edits are expected here."""
    desired = _skill_files()
    changes: list[dict[str, str]] = []
    for relative, content in sorted(desired.items()):
        path = destination / relative
        if not path.is_file():
            changes.append({"file": relative, "change": "missing"})
        elif sha256_file(path) != sha256_bytes(content):
            changes.append({"file": relative, "change": "modified"})
    for relative in sorted(_relative_files(destination) - set(desired)):
        changes.append({"file": relative, "change": "added"})
    return changes


def _merge_text(current: bytes, base: bytes, new: bytes) -> bytes | None:
    """Three-way merge with `git merge-file`; None on conflict or when git is unavailable."""
    with tempfile.TemporaryDirectory() as temporary:
        paths = []
        for name, value in (("current", current), ("base", base), ("new", new)):
            path = Path(temporary) / name
            path.write_bytes(value)
            paths.append(str(path))
        try:
            result = subprocess.run(
                ["git", "merge-file", "-p", *paths], capture_output=True, check=False
            )
        except OSError:
            return None
    return result.stdout if result.returncode == 0 else None


def _baseline_content(baseline: Path, relative: str, digest: str | None) -> bytes | None:
    path = baseline / relative
    if digest is None or not path.is_file():
        return None
    content = path.read_bytes()
    return content if sha256_bytes(content) == digest else None


def _plan_update(
    destination: Path, files: dict[str, bytes], manifest: dict[str, Any], baseline: Path
) -> dict[str, Any]:
    """Carry Hermes's edits forward: replace unedited files, merge edited ones, keep conflicts."""
    base_hashes: dict[str, str] = manifest["files"]
    writes: dict[str, bytes] = {}
    upstream: dict[str, bytes] = {}
    plan: dict[str, list[str]] = {"updated": [], "merged": [], "kept_local": [], "removed": []}
    for relative in sorted(set(files) | set(base_hashes)):
        new = files.get(relative)
        path = destination / relative
        current = path.read_bytes() if path.is_file() else None
        base_hash = base_hashes.get(relative)
        unedited = current is not None and sha256_bytes(current) == base_hash
        if new is None:
            if current is not None:
                plan["removed" if unedited else "kept_local"].append(relative)
        elif current is None:
            # Respect a file Hermes deleted unless this release changed it.
            if base_hash != sha256_bytes(new):
                writes[relative] = new
                plan["updated"].append(relative)
        elif current == new or sha256_bytes(new) == base_hash:
            # Identical, or this release did not change the file: keep Hermes's version.
            continue
        elif unedited:
            writes[relative] = new
            plan["updated"].append(relative)
        else:
            base = _baseline_content(baseline, relative, base_hash)
            merged = _merge_text(current, base, new) if base is not None else None
            if merged is None:
                upstream[relative] = new
                plan["kept_local"].append(relative)
            else:
                writes[relative] = merged
                plan["merged"].append(relative)
    return {"writes": writes, "upstream": upstream, **plan}


def install_skill(
    profile: str | None, *, apply: bool = False, replace_unmanaged: bool = False
) -> dict[str, Any]:
    name = selected_profile(profile)
    root = profile_root(profile)
    if not root.is_dir():
        raise ReviewError(f"Hermes profile does not exist: {root}")
    destination = root / "skills" / SKILL_NAME
    if not destination.exists():
        config, _problems = _load_config(root / "config.yaml")
        loaded, source = _configured_skill(config, root)
        if source == "external_dir":
            # A managed copy as well would give Hermes two copies of the skill.
            raise ReviewError(
                f"the profile already loads {SKILL_NAME} from an external directory: {loaded}. "
                "Update that checkout instead (for example `git pull --ff-only`), or remove it "
                "from skills.external_dirs to use a managed copy"
            )
    baseline = root / BASELINE_DIR / SKILL_NAME
    files = _skill_files()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup: Path | None = None
    manifest = _existing_manifest(destination) if destination.exists() else None
    if destination.exists() and manifest is None:
        if not replace_unmanaged:
            raise ReviewError(
                f"refusing to overwrite unmanaged skill: {destination}; "
                "rerun with --replace-unmanaged to move it to a backup first"
            )
        # Outside skills/ so Hermes does not discover the backup as a second skill.
        backup = root / BACKUPS_DIR / f"{SKILL_NAME}-{stamp}"
    if manifest is None:
        update = {
            "writes": dict(files),
            "upstream": {},
            "updated": sorted(files),
            "merged": [],
            "kept_local": [],
            "removed": [],
        }
    else:
        update = _plan_update(destination, files, manifest, baseline)

    skill_path = destination / "SKILL.md"
    skill = update["writes"].get("SKILL.md")
    if skill is None:
        skill = skill_path.read_bytes() if skill_path.is_file() else files["SKILL.md"]
    restored = _restore_privacy_block(skill.decode("utf-8")).encode("utf-8")
    privacy_block_restored = restored != skill
    if privacy_block_restored or not skill_path.is_file():
        update["writes"]["SKILL.md"] = restored

    upstream_copies = root / UPDATES_DIR / stamp if update["upstream"] else None
    plan = {
        "applied": apply,
        "profile": name,
        "destination": str(destination),
        "files": sorted(files),
        "updated": update["updated"],
        "merged": update["merged"],
        "kept_local": update["kept_local"],
        "removed": update["removed"],
        "upstream_copies": str(upstream_copies) if upstream_copies else None,
        "privacy_block_restored": privacy_block_restored and manifest is not None,
        "backup": str(backup) if backup else None,
        "profile_configuration_changed": False,
    }
    if not apply:
        return plan
    if backup is not None:
        ensure_private_dir(backup.parent)
        destination.rename(backup)
    for relative in update["removed"]:
        (destination / relative).unlink()
    ensure_private_dir(destination)
    for relative, content in update["writes"].items():
        _write_private(destination / relative, content)
    # Conflicting upstream versions go outside skills/ so Hermes does not load them.
    for relative, content in update["upstream"].items():
        _write_private(upstream_copies / relative, content)
    if baseline.exists():
        shutil.rmtree(baseline)
    for relative, content in files.items():
        _write_private(baseline / relative, content)
    atomic_write_json(destination / MANIFEST_NAME, _manifest_for(files, name))
    return plan


def _write_private(path: Path, content: bytes) -> None:
    ensure_private_dir(path.parent)
    path.write_bytes(content)
    path.chmod(0o600)


def _resolved_skill(profile: str | None) -> Path:
    root = profile_root(profile)
    config, _problems = _load_config(root / "config.yaml")
    destination, _source = _configured_skill(config, root)
    if destination is None:
        raise ReviewError(f"{SKILL_NAME} is not available from the profile or skills.external_dirs")
    if not (destination / "SKILL.md").is_file():
        raise ReviewError(f"skill has no SKILL.md: {destination}")
    return destination


def skill_diff(profile: str | None) -> dict[str, Any]:
    destination = _resolved_skill(profile)
    text = (destination / "SKILL.md").read_text(encoding="utf-8")
    span = _block_span(text)
    installed = _normalize_block(text[span[0] : span[1]]) if span else ""
    diff = difflib.unified_diff(
        _normalize_block(_packaged_block()).splitlines(),
        installed.splitlines(),
        fromfile=f"creview {__version__} privacy block",
        tofile=f"{destination / 'SKILL.md'} privacy block",
        lineterm="",
    )
    return {
        "skill_path": str(destination),
        "privacy_block": privacy_block_status(text),
        "privacy_block_diff": "\n".join(diff),
        "skill_changes": skill_changes(destination),
    }


def restore_privacy_block(profile: str | None, *, apply: bool = False) -> dict[str, Any]:
    destination = _resolved_skill(profile)
    path = destination / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    status = privacy_block_status(text)
    if apply and status != "match":
        restored = _restore_privacy_block(text)
        mode = path.stat().st_mode & 0o777
        path.write_bytes(restored.encode("utf-8"))
        path.chmod(mode)
    return {
        "applied": apply,
        "skill_path": str(path),
        "privacy_block": status,
        "changed": status != "match",
        "other_edits_preserved": True,
    }


def _truthy_fallbacks(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in MODEL_FALLBACK_KEYS and child not in (None, False, "", [], {}):
                found.append(key_path)
            found.extend(_truthy_fallbacks(child, key_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_truthy_fallbacks(child, f"{prefix}[{index}]"))
    return found


def _configured_toolsets(config: dict[str, Any]) -> set[str]:
    """Resolve enough of old and current Hermes schemas to verify file and terminal access."""
    legacy_tools = config.get("tools") or {}
    legacy = legacy_tools.get("enabled_toolsets") if isinstance(legacy_tools, dict) else None
    if isinstance(legacy, list):
        enabled = {str(value) for value in legacy}
    else:
        enabled: set[str] = set()
        platforms = config.get("platform_toolsets") or {}
        if isinstance(platforms, dict):
            cli_toolsets = platforms.get("cli")
            if isinstance(cli_toolsets, list):
                enabled.update(str(value) for value in cli_toolsets)
        top_level = config.get("toolsets")
        if isinstance(top_level, list):
            enabled.update(str(value) for value in top_level)
        if not enabled:
            enabled.add("hermes-cli")

    if enabled & TOOLSET_BUNDLES_WITH_REQUIRED_TOOLS:
        enabled.update(REQUIRED_TOOLSETS)
    agent = config.get("agent") or {}
    disabled = agent.get("disabled_toolsets") if isinstance(agent, dict) else None
    if isinstance(disabled, list):
        enabled.difference_update(str(value) for value in disabled)
    return enabled


def _selected_model_and_provider(
    config: dict[str, Any],
) -> tuple[str | None, str | None, str | None]:
    model_value = config.get("model")
    provider_name: str | None = None
    model_name: str | None = None
    direct_base: str | None = None
    if isinstance(model_value, str):
        model_name = model_value
    elif isinstance(model_value, dict):
        model_name = model_value.get("default") or model_value.get("model")
        provider_name = model_value.get("provider")
        direct_base = model_value.get("base_url")
    provider_name = provider_name or config.get("provider")
    providers = config.get("providers") or {}
    provider_entry = providers.get(provider_name or "", {}) if isinstance(providers, dict) else {}
    if isinstance(provider_entry, dict):
        direct_base = direct_base or provider_entry.get("base_url")
    custom = config.get("custom_providers") or []
    for entry in custom:
        if not isinstance(entry, dict):
            continue
        listed_models = entry.get("models") or []
        if not isinstance(listed_models, list):
            listed_models = []
        models = {value for value in [entry.get("model"), *listed_models] if isinstance(value, str)}
        if entry.get("name") == provider_name or (model_name and model_name in models):
            direct_base = direct_base or entry.get("base_url")
            if not model_name and isinstance(entry.get("model"), str):
                model_name = entry["model"]
            break
    return (
        str(model_name) if model_name else None,
        str(provider_name) if provider_name else None,
        str(direct_base).rstrip("/") if direct_base else None,
    )


def _load_config(config_path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {}, [f"profile config not found: {config_path}"]
    except (OSError, yaml.YAMLError) as exc:
        return {}, [f"cannot read profile config: {exc}"]
    if not isinstance(config, dict):
        return {}, ["profile config must be a mapping"]
    return config, []


def agent_max_turns(profile: str | None = None) -> int | None:
    """The tool-call budget Hermes gives one turn, when the profile sets it."""
    config, _ = _load_config(profile_root(profile) / "config.yaml")
    agent = config.get("agent")
    raw = agent.get("max_turns") if isinstance(agent, dict) else None
    if raw is None:
        raw = config.get("max_turns")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _transcript_problem(root: Path) -> str | None:
    """creview checks reviewer confirmations against the session's messages in `state.db`."""
    path = root / "state.db"
    if not path.is_file():
        return None  # Hermes creates it with the first session
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            db.execute("SELECT session_id, role, content, timestamp FROM messages LIMIT 0")
    except sqlite3.Error as exc:
        return (
            f"cannot read session messages from {path} ({exc}); creview checks the reviewer's "
            "confirmations against them, so this Hermes version is not supported"
        )
    return None


def inspect_profile(
    profile: str | None, *, live: bool = True, timeout: float = 3.0
) -> dict[str, Any]:
    name = selected_profile(profile)
    root = profile_root(profile)
    config, problems = _load_config(root / "config.yaml")

    model, provider, base_url = _selected_model_and_provider(config)
    settings = trusted_gateway()
    wanted_url, wanted_model = settings["url"], settings["model"]
    allowed_models = settings["trusted_models"]
    route_report: dict[str, Any] = {"routes": [], "problems": [], "warnings": [], "credentials": []}
    endpoint_matches = False
    if wanted_url and wanted_model:
        base_url = base_url or default_base_url(provider, read_env_file(root / ".env"))
        endpoint_matches = _normalized_endpoint(base_url) == _normalized_endpoint(wanted_url)
        if base_url is None:
            problems.append(
                f"model.base_url is not set; set it to the trusted gateway {wanted_url}"
            )
        elif not endpoint_matches:
            problems.append(f"selected model endpoint is {base_url!r}; expected {wanted_url!r}")
        if model not in allowed_models:
            problems.append(f"selected model is {model!r}; expected one of {allowed_models!r}")
        route_report = check_routes(config, root, wanted_url, allowed_models)
        problems.extend(route_report["problems"])
    else:
        problems.append(NOT_CONFIGURED)
    warnings = list(route_report["warnings"])
    schema = config.get("_config_version")
    low, high = VERIFIED_CONFIG_VERSIONS
    if config and not (isinstance(schema, int) and low <= schema <= high):
        warnings.append(
            f"Hermes config schema {schema!r} is outside the versions this route check was "
            f"verified against ({low}-{high}); routes added or changed since may not be checked"
        )
    if (provider or "").strip().lower() in {"", "auto", "moa"}:
        # Hermes's auxiliary discovery chain (OpenRouter, Nous, ...) runs only for these.
        problems.append(
            f"model.provider is {provider or 'unset'!r}; Hermes may then send side tasks such as "
            "context compression to OpenRouter or Nous. Name the trusted provider instead"
        )
    checked_fallbacks = {"fallback_providers", "fallback_model", "delegation.fallback_providers"}
    fallback_keys = [key for key in _truthy_fallbacks(config) if key not in checked_fallbacks]
    if fallback_keys:
        problems.append("profile has unrecognized fallback routing: " + ", ".join(fallback_keys))
    enabled = _configured_toolsets(config)
    missing_tools = sorted(REQUIRED_TOOLSETS - enabled)
    if missing_tools:
        problems.append("profile is missing toolsets: " + ", ".join(missing_tools))
    outbound = sorted(enabled & OUTBOUND_TOOLSETS)
    if outbound:
        warnings.append(
            f"toolsets {', '.join(outbound)} can send text to outside services, and only the "
            "privacy rules keep the agent from using them on a manuscript; list them under "
            "agent.disabled_toolsets in the review profile to make that a setting"
        )
    mcp_servers = config.get("mcp_servers")
    if isinstance(mcp_servers, dict) and mcp_servers:
        warnings.append(
            f"MCP servers {', '.join(sorted(map(str, mcp_servers)))} are configured; any that "
            "reach outside services can receive manuscript text, which creview cannot check"
        )

    destination, skill_source = _configured_skill(config, root)
    privacy_block: str | None = None
    changes: list[dict[str, str]] = []
    if destination is None:
        problems.append(f"{SKILL_NAME} is not available from the profile or skills.external_dirs")
    elif not (destination / "SKILL.md").is_file():
        problems.append(f"skill has no SKILL.md: {destination}")
    else:
        privacy_block = privacy_block_status((destination / "SKILL.md").read_text(encoding="utf-8"))
        changes = skill_changes(destination)
        if privacy_block == "missing":
            problems.append(
                f"skill privacy block is missing from {destination / 'SKILL.md'}; update with "
                "`creview hermes install --apply` or restore only the block with "
                "`creview hermes skill-restore --apply`"
            )
        elif privacy_block == "changed":
            problems.append(
                f"skill privacy block differs from creview {__version__}; review it with "
                "`creview hermes skill-diff`, then run `creview hermes skill-restore --apply`"
            )
    problems.extend(assert_private_store())
    transcript_problem = _transcript_problem(root)
    if transcript_problem:
        problems.append(transcript_problem)

    gateway: dict[str, Any] = {"checked": False}
    if live and endpoint_matches and model in allowed_models:
        try:
            started = now_iso()
            api_key = os.environ.get("CREVIEW_MODEL_API_KEY")
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            response = httpx.get(_models_url(wanted_url), headers=headers, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            ids = [item.get("id") for item in payload.get("data", []) if isinstance(item, dict)]
            gateway = {"checked": True, "at": started, "models": ids}
            routed = {
                route["model"]
                for route in route_report["routes"]
                if route["ok"] and route["model"] and route["target"] in {"trusted", "main"}
            }
            for model_name in sorted({model, *routed}):
                if model_name not in ids:
                    problems.append(f"trusted gateway does not advertise {model_name}")
        except Exception as exc:
            gateway = {"checked": True, "error": str(exc)}
            problems.append(f"trusted gateway health check failed: {exc}")

    return {
        "ready": not problems,
        "profile": name,
        "profile_root": str(root),
        "model": model,
        "provider": provider,
        "base_url": base_url,
        "trusted_url": wanted_url,
        "expected_model": wanted_model,
        "trusted_models": allowed_models,
        "routes": route_report["routes"],
        "cloud_credentials": route_report["credentials"],
        "warnings": warnings,
        "gateway_settings": settings["settings_path"],
        "gateway": gateway,
        "skill_installed": destination is not None,
        "skill_privacy_block": privacy_block,
        "skill_changes": changes,
        "skill_path": str(destination) if destination else None,
        "skill_source": skill_source,
        "privacy_boundary": "instructional_shell_guardrail",
        "problems": problems,
    }


def require_ready_profile(profile: str | None, *, live: bool = True) -> dict[str, Any]:
    report = inspect_profile(profile, live=live)
    if not report["ready"]:
        raise ReviewError("Hermes profile is not ready: " + "; ".join(report["problems"]))
    return report
