import copy
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from test_support import begin, finish
from test_support import support_env as support_env
from test_support_profile import active
from test_support_profile import managed as managed

from closed_review.errors import ReviewError
from closed_review.io import read_json
from closed_review.session import start_session
from closed_review.smoke import environment
from closed_review.support import workflow
from closed_review.support.sources import snapshot

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/probe-support-scope.py"
SPEC = importlib.util.spec_from_file_location("support_scope", SCRIPT)
scope = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scope)


def probe_fixture(tmp_path, monkeypatch, *, modules=None, language="ko"):
    paper = tmp_path / "paper.md"
    paper.write_text("Synthetic manuscript with 12 patients.")
    state = {
        "title": "통계 지원",
        "summary": "제한적인 방법론 지원입니다.",
        "criteria": [{"analysis": "본문의 근거를 확인해야 합니다."}],
        "observations": [{"explanation": "출처 수치의 의미는 검토자가 확인합니다."}],
        "facts": [{"id": "statistics-f0001"}],
        "reads": [{"ids": ["b1", "statistics-f0001"]}],
        "connections": [],
        "provided_blocks": ["b1"],
    }
    run = {
        "resolved_language": language,
        "source": {"blocks": [{"id": "b1"}], "path": str(paper)},
        "tasks": [{"stage": "extract"}],
        "modules": modules or {"statistics": state},
    }
    monkeypatch.setattr(scope, "load_pilot", lambda: SimpleNamespace(saved_run=lambda root: run))
    result = {
        "engineering_passed": True,
        "checks": {"receipt_integrity": True},
        "profile_root": str(tmp_path),
    }
    return run, result


def test_long_source_is_deterministic_multichunk_and_not_quality_evidence(tmp_path):
    original = "# Synthetic study\n\nNo external sources were retrieved."
    text = scope.long_source(original)
    assert text.startswith(original)
    assert len(text.split()) >= 6500
    assert text == scope.long_source(original)
    paper = tmp_path / "long.md"
    paper.write_text(text)
    source = snapshot(paper)
    assert len(source["blocks"]) > 40
    assert "not to simulate a representative medical article" in text


def test_korean_probe_requires_prose_not_only_a_language_flag(tmp_path, monkeypatch):
    run, result = probe_fixture(tmp_path, monkeypatch)
    assert scope.inspect_probe("korean", result)["probe_passed"]
    run["modules"]["statistics"]["criteria"][0]["analysis"] = "English only"
    report = scope.inspect_probe("korean", result)
    assert not report["probe_passed"]
    assert report["qualification"] == "not_qualified"
    assert "semantic_quality" in report and "fidelity" in report["manual_audit"]


def test_korean_smoke_signal_never_overrides_a_failed_base_check(tmp_path, monkeypatch):
    _, result = probe_fixture(tmp_path, monkeypatch)
    result["engineering_passed"] = False
    assert not scope.inspect_probe("korean", result)["probe_passed"]


def test_multi_module_requires_exact_scope_and_context_isolation(tmp_path, monkeypatch):
    run, result = probe_fixture(tmp_path, monkeypatch)
    state = copy.deepcopy(run["modules"]["statistics"])
    state["facts"] = [{"id": "logic-f0001"}]
    state["reads"] = [{"ids": ["b1", "logic-f0001"]}]
    run["modules"]["logic"] = state
    assert scope.inspect_probe("multi-module", result)["probe_passed"]
    state["reads"][0]["ids"].append("statistics-f0001")
    assert not scope.inspect_probe("multi-module", result)["probe_passed"]
    state["reads"] = []
    state["connections"] = [{"from": ["logic-f0001"], "to": ["statistics-f0001"]}]
    assert not scope.inspect_probe("multi-module", result)["probe_passed"]


