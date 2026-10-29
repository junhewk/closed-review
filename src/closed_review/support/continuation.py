"""Recognize a host-recorded iteration handoff, never infer success from model prose."""

from __future__ import annotations

import re
from pathlib import Path

from ..io import sha256_file

TURN_EVENT = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} INFO \[([^\]\r\n]+)\] "
    r"agent\.conversation_loop: Turn ended: reason=(\S+) model=(\S+) "
    r"api_calls=(\d+)/(\d+) budget=(\d+)/(\d+) tool_turns=\d+ "
    r"last_msg_role=\S+ response_len=\d+ session=(\S+)$",
    re.MULTILINE,
)


def iteration_handoff(
    before: dict | None,
    after: dict | None,
    *,
    expected_session: str | None,
    observed_session: str | None,
    source_path: Path,
    source_hash: str,
    runner: str,
    max_turns: int,
    agent_log: str,
    turn_output: str,
) -> dict | None:
    """A handoff permits bounded same-session continuation, not an engineering pass.

    The caller supplies only the NEW host-log suffix from this invocation. Any edit-verifier
    failure, traceback, host error, identity/source/route drift or lack of committed task
    progress keeps the original nonzero exit fatal. Refusal counters are never reset.
    """
    if (
        not before
        or not after
        or not expected_session
        or observed_session != expected_session
        or not agent_log
        or type(max_turns) is not int
        or max_turns < 1
        or any(
            token in agent_log + turn_output
            for token in (
                "Traceback (most recent call last)",
                "File-mutation verifier:",
            )
        )
        or re.search(r"^\d{4}-\d{2}-\d{2} .* (?:ERROR|CRITICAL) \[", agent_log, re.MULTILINE)
    ):
        return None
    events = list(TURN_EVENT.finditer(agent_log))
    if not events:
        return None
    event = events[-1]
    logged_session, reason, model, used, limit, budget_used, budget_limit, session = event.groups()
    bounded = re.fullmatch(r"max_iterations_reached\(([1-9][0-9]*)/([1-9][0-9]*)\)", reason)
    if (
        not bounded
        or logged_session != expected_session
        or session != expected_session
        or len(re.findall(r"Turn ended: reason=", agent_log)) != len(events)
        or len(events) != 1
    ):
        return None
    count, cap = map(int, bounded.groups())
    if not count == cap == int(used) == int(limit) == int(budget_used) == int(budget_limit):
        return None
    if cap > max_turns:
        return None
    first, last = before.get("cursor"), after.get("cursor")
    tasks = before.get("tasks")
    if (
        type(first) is not int
        or type(last) is not int
        or not isinstance(tasks, list)
        or not 0 <= first < last <= len(tasks)
        or after.get("tasks") != tasks
        or not before.get("id")
        or after.get("id") != before["id"]
        or after.get("session_id") != before.get("session_id")
        or any(
            after.get(k) != before.get(k)
            for k in (
                "protocol",
                "schema_version",
                "contract_version",
                "source",
            )
        )
        or after.get("identity", {}).get("runner") != runner
        or before.get("identity", {}).get("runner") != runner
        or after.get("route") != before.get("route")
        or after.get("route", {}).get("model") != model
        or after.get("source", {}).get("sha256") != source_hash
        or before.get("source", {}).get("sha256") != source_hash
        or after.get("notes") != before.get("notes")
        or set(after.get("modules", {})) != set(before.get("modules", {}))
        or any(state.get("failures") for state in after.get("modules", {}).values())
        or any(
            after.get("attempts", {}).get(k, 0) < v for k, v in before.get("attempts", {}).items()
        )
        or not source_path.is_file()
        or source_path.is_symlink()
        or sha256_file(source_path) != source_hash
    ):
        return None
    return {
        "reason": reason,
        "session": session,
        "run_id": after["id"],
        "from_task": first,
        "to_task": last,
        "verified_host_event": True,
        "engineering_success_claimed": False,
    }
