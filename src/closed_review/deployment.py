"""Managed review profiles. Configuration is a guardrail, not a network sandbox."""

from __future__ import annotations

import os
import re
import shlex
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from . import __version__
from .errors import ReviewError
from .io import atomic_write_json, atomic_write_text, ensure_private_dir, read_json, sha256_file
from .settings import _validate_url
from .support.budgets import TOOL_OUTPUT

PROFILE_MANIFEST = "creview-profile.json"
REVIEW_TOOLS = ["terminal", "file", "skills", "clarify"]


def _install_runner_launcher(root: Path) -> None:
    if os.name == "nt":
        return  # Native Windows runner selection is checked by the smoke test.
    launchers = ensure_private_dir(root / "review-bin")
    launcher = launchers / "creview"
    atomic_write_text(
        launcher, "#!/bin/sh\n" + f'exec {shlex.quote(sys.executable)} -m closed_review.cli "$@"\n'
    )
    launcher.chmod(0o700)
    atomic_write_text(
        root / "review-shell.sh",
        f"export CREVIEW_HOME={shlex.quote(str(root / 'review-data'))}\n"
        f'export PATH={shlex.quote(str(launchers))}:"$PATH"\n',
    )


@contextmanager
def profile_store(root: Path):
    """Select a managed profile's store for commands run outside Hermes, too."""
    previous = {key: os.environ.get(key) for key in ("CREVIEW_HOME", "HERMES_HOME")}
    if (root / PROFILE_MANIFEST).is_file():
        os.environ["CREVIEW_HOME"] = str(root / "review-data")
        os.environ["HERMES_HOME"] = str(root)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def profile_config(root: Path, url: str, model: str, context_length: int | None) -> dict:
    route = {"provider": "custom", "base_url": url, "model": model}
    config: dict[str, Any] = {
        "_config_version": 49,
        "model": {"provider": "custom", "base_url": url, "default": model},
        "platform_toolsets": {"cli": REVIEW_TOOLS, "tui": REVIEW_TOOLS},
        "agent": {
            "max_turns": 150,
            "disabled_toolsets": [
                "web",
                "browser",
                "memory",
                "delegation",
                "cronjob",
                "kanban",
                "vision",
                "connections",
                "session_search",
                "code_execution",
                "computer_use",
            ],
        },
        "auxiliary": {
            "compression": route.copy(),
            "title_generation": route.copy(),
            "vision": route.copy(),
            "background_review": {**route, "enabled": False},
        },
        "memory": {"memory_enabled": False, "user_profile_enabled": False, "nudge_interval": 0},
        "skills": {"creation_nudge_interval": 0, "external_dirs": []},
        "plugins": {"enabled": [], "disabled": []},
        "mcp_servers": {},
        "compression": {"enabled": True, "threshold": 0.5},
        "max_concurrent_sessions": 1,
        "display": {"inline_diffs": False, "tool_progress": "off"},
        "tool_output": dict(TOOL_OUTPUT),
        "terminal": {"backend": "local", "cwd": str(root / "work"), "timeout": 180},
        "auth": {"adopt_external_logins": False},
        "stt": {"enabled": False},
        "updates": {"check": False},
        "telemetry": {"shared_metrics": {"enabled": False, "send": False}},
    }
    if context_length is not None:
        config["model"]["context_length"] = context_length
    if os.name != "nt":
        config["terminal"]["shell_init_files"] = [str(root / "review-shell.sh")]
        config["terminal"]["auto_source_bashrc"] = False
    return config


def setup_profile(
    profile: str = "closed-review",
    *,
    gateway_url: str,
    model: str,
    context_length: int | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    from .detect import TRUSTED_CLASSES, _resolved_class
    from .hermes import install_skill, profile_root

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", profile) or profile == "default":
        raise ReviewError("choose a named review profile (letters, numbers, hyphens, underscores)")
    root = profile_root(profile).resolve()
    url = _validate_url(gateway_url)
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ReviewError("gateway URL must not contain credentials, a query, or a fragment")
    if _resolved_class(url) not in TRUSTED_CLASSES:
        raise ReviewError("a review profile requires a loopback or private-network model endpoint")
    if not model.strip() or any(c in model for c in "\r\n"):
        raise ReviewError("model must be a nonempty single-line model id")
    if context_length is not None and context_length < 65536:
        raise ReviewError("full-scan profiles require at least 65536 configured context tokens")
    config = profile_config(root, url, model.strip(), context_length)
    manifest_path = root / PROFILE_MANIFEST
    if root.exists() and any(root.iterdir()):
        if not manifest_path.is_file():
            raise ReviewError(f"refusing to overwrite unmanaged profile: {root}; choose a new name")
        manifest = read_json(manifest_path)
        if manifest.get("schema_version") != 1:
            raise ReviewError("unsupported managed profile manifest; no files changed")
        previous = manifest.get("settings", {})
        requested = {"url": url, "model": model.strip(), "context_length": context_length}
        if previous != requested:
            raise ReviewError(
                "model settings differ; create a new profile to qualify that configuration"
            )
        # Hermes migrates config.yaml. Do not overwrite migrations or a reviewer's edits.
        if apply:
            for relative, digest in manifest.get("runner_files", {}).items():
                if relative not in {"review-shell.sh", "review-bin/creview"}:
                    raise ReviewError("invalid managed runner path")
                path = root / relative
                if not path.is_file() or sha256_file(path) != digest:
                    raise ReviewError("managed runner launcher was edited; choose a new profile")
            _install_runner_launcher(root)
            install_skill(profile, apply=True)
            manifest["package_version"] = __version__
            manifest["runner_files"] = _runner_files(root)
            atomic_write_json(manifest_path, manifest)
        return {
            "applied": apply,
            "profile": profile,
            "profile_root": str(root),
            "existing_config_preserved": True,
            "skill_updated": apply,
        }
    result = {
        "applied": apply,
        "profile": profile,
        "profile_root": str(root),
        "config": config,
        "review_store": str(root / "review-data"),
        "privacy_boundary": "profile_guardrails_only",
        "model_quality": "not_qualified",
        "next": [
            f"creview hermes doctor --profile {profile}",
            "creview support modules",
            f"hermes -p {profile}",
        ],
    }
    if not apply:
        return result
    ensure_private_dir(root)
    ensure_private_dir(root / "work")
    atomic_write_text(root / "config.yaml", yaml.safe_dump(config, sort_keys=False))
    atomic_write_text(
        root / ".env",
        f"CREVIEW_HOME={str(root / 'review-data')!r}\n"
        f"OPENAI_BASE_URL={url!r}\nNO_PROXY={parsed.hostname!r}\n",
    )
    _install_runner_launcher(root)
    atomic_write_json(
        root / "review-data" / "gateway.json",
        {"url": url, "model": model.strip(), "trusted_models": []},
    )
    install_skill(profile, apply=True)
    # Write last: an interrupted installation must not be mistaken for a managed profile.
    atomic_write_json(
        manifest_path,
        {
            "schema_version": 1,
            "package_version": __version__,
            "settings": {"url": url, "model": model.strip(), "context_length": context_length},
            "runner_files": _runner_files(root),
        },
    )
    return result


def _runner_files(root: Path) -> dict[str, str]:
    return {
        name: sha256_file(root / name)
        for name in ("review-shell.sh", "review-bin/creview")
        if (root / name).is_file()
    }
