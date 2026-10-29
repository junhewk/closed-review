"""Exercise the installed Hermes host with synthetic material in a disposable profile.

No model API is called by creview: Hermes does the reading and tool calls. Scripted responses
are sent through Hermes's normal user-message path, never inserted into its transcript database.
This tests workflow compatibility, not scientific accuracy or network isolation.
"""

from __future__ import annotations

import os
import shutil
import signal
import sqlite3
import subprocess
import tempfile
import time
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from .deployment import PROFILE_MANIFEST, REVIEW_TOOLS, setup_profile
from .direct import _accepted_scan_records, check_export_scope, check_export_severity
from .errors import ReviewError
from .hermes import _configured_toolsets, inspect_profile, profile_root
from .io import atomic_write_json, atomic_write_text, read_json
from .receipts import SUBJECT_ROLES, installed_identity, verify_receipt
from .routes import CREDENTIAL_ENV


@contextmanager
def environment(values: dict[str, str]):
    original = dict(os.environ)
    os.environ.clear()
    os.environ.update(values)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


def review_profile_problems(config: dict) -> list[str]:
    problems = []
    if _configured_toolsets(config) != set(REVIEW_TOOLS):
        problems.append("review toolsets must be terminal, file, skills, and clarify only")
    for key in ("memory_enabled", "user_profile_enabled"):
        if config.get("memory", {}).get(key) is not False:
            problems.append(f"memory.{key} must be false")
    if config.get("auxiliary", {}).get("background_review", {}).get("enabled") is not False:
        problems.append("auxiliary.background_review.enabled must be false")
    if config.get("mcp_servers") or config.get("plugins", {}).get("enabled"):
        problems.append("the review profile must not enable MCP servers or plugins")
    if config.get("skills", {}).get("external_dirs"):
        problems.append("the review profile must not load external skill directories")
    if config.get("display", {}).get("inline_diffs") is not False:
        problems.append("display.inline_diffs must be false")
    if config.get("display", {}).get("tool_progress") == "verbose":
        problems.append("display.tool_progress must not be verbose")
    return problems


def _child_environment(root: Path, *, gateway_url: str | None = None) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in CREDENTIAL_ENV
        and not key.startswith(("HERMES_", "AUXILIARY_", "CREVIEW_", "OPENAI_", "LM_"))
        and key.lower() not in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}
    }
    env["HERMES_HOME"] = str(root)
    env["PYTHONUNBUFFERED"] = "1"
    if gateway_url:
        from urllib.parse import urlsplit

        env["OPENAI_BASE_URL"] = gateway_url
        env["NO_PROXY"] = urlsplit(gateway_url).hostname or ""
    # Only an explicitly provided credential for the trusted endpoint is inherited.
    if os.environ.get("CREVIEW_MODEL_API_KEY"):
        env["CREVIEW_MODEL_API_KEY"] = os.environ["CREVIEW_MODEL_API_KEY"]
        env["OPENAI_API_KEY"] = os.environ["CREVIEW_MODEL_API_KEY"]
    return env


def _run_turn(command: list[str], env: dict[str, str], work: Path, log: Path, deadline: float):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ReviewError("synthetic workflow exceeded its total time limit")
    with log.open("wb") as output:
        proc = subprocess.Popen(
            command,
            cwd=work,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=os.name != "nt",
        )
        try:
            code = proc.wait(timeout=remaining)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
            else:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            raise ReviewError(
                "synthetic workflow stopped at its time limit or was interrupted"
            ) from None
    if code:
        raise ReviewError(f"Hermes exited with status {code}; inspect {log.name} with --keep")


def _session(root: Path) -> str | None:
    path = root / "state.db"
    if not path.is_file():
        return None
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        sessions = db.execute(
            "SELECT DISTINCT session_id FROM messages WHERE role='user'"
        ).fetchall()
    if len(sessions) != 1:
        raise ReviewError("smoke expected exactly one synthetic Hermes session")
    return str(sessions[0][0])


def _scan(root: Path) -> dict | None:
    paths = list((root / "review-data" / "scans").glob("*/scan.json"))
    if len(paths) > 1:
        raise ReviewError("Hermes started multiple scans instead of resuming the existing one")
    return read_json(paths[0]) if paths else None


