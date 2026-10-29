"""Pre-start recovery requires actual host/state evidence and remains bounded."""

import copy
import hashlib
import importlib.util
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from closed_review.io import atomic_write_json, read_json, sha256_file
from closed_review.receipts import installed_identity
from closed_review.session import start_session
from closed_review.support import workflow
from closed_review.support.render import export

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/test-support-hermes.py"
SPEC = importlib.util.spec_from_file_location("startup_pilot", SCRIPT)
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)
SETTINGS = {"gateway_url": "http://127.0.0.1:8091/v1", "model": "qwen3.8-flash-next",
            "context_length": 65536}
SESSION = "startup-test-session"


def host_event(session=SESSION):
    prefix = f"2026-10-29 15:10:00,000 WARNING [{session}] agent.conversation_loop: "
    return (
        prefix + "Reasoning-only clean stop (1065 chars) — returning the reasoning as the "
        f"final response (model=qwen3.8-flash-next provider=custom api_calls=3 tool_turns=2)\n"
        f"2026-10-29 15:10:00,001 INFO [{session}] agent.conversation_loop: "
        "Turn ended: reason=text_response(finish_reason=stop) model=qwen3.8-flash-next "
        f"api_calls=3/12 budget=3/12 tool_turns=2 last_msg_role=assistant response_len=1065 "
        f"session={session}\n"
    )


def setup_session(root, work):
    with sqlite3.connect(root / "state.db") as db:
        db.execute("CREATE TABLE messages (role TEXT, session_id TEXT, "
                   "content TEXT, timestamp REAL)")
        db.execute("INSERT INTO messages VALUES ('user', ?, 'test fixture', 0)", (SESSION,))
        db.execute("CREATE TABLE sessions (id TEXT, model TEXT, billing_provider TEXT, "
                   "billing_base_url TEXT)")
        db.execute("INSERT INTO sessions VALUES (?, ?, 'custom', ?)",
                   (SESSION, SETTINGS["model"], SETTINGS["gateway_url"]))
    atomic_write_json(work / "runner.json", installed_identity())
    start_session(None, live=False, support=True)


@pytest.fixture
def pristine(isolated_env):
    env = pilot._child_environment(isolated_env / "isolated", gateway_url=SETTINGS["gateway_url"])
    with pilot.environment(env):
        setup = pilot.setup_profile("pilot", **SETTINGS, apply=True)
    root = Path(setup["profile_root"])
    env.update(HERMES_HOME=str(root), CREVIEW_HOME=str(root / "review-data"))
    paper = root / "work/manuscript.md"
    paper.write_text("# Synthetic startup fixture\n\nNo medical assessment is made.\n")
    pins = pilot.startup_pins(root)
    with pilot.environment(dict(env, HERMES_SESSION_ID=SESSION)):
        setup_session(root, paper.parent)
    kwargs = dict(before=None, after=None, session=SESSION, paper=paper,
                  paper_hash=sha256_file(paper), runner=installed_identity()["sums_sha256"],
                  model=SETTINGS["model"], pins=pins, agent_log=host_event(),
                  turn_output="Test fixture: no execution yet.", max_turns=12)
    return root, env, kwargs


def test_real_state_guard_allows_one_continuation_not_a_success(pristine):
    root, env, kwargs = pristine
    before = copy.deepcopy(kwargs)
    result = pilot.startup_handoff(root, env, **kwargs)
    assert result and result["verified_host_event"] and result["preflight_ready"]
    assert result["engineering_success_claimed"] is False
    assert kwargs == before and pilot.saved_run(root) is None


