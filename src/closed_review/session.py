"""Session preflight: the privacy check a Hermes session runs before reading a manuscript.

The rules come from this package, not from the skill, so Hermes's skill self-improvement cannot
change them. A preflight record lets an export receipt state whether the session ran the check.
"""

from __future__ import annotations

import os
import re
import secrets
from importlib import resources
from pathlib import Path
from typing import Any

from . import __version__
from .errors import ReviewError
from .hermes import inspect_profile
from .io import atomic_write_json, data_home, ensure_private_dir, now_iso, read_json, sha256_bytes

SESSION_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def privacy_rules() -> str:
    return (
        resources.files("closed_review")
        .joinpath("resources", "privacy-rules.md")
        .read_text(encoding="utf-8")
    )


def session_key(explicit: str | None = None) -> tuple[str | None, str | None]:
    """Resolve `--session`, else the HERMES_SESSION_ID that Hermes sets for terminal commands."""
    if explicit:
        if not SESSION_ID_RE.fullmatch(explicit):
            raise ReviewError("invalid session id")
        return explicit, "explicit"
    hermes_session = os.environ.get("HERMES_SESSION_ID")
    if hermes_session:
        # Stored hashed: the receipt needs only to link the export to its preflight.
        return sha256_bytes(hermes_session.encode("utf-8"))[:32], "hermes_session"
    return None, None


def start_session(
    profile: str | None, *, live: bool = True, support: bool = False
) -> dict[str, Any]:
    from .deployment import profile_store
    from .hermes import profile_root

    with profile_store(profile_root(profile)):
        return _start_session(profile, live=live, support=support)


def _start_session(
    profile: str | None, *, live: bool = True, support: bool = False
) -> dict[str, Any]:
    key, source = session_key()
    if key is None:
        key, source = secrets.token_hex(16), "explicit"
    report = inspect_profile(profile, live=live)
    problems = list(report["problems"])
    if support:
        problems += report["support_readiness"]["problems"]
    record = {
        "session_id": key,
        "session_source": source,
        "checked_at": now_iso(),
        "profile": report["profile"],
        "ready": report["ready"] and not problems,
        "problems": list(dict.fromkeys(problems)),
        "support_required": support,
        "skill_privacy_block": report["skill_privacy_block"],
        "creview_version": __version__,
    }
    preflights = ensure_private_dir(ensure_private_dir(data_home()) / "preflights")
    atomic_write_json(preflights / f"{key}.json", record)
    if not record["ready"]:
        raise ReviewError("privacy preflight failed: " + "; ".join(record["problems"]))
    export_command = "creview direct prepare-export"
    if source == "explicit":
        export_command += f" --session {key}"
    return {
        "session_id": key,
        "session_source": source,
        "checked_at": record["checked_at"],
        "profile": report["profile"],
        "model": report["model"],
        "skill_privacy_block": report["skill_privacy_block"],
        "skill_changes": report["skill_changes"],
        "warnings": report["warnings"],
        "support_readiness": report["support_readiness"],
        "rules": privacy_rules(),
        "export_command": export_command,
    }


def preflight_summary(key: str | None, source: str | None) -> dict[str, Any]:
    if key is None:
        return {"status": "none", "session_source": None, "checked_at": None}
    path = data_home() / "preflights" / f"{key}.json"
    if not path.is_file():
        return {"status": "none", "session_source": source, "checked_at": None}
    record = read_json(path)
    return {
        "status": "passed" if record.get("ready") else "failed",
        "session_source": record.get("session_source", source),
        "checked_at": record.get("checked_at"),
    }


def _preflight_path(key: str) -> Path:
    return data_home() / "preflights" / f"{key}.json"


def record_profiles(key: str, profiles: list[str], words: str = "") -> None:
    """Store the design profiles chosen for the session with its preflight, and the reviewer's
    words about them if the agent gave any (not checked)."""
    path = _preflight_path(key)
    record = read_json(path)
    record.update(profiles=profiles, profile_words=words.strip() or None, profiles_at=now_iso())
    atomic_write_json(path, record)
