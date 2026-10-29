import json
import sqlite3
from pathlib import Path

import pytest
import yaml
from conftest import reviewer_says

from closed_review.deployment import setup_profile
from closed_review.errors import ReviewError
from closed_review.hermes import inspect_profile
from closed_review.session import start_session
from closed_review.smoke import _child_environment, environment
from closed_review.support import workflow
from closed_review.support.budgets import TOOL_OUTPUT

URL = "http://127.0.0.1:8091/v1"
MODEL = "qwen3.8-flash-next"


@pytest.fixture
def managed(isolated_env):
    return Path(
        setup_profile("strict", gateway_url=URL, model=MODEL, context_length=65536, apply=True)[
            "profile_root"
        ]
    )


def edit(root, change):
    path = root / "config.yaml"
    config = yaml.safe_load(path.read_text())
    change(config)
    path.write_text(yaml.safe_dump(config))


def active(root, monkeypatch, *, provider="custom", endpoint=URL, model=MODEL):
    monkeypatch.setenv("HERMES_HOME", str(root))
    monkeypatch.setenv("HERMES_SESSION_ID", "current-private-test-session")
    reviewer_says(root, "current-private-test-session", "Review this synthetic manuscript.")
    with sqlite3.connect(root / "state.db") as db:
        db.execute(
            "CREATE TABLE sessions (id TEXT, model TEXT, billing_provider TEXT, "
            "billing_base_url TEXT)"
        )
        db.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?)",
            ("current-private-test-session", model, provider, endpoint),
        )


def test_strict_checks_do_not_confuse_runtime_safety_with_quality(managed):
    report = inspect_profile("strict", live=False)
    assert report["ready"] and report["support_readiness"]["ready"]
    assert report["support_readiness"]["quality"] == "not_qualified"
    assert report["support_readiness"]["network_isolation"] == "not_enforced"


@pytest.mark.parametrize("key", list(TOOL_OUTPUT))
@pytest.mark.parametrize("bad", [None, False, "50000", -1, 1])
def test_tool_output_limits_are_explicit_and_cannot_clip_managed_tasks(managed, key, bad):
    edit(managed, lambda config: config["tool_output"].update({key: bad}))
    report = inspect_profile("strict", live=False)
    assert not report["support_readiness"]["ready"]
    assert any(f"tool_output.{key}" in error for error in report["support_readiness"]["problems"])


def test_missing_tool_limits_do_not_silently_rely_on_hermes_defaults(managed):
    edit(managed, lambda config: config.pop("tool_output"))
    report = inspect_profile("strict", live=False)
    assert not report["support_readiness"]["ready"]
    assert len([e for e in report["support_readiness"]["problems"] if "tool_output." in e]) == 3


def test_changed_tool_limits_require_a_new_run_even_when_both_settings_are_allowed(
    managed, monkeypatch, tmp_path
):
    active(managed, monkeypatch)
    start_session(None, live=False, support=True)
    paper = tmp_path / "synthetic.md"
    paper.write_text("# Methods\n\nA synthetic study with 20 patients.")
    run_id = workflow.start(paper, ["statistics"])["run_id"]
    edit(managed, lambda config: config["tool_output"].update(max_bytes=60000))
    assert inspect_profile(None, live=False)["support_readiness"]["ready"]
    with pytest.raises(ReviewError, match="routes changed"):
        workflow.next_task(run_id)


@pytest.mark.parametrize("task", ["compression", "title_generation", "vision", "background_review"])
def test_every_auxiliary_lane_requires_an_explicit_pin(managed, task):
    edit(managed, lambda c: c["auxiliary"].pop(task))
    report = inspect_profile("strict", live=False)
    assert report["ready"]  # Legacy route inheritance compatibility is not support readiness.
    assert not report["support_readiness"]["ready"]
    assert any(f"auxiliary.{task}" in p for p in report["support_readiness"]["problems"])


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c["memory"].update(memory_enabled=True),
        lambda c: c.update(mcp_servers={"external": {"url": "https://example.test"}}),
        lambda c: c["skills"].update(external_dirs=["/unreviewed/skills"]),
        lambda c: c["platform_toolsets"].update(cli=["terminal", "file", "skills", "web"]),
        lambda c: c.update(_config_version=999),
        lambda c: c["model"].pop("context_length"),
        lambda c: c["platform_toolsets"].update(tui=["terminal", "file", "skills", "browser"]),
        lambda c: c["terminal"].update(backend="docker"),
        lambda c: c["terminal"].update(auto_source_bashrc=True),
        lambda c: c["auth"].update(adopt_external_logins=True),
        lambda c: c["telemetry"]["shared_metrics"].update(send=True),
    ],
)
def test_unsafe_or_unverified_profile_settings_fail_closed(managed, change):
    edit(managed, change)
    report = inspect_profile("strict", live=False)
    assert not report["support_readiness"]["ready"]
    assert report["support_readiness"]["problems"]