def _audit(root: Path, expected_identity: str, acceptance: str) -> dict[str, bool]:
    scan = _scan(root) or {}
    probe = root / "work" / "runner.json"
    accepted = [v for v in scan.get("surfaced", {}).values() if v.get("disposition") == "accepted"]
    receipts = list((root / "review-data" / "exports").glob("*/receipt.json"))
    meta_path = receipts[0].parent / "export.json" if len(receipts) == 1 else None
    meta = read_json(meta_path) if meta_path and meta_path.is_file() else {}
    linked = bool(scan.get("scan_id") and meta.get("scan_id") == scan["scan_id"])
    severity_ok = False
    scope_ok = False
    if linked:
        records = _accepted_scan_records(meta["scan_id"], meta.get("session_id"))
        severity_ok = (
            check_export_severity(receipts[0].parent, records)["status"]
            == "no_explicit_conflict_found"
        )
        scope_ok = check_export_scope(receipts[0].parent)["status"] == "no_explicit_conflict_found"
    checks = {
        "runner_identity": probe.is_file()
        and read_json(probe).get("sums_sha256") == expected_identity,
        "scan_completed": scan.get("phase") == "ready",
        "reviewer_response_verified": len(accepted) == 1
        and accepted[0].get("response", {}).get("verified") is True
        and accepted[0]["response"].get("words") == acceptance,
        "three_export_files": len(receipts) == 1
        and all((receipts[0].parent / name).is_file() for name in SUBJECT_ROLES),
        "receipt_verified": len(receipts) == 1 and verify_receipt(receipts[0])["verified"],
        "preflight_recorded": len(receipts) == 1
        and read_json(receipts[0]).get("preflight", {}).get("status") == "passed",
        "scan_linked": linked,
        "explicit_severity_consistent": severity_ok,
        "no_explicit_unsurfaced_mentions": scope_ok,
    }
    return checks


def run_smoke(
    profile: str,
    *,
    hermes: str | None = None,
    timeout: int = 900,
    keep: bool = False,
) -> dict[str, Any]:
    return _run_probe(profile, hermes=hermes, timeout=timeout, keep=keep)


def run_synthetic_scan(
    profile: str,
    manuscript: Path,
    designs: list[str],
    *,
    hermes: str | None = None,
    timeout: int = 1800,
) -> dict[str, Any]:
    """Qualification harness entry point. Pass only synthetic manuscripts, never answer keys."""
    return _run_probe(
        profile, hermes=hermes, timeout=timeout, keep=True, manuscript=manuscript, designs=designs
    )


