import json

import pytest
import yaml
from test_hermes import make_profile

from closed_review import hermes
from closed_review.cli import main
from closed_review.errors import ReviewError
from closed_review.settings import gateway_path, set_gateway, trusted_gateway


@pytest.fixture
def unconfigured(isolated_env, monkeypatch):
    for name in ("CREVIEW_TRUSTED_MODEL_URL", "CREVIEW_MODEL", "CREVIEW_TRUSTED_MODELS"):
        monkeypatch.delenv(name, raising=False)
    return isolated_env


def test_there_is_no_default_gateway(unconfigured) -> None:
    assert trusted_gateway()["url"] is None
    assert trusted_gateway()["trusted_models"] == []
    make_profile(unconfigured)
    hermes.install_skill("reviewer", apply=True)

    report = hermes.inspect_profile("reviewer", live=False)

    assert not report["ready"]
    assert any("no trusted model gateway is configured" in p for p in report["problems"])


def test_stored_gateway_is_private_and_used_by_doctor(unconfigured) -> None:
    saved = set_gateway("http://127.0.0.1:8091/v1/", "qwen3.8-flash-next", ["gemma-4-31b"])
    assert saved["url"] == "http://127.0.0.1:8091/v1"
    assert saved["trusted_models"] == ["qwen3.8-flash-next", "gemma-4-31b"]
    assert gateway_path().stat().st_mode & 0o777 == 0o600
    make_profile(unconfigured)
    hermes.install_skill("reviewer", apply=True)

    report = hermes.inspect_profile("reviewer", live=False)

    assert report["ready"], report["problems"]
    assert report["trusted_models"] == ["qwen3.8-flash-next", "gemma-4-31b"]


def test_environment_overrides_stored_gateway(unconfigured, monkeypatch) -> None:
    set_gateway("http://127.0.0.1:8091/v1", "qwen3.8-flash-next")
    monkeypatch.setenv("CREVIEW_MODEL", "other-model")
    monkeypatch.setenv("CREVIEW_TRUSTED_MODELS", "")
    gateway = trusted_gateway()
    assert gateway["model"] == "other-model"
    assert gateway["trusted_models"] == ["other-model"]


def test_gateway_rejects_bad_values(unconfigured) -> None:
    with pytest.raises(ReviewError):
        set_gateway("127.0.0.1:8091", "m")
    with pytest.raises(ReviewError):
        set_gateway("http://127.0.0.1:8091/v1", " ")


def test_config_cli_round_trip(unconfigured, capsys) -> None:
    code = main(
        [
            "config",
            "gateway",
            "--url",
            "http://10.0.0.5:8000/v1",
            "--model",
            "m1",
            "--trusted-model",
            "m2",
        ]
    )
    assert code == 0
    capsys.readouterr()
    assert main(["config", "show"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["url"] == "http://10.0.0.5:8000/v1"
    assert shown["trusted_models"] == ["m1", "m2"]


def test_doctor_warns_outside_verified_hermes_schema(isolated_env) -> None:
    profile = make_profile(isolated_env)
    config = yaml.safe_load((profile / "config.yaml").read_text())
    config["_config_version"] = 50
    (profile / "config.yaml").write_text(yaml.safe_dump(config))
    hermes.install_skill("reviewer", apply=True)
    assert not any(
        "schema" in w for w in hermes.inspect_profile("reviewer", live=False)["warnings"]
    )

    config["_config_version"] = 60
    (profile / "config.yaml").write_text(yaml.safe_dump(config))
    report = hermes.inspect_profile("reviewer", live=False)
    assert report["ready"]
    assert any("schema 60 is outside" in w for w in report["warnings"])
