"""Post-reboot orchestration refuses replacement and observes gaps without repairs."""

import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def controller():
    path = Path(__file__).resolve().parents[1] / "evals/deployment/b15-restored-controller.py"
    spec = importlib.util.spec_from_file_location("restored_controller", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def no_spawn(*args, **kwargs):
    pytest.fail("a read-only check must not spawn or restart a test")


def test_existing_attempt_is_never_replaced(controller, tmp_path, monkeypatch):
    state = tmp_path / "suite-state.json"
    state.write_text('{"status":"running","original":true}')
    original = state.read_bytes()
    monkeypatch.setattr(controller.subprocess, "Popen", no_spawn)
    with pytest.raises(AssertionError, match="preserve this attempt"):
        controller.main(tmp_path)
    assert state.read_bytes() == original
    assert list(tmp_path.iterdir()) == [state]


def test_wrong_bundle_is_rejected_before_process_inspection(controller, tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "SHA256SUMS").write_text("wrong frozen bundle")
    monkeypatch.setattr(controller, "installed_identity",
                        lambda: {"sums_sha256": controller.RUNNER})
    monkeypatch.setattr(controller, "ticks", no_spawn)
    monkeypatch.setattr(controller.subprocess, "Popen", no_spawn)
    with pytest.raises(AssertionError):
        controller.verify(tmp_path, {})


def test_partial_gap_observation_keeps_original_run_unchanged(controller, tmp_path, monkeypatch):
    path = tmp_path / "public-pairs/case/hermes/review-data/support/support-fixture/run.json"
    path.parent.mkdir(parents=True)
    gap = {"task_id": "task-0001", "kind": "fact_cap", "block_ids": ["p1"],
           "role": "outcome", "detail": "Test fixture only: remaining reconstruction."}
    run = {"id": "support-fixture", "cursor": 4, "tasks": [{}, {}, {}, {}], "modules": {
        "statistics": {"status": "partial", "facts": [{}] * 24, "calculations": [],
                       "observations": [], "failures": [], "extraction_limits": [],
                       "coverage_gaps": [gap]}}}
    path.write_text(json.dumps(run))
    original = path.read_bytes()
    monkeypatch.setattr(controller.subprocess, "Popen", no_spawn)
    controller.progress(tmp_path, {"name": "public-pairs", "pid": 123})
    saved = json.loads((tmp_path / "latest-observation.json").read_text())
    state = saved["records"][0]["modules"]["statistics"]
    assert state["status"] == "partial" and state["coverage_gaps"] == [gap]
    assert state["facts"] == 24 and state["extraction_limits"] == []
    assert path.read_bytes() == original


def test_unreadable_observation_is_recorded_without_restarting(controller, tmp_path, monkeypatch):
    path = tmp_path / "public-pairs/case/review-data/support/support-fixture/run.json"
    path.parent.mkdir(parents=True)
    path.write_text("incomplete observation fixture")
    monkeypatch.setattr(controller.subprocess, "Popen", no_spawn)
    controller.progress(tmp_path, {"name": "public-pairs", "pid": 123})
    saved = json.loads((tmp_path / "latest-observation.json").read_text())
    assert saved["observation_errors"] == ["JSONDecodeError"] and saved["records"] == []
    assert path.read_text() == "incomplete observation fixture"