def _run_probe(
    profile: str,
    *,
    hermes: str | None,
    timeout: int,
    keep: bool,
    manuscript: Path | None = None,
    designs: list[str] | None = None,
) -> dict[str, Any]:
    if timeout < 30:
        raise ReviewError("smoke timeout must be at least 30 seconds")
    executable = shutil.which(hermes or "hermes")
    if not executable:
        raise ReviewError("Hermes executable not found; use --hermes /absolute/path/to/hermes")
    source = profile_root(profile)
    if not (source / PROFILE_MANIFEST).is_file():
        raise ReviewError("create a dedicated profile with `creview hermes setup-profile` first")
    report = inspect_profile(profile)
    if not report["ready"]:
        raise ReviewError("profile preflight failed: " + "; ".join(report["problems"]))
    config = yaml.safe_load((source / "config.yaml").read_text(encoding="utf-8"))
    problems = report.get("compatibility", {}).get("deployment_problems", [])
    problems = list(dict.fromkeys([*problems, *review_profile_problems(config)]))
    if report["skill_changes"]:
        problems.append("smoke requires the unmodified packaged review skill")
    if problems:
        raise ReviewError("profile needs attention: " + "; ".join(problems))

    started = time.monotonic()
    temporary = Path(tempfile.mkdtemp(prefix="creview-smoke-"))
    base = temporary / "hermes"
    env = _child_environment(base, gateway_url=report["base_url"])
    result: dict[str, Any] = {
        "passed": False,
        "synthetic_only": True,
        "profile": profile,
        "model": report["model"],
        "checks": {},
        "review_quality": "not_assessed",
        "network_isolation": "not_enforced",
        "compression_recovery": "not_forced_by_smoke",
        "turns": 0,
    }
    acceptance = "I accept this concern. Please ask the authors to resolve it."
    try:
        with environment(env):
            setup = setup_profile(
                "smoke",
                gateway_url=report["base_url"],
                model=report["model"],
                context_length=config.get("model", {}).get("context_length"),
                apply=True,
            )
        root = Path(setup["profile_root"])
        # Keep the actual reviewed configuration, changing only profile-local paths.
        local = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
        config["terminal"] = local["terminal"]
        atomic_write_text(root / "config.yaml", yaml.safe_dump(config, sort_keys=False))
        env["HERMES_HOME"] = str(root)
        env["CREVIEW_HOME"] = str(root / "review-data")
        work = root / "work"
        paper = work / "synthetic-manuscript.md"
        paper_text = (
            manuscript.read_text(encoding="utf-8")
            if manuscript
            else resources.files("closed_review")
            .joinpath("resources", "deployment", "smoke.md")
            .read_text(encoding="utf-8")
        )
        atomic_write_text(paper, paper_text)
        result["manuscript_words"] = len(paper_text.split())
        expected_identity = installed_identity()["sums_sha256"]
        prompt = (
            "This is an automated SYNTHETIC deployment test, with scripted user responses. "
            "The journal permits local AI assistance for this synthetic test. I confirm these "
            "design profiles: " + ", ".join(designs or ["quantitative"]) + ". "
            "Follow journal-article-review on " + str(paper) + ". "
            "First use your terminal to run `creview receipts sums` and save its JSON output "
            "to " + str(work / "runner.json") + ". Then run the normal preflight and scan. "
            "For this first turn, stop after `creview scan start` and `creview scan next`: "
            "do not submit an answer yet. I will ask you to resume in my next message. "
            "Do not ask clarify questions. Do not export or purge these synthetic records."
        )
        session = None
        interrupted_scan = None
        # A deliberately short first turn exercises resumption through the real transcript.
        for turn in range(6):
            query = work / f"query-{turn}.txt"
            atomic_write_text(query, prompt)
            command = [
                executable,
                "chat",
                "--query-file",
                str(query),
                "--oneshot",
                "-Q",
                "--skills",
                "journal-article-review",
                "--max-turns",
                "12" if turn == 0 else "150",
            ]
            if session:
                command += ["--resume", session]
            _run_turn(command, env, work, temporary / f"turn-{turn}.log", started + timeout)
            result["turns"] += 1
            probe = work / "runner.json"
            if probe.is_file() and read_json(probe).get("sums_sha256") != expected_identity:
                raise ReviewError(
                    "Hermes terminal selected a different creview build; fix runner selection"
                )
            session = _session(root)
            scan = _scan(root)
            if turn == 0 and scan and scan["phase"] != "ready":
                interrupted_scan = scan["scan_id"]
            if scan and scan["phase"] == "ready" and (manuscript or scan.get("surfaced")):
                break
            prompt = (
                "Continue this same synthetic scan from its saved state using creview scan next. "
                "Do not start another scan. Present the first finding in chat when ready; "
                "do not ask clarify questions or export yet."
            )
        else:
            raise ReviewError("scan did not reach a surfaced finding within six turns")
        result["checks"]["resumed_scan"] = bool(interrupted_scan == scan["scan_id"])
        result["scan_elapsed_seconds"] = round(time.monotonic() - started, 2)
        if manuscript:
            result["checks"].update(
                {
                    "scan_completed": scan["phase"] == "ready",
                    "runner_identity": (work / "runner.json").is_file()
                    and read_json(work / "runner.json").get("sums_sha256") == expected_identity,
                }
            )
            result["passed"] = all(result["checks"].values())
            result["scan_path"] = str(root / "review-data/scans" / scan["scan_id"] / "scan.json")
            return result
        query = work / "accept-and-export.txt"
        atomic_write_text(
            query,
            acceptance + "\nRecord that exact response for the first finding "
            "you just showed, then export my accepted finding only. Do not accept "
            "additional findings or give a recommendation. Keep all synthetic records.",
        )
        _run_turn(
            [
                executable,
                "chat",
                "--query-file",
                str(query),
                "--oneshot",
                "-Q",
                "--resume",
                session,
                "--max-turns",
                "60",
            ],
            env,
            work,
            temporary / "export.log",
            started + timeout,
        )
        result["turns"] += 1
        with environment(env):
            result["checks"].update(_audit(root, expected_identity, acceptance))
        result["passed"] = all(result["checks"].values())
        result["semantic_export_audit"] = "requires_human_review; hashes do not check wording"
    except (ReviewError, OSError, sqlite3.Error, ValueError) as exc:
        result["error"] = str(exc)
    finally:
        result["elapsed_seconds"] = round(time.monotonic() - started, 2)
        if keep:
            result["artifacts"] = str(temporary)
            atomic_write_json(temporary / "result.json", result)
        else:
            shutil.rmtree(temporary)
    return result
