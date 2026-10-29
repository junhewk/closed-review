import importlib.util
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, read_json
from closed_review.receipts import installed_identity
from closed_review.session import start_session
from closed_review.smoke import environment
from closed_review.support import workflow
from closed_review.support.render import export
from closed_review.support.sources import snapshot

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/probe-support-recovery.py"
SPEC = importlib.util.spec_from_file_location("support_recovery", SCRIPT)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)
PILOT = recovery.load_pilot()


def checkpoint_run(identifier):
    return {
        "id": identifier, "cursor": 0, "issued_task": "task-0001", "attempts": {},
        "modules": {"statistics": {"status": "running", "provided_blocks": ["b1"]}},
    }


@pytest.mark.parametrize("mode", ["turn-limit", "compression"])
@pytest.mark.parametrize("event", [False, True])
@pytest.mark.parametrize("bootstrap", [0, 1])
def test_probe_requires_real_observed_event_and_mutates_only_its_test_setting(
    tmp_path,
    monkeypatch,
    mode,
    event,
    bootstrap,
):
    root = tmp_path / "isolated"
    work = root / "work"
    work.mkdir(parents=True)
    (root / "logs").mkdir()
    config = {"model": {"default": "local"}, "compression": {"threshold": 0.5}}
    (root / "config.yaml").write_text(yaml.safe_dump(config))
    commands = []
    fake = SimpleNamespace()
    def saved_run(_):
        if not commands:
            return None
        run = checkpoint_run("unchanged-test-run")
        if bootstrap and len(commands) == 1:
            run.pop("issued_task")
            run["modules"]["statistics"].update(status="pending", provided_blocks=[])
        return run

    fake.saved_run = saved_run
    fake.checkpoint_state = PILOT.checkpoint_state
    fake._session = lambda _: "original-session"

    def original(command, env, work, log, deadline):
        commands.append(list(command))
        if event:
            log_path = root / "logs/agent.log"
            previous = log_path.read_text() if log_path.exists() else ""
            log_path.write_text(
                previous
                + (
                    "Compression #1 complete\n"
                    if mode == "compression"
                    else "Turn ended: reason=max_iterations_reached\n"
                )
            )

    fake._run_turn = original

    def run_case(*args):
        for index in range(3 + bootstrap):
            fake._run_turn(
                ["hermes", "--max-turns", "12" if index <= bootstrap else "150"]
                + (["--resume", "original-session"] if index else []),
                {"HERMES_HOME": str(root)},
                work,
                root / f"turn-{index}.log",
                100,
            )
        return {"engineering_passed": True}

    fake.run_case = run_case
    monkeypatch.setattr(recovery, "load_pilot", lambda: fake)
    result = recovery.recovery(mode, SimpleNamespace(timeout=30), {})
    assert result["probe_passed"] is event
    assert result["observed"]["instrumented_invocation"] == 2 + bootstrap
    assert result["qualification"] == "not_qualified"
    assert fake._run_turn is original
    saved = yaml.safe_load((root / "config.yaml").read_text())
    assert saved["model"] == config["model"]
    if mode == "turn-limit":
        assert commands == [["hermes", "--max-turns", "12"]] + (
            [["hermes", "--max-turns", "12", "--resume", "original-session"]]
            if bootstrap else []
        ) + [
            ["hermes", "--max-turns", "3", "--resume", "original-session"],
            ["hermes", "--max-turns", "150", "--resume", "original-session"],
        ]
        assert saved == config
    else:
        assert saved["compression"] == {"threshold": 0.5, "threshold_tokens": 20000}


@pytest.mark.parametrize(
    "problem", [None, "aborted", "other-session", "fallback", "start", "bad-json"]
)
def test_compression_commit_telemetry_is_scoped_and_fail_closed(problem):
    import json

    event = {
        "event": "compression_attempt",
        "session_id": "original-session",
        "commit_status": "committed",
        "fallback_used": False,
    }
    if problem == "aborted":
        event["commit_status"] = "aborted"
    elif problem == "other-session":
        event["session_id"] = "unrelated-session"
    elif problem == "fallback":
        event["fallback_used"] = True
    elif problem == "start":
        event["event"] = "compression_started"
    line = (
        "2026-10-28 INFO agent.conversation_compression: "
        "context compression attempt telemetry: "
    ) + ("invalid-json" if problem == "bad-json" else json.dumps(event))
    assert recovery.compression_committed(line, "original-session") is (problem is None)
    assert not recovery.compression_committed(line, None)


