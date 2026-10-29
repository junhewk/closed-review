"""Fail-closed medical-support profile checks, separate from legacy compatibility."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from ..io import read_json, sha256_file
from ..routes import VERIFIED_CONFIG_VERSIONS, normalized_endpoint, read_env_file
from .budgets import TOOL_OUTPUT


def readiness(
    config: dict,
    root: Path,
    url: str | None,
    models: list[str],
    route_report: dict,
    context: int | None,
    deployment_problems: list[str],
) -> dict:
    from ..detect import TRUSTED_CLASSES, _resolved_class

    problems = list(deployment_problems)
    limits = config.get("tool_output", {})
    for name, minimum in TOOL_OUTPUT.items():
        value = limits.get(name) if isinstance(limits, dict) else None
        if type(value) is not int or value < minimum:
            problems.append(f"tool_output.{name} must be an explicit integer >= {minimum}")
    expected_tools = {"terminal", "file", "skills", "clarify"}
    toolsets = config.get("platform_toolsets", {})
    for surface in ("cli", "tui"):
        selected = toolsets.get(surface) if isinstance(toolsets, dict) else None
        if not isinstance(selected, list) or set(selected) != expected_tools:
            problems.append(f"platform_toolsets.{surface} must allow only review toolsets")
    terminal = config.get("terminal", {})
    if (
        not isinstance(terminal, dict)
        or terminal.get("backend") != "local"
        or terminal.get("cwd") != str(root / "work")
    ):
        problems.append("medical support requires the managed local terminal/work directory")
    elif os.name != "nt" and (
        terminal.get("auto_source_bashrc") is not False
        or terminal.get("shell_init_files") != [str(root / "review-shell.sh")]
    ):
        problems.append("use only the managed review-shell.sh without sourcing the personal shell")
    auth = config.get("auth", {})
    if not isinstance(auth, dict) or auth.get("adopt_external_logins") is not False:
        problems.append("auth.adopt_external_logins must be false in the review profile")
    metrics = config.get("telemetry", {}).get("shared_metrics", {})
    if not isinstance(metrics, dict) or any(
        metrics.get(k) is not False for k in ("enabled", "send")
    ):
        problems.append("shared telemetry must be disabled in the review profile")
    manifest = root / "creview-profile.json"
    if not manifest.is_file():
        problems.append("use a dedicated managed profile created by creview hermes setup-profile")
    else:
        try:
            value = read_json(manifest)
            if value.get("schema_version") != 1:
                problems.append("unsupported managed profile manifest")
            for relative in ("review-shell.sh", "review-bin/creview") if os.name != "nt" else ():
                path = root / relative
                if not path.is_file() or sha256_file(path) != value.get("runner_files", {}).get(
                    relative
                ):
                    problems.append(f"managed runner changed: {relative}; create a new profile")
        except (OSError, ValueError, AttributeError):
            problems.append("cannot verify managed profile manifest")
    schema = config.get("_config_version")
    low, high = VERIFIED_CONFIG_VERSIONS
    if type(schema) is not int or not low <= schema <= high:
        problems.append("Hermes route schema is not verified for medical support")
    try:
        parsed = urlsplit(url or "")
        private = bool(url) and _resolved_class(url) in TRUSTED_CLASSES
        if (
            not private
            or parsed.scheme not in {"http", "https"}
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            problems.append("medical support requires a credential-free local/private gateway URL")
    except (ValueError, OSError):
        problems.append("medical support gateway URL cannot be verified")
    if type(context) is not int or context < 65536:
        problems.append("set a verified context length of at least 65536 before medical support")
    main = config.get("model", {})
    configured_context = main.get("context_length") if isinstance(main, dict) else None
    if type(configured_context) is not int or configured_context < 65536:
        problems.append(
            "set model.context_length explicitly to at least 65536; "
            "support guards cannot rely on an earlier health-check response"
        )
    if not isinstance(main, dict) or main.get("provider") != "custom":
        problems.append(
            "managed medical support must explicitly use the custom local gateway provider"
        )
    auxiliary = config.get("auxiliary", {})
    for task in ("compression", "title_generation", "vision", "background_review"):
        entry = auxiliary.get(task) if isinstance(auxiliary, dict) else None
        if (
            not isinstance(entry, dict)
            or entry.get("provider") != "custom"
            or normalized_endpoint(entry.get("base_url")) != normalized_endpoint(url)
            or entry.get("model") not in models
        ):
            problems.append(f"auxiliary.{task} must explicitly pin the trusted gateway and model")
    for credential in route_report.get("credentials", []):
        problems.append(
            f"remove cloud credential {credential['name']} from the review process/profile"
        )
    env_file = read_env_file(root / ".env")
    env = {**env_file, **dict(os.environ)}
    proxy_names = [
        k
        for k in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        )
        if env.get(k)
    ]
    bypass = {
        v.strip().lower()
        for k in ("NO_PROXY", "no_proxy")
        for v in env.get(k, "").split(",")
        if v.strip()
    }
    host = (urlsplit(url or "").hostname or "").lower()
    if proxy_names and host not in bypass and "*" not in bypass:
        problems.append(
            "proxy environment may route manuscript requests off-host; unset proxies "
            "or set NO_PROXY to the exact gateway hostname before launching Hermes"
        )
    runtime = runtime_route(root, url, models)
    problems += runtime.pop("problems")
    return {
        "ready": not problems,
        "problems": list(dict.fromkeys(problems)),
        "runtime": runtime,
        "tool_output": limits,
        "network_isolation": "not_enforced",
        "quality": "not_qualified",
    }


def runtime_route(root: Path, url: str | None, models: list[str]) -> dict:
    """Read this session's actual recorded route, not just config defaults or another session."""
    session = os.environ.get("HERMES_SESSION_ID")
    if not session:
        return {"status": "not_in_hermes", "problems": []}
    try:
        with sqlite3.connect(f"file:{root / 'state.db'}?mode=ro", uri=True) as db:
            row = db.execute(
                "SELECT model, billing_provider, billing_base_url FROM sessions WHERE id = ?",
                (session,),
            ).fetchone()
    except sqlite3.Error:
        row = None
    if not row or not all(row):
        return {
            "status": "unverifiable",
            "problems": [
                "cannot verify this Hermes session's recorded model/provider/endpoint; "
                "use a supported Hermes runtime, not an unverifiable model override"
            ],
        }
    model, provider, endpoint = row
    okay = (
        model in models
        and provider == "custom"
        and normalized_endpoint(endpoint) == normalized_endpoint(url)
    )
    return {
        "status": "verified" if okay else "mismatch",
        "model": model,
        "provider": provider,
        "base_url": endpoint,
        "problems": []
        if okay
        else [
            "the live Hermes session route differs from the allowed local gateway/model; "
            "start a new session without model/provider overrides"
        ],
    }
