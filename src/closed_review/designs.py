"""Design profiles, read from the installed package rather than the mutable Hermes skill copy.

A deep scan records the profiles the reviewer confirmed. creview then hands each pass, and the
screening step, those profiles' monitoring areas, common false alarms, and major flaws itself, so
checking a candidate against them does not depend on the agent having read the profile files.
"""

from __future__ import annotations

import re
from importlib import resources
from typing import Any

from .errors import ReviewError

MAX_PROFILES = 3


def _references():
    return resources.files("closed_review").joinpath(
        "resources", "skills", "journal-article-review", "references"
    )


def _designs():
    return _references().joinpath("designs")


def profile_names() -> list[str]:
    return sorted(
        item.name.removesuffix(".md")
        for item in _designs().iterdir()
        if item.name.endswith(".md") and item.name != "index.md"
    )


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return match.group(1).strip() if match else ""


def _bullets(section: str) -> list[str]:
    items: list[str] = []
    for line in section.splitlines():
        if line.startswith("- "):
            items.append(line[2:].strip())
        elif line.startswith("  ") and items:
            items[-1] += " " + line.strip()
    return items


def _areas(section: str) -> list[str]:
    areas: list[str] = []
    for sentence in " ".join(section.split()).split("."):
        # "With the authors' own data, also: aim; integration" lists areas after the colon.
        for area in sentence.rsplit(":", 1)[-1].split(";"):
            if area.strip():
                areas.append(area.strip())
    return areas


def _major_flaws(section: str) -> list[dict[str, str]]:
    """`- **slug**: description` bullets."""
    flaws = []
    for item in _bullets(section):
        match = re.match(r"\*\*([a-z0-9-]+)\*\*:\s*(.+)", item)
        if match:
            flaws.append({"id": match.group(1), "flaw": match.group(2)})
    return flaws


def general_major_flaws() -> list[dict[str, str]]:
    """Major flaws in any design, from the general rubric."""
    text = _references().joinpath("review-rubric.md").read_text(encoding="utf-8")
    return _major_flaws(_section(text, "Major flaws in any design"))


def load_profiles(names: list[str]) -> list[dict[str, Any]]:
    known = profile_names()
    unknown = [name for name in names if name not in known]
    if unknown:
        raise ReviewError(
            f"unknown design profile {', '.join(unknown)}; choose from {', '.join(known)}"
        )
    if len(names) > MAX_PROFILES:
        raise ReviewError(f"confirm at most {MAX_PROFILES} design profiles")
    profiles = []
    for name in dict.fromkeys(names):
        text = _designs().joinpath(f"{name}.md").read_text(encoding="utf-8")
        profiles.append(
            {
                "id": name,
                "monitoring_areas": _areas(_section(text, "Monitoring areas")),
                "false_alarms": _bullets(_section(text, "Common false alarms")),
                "major_flaws": _major_flaws(_section(text, "Major flaws")),
            }
        )
    return profiles
