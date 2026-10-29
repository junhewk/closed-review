"""The deliberate early stop must be observed, not merely requested or inferred."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from closed_review.errors import ReviewError

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/probe-support-bootstrap.py"
SPEC = importlib.util.spec_from_file_location("support_bootstrap", SCRIPT)
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


@pytest.mark.parametrize(
    "problem",
    [
        None,
        "issued",
        "no-request",
        "no-checkpoint",
        "wrong-invocation",
        "too-many-turns",
        "event-failed",
    ],
)
def test_start_only_prompt_is_preserved_and_only_actual_bounded_branch_can_pass(tmp_path, problem):
    work = tmp_path / "work"
    work.mkdir()
    query = work / "query-0.txt"
    original = "SYNTHETIC local privacy preflight. " + bootstrap.CHECKPOINT_PROMPT + "No decisions."
    query.write_text(original)
    calls = []
    pilot = SimpleNamespace(
        saved_run=lambda _: {"started": True} if calls else None,
        checkpoint_state=lambda _: "issued" if problem == "issued" else "unissued",
    )

    def turn(command, env, directory, log, deadline):
        assert directory == work
        text = Path(command[command.index("--query-file") + 1]).read_text()
        calls.append(command)
        assert bootstrap.START_ONLY_PROMPT in text
        assert bootstrap.CHECKPOINT_PROMPT not in text
        assert text.startswith("SYNTHETIC local privacy preflight.")
        assert text.endswith("No decisions.")

    pilot._run_turn = turn

    def recovery(mode, args, settings):
        probe.load_pilot()._run_turn(
            ["hermes", "--query-file", str(query)],
            {"HERMES_HOME": str(tmp_path)},
            work,
            tmp_path / "turn.log",
            100,
        )
        return {
            "probe_passed": problem != "event-failed",
            "case": {
                "initial_checkpoint_state": "unissued",
                "checkpoint_completion_requests": 0 if problem == "no-request" else 1,
                "checkpoint_reached": problem != "no-checkpoint",
                "turns": 7 if problem == "too-many-turns" else 4,
            },
            "observed": {"instrumented_invocation": 2 if problem == "wrong-invocation" else 3},
        }

    probe = SimpleNamespace(load_pilot=lambda: pilot, recovery=recovery)
    bootstrap.install_wrapper(probe)
    result = probe.recovery("turn-limit", None, {})
    assert result["probe_passed"] is (problem is None)
    assert result["mode"] == "bootstrap-turn-limit"
    assert query.read_text() == original
    assert result["bootstrap"]["original_query"] != result["bootstrap"]["bootstrap_query"]
    assert (
        result["bootstrap"]["original_query_sha256"]
        != (result["bootstrap"]["bootstrap_query_sha256"])
    )


def test_changed_prompt_or_existing_run_is_refused_without_guessing_or_overwriting(tmp_path):
    work = tmp_path
    query = work / "query-0.txt"
    query.write_text("changed prompt")
    calls = []
    pilot = SimpleNamespace(saved_run=lambda _: None, _run_turn=lambda *args: calls.append(args))
    probe = SimpleNamespace(load_pilot=lambda: pilot, recovery=lambda *args: None)
    bootstrap.install_wrapper(probe)
    wrapped = probe.load_pilot()
    with pytest.raises(ReviewError, match="prompt changed"):
        wrapped._run_turn(
            ["hermes", "--query-file", str(query)],
            {"HERMES_HOME": str(work)},
            work,
            work / "log",
            100,
        )
    assert not calls and query.read_text() == "changed prompt"
    pilot.saved_run = lambda _: {"already": "started"}
    wrapped = probe.load_pilot()
    with pytest.raises(ReviewError, match="fresh session/run"):
        wrapped._run_turn(
            ["hermes", "--query-file", str(query)],
            {"HERMES_HOME": str(work)},
            work,
            work / "log",
            100,
        )


def test_bootstrap_wrapper_cannot_be_used_for_other_recovery_modes():
    probe = SimpleNamespace(load_pilot=lambda: None, recovery=lambda *args: None)
    bootstrap.install_wrapper(probe)
    with pytest.raises(ReviewError, match="only the turn-limit"):
        probe.recovery("compression", None, {})
