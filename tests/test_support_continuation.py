"""A nonzero host handoff is never a model-authored success assertion."""

import copy

import pytest

from closed_review.io import sha256_file
from closed_review.support.continuation import iteration_handoff


def host_event(session="actual-session", reason="max_iterations_reached(150/150)"):
    return (
        f"2026-10-29 08:40:17,684 INFO [{session}] agent.conversation_loop: "
        f"Turn ended: reason={reason} model=local-model api_calls=150/150 budget=150/150 "
        f"tool_turns=37 last_msg_role=assistant response_len=2948 session={session}\n"
    )


def context(tmp_path):
    source = tmp_path / "manuscript.md"
    source.write_text("Synthetic continuation fixture. No medical judgments.")
    before = {
        "id": "same-run",
        "cursor": 0,
        "tasks": [{"id": i} for i in range(3)],
        "session_id": "same-session-hash",
        "protocol": "medical-methods-v1",
        "schema_version": 1,
        "contract_version": 10,
        "identity": {"runner": "c" * 64},
        "route": {"model": "local-model"},
        "source": {"sha256": sha256_file(source)},
        "notes": [],
        "attempts": {"task1": 1},
        "modules": {"statistics": {"failures": []}},
    }
    after = {**copy.deepcopy(before), "cursor": 2}
    kwargs = dict(
        expected_session="actual-session",
        observed_session="actual-session",
        source_path=source,
        source_hash=sha256_file(source),
        runner="c" * 64,
        max_turns=150,
        agent_log=host_event(),
        turn_output="Stopped with saved progress.",
    )
    return before, after, kwargs


def test_actual_iteration_event_allows_bounded_continuation_not_a_pass(tmp_path):
    before, after, kwargs = context(tmp_path)
    original = copy.deepcopy((before, after, kwargs))
    result = iteration_handoff(before, after, **kwargs)
    assert result["verified_host_event"] and result["from_task"] == 0 and result["to_task"] == 2
    assert result["engineering_success_claimed"] is False
    assert (before, after, kwargs) == original


@pytest.mark.parametrize(
    "problem",
    [
        "model-summary-only",
        "no-event",
        "other-session",
        "other-log-session",
        "fork-event",
        "other-logger",
        "wrong-reason",
        "second-turn",
        "extra-unparsed-turn",
        "unfinished-budget",
        "raised-budget",
        "traceback",
        "host-error",
        "edit-failure",
        "no-progress",
        "cursor-bool",
        "source-edited",
        "source-symlink",
        "snapshot-edited",
        "source-hash",
        "runner",
        "route",
        "new-run",
        "new-session-hash",
        "new-module",
        "module-failure",
        "refusals-reset",
        "notes",
        "changed-tasks",
        "missing-session",
        "changed-protocol",
    ],
)
def test_any_missing_or_conflicting_handoff_evidence_keeps_exit_fatal(tmp_path, problem):
    before, after, kwargs = context(tmp_path)
    if problem == "model-summary-only":
        kwargs.update(agent_log="", turn_output=host_event() + "I hit the iteration limit.")
    elif problem == "no-event":
        kwargs["agent_log"] = "2026-10-29 INFO A turn started."
    elif problem == "other-session":
        kwargs["observed_session"] = "other"
    elif problem == "other-log-session":
        kwargs["agent_log"] = host_event("other")
    elif problem == "fork-event":
        kwargs["agent_log"] = host_event().rstrip() + " origin=background_review\n"
    elif problem == "other-logger":
        kwargs["agent_log"] = host_event().replace("agent.conversation_loop", "tool.fake_log")
    elif problem == "wrong-reason":
        kwargs["agent_log"] = host_event(reason="all_retries_exhausted_no_response")
    elif problem == "second-turn":
        kwargs["agent_log"] += host_event(reason="text_response(finish_reason=stop)")
    elif problem == "extra-unparsed-turn":
        kwargs["agent_log"] += "Turn ended: reason=local_processing_error\n"
    elif problem == "unfinished-budget":
        kwargs["agent_log"] = host_event().replace("budget=150/150", "budget=149/150")
    elif problem == "raised-budget":
        kwargs["max_turns"] = 149
    elif problem == "traceback":
        kwargs["turn_output"] += "Traceback (most recent call last)"
    elif problem == "host-error":
        kwargs["agent_log"] += "2026-10-29 08:40:18,000 ERROR [actual-session] disk failed\n"
    elif problem == "edit-failure":
        kwargs["turn_output"] += "⚠️ File-mutation verifier: 1 file edit(s) FAILED"
    elif problem == "no-progress":
        after["cursor"] = 0
    elif problem == "cursor-bool":
        before["cursor"] = False
    elif problem == "source-edited":
        kwargs["source_path"].write_text("changed source")
    elif problem == "source-symlink":
        link = tmp_path / "link.md"
        link.symlink_to(kwargs["source_path"])
        kwargs["source_path"] = link
    elif problem == "snapshot-edited":
        after["source"]["blocks"] = ["different extracted text"]
    elif problem == "source-hash":
        after["source"]["sha256"] = "d" * 64
    elif problem == "runner":
        after["identity"]["runner"] = "d" * 64
    elif problem == "route":
        after["route"]["model"] = "other-model"
    elif problem == "new-run":
        after["id"] = "replacement-run"
    elif problem == "new-session-hash":
        after["session_id"] = "replacement-session"
    elif problem == "new-module":
        after["modules"]["logic"] = {"failures": []}
    elif problem == "module-failure":
        after["modules"]["statistics"]["failures"] = [{"error": "second refusal"}]
    elif problem == "refusals-reset":
        after["attempts"] = {}
    elif problem == "notes":
        after["notes"] = ["invented reviewer approval"]
    elif problem == "changed-tasks":
        after["tasks"] = after["tasks"][:2]
    elif problem == "missing-session":
        kwargs["expected_session"] = None
    else:
        after["protocol"] = "legacy"
    assert iteration_handoff(before, after, **kwargs) is None