@pytest.mark.parametrize("problem", [None, "no-event", "different-run", "traceback", "other-exit"])
def test_only_the_expected_forced_exit_can_resume_the_same_saved_run(
    tmp_path, monkeypatch, problem
):
    root = tmp_path / "isolated"
    work = root / "work"
    work.mkdir(parents=True)
    (root / "logs").mkdir()
    calls = []
    fake = SimpleNamespace()
    fake.saved_run = lambda _: checkpoint_run(
        "changed" if problem == "different-run" and len(calls) >= 2 else "original"
    )
    fake.checkpoint_state = PILOT.checkpoint_state
    fake._session = lambda _: "original-session"

    def original(command, env, work, log, deadline):
        calls.append(command)
        if len(calls) == 2:
            if problem != "no-event":
                (root / "logs/agent.log").write_text(
                    "Turn ended: reason=max_iterations_reached(3/3)\n"
                )
            log.write_text(
                "Traceback (most recent call last)"
                if problem == "traceback"
                else "Turn limit reached; saved."
            )
            raise ReviewError(
                "Hermes exited with status 2; inspect log"
                if problem == "other-exit"
                else "Hermes exited with status 1; inspect log"
            )

    fake._run_turn = original

    def run_case(*args):
        for index in range(3):
            fake._run_turn(
                [
                    "hermes",
                    "--max-turns",
                    "12" if index == 0 else "150",
                    "--resume",
                    "original-session",
                ],
                {"HERMES_HOME": str(root)},
                work,
                root / f"turn-{index}.log",
                100,
            )
        return {"engineering_passed": True}

    fake.run_case = run_case
    monkeypatch.setattr(recovery, "load_pilot", lambda: fake)
    if problem is None:
        result = recovery.recovery("turn-limit", SimpleNamespace(timeout=30), {})
        assert result["probe_passed"] and result["observed"]["expected_forced_exit_recovered"]
        assert len(calls) == 3
    else:
        with pytest.raises(ReviewError):
            recovery.recovery("turn-limit", SimpleNamespace(timeout=30), {})
        assert len(calls) == 2
    assert fake._run_turn is original


def test_image_only_fixture_is_a_real_pdf_without_text_layer(tmp_path):
    path = tmp_path / "image-only.pdf"
    recovery.image_only_pdf(path)
    source = snapshot(path)
    assert path.read_bytes().startswith(b"%PDF")
    assert not source["blocks"] and source["warnings"]


def test_unreadable_probe_accepts_only_a_honest_not_assessable_export(isolated_env, monkeypatch):
    args = SimpleNamespace(
        output=isolated_env / "probe", language="en", hermes="fake-hermes", timeout=30
    )

    def fake_hermes(command, env, work, log, deadline):
        root = Path(env["HERMES_HOME"])
        with environment(dict(env, HERMES_SESSION_ID="pdf-probe-test")):
            with sqlite3.connect(root / "state.db") as db:
                db.execute(
                    "CREATE TABLE messages (role TEXT, session_id TEXT, content TEXT, "
                    "timestamp REAL)"
                )
                db.execute("INSERT INTO messages VALUES ('user', 'pdf-probe-test', 'synthetic', 0)")
                db.execute(
                    "CREATE TABLE sessions (id TEXT, model TEXT, billing_provider TEXT, "
                    "billing_base_url TEXT)"
                )
                db.execute(
                    "INSERT INTO sessions VALUES ('pdf-probe-test', 'qwen3.8-flash-next', "
                    "'custom', 'http://127.0.0.1:8091/v1')"
                )
            atomic_write_json(work / "runner.json", installed_identity())
            start_session(None, live=False, support=True)
            run = workflow.start(work / "manuscript.pdf", ["statistics"], language="en")
            assert workflow.status(run["run_id"])["phase"] == "not_assessable"
            export(run["run_id"])

    monkeypatch.setattr(recovery, "_run_turn", fake_hermes)
    result = recovery.unreadable(
        args,
        {
            "gateway_url": "http://127.0.0.1:8091/v1",
            "model": "qwen3.8-flash-next",
            "context_length": 65536,
        },
    )
    assert result["probe_passed"], result
    assert result["checks"]["not_assessable"] and result["checks"]["no_observations"]
    assert result["checks"]["receipt_integrity"]
    assert result["qualification"] == "not_qualified"
    artifact = Path(result["dossier"]) / "support.json"
    assert read_json(artifact)["modules"]["statistics"]["status"] == "not_assessable"
