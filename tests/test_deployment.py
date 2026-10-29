import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from closed_review import deployment, hermes, smoke
from closed_review.cli import main
from closed_review.errors import ReviewError
from closed_review.io import data_home


def setup(**kwargs):
    return deployment.setup_profile(
        "closed-review",
        gateway_url="http://127.0.0.1:8091/v1",
        model="qwen3.8-flash-next",
        **kwargs,
    )


def test_preview_creates_nothing_and_apply_isolated(isolated_env, monkeypatch):
    root = Path(setup()["profile_root"])
    assert not root.exists()
    setup(apply=True)
    config = yaml.safe_load((root / "config.yaml").read_text())
    assert smoke.review_profile_problems(config) == []
    assert (root / "skills/journal-article-review/SKILL.md").is_file()
    assert not (isolated_env / "data/gateway.json").exists()
    monkeypatch.delenv("CREVIEW_TRUSTED_MODEL_URL")
    monkeypatch.delenv("CREVIEW_MODEL")
    report = hermes.inspect_profile("closed-review", live=False)
    assert report["ready"], report["problems"]
    assert report["gateway_settings"] == str(root / "review-data/gateway.json")
    assert report["capability"]["review_quality"] == "not_assessed"
    assert os.environ["CREVIEW_HOME"] == str(isolated_env / "data")
    monkeypatch.delenv("CREVIEW_HOME")
    monkeypatch.setenv("HERMES_HOME", str(root))
    monkeypatch.setenv("CREVIEW_HOME", str(isolated_env / "stale-personal-store"))
    assert data_home() == root / "review-data"


def test_explicit_profile_preflight_uses_that_profiles_store(isolated_env, monkeypatch):
    from closed_review.session import start_session

    root = Path(setup(apply=True)["profile_root"])
    monkeypatch.delenv("CREVIEW_TRUSTED_MODEL_URL")
    monkeypatch.delenv("CREVIEW_MODEL")
    record = start_session("closed-review", live=False)
    assert (root / "review-data/preflights" / f"{record['session_id']}.json").is_file()
    assert not (isolated_env / "data/preflights").exists()


def test_unmanaged_profile_never_overwritten(isolated_env):
    root = Path(setup()["profile_root"])
    root.mkdir(parents=True)
    (root / "config.yaml").write_text("personal: true\n")
    with pytest.raises(ReviewError, match="unmanaged"):
        setup(apply=True)
    assert (root / "config.yaml").read_text() == "personal: true\n"
    assert not (root / deployment.PROFILE_MANIFEST).exists()


def test_update_preserves_config_and_records(isolated_env):
    root = Path(setup(apply=True)["profile_root"])
    config_path = root / "config.yaml"
    changed = config_path.read_text() + "user_preference: keep\n"
    config_path.write_text(changed)
    (root / "review-data/keep.txt").write_text("review records")
    assert setup(apply=True)["existing_config_preserved"]
    assert config_path.read_text() == changed
    assert (root / "review-data/keep.txt").read_text() == "review records"


@pytest.mark.skipif(os.name == "nt", reason="Unix Hermes terminal snapshot")
def test_launcher_survives_environment_only_shell_snapshot(isolated_env):
    root = Path(setup(apply=True)["profile_root"])
    # Hermes snapshots exported variables, not shell functions. Start a fresh shell with only
    # that PATH and prove it selects this runner instead of the normal user installation.
    launchers = str(root / "review-bin")
    env = dict(os.environ, PATH=launchers + os.pathsep + os.environ["PATH"])
    result = subprocess.run(
        ["sh", "-c", "creview --version"], env=env, text=True, capture_output=True, check=True
    )
    from closed_review import __version__

    assert result.stdout.strip() == f"creview {__version__}"
    (root / "review-shell.sh").write_text("user modification\n")
    with pytest.raises(ReviewError, match="edited"):
        setup(apply=True)


@pytest.mark.parametrize("profile", ["default", "../escape", "review/name", "x;touch", ""])
def test_profile_names_are_not_paths_or_commands(isolated_env, profile):
    with pytest.raises(ReviewError):
        deployment.setup_profile(profile, gateway_url="http://127.0.0.1:8091/v1", model="local")


@pytest.mark.parametrize(
    "url", ["https://8.8.8.8/v1", "http://u:p@localhost/v1", "http://localhost/v1?key=x"]
)
def test_setup_rejects_public_or_credential_bearing_endpoints(isolated_env, url):
    with pytest.raises(ReviewError):
        deployment.setup_profile(gateway_url=url, model="local", apply=True)
    assert not (isolated_env / "hermes").exists()


def test_context_and_changed_model_require_deliberate_setup(isolated_env):
    with pytest.raises(ReviewError, match="65536"):
        setup(context_length=32768)
    setup(apply=True)
    with pytest.raises(ReviewError, match="settings differ"):
        setup(context_length=131072, apply=True)


def test_profile_drift_detected(isolated_env):
    root = Path(setup(apply=True)["profile_root"])
    config = yaml.safe_load((root / "config.yaml").read_text())
    config["memory"]["memory_enabled"] = True
    config["mcp_servers"] = {"external": {}}
    config["auxiliary"]["background_review"]["enabled"] = True
    assert len(smoke.review_profile_problems(config)) == 3


def test_smoke_drops_inherited_routing_and_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "do-not-copy")
    monkeypatch.setenv("AUXILIARY_COMPRESSION_PROVIDER", "openrouter")
    monkeypatch.setenv("HERMES_SESSION_ID", "personal-session")
    monkeypatch.setenv("CREVIEW_MODEL_API_KEY", "trusted-endpoint-only")
    env = smoke._child_environment(tmp_path)
    assert "OPENROUTER_API_KEY" not in env
    assert "AUXILIARY_COMPRESSION_PROVIDER" not in env
    assert "HERMES_SESSION_ID" not in env
    assert env["OPENAI_API_KEY"] == "trusted-endpoint-only"
    assert env["HERMES_HOME"] == str(tmp_path)


