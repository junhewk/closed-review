from __future__ import annotations

import copy
import importlib.util
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, read_json, sha256_file
from closed_review.receipts import installed_identity
from closed_review.session import start_session
from closed_review.support import workflow
from closed_review.support.calculators import calculate
from closed_review.support.render import export
from closed_review.support.sources import snapshot

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/test-support-hermes.py"
spec = importlib.util.spec_from_file_location("support_pilot", SCRIPT)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
CORPUS = SCRIPT.parents[1] / "evals/support-pilot/manuscripts"


@pytest.mark.parametrize("synthetic", [False, True])
def test_source_context_never_calls_real_papers_synthetic_or_invents_journal_permission(synthetic):
    actual, label, prompt = pilot.source_context(SimpleNamespace(synthetic_only=synthetic))
    assert actual is synthetic
    if synthetic:
        assert label == "synthetic" and "SYNTHETIC" in prompt
    else:
        assert label == "published-article" and "REAL published open-access" in prompt
        assert "not a journal peer-review assignment" in prompt
        assert "synthetic journal" not in prompt and "explicitly permits" not in prompt
        assert "error-free control" in prompt


@pytest.mark.parametrize("value", [None, 0, 1, "false"])
def test_bad_source_context_is_refused_not_guessed(value):
    with pytest.raises(ReviewError, match="explicit boolean"):
        pilot.source_context(SimpleNamespace(synthetic_only=value))


def test_fixture_corpus_covers_all_six_branches_with_pairs():
    assert len(pilot.CASES) == 12
    assert set(pilot.CASES.values()) == {
        "statistics",
        "qualitative-study",
        "systematic-review",
        "scoping-review",
        "narrative-review",
        "logic",
    }
    assert {p.stem for p in CORPUS.glob("*.md")} == set(pilot.CASES)
    for case in pilot.CASES:
        source = snapshot(CORPUS / f"{case}.md")
        assert source["blocks"] and not source["warnings"]
        assert "Synthetic" in (CORPUS / f"{case}.md").read_text()


def test_saved_run_rejects_restarts(tmp_path):
    assert pilot.saved_run(tmp_path) is None
    atomic_write_json(tmp_path / "review-data/support/first/run.json", {"id": "first"})
    assert pilot.saved_run(tmp_path)["id"] == "first"
    atomic_write_json(tmp_path / "review-data/support/second/run.json", {"id": "second"})
    with pytest.raises(ReviewError, match="multiple runs"):
        pilot.saved_run(tmp_path)


@pytest.mark.parametrize(
    "change",
    [
        "cursor",
        "attempts",
        "notes",
        "facts",
        "criteria",
        "calculations",
        "connections",
        "observations",
        "withdrawn",
        "coverage_gaps",
        "reads",
        "failures",
        "wrong-task",
        "pending",
    ],
)
def test_checkpoint_classification_refuses_progress_refusals_or_unissued_claims(change):
    run = {
        "cursor": 0,
        "attempts": {},
        "issued_task": "task-0001",
        "notes": [],
        "modules": {"statistics": {"status": "running", "provided_blocks": ["b1"]}},
    }
    assert pilot.checkpoint_state(run) == "issued"
    if change == "cursor":
        run["cursor"] = 1
    elif change in {"attempts", "notes"}:
        run[change] = {"submitted": True}
    elif change == "wrong-task":
        run["issued_task"] = "task-0002"
    elif change == "pending":
        run["modules"]["statistics"]["status"] = "pending"
    else:
        run["modules"]["statistics"][change] = ["persisted work"]
    assert pilot.checkpoint_state(run) is None


def test_evidence_audit_rejects_false_quotes_and_counterevidence():
    source = snapshot(CORPUS / "case-01.md")
    block = source["blocks"][0]
    run = {
        "source": source,
        "modules": {
            "statistics": {
                "facts": [{"evidence": [{"block_id": block["id"], "quote": block["text"]}]}],
                "criteria": [],
                "connections": [],
                "observations": [],
                "withdrawn": [],
            }
        },
    }
    assert pilot.evidence_bound(run)
    bad = copy.deepcopy(run)
    bad["modules"]["statistics"]["facts"][0]["counterevidence"] = [
        {"block_id": block["id"], "quote": "not in this manuscript"}
    ]
    assert not pilot.evidence_bound(bad)


def test_empty_outputs_and_agent_success_claims_do_not_pass(tmp_path):
    result = pilot.audit(tmp_path, "statistics", "expected", "paper-hash", None)
    assert not result["engineering_passed"]
    assert not result["checks"]["runner_identity"]
    assert not result["checks"]["module_completed"]
    assert not result["checks"]["export_files_exist"]


def test_case_failure_is_retained_without_retries_or_fake_quality(tmp_path, monkeypatch):
    args = SimpleNamespace(
        output=tmp_path / "results", corpus=CORPUS, hermes="hermes", language="en"
    )

    def unavailable(*args, **kwargs):
        raise ReviewError("gateway unavailable")

    monkeypatch.setattr(pilot, "setup_profile", unavailable)
    result = pilot.run_case(args, "case-01", "statistics", {}, 100)
    assert not result["engineering_passed"]
    assert result["turns"] == 0
    assert result["error"] == "gateway unavailable"
    assert result["qualification"] == "not_qualified"
    assert result == read_json(args.output / "case-01/result.json")