def test_long_source_requires_all_blocks_and_multiple_tasks(tmp_path, monkeypatch):
    run, result = probe_fixture(tmp_path, monkeypatch)
    report = scope.inspect_probe("long-source", result)
    assert not report["probe_passed"]
    paper = Path(run["source"]["path"])
    paper.write_text(scope.long_source(paper.read_text()))
    run["tasks"] = [{"stage": "extract"}] * 3
    assert scope.inspect_probe("long-source", result)["probe_passed"]
    run["modules"]["statistics"]["provided_blocks"] = []
    assert not scope.inspect_probe("long-source", result)["probe_passed"]


def test_scope_main_uses_only_disposable_explicit_input_and_records_harness(tmp_path, monkeypatch):
    monkeypatch.delenv("HERMES_SESSION_ID", raising=False)
    monkeypatch.setattr(scope.shutil, "which", lambda name: "/bin/true")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "case-01.md").write_text("# Synthetic ordinary source")
    (corpus / "case-02.md").write_text("# Synthetic scope source")
    seen = []

    def run_case(args, case, module, settings, deadline):
        seen.append((case, args.requested_modules, args.language))
        return {"engineering_passed": False, "error": "synthetic unavailable gateway"}

    monkeypatch.setattr(
        scope, "load_pilot", lambda: SimpleNamespace(run_case=run_case, __file__=SCRIPT)
    )
    output = tmp_path / "new-output"
    assert (
        scope.main(
            [
                "multi-module",
                "--gateway-url",
                "http://127.0.0.1:8091/v1",
                "--model",
                "local",
                "--context-length",
                "262144",
                "--corpus",
                str(corpus),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert seen == [("case-02", ["statistics", "logic"], "en")]
    assert (output / "probe.json").is_file()


def test_fault_probe_does_not_relabel_an_ordinary_failure_as_success(tmp_path, monkeypatch):
    run, result = probe_fixture(tmp_path, monkeypatch)
    run["modules"]["statistics"]["status"] = "failed"
    run["modules"]["logic"] = {
        **copy.deepcopy(run["modules"]["statistics"]),
        "status": "complete",
        "facts": [],
        "reads": [],
        "connections": [],
    }
    result["engineering_passed"] = False
    result["checks"]["module_completed"] = False
    assert not scope.inspect_probe("module-failure", result)["probe_passed"]
    result["injected_fault"] = {"two_refusals_observed": True}
    assert scope.inspect_probe("module-failure", result)["probe_passed"]
    assert not scope.inspect_probe("multi-module", result)["probe_passed"]
    result["checks"]["receipt_integrity"] = False
    assert not scope.inspect_probe("module-failure", result)["probe_passed"]


@pytest.mark.parametrize("bootstrap", [0, 1])
def test_fault_is_injected_only_after_an_issued_checkpoint(
    tmp_path, monkeypatch, bootstrap,
):
    root = tmp_path / "test-profile"
    work = root / "work"
    work.mkdir(parents=True)
    sequence = []

    def invoke(*args):
        sequence.append("hermes")

    def inject(*args):
        sequence.append("injected")
        return {"two_refusals_observed": True}

    def saved_run(_):
        if not sequence:
            return None
        state = {
            "cursor": 0, "attempts": {}, "issued_task": "task-0001",
            "modules": {"statistics": {"status": "running", "provided_blocks": ["b1"]}},
        }
        if bootstrap and sequence.count("hermes") == 1:
            state.pop("issued_task")
            state["modules"]["statistics"].update(status="pending", provided_blocks=[])
        return state

    pilot = SimpleNamespace(
        _run_turn=invoke, saved_run=saved_run, checkpoint_state=scope.load_pilot().checkpoint_state,
    )

    def run_case(*args):
        for index in range(3 + bootstrap):
            command = ["hermes"] + (["--resume", "same-session"] if index else [])
            pilot._run_turn(command, {"HERMES_HOME": str(root)}, work, work / "log", 100)
        return {"engineering_passed": False}

    pilot.run_case = run_case
    monkeypatch.setattr(scope, "inject_module_failure", inject)
    args = SimpleNamespace(mode="module-failure", output=tmp_path, timeout=30)
    result = scope.run_probe(args, "case-02", {}, pilot)
    assert sequence == ["hermes"] * (1 + bootstrap) + ["injected", "hermes", "hermes"]
    assert result["injected_fault"]["instrumented_invocation"] == 2 + bootstrap
    assert result["injected_fault"]["two_refusals_observed"]
    assert pilot._run_turn is invoke
    assert read_json(tmp_path / "fault-injection.json")["two_refusals_observed"]


def test_fault_injection_refuses_unrelated_or_unpaused_runs(tmp_path):
    import pytest

    from closed_review.errors import ReviewError

    pilot = SimpleNamespace(saved_run=lambda root: {"cursor": 1, "modules": {"statistics": {}}})
    with pytest.raises(ReviewError, match="paused disposable"):
        scope.inject_module_failure(tmp_path, {"HERMES_HOME": str(tmp_path)}, pilot)


def test_real_workflow_fault_stops_only_statistics_and_preserves_rejections(support_env, tmp_path):
    run_id = begin(support_env, ["statistics", "logic"])
    workflow.next_task(run_id)
    root = workflow._root(run_id)
    pilot = SimpleNamespace(
        saved_run=lambda _: workflow._load(root),
        _session=lambda _: "synthetic-cli-adapter",
    )
    env = dict(os.environ, HERMES_HOME=str(tmp_path / "disposable"))
    Path(env["HERMES_HOME"]).mkdir()
    (Path(env["HERMES_HOME"]) / "config.yaml").write_text(yaml.safe_dump({"auxiliary": {}}))
    result = scope.inject_module_failure(Path(env["HERMES_HOME"]), env, pilot)
    assert result["two_refusals_observed"]
    state = workflow.status(run_id)["modules"]
    assert state["statistics"]["status"] == "failed" and state["logic"]["status"] == "pending"
    assert len(list((root / "answers").glob("task-0001-rejected-*.json"))) == 2
    run = finish(run_id)
    assert run["modules"]["logic"]["status"] == "complete"
    assert run["modules"]["statistics"]["status"] == "failed"
    assert not run["notes"]


def test_fault_injection_matches_real_terminal_routes_without_bypassing_guard(
    managed, monkeypatch, tmp_path
):
    import pytest

    active(managed, monkeypatch)
    monkeypatch.setenv("CREVIEW_HOME", str(managed / "review-data"))
    config = yaml.safe_load((managed / "config.yaml").read_text())
    for field in ("provider", "model"):
        monkeypatch.setenv(
            f"AUXILIARY_VISION_{field.upper()}", config["auxiliary"]["vision"][field]
        )
    start_session(None, live=False, support=True)
    paper = tmp_path / "synthetic.md"
    paper.write_text("# Methods\n\nA synthetic manuscript with 20 events among 100 patients.")
    run_id = workflow.start(paper, ["statistics", "logic"])["run_id"]
    workflow.next_task(run_id)
    root = workflow._root(run_id)
    pilot = SimpleNamespace(
        saved_run=lambda _: workflow._load(root),
        _session=lambda _: os.environ["HERMES_SESSION_ID"],
    )
    env = {key: value for key, value in os.environ.items() if not key.startswith("AUXILIARY_")}
    with environment(env):
        with pytest.raises(ReviewError, match="routes changed"):
            workflow.next_task(run_id)
        injected = scope.inject_module_failure(managed, env, pilot)
    assert injected["two_refusals_observed"]
    state = workflow._load(root)
    assert state["modules"]["statistics"]["status"] == "failed"
    assert state["modules"]["logic"]["status"] == "pending"
    assert len(list((root / "answers").glob("task-0001-rejected-*.json"))) == 2
    original_route = state["route"]
    config["auxiliary"]["vision"]["model"] = "not-the-local-model"
    (managed / "config.yaml").write_text(yaml.safe_dump(config))
    with environment(env), pytest.raises(ReviewError, match="preflight|ready"):
        workflow.next_task(run_id)
    assert workflow._load(root)["route"] == original_route