@pytest.mark.parametrize("problem", [
    "no-event", "model-spoof", "no-marker", "other-session", "other-model", "other-provider",
    "other-logger", "fork", "two-events", "unparsed-event", "marker-after-event",
    "used-limit", "counter-drift", "tool-counter", "wrong-bound", "before-run", "after-run",
    "traceback", "host-error", "edit-error", "tool-error", "blocked-command",
    "source-change", "source-symlink", "config-change", "runner-probe", "orphan-draft",
    "legacy-scan", "preflight-missing", "preflight-failed", "preflight-other-session",
    "preflight-version", "preflight-legacy", "preflight-privacy", "runtime-route",
    "probe-wrong-shape", "preflight-wrong-shape", "bool-bound", "missing-profile-pin",
])
def test_unsafe_or_unverifiable_startup_is_not_recovered(pristine, problem):
    root, env, kwargs = pristine
    log = kwargs["agent_log"]
    if problem == "no-event":
        kwargs["agent_log"] = ""
    elif problem == "model-spoof":
        kwargs.update(agent_log="", turn_output=log)
    elif problem == "no-marker":
        kwargs["agent_log"] = log.splitlines()[1] + "\n"
    elif problem == "other-session":
        kwargs["session"] = "different-session"
    elif problem in {"other-model", "other-provider", "other-logger"}:
        old, new = {"other-model": ("qwen3.8-flash-next", "other-model"),
                    "other-provider": ("provider=custom", "provider=external"),
                    "other-logger": ("agent.conversation_loop", "tool.fake")}[problem]
        kwargs["agent_log"] = log.replace(old, new)
    elif problem == "fork":
        kwargs["agent_log"] = log.rstrip() + " origin=background_review\n"
    elif problem == "two-events":
        kwargs["agent_log"] += log
    elif problem == "unparsed-event":
        kwargs["agent_log"] += "Turn ended: reason=unknown\n"
    elif problem == "marker-after-event":
        kwargs["agent_log"] = "\n".join(reversed(log.splitlines())) + "\n"
    elif problem == "used-limit":
        kwargs["agent_log"] = log.replace("api_calls=3", "api_calls=12").replace(
            "budget=3", "budget=12")
    elif problem == "counter-drift":
        kwargs["agent_log"] = log.replace("budget=3/12", "budget=2/12")
    elif problem == "tool-counter":
        kwargs["agent_log"] = log.replace("tool_turns=2 last_msg", "tool_turns=1 last_msg")
    elif problem == "wrong-bound":
        kwargs["max_turns"] = 13
    elif problem == "bool-bound":
        kwargs["max_turns"] = True
    elif problem in {"before-run", "after-run"}:
        kwargs["before" if problem == "before-run" else "after"] = {}
    elif problem in {"traceback", "edit-error", "blocked-command"}:
        kwargs["turn_output"] += {"traceback": "Traceback (most recent call last)",
                                  "edit-error": "File-mutation verifier: FAILED",
                                  "blocked-command": "BLOCKED: command"}[problem]
    elif problem in {"host-error", "tool-error"}:
        kwargs["agent_log"] += (
            "2026-10-29 15:10:00,002 ERROR [startup-test-session] disk failed\n"
            if problem == "host-error" else "Tool terminal returned error\n"
        )
    elif problem == "source-change":
        kwargs["paper"].write_text("Changed source")
    elif problem == "source-symlink":
        link = root / "work/link.md"
        link.symlink_to(kwargs["paper"])
        kwargs["paper"] = link
    elif problem == "config-change":
        with (root / "config.yaml").open("a") as stream:
            stream.write("\n# changed configuration\n")
    elif problem == "runner-probe":
        atomic_write_json(root / "work/runner.json", {"sums_sha256": "f" * 64})
    elif problem == "probe-wrong-shape":
        atomic_write_json(root / "work/runner.json", [])
    elif problem == "missing-profile-pin":
        (root / "config.yaml").unlink()
    elif problem in {"orphan-draft", "legacy-scan"}:
        path = root / "review-data" / ("support/orphan/answers/draft.json"
                                      if problem == "orphan-draft" else "scans/old/scan.json")
        atomic_write_json(path, {})
    elif problem.startswith("preflight-"):
        key = hashlib.sha256(SESSION.encode()).hexdigest()[:32]
        path = root / "review-data/preflights" / f"{key}.json"
        if problem == "preflight-wrong-shape":
            atomic_write_json(path, [])
        elif problem == "preflight-missing":
            path.unlink()
        else:
            record = read_json(path)
            field, value = {"preflight-failed": ("ready", False),
                            "preflight-other-session": ("session_id", "other"),
                            "preflight-version": ("creview_version", "other"),
                            "preflight-legacy": ("support_required", False),
                            "preflight-privacy": ("skill_privacy_block", "changed")}[problem]
            record[field] = value
            atomic_write_json(path, record)
    elif problem == "runtime-route":
        with sqlite3.connect(root / "state.db") as db:
            db.execute("UPDATE sessions SET billing_provider='external'")
    assert pilot.startup_handoff(root, env, **kwargs) is None