def test_main_rejects_reusing_results_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("HERMES_SESSION_ID", raising=False)
    monkeypatch.setattr(pilot.shutil, "which", lambda name: "/bin/true")
    with pytest.raises(SystemExit) as err:
        pilot.main(
            [
                "--output",
                str(tmp_path),
                "--gateway-url",
                "http://127.0.0.1/v1",
                "--model",
                "synthetic",
                "--context-length",
                "65536",
            ]
        )
    assert err.value.code == 2


def test_only_selected_allowlisted_manuscripts_are_run(tmp_path, monkeypatch):
    monkeypatch.delenv("HERMES_SESSION_ID", raising=False)
    monkeypatch.setattr(pilot.shutil, "which", lambda name: "/bin/true")
    seen = []

    def fake_run(args, case, module, settings, deadline):
        seen.append(case)
        return {
            "case_id": case,
            "engineering_passed": True,
            "elapsed_seconds": 1,
            "manuscript_sha256": sha256_file(args.corpus / f"{case}.md"),
        }

    monkeypatch.setattr(pilot, "run_case", fake_run)
    output = tmp_path / "new-output"
    assert (
        pilot.main(
            [
                "--output",
                str(output),
                "--corpus",
                str(CORPUS),
                "--case",
                "case-02",
                "--gateway-url",
                "http://127.0.0.1/v1",
                "--model",
                "synthetic",
                "--context-length",
                "65536",
            ]
        )
        == 0
    )
    assert seen == ["case-02"]
    batch = read_json(output / "batch.json")
    assert batch["engineering_passed"]
    assert batch["qualification"] == "not_qualified"
    assert batch["semantic_quality"] == "not_assessed_requires_human_review"


