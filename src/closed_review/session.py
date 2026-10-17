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
from .cases import now_iso
from .designs import load_profiles
from .errors import ReviewError
from .hermes import inspect_profile
from .io import atomic_write_json, data_home, ensure_private_dir, read_json, sha256_bytes
from .transcript import reviewer_words

SESSION_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def privacy_rules() -> str:
    return resources.files("closed_review").joinpath("resources", "privacy-rules.md").read_text(
        encoding="utf-8"
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


def start_session(profile: str | None, *, live: bool = True) -> dict[str, Any]:
    key, source = session_key()
    if key is None:
        key, source = secrets.token_hex(16), "explicit"
    report = inspect_profile(profile, live=live)
    record = {
        "session_id": key,
        "session_source": source,
        "checked_at": now_iso(),
        "profile": report["profile"],
        "ready": report["ready"],
        "problems": report["problems"],
        "skill_privacy_block": report["skill_privacy_block"],
        "creview_version": __version__,
    }
    preflights = ensure_private_dir(ensure_private_dir(data_home()) / "preflights")
    atomic_write_json(preflights / f"{key}.json", record)
    if not report["ready"]:
        raise ReviewError("privacy preflight failed: " + "; ".join(report["problems"]))
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


def record_profiles(key: str, profiles: list[str], confirmed_by: dict[str, Any]) -> None:
    """Store the design profiles the reviewer confirmed with the session's preflight."""
    path = _preflight_path(key)
    record = read_json(path)
    record.update(profiles=profiles, profile_confirmation=confirmed_by, profiles_at=now_iso())
    atomic_write_json(path, record)


def confirm_profiles(
    profiles: list[str], confirmation: str, session: str | None = None
) -> dict[str, Any]:
    """Check that the reviewer, not the agent, confirmed the design profiles, and record them.

    The words must come from a message the reviewer sent after `creview session start`, so the
    opening request ("I confirm that") or an unanswered question cannot stand in for them."""
    key, source = session_key(session)
    summary = preflight_summary(key, source)
    if summary["status"] != "passed":
        raise ReviewError("run `creview session start` in this session before confirming profiles")
    confirmed = load_profiles(profiles)
    confirmed_by = reviewer_words(
        confirmation,
        hermes_session=summary["session_source"] == "hermes_session",
        what="the design-profile confirmation",
        since=summary["checked_at"],
        min_chars=8,
    )
    names = [p["id"] for p in confirmed]
    record_profiles(key, names, confirmed_by)
    return {
        "profiles": names,
        "monitoring_areas": [a for p in confirmed for a in p["monitoring_areas"]],
    }


def profiles_confirmed(key: str | None) -> bool:
    if key is None or not _preflight_path(key).is_file():
        return False
    return "profile_confirmation" in read_json(_preflight_path(key))