@pytest.mark.parametrize("module", list(pilot.CASES.values())[::2])
def test_bounded_startup_continuation_finishes_each_actual_module_workflow(
    isolated_env, monkeypatch, module,
):
    run_adapter(isolated_env, monkeypatch, module)


@pytest.mark.parametrize("problem", ["second-stop", "changed-session", "start-only"])
def test_repeated_stop_and_session_drift_fail_and_existing_checkpoint_stays_bounded(
    isolated_env, monkeypatch, problem,
):
    run_adapter(isolated_env, monkeypatch, "qualitative-study", problem)


def run_adapter(root, monkeypatch, module, problem=None):
    """Deterministic adapter, not local-model or medical-quality evidence."""
    paper = root / "synthetic.md"
    paper.write_text("# Synthetic fixture\n\nParticipants described a test process.\n")
    args = SimpleNamespace(output=root / "results", paper_override=paper, corpus=root,
                           hermes="fake-hermes", language="en", synthetic_only=True)
    calls = []

    def fake_turn(command, env, work, log, deadline):
        calls.append(command)
        profile = Path(env["HERMES_HOME"])
        with pilot.environment(dict(env, HERMES_SESSION_ID=SESSION)):
            if len(calls) == 1:
                setup_session(profile, work)
            if len(calls) == 1 or (problem == "second-stop" and len(calls) == 2):
                atomic_write_json(profile / "fixture-only.json", {"not_model_evidence": True})
                agent_log = profile / "logs/agent.log"
                agent_log.parent.mkdir(exist_ok=True)
                with agent_log.open("a") as stream:
                    stream.write(host_event())
                log.write_text("Synthetic adapter clean stop; no model inference.")
                return
            if problem == "changed-session":
                with sqlite3.connect(profile / "state.db") as db:
                    db.execute("UPDATE messages SET session_id='other'")
                return
            current = pilot.saved_run(profile)
            if current is None:
                run_id = workflow.start(work / "manuscript.md", [module], language="en")["run_id"]
                if problem != "start-only":
                    workflow.next_task(run_id)
                return
            run_id = current["id"]
            if problem == "start-only" and len(calls) == 3:
                workflow.next_task(run_id)
                return
            while workflow.status(run_id)["phase"] == "running":
                issued = workflow.next_task(run_id)
                answer = copy.deepcopy(issued["context"]["answer_template"])
                if issued["task"]["stage"] == "appraise":
                    answer["assessments"] = [dict(criterion=c, status="not_assessable",
                        analysis="Adapter only, no medical inference.", why_matters="", limits="",
                        evidence=[], counterevidence=[]) for c in issued["task"]["criteria"]]
                elif issued["task"]["stage"] == "consolidate":
                    answer.update(language="en", title="Adapter only", summary="Not an appraisal.")
                atomic_write_json(Path(issued["answer_path"]), answer)
                assert workflow.submit(run_id, Path(issued["answer_path"]))["accepted"]
            export(run_id)

    monkeypatch.setattr(pilot, "_run_turn", fake_turn)
    result = pilot.run_case(args, "startup-fixture", module, SETTINGS, time.monotonic() + 30)
    assert result["startup_completion_requests"] == 1
    assert len(result["startup_handoffs"]) == 1
    assert calls[1][-2:] == ["--resume", SESSION]
    assert [c[c.index("--max-turns") + 1] for c in calls[:2]] == ["12", "12"]
    assert result["qualification"] == "not_qualified"
    if problem in {"second-stop", "changed-session"}:
        assert not result["engineering_passed"] and len(calls) == 2
        assert "one bounded continuation" in result["error"] if problem == "second-stop" else (
            "changed session" in result["error"])
    else:
        assert result["engineering_passed"], result
        assert len(calls) == (4 if problem == "start-only" else 3)
        assert result["checkpoint_completion_requests"] == int(problem == "start-only")
