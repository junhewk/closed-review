"""Check every Hermes model route a review conversation can reach against the trusted gateway.

Hermes sends conversation content to models other than the main one: auxiliary tasks (context
compression, title generation, the self-improvement review, vision), delegated subagents, fallback
chains, mixture-of-agents presets, and endpoints a user can switch to with ``/model``. A route that
leaves the trusted gateway, or names a model outside the allowlist, makes the profile unready.

Routing rules mirror Hermes's ``agent/auxiliary_client.py``: an auxiliary task on ``auto`` uses the
main provider first, and the OpenRouter/Nous discovery chain runs only when the main provider is
itself empty or ``auto``. Vision is the exception: it tries OpenRouter, Nous, and DeepInfra when
Hermes treats the main model as text-only, so credentials for those make unpinned vision unsafe.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

INHERIT = {"", "auto", "main"}
# Hermes maps these local-server aliases to `custom` (_LOCAL_SERVER_ALIASES in its
# agent/auxiliary_client.py).
CUSTOM = {"custom", "ollama", "vllm", "llamacpp", "llama.cpp", "llama-cpp"}
LMSTUDIO = {"lmstudio", "lm-studio", "lm_studio"}
LMSTUDIO_DEFAULT_URL = "http://127.0.0.1:1234/v1"
VISION_LANES = {"openrouter", "nous", "deepinfra"}
CREDENTIAL_ENV = {
    "OPENROUTER_API_KEY": "openrouter",
    "NOUS_API_KEY": "nous",
    "DEEPINFRA_API_KEY": "deepinfra",
    "ANTHROPIC_API_KEY": "anthropic",
    "OPENAI_API_KEY": "openai",
    "GOOGLE_API_KEY": "gemini",
    "GEMINI_API_KEY": "gemini",
    "GLM_API_KEY": "zai",
    "KIMI_API_KEY": "kimi-coding",
    "MINIMAX_API_KEY": "minimax",
    "MINIMAX_CN_API_KEY": "minimax-cn",
    "HF_TOKEN": "huggingface",
    "NVIDIA_API_KEY": "nvidia",
    "XIAOMI_API_KEY": "xiaomi",
    "ARCEEAI_API_KEY": "arcee",
    "OLLAMA_API_KEY": "ollama-cloud",
    "KILOCODE_API_KEY": "kilocode",
    "AI_GATEWAY_API_KEY": "ai-gateway",
}
AUXILIARY_ENV = re.compile(r"^AUXILIARY_([A-Z_]+?)_(PROVIDER|MODEL|BASE_URL)$")
# Hermes `_config_version` values whose routing this module was checked against: 49 is Hermes
# v0.21.5 (ebadb54, 2026-09-24) and 51 is upstream acc3cad (2026-10-16).
VERIFIED_CONFIG_VERSIONS = (49, 51)
# Subtrees whose nested provider/base_url entries are model routes Hermes may call.
ROUTE_SUBTREES = ("moa", "gateway", "platforms")


def _canonical_host(netloc: str) -> str:
    """Treat every loopback spelling (localhost, 127.x, ::1, 0.0.0.0) as one host."""
    parsed = urlsplit(f"//{netloc}")
    host = (parsed.hostname or "").lower()
    try:
        port = parsed.port
    except ValueError:
        return netloc.lower()
    loopback = host in {"localhost", "0.0.0.0", "::"}
    if not loopback:
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = False
    if loopback:
        host = "loopback"
    elif ":" in host:
        host = f"[{host}]"
    return f"{host}:{port}" if port is not None else host


def normalized_endpoint(value: str | None) -> str | None:
    """Compare OpenAI-compatible endpoints with an optional terminal /v1."""
    if not value:
        return None
    parsed = urlsplit(str(value).strip())
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3].rstrip("/")
    return urlunsplit(
        (parsed.scheme.lower(), _canonical_host(parsed.netloc), path, parsed.query, parsed.fragment)
    )


def default_base_url(provider: str | None, env_file: dict[str, str]) -> str | None:
    """The URL Hermes uses for a local-server provider that names no base_url."""
    if (provider or "").strip().lower() in LMSTUDIO:
        return os.environ.get("LM_BASE_URL") or env_file.get("LM_BASE_URL") or LMSTUDIO_DEFAULT_URL
    return None


def _entry_url(entry: dict[str, Any]) -> str | None:
    value = entry.get("base_url") or entry.get("api")
    return str(value) if value else None


def trusted_provider_names(config: dict[str, Any], url: str) -> set[str]:
    """Names under which the trusted gateway is configured, as `model.provider` may cite them."""
    wanted = normalized_endpoint(url)
    names: set[str] = set()
    providers = config.get("providers")
    if isinstance(providers, dict):
        for key, entry in providers.items():
            if isinstance(entry, dict) and normalized_endpoint(_entry_url(entry)) == wanted:
                names.update(str(value) for value in (key, entry.get("name")) if value)
    custom = config.get("custom_providers")
    if isinstance(custom, list):
        for entry in custom:
            trusted = isinstance(entry, dict) and normalized_endpoint(_entry_url(entry)) == wanted
            if trusted and entry.get("name"):
                names.add(str(entry["name"]))
    return names


class RouteCheck:
    def __init__(
        self,
        config: dict[str, Any],
        url: str,
        models: list[str],
        env_file: dict[str, str] | None = None,
    ) -> None:
        self.url = url
        self.env_file = env_file or {}
        self.endpoint = normalized_endpoint(url)
        self.models = set(models)
        self.names = {name.lower() for name in trusted_provider_names(config, url)}
        self.routes: list[dict[str, Any]] = []
        self.problems: list[str] = []

    def check(self, path: str, entry: dict[str, Any], *, inherit: bool) -> str | None:
        """Record one route; return 'trusted', 'main', or None when it is not acceptable."""
        provider = str(entry.get("provider") or "").strip()
        key = provider.lower()
        url = _entry_url(entry) or default_base_url(key, self.env_file)
        model = entry.get("model")
        model = str(model).strip() if isinstance(model, str) and model.strip() else None
        problems: list[str] = []
        target: str | None
        if url:
            target = "trusted" if normalized_endpoint(url) == self.endpoint else None
            if target is None:
                problems.append(f"{path} sends requests to {url!r}, not the trusted gateway")
        elif key in INHERIT:
            target = "main" if inherit else None
            if target is None:
                problems.append(f"{path} names no provider or base_url, so its endpoint is unknown")
        elif key in CUSTOM:
            # Without base_url Hermes reuses the main custom endpoint, checked separately.
            target = "main" if inherit else None
            if target is None:
                problems.append(
                    f"{path} uses provider {provider!r} without base_url; "
                    f"set base_url to {self.url}"
                )
        elif key in self.names or key.removeprefix("custom:") in self.names:
            target = "trusted"
        else:
            target = None
            problems.append(f"{path} routes to provider {provider!r}, not the trusted gateway")
        if model and target is not None and model not in self.models:
            problems.append(
                f"{path} selects model {model!r}, which is not in the trusted models "
                f"({', '.join(sorted(self.models))}); add it to CREVIEW_TRUSTED_MODELS if the "
                "trusted gateway serves it"
            )
        self.routes.append(
            {
                "path": path,
                "provider": provider or None,
                "base_url": url,
                "model": model,
                "target": target or "untrusted",
                "ok": not problems,
            }
        )
        self.problems.extend(problems)
        return target if not problems else None

    def check_entries(self, path: str, value: Any) -> None:
        """A fallback chain: a list of concrete routes, a single route, or a bare model name."""
        if value in (None, "", [], {}, False):
            return
        if isinstance(value, str):
            value = {"model": value}
        entries = value if isinstance(value, list) else [value]
        for index, entry in enumerate(entries):
            label = f"{path}[{index}]" if isinstance(value, list) else path
            if isinstance(entry, dict):
                self.check(label, entry, inherit=False)
            else:
                self.check(label, {"model": str(entry)}, inherit=False)


def _walk_routes(check: RouteCheck, value: Any, path: str) -> None:
    if isinstance(value, dict):
        if value.get("provider") or value.get("base_url"):
            check.check(path, value, inherit=False)
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                _walk_routes(check, child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_routes(check, child, f"{path}[{index}]")


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return values
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        value = value.strip().strip("\"'")
        if value:
            values[key.strip()] = value
    return values


def cloud_credentials(
    profile_root: Path, env_file: dict[str, str], url: str
) -> list[dict[str, str]]:
    """Name (never the value of) each cloud credential Hermes could use from this profile."""
    found: list[dict[str, str]] = []
    for source, values in (("environment", os.environ), (".env", env_file)):
        for name, lane in CREDENTIAL_ENV.items():
            if not values.get(name, "").strip():
                continue
            # OPENAI_API_KEY is also how a custom endpoint is authenticated.
            base = env_file.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
            if name == "OPENAI_API_KEY" and normalized_endpoint(base) == normalized_endpoint(url):
                continue
            found.append({"source": source, "name": name, "provider": lane})
    try:
        auth = json.loads((profile_root / "auth.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        auth = {}
    if isinstance(auth, dict):
        for field in ("providers", "credential_pool"):
            entries = auth.get(field)
            if isinstance(entries, dict):
                for name, entry in entries.items():
                    if entry not in (None, "", [], {}):
                        found.append(
                            {
                                "source": f"auth.json {field}",
                                "name": str(name),
                                "provider": str(name),
                            }
                        )
        active = auth.get("active_provider")
        if active:
            found.append(
                {
                    "source": "auth.json active_provider",
                    "name": str(active),
                    "provider": str(active),
                }
            )
    return found


def _auxiliary_env(sources: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    tasks: dict[str, dict[str, str]] = {}
    for values in sources:
        for name, value in values.items():
            match = AUXILIARY_ENV.match(name)
            if match and value.strip():
                field = {"PROVIDER": "provider", "MODEL": "model", "BASE_URL": "base_url"}
                tasks.setdefault(match.group(1).lower(), {})[field[match.group(2)]] = value
    return tasks


def check_routes(
    config: dict[str, Any], profile_root: Path, url: str, models: list[str]
) -> dict[str, Any]:
    """Every non-main route in the profile; the main route is checked by the caller."""
    env_file = read_env_file(profile_root / ".env")
    check = RouteCheck(config, url, models, env_file)

    auxiliary = config.get("auxiliary") if isinstance(config.get("auxiliary"), dict) else {}
    for task, entry in auxiliary.items():
        if isinstance(entry, dict):
            check.check(f"auxiliary.{task}", entry, inherit=True)
            check.check_entries(f"auxiliary.{task}.fallback_chain", entry.get("fallback_chain"))
    curator = config.get("curator")
    if isinstance(curator, dict) and isinstance(curator.get("auxiliary"), dict):
        check.check("curator.auxiliary", curator["auxiliary"], inherit=True)

    delegation = config.get("delegation")
    if isinstance(delegation, dict):
        check.check("delegation", delegation, inherit=True)
        check.check_entries("delegation.fallback_providers", delegation.get("fallback_providers"))

    for key in ("fallback_providers", "fallback_model"):
        check.check_entries(key, config.get(key))

    aliases = config.get("model_aliases")
    if isinstance(aliases, dict):
        for alias, entry in aliases.items():
            if isinstance(entry, dict):
                check.check(f"model_aliases.{alias}", entry, inherit=False)
            else:
                check.check(f"model_aliases.{alias}", {"model": str(entry)}, inherit=False)

    providers = config.get("providers")
    if isinstance(providers, dict):
        for name, entry in providers.items():
            if isinstance(entry, dict) and _entry_url(entry):
                check.check(f"providers.{name}", {"base_url": _entry_url(entry)}, inherit=False)
    custom = config.get("custom_providers")
    if isinstance(custom, list):
        for index, entry in enumerate(custom):
            if isinstance(entry, dict):
                label = f"custom_providers[{entry.get('name') or index}]"
                check.check(label, {"base_url": _entry_url(entry)}, inherit=False)

    for key in ROUTE_SUBTREES:
        if key in config:
            _walk_routes(check, config[key], key)

    memory = config.get("memory")
    memory_provider = memory.get("provider") if isinstance(memory, dict) else None
    if memory_provider:
        check.problems.append(
            f"memory.provider is {memory_provider!r}; external memory providers receive "
            "conversation content outside the trusted gateway"
        )

    for task, entry in sorted(_auxiliary_env([env_file, dict(os.environ)]).items()):
        check.check(f"AUXILIARY_{task.upper()}_* environment", entry, inherit=True)

    credentials = cloud_credentials(profile_root, env_file, url)
    vision_pinned = any(
        route["path"] in {"auxiliary.vision", "AUXILIARY_VISION_* environment"}
        and route["target"] == "trusted"
        for route in check.routes
    )
    vision_lanes = sorted({c["provider"] for c in credentials} & VISION_LANES)
    if vision_lanes and not vision_pinned:
        check.problems.append(
            "auxiliary.vision is not pinned to the trusted gateway while credentials for "
            f"{', '.join(vision_lanes)} exist; Hermes may send images there when it treats the "
            f"main model as text-only. Set auxiliary.vision.provider: custom and base_url: {url}"
        )
    warnings = [
        f"cloud credential {c['name']} ({c['source']}) lets `/model` or a client switch this "
        "session to a cloud provider; creview cannot see such a switch"
        for c in credentials
    ]
    return {
        "routes": check.routes,
        "problems": check.problems,
        "warnings": warnings,
        "credentials": credentials,
    }