@pytest.mark.parametrize(
    "case,reported,comparison",
    [
        ("case-01", "20", "match"),
        ("case-02", "35", "mismatch"),
    ],
)
def test_synthetic_table_percentage_replays_locally(case, reported, comparison):
    source = snapshot(CORPUS / f"{case}.md")

    def bound(token, containing):
        label = next(b for b in source["blocks"] if containing in b["text"])
        block = next(
            b
            for b in source["blocks"]
            if b.get("table_id") == label["table_id"]
            and b.get("row") == label["row"]
            and b.get("column") == 2
        )
        assert token in block["text"]
        return {"value": token, "evidence": [{"block_id": block["id"], "quote": token}]}

    calc = {
        "method": "percentage",
        "inputs": {
            "numerator": bound("20", "Readmitted, n"),
            "denominator": bound("100", "Randomized, n"),
        },
        "parameters": {},
        "method_evidence": [
            {
                "block_id": next(b["id"] for b in source["blocks"] if b["text"] == "Readmitted, n"),
                "quote": "Readmitted, n",
            }
        ],
        "assumptions": ["Unweighted readmissions per randomized patient, first group only."],
        "reported": {**bound(reported, "Readmitted, %"), "output": "value"},
    }
    result = calculate(calc, source)
    assert result["outputs"]["value"] == 20
    assert result["comparison"]["status"] == comparison


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize(
    "pause",
    [
        "none",
        "once",
        "twice",
        "overstep",
        "answer-file",
        "stall",
        "handoff",
        "edit-error",
        "fake-limit",
    ],
)
def test_two_turn_adapter_checks_actual_workflow_and_export(
    isolated_env,
    monkeypatch,
    partial,
    pause,
):
    """Deterministic adapter test: no real Hermes executable, inference or network."""
    args = SimpleNamespace(
        output=isolated_env / "results", corpus=CORPUS, hermes="fake-hermes", language="en"
    )
    calls = []

    def fake_hermes(command, env, work, log, deadline):
        calls.append(command)
        with pilot.environment(dict(env, HERMES_SESSION_ID="pilot-test-session")):
            root = Path(env["HERMES_HOME"])
            if len(calls) == 1:
                with sqlite3.connect(root / "state.db") as db:
                    db.execute(
                        "CREATE TABLE messages (role TEXT, session_id TEXT, "
                        "content TEXT, timestamp REAL)"
                    )
                    db.execute(
                        "INSERT INTO messages VALUES ('user', 'pilot-test-session', 'pilot', 0)"
                    )
                atomic_write_json(work / "runner.json", installed_identity())
                with sqlite3.connect(root / "state.db") as db:
                    db.execute(
                        "CREATE TABLE sessions (id TEXT, model TEXT, billing_provider TEXT, "
                        "billing_base_url TEXT)"
                    )
                    db.execute(
                        "INSERT INTO sessions VALUES (?, ?, ?, ?)",
                        (
                            "pilot-test-session",
                            "qwen3.8-flash-next",
                            "custom",
                            "http://127.0.0.1:8091/v1",
                        ),
                    )
                start_session(None, live=False)
                run_id = workflow.start(work / "manuscript.md", ["statistics"], language="en")[
                    "run_id"
                ]
                if pause == "overstep":
                    issued = workflow.next_task(run_id)
                    answer = copy.deepcopy(issued["context"]["answer_template"])
                    atomic_write_json(Path(issued["answer_path"]), answer)
                    assert workflow.submit(run_id, Path(issued["answer_path"]))["accepted"]
                elif pause == "answer-file":
                    atomic_write_json(
                        workflow._root(run_id) / "answers/draft.json",
                        {"draft": True},
                    )
                elif pause in {"none", "stall", "handoff", "edit-error", "fake-limit"}:
                    workflow.next_task(run_id)
                return
            run_id = pilot.saved_run(root)["id"]
            if pause == "stall":
                return
            if pause in {"once", "twice"} and len(calls) == 2:
                if pause == "once":
                    workflow.next_task(run_id)
                return
            while workflow.status(run_id)["phase"] == "running":
                task = workflow.next_task(run_id)
                answer = copy.deepcopy(task["context"]["answer_template"])
                stage = task["task"]["stage"]
                if stage == "extract" and partial:
                    answer["coverage_gaps"] = [
                        {
                            "kind": "unreconstructed_content",
                            "block_ids": [task["task"]["block_ids"][0]],
                            "role": "population",
                            "detail": "Simulated adapter gap in population reconstruction.",
                        }
                    ]
                elif stage == "appraise":
                    answer["assessments"] = [
                        {
                            "criterion": c,
                            "status": "not_assessable",
                            "analysis": "Deterministic adapter only; not an appraisal.",
                            "why_matters": "",
                            "limits": "No model inference in this test.",
                            "evidence": [],
                            "counterevidence": [],
                        }
                        for c in task["task"]["criteria"]
                    ]
                elif stage == "consolidate":
                    answer.update(
                        language="en",
                        title="Adapter test",
                        summary="No scientific appraisal performed.",
                    )
                atomic_write_json(Path(task["answer_path"]), answer)
                assert workflow.submit(run_id, Path(task["answer_path"]))["accepted"]
                if pause in {"handoff", "edit-error", "fake-limit"} and len(calls) == 2:
                    if pause != "fake-limit":
                        agent_log = root / "logs/agent.log"
                        agent_log.parent.mkdir(exist_ok=True)
                        agent_log.write_text(
                            "2026-10-29 08:40:17,684 INFO [pilot-test-session] "
                            "agent.conversation_loop: Turn ended: "
                            "reason=max_iterations_reached(150/150) model=qwen3.8-flash-next "
                            "api_calls=150/150 budget=150/150 tool_turns=37 "
                            "last_msg_role=assistant response_len=100 session=pilot-test-session\n"
                        )
                    log.write_text(
                        "File-mutation verifier: 1 file edit(s) FAILED"
                        if pause == "edit-error"
                        else "Model claims an iteration limit."
                    )
                    raise ReviewError("Hermes exited with status 1; inspect turn-1.log with --keep")
            export(run_id)

    monkeypatch.setattr(pilot, "_run_turn", fake_hermes)
    result = pilot.run_case(
        args,
        "case-01",
        "statistics",
        {
            "gateway_url": "http://127.0.0.1:8091/v1",
            "model": "qwen3.8-flash-next",
            "context_length": 65536,
        },
        time.monotonic() + 30,
    )
    if pause in {"twice", "overstep", "answer-file", "stall", "edit-error", "fake-limit"}:
        assert not result["engineering_passed"]
        assert result["checkpoint_reached"] is (pause in {"stall", "edit-error", "fake-limit"})
        assert len(calls) == (
            6 if pause == "stall" else 2 if pause in {"twice", "edit-error", "fake-limit"} else 1
        )
        assert "error" in result and result["qualification"] == "not_qualified"
        assert len(list(Path(result["profile_root"]).glob("review-data/support/*/run.json"))) == 1
        return
    assert result["engineering_passed"] is not partial, result
    assert len(calls) == (3 if pause in {"once", "handoff"} else 2)
    assert result["checkpoint_completion_requests"] == (1 if pause == "once" else 0)
    assert result["checkpoint_reached"] is True
    assert [c[c.index("--max-turns") + 1] for c in calls] == (
        ["12", "12", "150"]
        if pause == "once"
        else ["12", "150", "150"]
        if pause == "handoff"
        else ["12", "150"]
    )
    assert len(result["iteration_handoffs"]) == (1 if pause == "handoff" else 0)
    assert "error" not in result
    assert result["modules"]["statistics"]["status"] == ("partial" if partial else "complete")
    assert result["checks"]["export_files_exist"]
    assert calls[1][-2:] == ["--resume", "pilot-test-session"]
    assert result["checks"]["same_run_resumed"]
    assert result["checks"]["receipt_integrity"]
    assert result["qualification"] == "not_qualified"
    assert result["semantic_quality"] == "not_assessed_requires_human_review"