def test_empty_or_forged_smoke_outputs_do_not_pass(tmp_path):
    assert not any(smoke._audit(tmp_path, "expected", "my response").values())
    (tmp_path / "work").mkdir()
    (tmp_path / "work/runner.json").write_text(json.dumps({"sums_sha256": "wrong"}))
    assert smoke._audit(tmp_path, "expected", "my response")["runner_identity"] is False


def test_prepared_export_and_verified_acceptance_are_not_completed_exports(tmp_path):
    from closed_review.io import atomic_write_json

    atomic_write_json(tmp_path / "work/runner.json", {"sums_sha256": "expected"})
    atomic_write_json(
        tmp_path / "review-data/scans/scan-example/scan.json",
        {
            "phase": "ready",
            "surfaced": {
                "F1": {
                    "disposition": "accepted",
                    "response": {"verified": True, "words": "my response"},
                }
            },
        },
    )
    atomic_write_json(tmp_path / "review-data/exports/direct-example/export.json", {})
    checks = smoke._audit(tmp_path, "expected", "my response")
    assert checks["runner_identity"] and checks["scan_completed"]
    assert checks["reviewer_response_verified"]
    assert not checks["three_export_files"]
    assert not checks["receipt_verified"]
    assert not checks["preflight_recorded"]


def test_managed_profile_cannot_finalize_missing_or_empty_drafts(isolated_env, monkeypatch):
    from closed_review.direct import finalize_direct_export, prepare_direct_export

    root = Path(setup(apply=True)["profile_root"])
    monkeypatch.setenv("HERMES_HOME", str(root))
    prepared = prepare_direct_export()
    directory = Path(prepared["directory"])
    Path(prepared["output_paths"]["authors"]).write_text("Author draft")
    Path(prepared["output_paths"]["editor"]).write_text("Editor draft")
    for content in (None, "  \n"):
        if content is not None:
            Path(prepared["output_paths"]["development"]).write_text(content)
        with pytest.raises(ReviewError, match="review-development.md"):
            finalize_direct_export(prepared["export_id"])
        assert not (directory / "receipt.json").exists()
    Path(prepared["output_paths"]["development"]).write_text("Development record")
    result = finalize_direct_export(prepared["export_id"])
    assert set(result["subjects"]) == {"authors", "editor", "development"}


def test_smoke_checks_linkage_and_explicit_severity_not_just_receipt(isolated_env, monkeypatch):
    from closed_review.direct import prepare_direct_export
    from closed_review.io import atomic_write_json
    from closed_review.session import session_key

    root = Path(setup(apply=True)["profile_root"])
    monkeypatch.setenv("HERMES_HOME", str(root))
    monkeypatch.setenv("HERMES_SESSION_ID", "synthetic-session")
    key, _ = session_key()
    scan_id = "scan-20261028T120000Z-0123abcd"
    response = "I accept this concern."
    atomic_write_json(
        root / "review-data/scans" / scan_id / "scan.json",
        {
            "schema_version": "2",
            "scan_id": scan_id,
            "session_id": key,
            "phase": "ready",
            "surfaced": {
                "F1": {
                    "disposition": "accepted",
                    "response": {"words": response, "verified": True},
                }
            },
            "review": {"findings": [{"id": "F1", "model_severity": "minor"}]},
        },
    )
    atomic_write_json(root / "work/runner.json", {"sums_sha256": "expected"})
    prepared = prepare_direct_export(scan_id=scan_id)
    for kind, path in prepared["output_paths"].items():
        Path(path).write_text("One major inconsistency." if kind == "editor" else "Draft text.")
    atomic_write_json(Path(prepared["receipt_path"]), {"preflight": {"status": "passed"}})
    monkeypatch.setattr(smoke, "verify_receipt", lambda _: {"verified": True})
    result = smoke._audit(root, "expected", response)
    assert result["scan_linked"] and result["receipt_verified"]
    assert not result["explicit_severity_consistent"]
    Path(prepared["output_paths"]["editor"]).write_text("One minor inconsistency.")
    assert all(smoke._audit(root, "expected", response).values())
    Path(prepared["output_paths"]["development"]).write_text(
        "Minor-severity candidates were not surfaced."
    )
    assert not smoke._audit(root, "expected", response)["no_explicit_unsurfaced_mentions"]


def test_smoke_stops_on_wrong_runner_without_touching_original_profile(isolated_env, monkeypatch):
    root = Path(setup(apply=True)["profile_root"])
    original = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    report = hermes.inspect_profile("closed-review", live=False)
    monkeypatch.setattr(smoke, "inspect_profile", lambda *_: report)
    monkeypatch.setattr(smoke.shutil, "which", lambda _: "/fake/hermes")
    calls = []

    def wrong_runner(command, env, work, log, deadline):
        calls.append(command)
        (work / "runner.json").write_text(json.dumps({"sums_sha256": "old-installation"}))

    monkeypatch.setattr(smoke, "_run_turn", wrong_runner)
    result = smoke.run_smoke("closed-review")
    assert not result["passed"]
    assert "different creview build" in result["error"]
    assert len(calls) == 1
    assert "artifacts" not in result
    assert original == {
        str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()
    }


def test_setup_cli_and_version_metadata(isolated_env, capsys):
    assert (
        main(
            [
                "hermes",
                "setup-profile",
                "--gateway-url",
                "http://localhost:8091/v1",
                "--model",
                "local",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["applied"] is False
