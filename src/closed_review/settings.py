"""The trusted model gateway: the only endpoint confidential conversation content may reach.

There is no built-in default. `creview config gateway` stores the gateway in the private data
directory; CREVIEW_TRUSTED_MODEL_URL, CREVIEW_MODEL, and CREVIEW_TRUSTED_MODELS override it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .errors import ReviewError
from .io import atomic_write_json, data_home, read_json

GATEWAY_FILE = "gateway.json"
NOT_CONFIGURED = (
    "no trusted model gateway is configured; run `creview config detect --apply` to find a local "
    "model server, or `creview config gateway --url URL --model MODEL` to name one"
)


def gateway_path() -> Path:
    return data_home() / GATEWAY_FILE


def _stored() -> dict[str, Any]:
    path = gateway_path()
    if not path.is_file():
        return {}
    value = read_json(path)
    if not isinstance(value, dict):
        raise ReviewError(f"gateway settings must be a JSON object: {path}")
    return value


def _models(value: Any) -> list[str]:
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def trusted_gateway() -> dict[str, Any]:
    stored = _stored()
    url = os.environ.get("CREVIEW_TRUSTED_MODEL_URL") or stored.get("url") or ""
    model = os.environ.get("CREVIEW_MODEL") or stored.get("model") or ""
    extra = os.environ.get("CREVIEW_TRUSTED_MODELS")
    extra_models = _models(extra) if extra is not None else _models(stored.get("trusted_models"))
    model = str(model).strip()
    return {
        "url": str(url).strip().rstrip("/") or None,
        "model": model or None,
        "trusted_models": list(dict.fromkeys([model, *extra_models])) if model else [],
        "settings_path": str(gateway_path()),
    }


def _validate_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ReviewError(f"gateway URL must be an http(s) URL with a host: {url!r}")
    return url.strip().rstrip("/")


def set_gateway(url: str, model: str, trusted_models: list[str] | None = None) -> dict[str, Any]:
    if not model.strip():
        raise ReviewError("gateway model must not be empty")
    settings = {
        "url": _validate_url(url),
        "model": model.strip(),
        "trusted_models": _models(trusted_models or []),
    }
    atomic_write_json(gateway_path(), settings)
    return {"saved": str(gateway_path()), **trusted_gateway()}
