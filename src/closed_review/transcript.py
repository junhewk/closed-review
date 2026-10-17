"""Check that words attributed to the reviewer are words the reviewer wrote in this session.

A profile confirmation, a disposition, or a lookup approval must quote one of the reviewer's own
messages. Inside Hermes, creview reads the session's user messages from the profile's `state.db`
(read-only) and refuses a statement that is not a verbatim part of one. This stops an agent from
recording consent the reviewer never gave, for example after a clarify prompt went unanswered.
Outside Hermes (an explicit `--session`), there is no transcript to check, and the record says so.
"""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime
from typing import Any

from .errors import ReviewError
from .hermes import profile_root

MIN_WORDS_CHARS = 2


def _normalized(text: str) -> str:
    text = text.translate(str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'}))
    return " ".join(text.split()).casefold()


def _user_messages(session_id: str, since: str | None) -> list[str] | None:
    """The reviewer's messages in this session, optionally only those sent after `since`. A skill
    invocation line ("/journal-article-review deep") is not the reviewer's statement."""
    path = profile_root(None) / "state.db"
    if not path.is_file():
        return None
    after = datetime.fromisoformat(since).timestamp() if since else 0.0
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            rows = db.execute(
                "SELECT content FROM messages WHERE session_id = ? AND role = 'user' "
                "AND timestamp >= ?",
                (session_id, after),
            ).fetchall()
    except sqlite3.Error:
        return None
    return [re.sub(r"^\s*/\S+.*$", "", str(row[0] or ""), flags=re.M) for row in rows]


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
