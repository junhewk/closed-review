"""Check that words attributed to the reviewer are words the reviewer wrote in this session.

A disposition or a lookup approval must quote the reviewer: one of their messages, or an answer
they gave to a clarify question (Hermes records it as the tool's result, with the status
"answered"). Inside Hermes, creview reads the session from the profile's `state.db` (read-only)
and refuses a statement that is not a verbatim part of one. This stops an agent from recording
consent the reviewer never gave, for example after a clarify question went unanswered.
Outside Hermes (an explicit `--session`), there is no transcript to check, and the record says so.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime
from typing import Any

from .errors import ReviewError
from .hermes import profile_root

MIN_WORDS_CHARS = 2

# Hermes stores a slash-invoked skill as one user message: an activation note, the whole skill
# text, then what the reviewer typed after the command (agent/skill_commands.py builds these and
# `extract_user_instruction_from_skill_message` reads them back). Only the typed part is the
# reviewer's: the skill's sentences must not pass as their consent.
_INVOKED = "[IMPORTANT: The user has invoked the "
_SINGLE_SKILL = "The full skill content is loaded below.]"
_SINGLE_INSTRUCTION = (
    "The user has provided the following instruction alongside the skill invocation: "
)
_RUNTIME_NOTE = "\n\n[Runtime note:"
_BUNDLE = " skill bundle,"
_BUNDLE_INSTRUCTION = "\nUser instruction: "
_BUNDLE_FIRST_SKILL = "\n\n[Loaded as part of the "
_AUTO_LOADED = '[IMPORTANT: The "'
_AUTO_LOADED_END = "then run them with the terminal tool using the absolute path."


def _normalized(text: str) -> str:
    text = text.translate(str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'}))
    return " ".join(text.split()).casefold()


def _between(text: str, start: int, marker: str, end: str) -> str:
    if start == -1:
        return ""
    rest = text[start + len(marker) :]
    stop = rest.find(end)
    return rest if stop == -1 else rest[:stop]


def _typed(content: str) -> str:
    """What the reviewer typed in a stored user message, without any skill text Hermes loaded
    into it; an invocation in a shape this does not know contributes nothing."""
    if content.startswith(_INVOKED):
        if _BUNDLE in content:
            at = content.find(_BUNDLE_INSTRUCTION)
            return _between(content, at, _BUNDLE_INSTRUCTION, _BUNDLE_FIRST_SKILL)
        if _SINGLE_SKILL in content:
            at = content.rfind(_SINGLE_INSTRUCTION)
            return _between(content, at, _SINGLE_INSTRUCTION, _RUNTIME_NOTE)
        return ""
    if content.startswith(_AUTO_LOADED) and "skill is auto-loaded" in content[:300]:
        at = content.rfind(_AUTO_LOADED_END)
        return content[at + len(_AUTO_LOADED_END) :] if at != -1 else ""
    return content


def _user_messages(session_id: str, since: str | None) -> list[str] | None:
    """What the reviewer said in this session, optionally only after `since`: their messages and
    their answers to clarify questions. A skill invocation line ("/journal-article-review")
    is not the reviewer's statement."""
    path = profile_root(None) / "state.db"
    if not path.is_file():
        return None
    after = datetime.fromisoformat(since).timestamp() if since else 0.0
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            rows = db.execute(
                "SELECT role, content FROM messages WHERE session_id = ? AND timestamp >= ? "
                "AND (role = 'user' OR (role = 'tool' AND tool_name = 'clarify'))",
                (session_id, after),
            ).fetchall()
    except sqlite3.Error:
        return None
    said: list[str] = []
    for role, content in rows:
        if role == "user":
            said.append(re.sub(r"^\s*/\S+.*$", "", _typed(str(content or "")), flags=re.M))
        else:
            said += _clarify_answers(content)
    return said


def _clarify_answers(content: Any) -> list[str]:
    """The answers the reviewer gave in one clarify result; an unanswered, cancelled or
    undelivered question (one-shot mode) has none."""
    try:
        result = json.loads(content or "")
    except ValueError:
        return []
    responses = result.get("responses") if isinstance(result, dict) else None
    return [
        r["user_response"]
        for r in responses or []
        if isinstance(r, dict)
        and r.get("status") == "answered"
        and isinstance(r.get("user_response"), str)
    ]


def reviewer_words(
    words: str,
    *,
    hermes_session: bool,
    what: str,
    since: str | None = None,
    min_chars: int = MIN_WORDS_CHARS,
) -> dict[str, Any]:
    """Verify `words` against the reviewer's messages; refuse what the reviewer did not write.

    `hermes_session` says the record belongs to a Hermes session, which must then be checkable.
    `since` limits the check to messages sent after that time, such as a reply to a candidate."""
    words = words.strip()
    if len(words) < min_chars:
        raise ReviewError(f"quote the reviewer's own words for {what}")
    session_id = os.environ.get("HERMES_SESSION_ID")
    if not session_id:
        if hermes_session:
            raise ReviewError(f"{what} must be recorded from inside the reviewer's Hermes session")
        return {"words": words, "verified": False}
    messages = _user_messages(session_id, since)
    if messages is None:
        raise ReviewError(
            f"cannot read this Hermes session's messages to check {what}; run `creview hermes "
            "doctor`"
        )
    wanted = _normalized(words)
    if not any(wanted in _normalized(message) for message in messages):
        raise ReviewError(
            f"{what} must quote the reviewer's own words from this conversation"
            + (" sent after it was asked" if since else "")
            + f"; {words[:80]!r} is not in any of those messages. If they have not answered, "
            "ask and wait"
        )
    return {"words": words, "verified": True}
