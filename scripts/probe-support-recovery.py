"""Bounded real-Hermes recovery probes for medical-methods-v1, never legacy scan smoke.

Use only synthetic material. Run serially after other model tests. Forced compression/turn
settings affect newly created disposable profiles only and are not qualification defaults.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import time
from pathlib import Path

import yaml

from closed_review.deployment import setup_profile
from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, atomic_write_text, ensure_private_dir, sha256_file
from closed_review.receipts import installed_identity
from closed_review.smoke import _child_environment, _run_turn, environment
from closed_review.support import PROTOCOL


def load_pilot():
    path = Path(__file__).with_name("test-support-hermes.py")
    spec = importlib.util.spec_from_file_location("medical_support_pilot", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compression_committed(log: str, session: str | None) -> bool:
    """Recognize actual compressor commits, never starts, no-ops or another session.

    Current Hermes emits structured attempt telemetry instead of the older numbered
    completion message. A committed transcript is event evidence, not summary fidelity.
    """
    if not session:
        return False
    for line in log.splitlines():
        marker = "agent.conversation_compression: context compression attempt telemetry: "
        if marker not in line:
            continue
        try:
            event = json.loads(line.split(marker, 1)[1])
        except (ValueError, TypeError):
            continue
        if (
            isinstance(event, dict)
            and event.get("event") == "compression_attempt"
            and event.get("session_id") == session
            and event.get("commit_status") == "committed"
            and event.get("fallback_used") is False
        ):
            return True
    return False


def recovery(mode: str, args, settings: dict) -> dict:
    pilot = load_pilot()
    original = pilot._run_turn
    observed = {
        "forced_turn_limit_observed": False,
        "compression_completed": False,
        "expected_forced_exit_recovered": False,
    }
    calls = 0
    applied = False

    def instrument(command, env, work, log, deadline):
        nonlocal calls, applied
        command = list(command)
        root = Path(env["HERMES_HOME"])
        agent_log = root / "logs/agent.log"
        previous = agent_log.read_text(encoding="utf-8") if agent_log.is_file() else ""
        before = pilot.saved_run(root)
        analysis_boundary = (
            calls >= 1 and not applied and "--resume" in command
            and pilot.checkpoint_state(before) == "issued"
        )
        if analysis_boundary:
            applied = True
            observed["instrumented_invocation"] = calls + 1
        if analysis_boundary and mode == "compression":
            config = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
            # Hermes floors percentage thresholds; use its explicit absolute test setting.
            config.setdefault("compression", {})["threshold_tokens"] = 20000
            atomic_write_text(root / "config.yaml", yaml.safe_dump(config, sort_keys=False))
        forced = mode == "turn-limit" and analysis_boundary
        if forced:
            command[command.index("--max-turns") + 1] = "3"
        calls += 1
        error = None
        try:
            return original(command, env, work, log, deadline)
        except ReviewError as exc:
            error = exc
        finally:
            text = agent_log.read_text(encoding="utf-8") if agent_log.is_file() else ""
            new_log = text[len(previous) :] if text.startswith(previous) else text
            if forced:
                observed["forced_turn_limit_observed"] = bool(
                    re.search(
                        r"Turn ended: reason=(?:max_iterations_reached|budget_exhausted)", new_log
                    )
                )
            if applied:
                observed["compression_completed"] |= bool(
                    re.search(r"Compression #\d+ complete", new_log)
                ) or compression_committed(new_log, pilot._session(root))
        if error is not None:
            after = pilot.saved_run(root) if forced else None
            session = pilot._session(root) if forced else None
            resumed = "--resume" in command and command[command.index("--resume") + 1] == session
            expected_exit = (
                forced
                and str(error).startswith("Hermes exited with status 1;")
                and observed["forced_turn_limit_observed"]
                and before
                and after
                and before.get("id") == after.get("id")
                and resumed
                and log.is_file()
                and "Traceback (most recent call last)" not in log.read_text(encoding="utf-8")
            )
            if expected_exit:
                # Hermes uses exit 1 for an intentionally interrupted one-shot turn. Preserve
                # that log, then let the existing bounded driver resume the SAME session/run.
                observed["expected_forced_exit_recovered"] = True
                return None
            raise error

    pilot._run_turn = instrument
    try:
        result = pilot.run_case(
            args, "case-02", "statistics", settings, time.monotonic() + args.timeout
        )
    finally:
        pilot._run_turn = original
    event = (
        observed["compression_completed"]
        if mode == "compression"
        else observed["forced_turn_limit_observed"]
    )
    return {
        "mode": mode,
        "probe_passed": result["engineering_passed"] and event,
        "forced_setting": {
            "compression.threshold_tokens": 20000, "requires_issued_checkpoint": True,
        }
        if mode == "compression"
        else {"analysis_invocation_max_turns": 3, "requires_issued_checkpoint": True},
        "observed": observed,
        "case": result,
        "synthetic_only": True,
        "semantic_quality": "not_assessed_requires_human_review",
        "qualification": "not_qualified",
        "note": "Event detection and workflow integrity do not prove summary/dossier meaning.",
    }


def image_only_pdf(path: Path) -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (800, 300), "white")
    ImageDraw.Draw(image).text((30, 120), "SYNTHETIC IMAGE ONLY - DATA 42", fill="black")
    image.save(path, "PDF", resolution=72)
    path.chmod(0o600)


def unreadable(args, settings: dict) -> dict:
    pilot = load_pilot()
    destination = ensure_private_dir(args.output / "image-only")
    env = _child_environment(destination / "hermes", gateway_url=settings["gateway_url"])
    result = {
        "mode": "unreadable-pdf",
        "synthetic_only": True,
        "probe_passed": False,
        "qualification": "not_qualified",
        "semantic_quality": "not_assessed",
    }
    started = time.monotonic()
    try:
        with environment(env):
            setup = setup_profile("pilot", **settings, apply=True)
        root = Path(setup["profile_root"])
        env.update(HERMES_HOME=str(root), CREVIEW_HOME=str(root / "review-data"))
        env.pop("PYTHONPATH", None)
        work = root / "work"
        paper = work / "manuscript.pdf"
        image_only_pdf(paper)
        query = work / "query.txt"
        atomic_write_text(
            query,
            "This is a SYNTHETIC medical support engineering test. The fictional journal "
            "explicitly permits local AI assistance. Use journal-article-review on "
            f"{paper}, selecting only statistics and response language {args.language}. "
            "First save `creview receipts sums` JSON to " + str(work / "runner.json") + ". "
            "Run the strict privacy preflight before opening the manuscript. Start exactly "
            "one support run. Follow its status honestly even if nothing is assessable. "
            "Export once. Do not use OCR, vision, web, raw data, other models, legacy scan, "
            "or make findings from content that the source extractor did not supply. "
            "No reviewer decisions are provided. Keep all records; start no browser/server.",
        )
        _run_turn(
            [
                args.hermes,
                "chat",
                "--query-file",
                str(query),
                "--oneshot",
                "-Q",
                "--skills",
                "journal-article-review",
                "--max-turns",
                "60",
            ],
            env,
            work,
            destination / "turn-0.log",
            started + args.timeout,
        )
        run = pilot.saved_run(root)
        if not run:
            raise ReviewError("Hermes did not save the not-assessable run")
        with environment(env):
            audited = pilot.audit(
                root, "statistics", installed_identity()["sums_sha256"], sha256_file(paper), None
            )
        checks = {
            k: v
            for k, v in audited["checks"].items()
            if k not in {"module_completed", "same_run_resumed"}
        }
        state = run["modules"]["statistics"]
        checks.update(
            not_assessable=state["status"] == "not_assessable",
            no_tasks=not run["tasks"],
            no_extracted_text=not run["source"]["blocks"],
            no_observations=not state["observations"],
            no_calculations=not state["calculations"],
            extraction_warning_visible=bool(run["source"]["warnings"]),
        )
        result.update(
            checks=checks,
            probe_passed=all(checks.values()),
            dossier=audited["dossier"],
            source_warnings=run["source"]["warnings"],
            profile_root=str(root),
        )
    except (ReviewError, OSError, ValueError, KeyError, TypeError) as exc:
        result["error"] = str(exc)
    result["elapsed_seconds"] = round(time.monotonic() - started, 2)
    result["manual_audit"] = "Verify the final chat did not invent medical content or assurances."
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["compression", "turn-limit", "unreadable-pdf"])
    parser.add_argument("--gateway-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--context-length", type=int, required=True)
    parser.add_argument("--hermes", default="hermes")
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "evals/support-pilot/manuscripts",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--language", default="en")
    args = parser.parse_args(argv)
    if os.environ.get("HERMES_SESSION_ID"):
        parser.error("run the evaluator outside Hermes")
    args.hermes = shutil.which(args.hermes)
    if not args.hermes or args.timeout < 30:
        parser.error("a Hermes executable and timeout of at least 30 seconds are required")
    if args.output.exists():
        parser.error("choose a NEW output directory; do not overwrite earlier probes")
    args.output = args.output.expanduser().resolve()
    args.corpus = args.corpus.expanduser().resolve()
    ensure_private_dir(args.output)
    settings = {
        "gateway_url": args.gateway_url,
        "model": args.model,
        "context_length": args.context_length,
    }
    result = (
        unreadable(args, settings)
        if args.mode == "unreadable-pdf"
        else recovery(args.mode, args, settings)
    )
    result.update(
        protocol=PROTOCOL,
        identity=installed_identity()["sums_sha256"],
        harness_sha256=sha256_file(Path(__file__)),
    )
    atomic_write_json(args.output / "probe.json", result)
    print(json.dumps(result, indent=2))
    return 0 if result["probe_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
