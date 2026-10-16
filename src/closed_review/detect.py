"""Find the trusted model server instead of asking the reviewer to type it.

Candidates are the Hermes profile's main model and the default ports of common local servers. A
candidate is adopted only when it is on this computer or a private network and answers
`/v1/models`; a cloud endpoint is never adopted automatically, even when Hermes uses it.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from typing import Any
from urllib.parse import urlsplit

import httpx

from .errors import ReviewError
from .hermes import _load_config, _models_url, _selected_model_and_provider, profile_root
from .receipts import SHARED_ADDRESS_SPACE, endpoint_class
from .routes import check_routes, default_base_url, normalized_endpoint, read_env_file
from .settings import set_gateway, trusted_gateway

LOCAL_SERVERS = (
    ("Ollama", "http://127.0.0.1:11434/v1"),
    ("LM Studio", "http://127.0.0.1:1234/v1"),
    ("llama.cpp", "http://127.0.0.1:8080/v1"),
    ("vLLM", "http://127.0.0.1:8000/v1"),
)
TRUSTED_CLASSES = {"loopback", "private-network"}


def _resolved_class(url: str) -> str:
    """Classify a URL, resolving a hostname so a name for a LAN machine can count as private."""
    category = endpoint_class(url)
    if category != "hostname":
        return category
    host = urlsplit(url).hostname or ""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return "unresolved"
    addresses = {ipaddress.ip_address(info[4][0].split("%")[0]) for info in infos}
    if addresses and all(
        a.is_loopback or a.is_private or a in SHARED_ADDRESS_SPACE for a in addresses
    ):
        return "private-network"
    return "public"


def _probe(url: str, timeout: float) -> tuple[list[str] | None, str | None]:
    api_key = os.environ.get("CREVIEW_MODEL_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        response = httpx.get(_models_url(url), headers=headers, timeout=timeout)
        response.raise_for_status()
        data = response.json().get("data", [])
    except Exception as exc:  # unreachable, refused, not OpenAI-compatible
        return None, str(exc) or type(exc).__name__
    return [str(item["id"]) for item in data if isinstance(item, dict) and item.get("id")], None


def _candidate(label: str, url: str, model: str | None, timeout: float) -> dict[str, Any]:
    category = _resolved_class(url)
    entry: dict[str, Any] = {
        "source": label,
        "url": url.rstrip("/"),
        "category": category,
        "model": model,
        "models": None,
    }
    if category not in TRUSTED_CLASSES:
        entry["note"] = (
            "not adopted automatically: this endpoint is not on this computer or a private "
            "network. If it is your own server, set it with `creview config gateway`."
        )
        return entry
    models, error = _probe(url, timeout)
    entry["models"] = models
    if models is None:
        entry["note"] = f"no answer from {_models_url(url)}: {error}"
    elif not models:
        entry["note"] = "the server lists no models"
    return entry


def detect_gateway(
    profile: str | None, *, model: str | None = None, apply: bool = False, timeout: float = 1.5
) -> dict[str, Any]:
    root = profile_root(profile)
    config, _problems = _load_config(root / "config.yaml")
    hermes_model, provider, base_url = _selected_model_and_provider(config)
    base_url = base_url or default_base_url(provider, read_env_file(root / ".env"))

    candidates: list[dict[str, Any]] = []
    if base_url:
        candidates.append(_candidate("Hermes profile main model", base_url, hermes_model, timeout))
    seen = {normalized_endpoint(entry["url"]) for entry in candidates}
    for label, url in LOCAL_SERVERS:
        if normalized_endpoint(url) not in seen:
            found = _candidate(label, url, None, timeout)
            if found["models"]:
                candidates.append(found)

    selected: dict[str, Any] | None = None
    reason = ""
    usable = [entry for entry in candidates if entry["models"]]
    profile_entry = next((e for e in usable if e["source"] == "Hermes profile main model"), None)
    choices = [profile_entry] if profile_entry else usable
    if len(choices) > 1:
        reason = "several local servers answer; set one with `creview config gateway --url URL`"
    elif choices:
        entry = choices[0]
        wanted = model or entry["model"]
        if wanted and wanted in entry["models"]:
            selected = {**entry, "model": wanted}
        elif not wanted and len(entry["models"]) == 1:
            selected = {**entry, "model": entry["models"][0]}
        elif wanted:
            reason = f"{entry['url']} does not list model {wanted!r}"
        else:
            reason = f"{entry['url']} serves several models; choose one with --model"
    else:
        reason = "no local or private model server answered"

    result: dict[str, Any] = {
        "applied": False,
        "profile_root": str(root),
        "selected": selected,
        "candidates": candidates,
        "current": trusted_gateway(),
    }
    if selected is None:
        result["reason"] = reason
        if apply:
            raise ReviewError(f"no gateway adopted: {reason}")
        return result

    # Models the profile already routes to on this server, such as a delegation model.
    routes = check_routes(config, root, selected["url"], [selected["model"]])["routes"]
    others = sorted(
        {
            route["model"]
            for route in routes
            if route["model"]
            and route["target"] in {"trusted", "main"}
            and route["model"] in selected["models"]
            and route["model"] != selected["model"]
        }
    )
    selected["trusted_models"] = others
    if apply:
        result["saved"] = set_gateway(selected["url"], selected["model"], others)
        result["applied"] = True
    return result
