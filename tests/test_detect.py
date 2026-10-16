import httpx
import pytest
import yaml
from test_hermes import make_profile

from closed_review import detect
from closed_review.errors import ReviewError
from closed_review.settings import trusted_gateway


class Models:
    def __init__(self, ids):
        self.ids = ids

    def raise_for_status(self):
        return None

    def json(self):
        return {"data": [{"id": name} for name in self.ids]}


@pytest.fixture
def unconfigured(isolated_env, monkeypatch):
    for name in ("CREVIEW_TRUSTED_MODEL_URL", "CREVIEW_MODEL", "CREVIEW_TRUSTED_MODELS"):
        monkeypatch.delenv(name, raising=False)
    return isolated_env


def serve(monkeypatch, servers: dict[str, list[str]]) -> list[str]:
    asked: list[str] = []

    def fake_get(url, headers=None, timeout=None):
        asked.append(url)
        for base, ids in servers.items():
            if url == f"{base}/v1/models":
                return Models(ids)
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(detect.httpx, "get", fake_get)
    return asked


def write_config(profile, **changes):
    config = yaml.safe_load((profile / "config.yaml").read_text())
    config.update(changes)
    (profile / "config.yaml").write_text(yaml.safe_dump(config))


def test_detect_adopts_hermes_main_model_on_local_server(unconfigured, monkeypatch) -> None:
    profile = make_profile(unconfigured)
    write_config(profile, delegation={"model": "gemma-4-31b"})
    serve(monkeypatch, {"http://127.0.0.1:8091": ["qwen3.8-flash-next", "gemma-4-31b"]})

    dry = detect.detect_gateway("reviewer")
    assert dry["applied"] is False
    assert trusted_gateway()["url"] is None
    assert dry["selected"]["url"] == "http://127.0.0.1:8091/v1"

    done = detect.detect_gateway("reviewer", apply=True)
    assert done["applied"]
    gateway = trusted_gateway()
    assert gateway["url"] == "http://127.0.0.1:8091/v1"
    assert gateway["trusted_models"] == ["qwen3.8-flash-next", "gemma-4-31b"]


def test_detect_never_adopts_a_cloud_main_model(unconfigured, monkeypatch) -> None:
    profile = make_profile(unconfigured)
    write_config(profile, providers={"local": {"base_url": "https://api.openai.com/v1"}})
    asked = serve(monkeypatch, {})

    result = detect.detect_gateway("reviewer")

    assert result["selected"] is None
    assert result["candidates"][0]["category"] == "public"
    assert not any("openai.com" in url for url in asked)
    with pytest.raises(ReviewError, match="no gateway adopted"):
        detect.detect_gateway("reviewer", apply=True)


def test_detect_probes_common_local_ports(unconfigured, monkeypatch) -> None:
    profile = make_profile(unconfigured)
    write_config(profile, providers={"local": {"base_url": "https://api.example.com/v1"}})
    serve(monkeypatch, {"http://127.0.0.1:11434": ["qwen3:32b"]})

    result = detect.detect_gateway("reviewer", apply=True)

    assert result["selected"]["source"] == "Ollama"
    assert trusted_gateway()["model"] == "qwen3:32b"


def test_detect_asks_for_model_when_server_lists_several(unconfigured, monkeypatch) -> None:
    profile = make_profile(unconfigured)
    write_config(profile, providers={"local": {"base_url": "https://api.example.com/v1"}})
    serve(monkeypatch, {"http://127.0.0.1:11434": ["a", "b"]})

    assert "choose one with --model" in detect.detect_gateway("reviewer")["reason"]
    assert detect.detect_gateway("reviewer", model="b")["selected"]["model"] == "b"


def test_detect_resolves_hostnames_before_trusting_them(monkeypatch) -> None:
    def resolve(address):
        return lambda host, port: [(None, None, None, None, (address, 0))]

    monkeypatch.setattr(detect.socket, "getaddrinfo", resolve("192.168.1.20"))
    assert detect._resolved_class("http://gpu-box:8000/v1") == "private-network"
    monkeypatch.setattr(detect.socket, "getaddrinfo", resolve("8.8.8.8"))
    assert detect._resolved_class("http://gpu-box:8000/v1") == "public"