def test_cloud_credentials_are_named_but_never_echoed(managed, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "PRIVATE-KEY-NEVER-PRINT")
    report = inspect_profile("strict", live=False)
    assert report["ready"] and not report["support_readiness"]["ready"]
    assert "OPENROUTER_API_KEY" in json.dumps(report)
    assert "PRIVATE-KEY-NEVER-PRINT" not in json.dumps(report)
    with pytest.raises(ReviewError, match="OPENROUTER_API_KEY"):
        start_session("strict", live=False, support=True)


def test_proxy_requires_exact_gateway_bypass_and_child_environment_is_scrubbed(
    managed, monkeypatch
):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example.test:3128")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("no_proxy", "")
    assert not inspect_profile("strict", live=False)["support_readiness"]["ready"]
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    assert inspect_profile("strict", live=False)["support_readiness"]["ready"]
    env = _child_environment(managed, gateway_url=URL)
    assert "HTTPS_PROXY" not in env and env["NO_PROXY"] == "127.0.0.1"


def test_only_explicit_private_endpoint_credential_is_inherited(managed, monkeypatch):
    monkeypatch.setenv("CREVIEW_MODEL_API_KEY", "private-gateway-key")
    env = _child_environment(managed, gateway_url=URL)
    with environment(env):
        report = inspect_profile(None, live=False)
    assert env["OPENAI_BASE_URL"] == URL
    assert report["support_readiness"]["ready"], report["support_readiness"]


@pytest.mark.parametrize(
    "provider,endpoint,model",
    [
        ("openrouter", "https://openrouter.ai/api/v1", "cloud-model"),
        ("custom", "https://outside.example.test/v1", MODEL),
        ("custom", URL, "not-allowlisted"),
    ],
)
def test_live_session_overrides_cannot_hide_behind_a_safe_profile(
    managed, monkeypatch, provider, endpoint, model
):
    active(managed, monkeypatch, provider=provider, endpoint=endpoint, model=model)
    report = inspect_profile(None, live=False)
    assert report["ready"] and not report["support_readiness"]["ready"]
    assert report["support_readiness"]["runtime"]["status"] == "mismatch"
    with pytest.raises(ReviewError, match="live Hermes session route"):
        start_session(None, live=False, support=True)


def test_actual_route_is_verified_and_later_allowlisted_model_switch_still_blocks_resume(
    managed,
    monkeypatch,
    tmp_path,
):
    active(managed, monkeypatch)
    monkeypatch.setenv("CREVIEW_TRUSTED_MODELS", "gemma-4-31b")
    start_session(None, live=False, support=True)
    paper = tmp_path / "synthetic.md"
    paper.write_text("# Methods\n\nA synthetic manuscript with 20 events among 100 patients.")
    run_id = workflow.start(paper, ["statistics"])["run_id"]
    assert workflow.next_task(run_id)["task"]["stage"] == "extract"
    with sqlite3.connect(managed / "state.db") as db:
        db.execute("UPDATE sessions SET model = 'gemma-4-31b'")
    assert inspect_profile(None, live=False)["support_readiness"]["ready"]
    with pytest.raises(ReviewError, match="routes changed"):
        workflow.next_task(run_id)


def test_missing_live_route_metadata_is_not_treated_as_config_verified(managed, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(managed))
    monkeypatch.setenv("HERMES_SESSION_ID", "missing-session")
    report = inspect_profile(None, live=False)
    assert not report["support_readiness"]["ready"]
    assert report["support_readiness"]["runtime"]["status"] == "unverifiable"


def test_managed_launcher_tampering_stops_support_without_modifying_it(managed):
    launcher = managed / "review-bin/creview"
    launcher.write_text("edited launcher")
    report = inspect_profile("strict", live=False)
    assert not report["support_readiness"]["ready"]
    assert any("managed runner changed" in p for p in report["support_readiness"]["problems"])
    assert launcher.read_text() == "edited launcher"
