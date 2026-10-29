"""Bounded medical-methods-v1 pilot on the real Hermes CLI.

Run outside Hermes. Standalone mode uses the twelve synthetic manuscripts; the manifest
scheduler can supply explicitly labeled public articles. Only selected manuscripts are copied
into disposable profiles. No private keys, automated reviewer decisions or legacy scans.
Engineering checks are not scientific-quality judgments or release qualification.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sqlite3
import time
from pathlib import Path

import yaml

from closed_review.deployment import setup_profile
from closed_review.errors import ReviewError
from closed_review.hermes import inspect_profile
from closed_review.io import (
    atomic_write_json,
    atomic_write_text,
    ensure_private_dir,
    now_iso,
    read_json,
    secure_file,
    sha256_file,
)
from closed_review.receipts import installed_identity, verify_receipt
from closed_review.smoke import _child_environment, _run_turn, _session, environment
from closed_review.support import PROTOCOL
from closed_review.support.continuation import TURN_EVENT, iteration_handoff
from closed_review.support.sources import resolve_evidence

CASES = {
    f"case-{i:02d}": module
    for i, module in enumerate(
        (
            "statistics",
            "statistics",
            "qualitative-study",
            "qualitative-study",
            "systematic-review",
            "systematic-review",
            "scoping-review",
            "scoping-review",
            "narrative-review",
            "narrative-review",
            "logic",
            "logic",
        ),
        1,
    )
}


def source_context(args) -> tuple[bool, str, str]:
    synthetic = getattr(args, "synthetic_only", True)
    if type(synthetic) is not bool:
        raise ReviewError("evaluation source kind must be an explicit boolean")
    if synthetic:
        return (
            True,
            "synthetic",
            (
                "This is a SYNTHETIC medical-methods-v1 deployment pilot. This synthetic journal "
                "explicitly permits this local AI assistance. "
            ),
        )
    return (
        False,
        "published-article",
        (
            "This is a REAL published open-access article supplied for an engineering evaluation "
            "of local review support, not a journal peer-review assignment. Do not invent journal "
            "approval or assume the article has errors or is an error-free control. "
        ),
    )


def saved_run(root: Path) -> dict | None:
    paths = list((root / "review-data/support").glob("*/run.json"))
    if len(paths) > 1:
        raise ReviewError("Hermes started multiple runs instead of resuming the same run")
    return read_json(paths[0]) if paths else None


def evidence_bound(run: dict) -> bool:
    """Check retained evidence, not the scientific interpretation of the quotations."""
    try:
        for state in run["modules"].values():
            for section in ("facts", "criteria", "connections", "observations", "withdrawn"):
                for item in state[section]:
                    resolve_evidence(item.get("evidence", []), run["source"])
                    resolve_evidence(item.get("counterevidence", []), run["source"])
    except (ReviewError, KeyError, TypeError, ValueError):
        return False
    return True


def audit(
    root: Path,
    module: str,
    identity: str,
    paper_hash: str,
    paused: str | None,
    *,
    requested_modules: list[str] | None = None,
) -> dict:
    run = saved_run(root) or {}
    probe = root / "work/runner.json"
    receipts = list((root / "review-data/support").glob("*/exports/*/receipt.json"))
    receipt = receipts[0] if len(receipts) == 1 else None
    dossier = read_json(receipt.parent / "support.json") if receipt else {}
    requested = requested_modules if requested_modules is not None else [module]
    checks = {
        "runner_identity": probe.is_file()
        and read_json(probe).get("sums_sha256") == identity
        and run.get("identity", {}).get("runner") == identity,
        "new_protocol": run.get("protocol") == PROTOCOL,
        "same_run_resumed": bool(paused and paused == run.get("id")),
        "requested_module_only": set(run.get("modules", {})) == set(requested),
        "module_completed": bool(requested)
        and all(
            run.get("modules", {}).get(name, {}).get("status") == "complete" for name in requested
        ),
        "source_unchanged": run.get("source", {}).get("sha256") == paper_hash,
        "source_quotes_bound": bool(run) and evidence_bound(run),
        "no_invented_reviewer_decisions": not run.get("notes") and not dossier.get("notes"),
        "no_legacy_scan": not list((root / "review-data/scans").glob("*/scan.json")),
        "dossier_matches_saved_run": bool(run) and dossier == run,
        "export_files_exist": bool(receipt)
        and all(
            (receipt.parent / name).is_file() and (receipt.parent / name).stat().st_size > 0
            for name in ("dossier.html", "dossier.md", "reviewer-notes.md", "support.json")
        ),
        "receipt_integrity": bool(receipt) and verify_receipt(receipt)["verified"],
    }
    return {
        "checks": checks,
        "run_id": run.get("id"),
        "artifact_sha256": sha256_file(receipt.parent / "support.json") if receipt else None,
        "engineering_passed": all(checks.values()),
        "dossier": str(receipt.parent) if receipt else None,
        "modules": {
            name: {
                "status": state["status"],
                "observations": len(state["observations"]),
                "calculations": len(state["calculations"]),
                "failures": state["failures"],
            }
            for name, state in run.get("modules", {}).items()
        },
    }


def checkpoint_state(run: dict | None) -> str | None:
    """An untouched first task may need one explicit same-session continuation.

    Never repair a progressed/failed run, submitted refusal or fabricated clean result.
    This describes saved state, not whether the model understood or read the manuscript.
    """
    if not run or run.get("cursor") != 0 or run.get("attempts") or run.get("notes"):
        return None
    states = run.get("modules", {})
    if not states or any(
        state.get(key)
        for state in states.values()
        for key in (
            "facts",
            "criteria",
            "calculations",
            "connections",
            "observations",
            "withdrawn",
            "coverage_gaps",
            "reads",
            "failures",
        )
    ):
        return None
    if run.get("issued_task") == "task-0001":
        return (
            "issued"
            if all(s.get("status") in {"pending", "running"} for s in states.values())
            and any(
                s.get("status") == "running" and s.get("provided_blocks") for s in states.values()
            )
            else None
        )
    if not run.get("issued_task") and all(
        s.get("status") == "pending" and not s.get("provided_blocks") for s in states.values()
    ):
        return "unissued"
    return None


def startup_pins(root: Path) -> dict:
    """Pin the isolated configuration/runner/skill without copying credential contents."""
    names = {"config.yaml", ".env", "creview-profile.json", "review-shell.sh", "review-bin/creview"}
    skill = root / "skills/journal-article-review"
    names.update(p.relative_to(root).as_posix() for p in skill.rglob("*") if p.is_file())
    result = {}
    for name in sorted(names):
        path = root / name
        if path.is_symlink():
            raise ReviewError("startup recovery requires regular managed profile files")
        result[name] = sha256_file(path) if path.is_file() else None
    return result


def startup_handoff(
    root: Path, env: dict, *, before: dict | None, after: dict | None, session: str,
    paper: Path, paper_hash: str, runner: str, model: str, pins: dict,
    agent_log: str, turn_output: str, max_turns: int,
) -> dict | None:
    """Recognize one clean pre-start stop, not a policy override or successful review.

    Only the newly appended host-log suffix is accepted. A passed current-session privacy
    preflight, actual local route, unchanged inputs/configuration, exact runner probe and no
    existing analysis are required. Model-authored explanations never establish eligibility.
    """
    marker = re.compile(
        r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} WARNING \[([^\]\r\n]+)\] "
        r"agent\.conversation_loop: Reasoning-only clean stop \([0-9]+ chars\) — "
        r"returning the reasoning as the final response "
        r"\(model=(\S+) provider=custom api_calls=([0-9]+) tool_turns=([0-9]+)\)$",
        re.MULTILINE,
    )
    if (
        before is not None or after is not None or not session or not pins
        or type(max_turns) is not int or max_turns < 1
        or any(s in agent_log + turn_output for s in (
            "Traceback (most recent call last)", "File-mutation verifier:",
            "returned error", "BLOCKED:",
        ))
        or re.search(r"^\d{4}-\d{2}-\d{2} .* (?:ERROR|CRITICAL) \[", agent_log, re.MULTILINE)
    ):
        return None
    events, markers = list(TURN_EVENT.finditer(agent_log)), list(marker.finditer(agent_log))
    if (
        len(events) != 1 or len(markers) != 1
        or len(re.findall(r"Turn ended: reason=", agent_log)) != 1
        or len(re.findall(r"Reasoning-only clean stop", agent_log)) != 1
        or markers[0].start() >= events[0].start()
    ):
        return None
    logged, reason, actual_model, used, cap, spent, budget, ended = events[0].groups()
    marked_session, marked_model, calls, tools = markers[0].groups()
    if (
        logged != session or ended != session or marked_session != session
        or actual_model != model or marked_model != model
        or reason != "text_response(finish_reason=stop)"
        or not 0 < int(tools) <= int(calls) == int(used) == int(spent) < int(cap)
        or int(cap) != max_turns or int(budget) != max_turns
        or f"tool_turns={int(tools)} " not in events[0].group()
    ):
        return None
    try:
        data = root / "review-data"
        # Any orphan draft/run/export or legacy scan also prevents pre-start recovery.
        if any(
            path.is_symlink() or (path.exists() and any(path.iterdir()))
            for path in (data / "support", data / "scans")
        ):
            return None
        probe = read_json(root / "work/runner.json")
        if (
            paper.is_symlink() or not paper.is_file() or sha256_file(paper) != paper_hash
            or startup_pins(root) != pins or installed_identity()["sums_sha256"] != runner
            or not isinstance(probe, dict) or probe.get("sums_sha256") != runner
            or _session(root) != session
        ):
            return None
        key = hashlib.sha256(session.encode()).hexdigest()[:32]
        preflight = read_json(data / "preflights" / f"{key}.json")
        if (
            not isinstance(preflight, dict) or preflight.get("session_id") != key
            or preflight.get("session_source") != "hermes_session"
            or preflight.get("ready") is not True or preflight.get("problems") != []
            or preflight.get("support_required") is not True
            or preflight.get("skill_privacy_block") != "match"
            or preflight.get("creview_version") != installed_identity()["version"]
        ):
            return None
        with environment(dict(env, HERMES_SESSION_ID=session)):
            report = inspect_profile(None, live=False)
        support = report.get("support_readiness", {})
        if (
            not report["ready"] or not support.get("ready")
            or report.get("model") != model
            or support.get("runtime", {}).get("status") != "verified"
        ):
            return None
    except (ReviewError, OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        return None
    return dict(reason="reasoning_only_pre_start_stop", session=session, api_calls=int(used),
                turn_limit=max_turns, verified_host_event=True, preflight_ready=True,
                unchanged_source_profile_runner=True, engineering_success_claimed=False)


def run_case(args, case: str, module: str, settings: dict, deadline: float) -> dict:
    destination = ensure_private_dir(args.output / case)
    env = _child_environment(destination / "hermes", gateway_url=settings.get("gateway_url"))
    started = time.monotonic()
    synthetic, source_label, introduction = source_context(args)
    result = {
        "case_id": case,
        "module": module,
        "engineering_passed": False,
        "turns": 0,
        "synthetic_only": synthetic,
    }
    paused = None
    root = None
    requested = getattr(args, "requested_modules", None) or [module]
    result["requested_modules"] = requested
    result.update(
        checkpoint_completion_requests=0,
        checkpoint_reached=False,
        invocations=0,
        iteration_handoffs=[],
        startup_completion_requests=0,
        startup_handoffs=[],
    )
    try:
        with environment(env):
            setup = setup_profile("pilot", **settings, apply=True)
        root = Path(setup["profile_root"])
        env.update(HERMES_HOME=str(root), CREVIEW_HOME=str(root / "review-data"))
        # Do not inherit the calling Python environment's module path into Hermes tools.
        # The managed runner launcher still selects this exact installed wheel/interpreter.
        env.pop("PYTHONPATH", None)
        work = root / "work"
        supplied = getattr(args, "paper_override", None) or args.corpus / f"{case}.md"
        paper = work / ("manuscript" + supplied.suffix.lower())
        original_hash = sha256_file(supplied)
        shutil.copyfile(supplied, paper)
        secure_file(paper)
        if sha256_file(supplied) != original_hash or sha256_file(paper) != original_hash:
            raise ReviewError("manuscript source changed while it was copied")
        paper_hash = sha256_file(paper)
        result["manuscript_sha256"] = paper_hash
        identity = installed_identity()["sums_sha256"]
        result["identity"] = identity
        pins = startup_pins(root)
        session = None
        prompt = (
            introduction + "Use journal-article-review on "
            f"{paper}. Select only these modules: {', '.join(requested)}, "
            f"with response language {args.language}. "
            "First run `creview receipts sums` and save its JSON output to "
            f"{work / 'runner.json'}. Run the normal privacy preflight before reading the paper. "
            "Start exactly one support run, then call `creview support next RUN`. STOP at that "
            "point without writing/submitting an answer or exporting. I will ask you to resume. "
            "Do not ask clarification questions, run legacy scan commands, fetch literature, "
            "change the profile or model, inspect other cases, or look for answer keys."
        )
        for turn in range(6):
            query = work / f"query-{turn}.txt"
            atomic_write_text(query, prompt)
            command = [
                args.hermes,
                "chat",
                "--query-file",
                str(query),
                "--oneshot",
                "-Q",
                "--skills",
                "journal-article-review",
                "--max-turns",
                str(getattr(args, "analysis_turn_limit", 150))
                if result["checkpoint_reached"]
                else "12",
            ]
            if session:
                command += ["--resume", session]
            before = saved_run(root)
            agent_log = root / "logs/agent.log"
            previous_log = agent_log.read_text(encoding="utf-8") if agent_log.is_file() else ""
            log = destination / f"turn-{turn}.log"
            result["invocations"] += 1
            try:
                _run_turn(command, env, work, log, deadline)
            except ReviewError as exc:
                # Hermes chat -Q exits 1 on a resumable iteration boundary as well as
                # real errors. Require the actual foreground host event and committed
                # same-run progress; never use the model's final summary as proof.
                current_log = agent_log.read_text(encoding="utf-8") if agent_log.is_file() else ""
                suffix = (
                    current_log[len(previous_log) :] if current_log.startswith(previous_log) else ""
                )
                handoff = (
                    iteration_handoff(
                        before,
                        saved_run(root),
                        expected_session=session,
                        observed_session=_session(root),
                        source_path=paper,
                        source_hash=paper_hash,
                        runner=identity,
                        max_turns=int(command[command.index("--max-turns") + 1]),
                        agent_log=suffix,
                        turn_output=log.read_text(encoding="utf-8") if log.is_file() else "",
                    )
                    if str(exc).startswith("Hermes exited with status 1;")
                    else None
                )
                if handoff is None or not result["checkpoint_reached"]:
                    raise
                result["iteration_handoffs"].append(
                    {
                        **handoff,
                        "invocation": result["invocations"],
                        "exit_code": 1,
                        "log": log.name,
                    }
                )
            result["turns"] += 1
            observed_session = _session(root)
            if not observed_session:
                raise ReviewError("Hermes did not persist its evaluation session")
            if session and observed_session != session:
                raise ReviewError("Hermes changed session during bounded continuation")
            session = observed_session
            run = saved_run(root)
            if run and run.get("identity", {}).get("runner") != identity:
                raise ReviewError("Hermes used a different installed runner")
            if paused and run and run["id"] != paused:
                raise ReviewError("do not replace the saved support run during continuation")
            if not result["checkpoint_reached"]:
                if before is None and run is None:
                    current_log = agent_log.read_text(encoding="utf-8")
                    suffix = (current_log[len(previous_log):]
                              if current_log.startswith(previous_log) else "")
                    handoff = startup_handoff(
                        root, env, before=before, after=run, session=session, paper=paper,
                        paper_hash=paper_hash, runner=identity, model=settings["model"], pins=pins,
                        agent_log=suffix, turn_output=log.read_text(encoding="utf-8"),
                        max_turns=int(command[command.index("--max-turns") + 1]),
                    )
                    if handoff:
                        if result["startup_completion_requests"]:
                            raise ReviewError(
                                "startup still missing after one bounded continuation"
                            )
                        result["startup_completion_requests"] = 1
                        result["initial_checkpoint_state"] = "pre_start"
                        result["startup_handoffs"].append(
                            dict(**handoff, invocation=result["invocations"],
                                 log=log.name, exit_code=0)
                        )
                        prompt = (
                            f"Continue the SAME {source_label} setup in this SAME session. "
                            "The saved privacy preflight passed, but no support run exists. "
                            "The previous response did not execute startup. This is one bounded "
                            "continuation, not a privacy/policy override or evidence of review. "
                            "Retain the original request's scope, language and local route. "
                            f"Use only {paper}; select only {', '.join(requested)}, "
                            f"with response language {args.language}. Respect the normal privacy "
                            "rules; no journal approval or reviewer decisions are being supplied. "
                            "Start exactly ONE support run and call support next ONCE, then STOP "
                            "without writing/submitting answers or exporting. Do not restart this "
                            "session, change profile/model/budgets, or fetch external material."
                        )
                        continue
                boundary = checkpoint_state(run)
                answers = list((root / "review-data/support").glob("*/answers/*"))
                if boundary is None or answers:
                    raise ReviewError("first turn did not stop at the requested task boundary")
                paused = run["id"]
                if turn == 0:
                    result["initial_checkpoint_state"] = boundary
                if boundary == "unissued":
                    if result["checkpoint_completion_requests"]:
                        raise ReviewError(
                            "issued checkpoint still missing after one bounded continuation"
                        )
                    result["checkpoint_completion_requests"] = 1
                    prompt = (
                        f"Continue the SAME untouched {source_label} support run {paused} in this "
                        "session. You stopped after start, before the requested checkpoint. "
                        "Call `creview support next RUN` exactly once, replacing RUN with "
                        f"{paused}, then STOP. Do not write or submit an answer, export, "
                        "start another run, or change profile/model/settings. "
                        "This is checkpoint setup only; no reviewer decisions are provided."
                    )
                    continue
                result["checkpoint_reached"] = True
            if run and all(
                s["status"] in {"complete", "partial", "failed", "not_assessable"}
                for s in run["modules"].values()
            ):
                with environment(env):
                    result.update(
                        audit(
                            root, module, identity, paper_hash, paused, requested_modules=requested
                        )
                    )
                if result["dossier"]:
                    break
            run_id = run["id"] if run else paused
            prompt = (
                f"Resume the SAME {source_label} support run {run_id} using support status/next. "
                "Follow each task's template and answer_path; submit and continue until no tasks "
                "remain. On a refusal call next for a fresh answer_path, repair only the "
                "stated problem into that new file, retry once, then respect "
                "visible module failure. Do not restart or change model/profile/budgets. "
                "Then call support report and support export ONCE, even for partial results. "
                "Do not accept/reject/edit findings on my behalf; no reviewer decisions were "
                "provided. Show the actual status, counts and dossier paths. Keep all records. "
                "Do not claim scientific validity or release qualification."
            )
        else:
            raise ReviewError("dossier was not completed within six bounded Hermes turns")
    except (ReviewError, OSError, sqlite3.Error, ValueError, KeyError, TypeError) as exc:
        result["error"] = str(exc)
    finally:
        if root:
            result["profile_root"] = str(root)
        result["elapsed_seconds"] = round(time.monotonic() - started, 2)
        result["semantic_quality"] = "not_assessed_requires_human_review"
        result["qualification"] = "not_qualified"
        atomic_write_json(destination / "result.json", result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--profile", help="read endpoint/model settings only; never modify profile")
    source.add_argument(
        "--gateway-url", help="explicit private endpoint instead of a source profile"
    )
    parser.add_argument("--model", help="required with --gateway-url")
    parser.add_argument("--context-length", type=int, help="required with --gateway-url")
    parser.add_argument("--hermes", default="hermes")
    parser.add_argument("--output", type=Path, required=True, help="NEW results directory")
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "evals/support-pilot/manuscripts",
    )
    parser.add_argument("--case", action="append", choices=list(CASES))
    parser.add_argument("--language", default="en", help="pilot response language (default en)")
    parser.add_argument("--timeout", type=int, default=900, help="seconds per article")
    parser.add_argument("--total-timeout", type=int, default=10800, help="seconds for entire batch")
    args = parser.parse_args(argv)
    if os.environ.get("HERMES_SESSION_ID"):
        parser.error("run this evaluator outside Hermes")
    args.hermes = shutil.which(args.hermes)
    if not args.hermes:
        parser.error("Hermes executable not found; supply --hermes /absolute/path")
    if args.output.exists():
        parser.error("choose a new output directory; previous results are never overwritten")
    if min(args.timeout, args.total_timeout) < 30:
        parser.error("timeouts must be at least 30 seconds")
    if args.gateway_url:
        if not args.model or not args.context_length:
            parser.error("--gateway-url requires --model and --context-length")
        settings = {
            "gateway_url": args.gateway_url,
            "model": args.model,
            "context_length": args.context_length,
        }
    else:
        if args.model or args.context_length:
            parser.error("model/context overrides need --gateway-url; do not alter source profiles")
        report = inspect_profile(args.profile or "closed-review", live=False)
        if not report["ready"]:
            parser.error("source profile preflight: " + "; ".join(report["problems"]))
        config = yaml.safe_load((Path(report["profile_root"]) / "config.yaml").read_text())
        settings = {
            "gateway_url": report["base_url"],
            "model": report["model"],
            "context_length": config.get("model", {}).get("context_length"),
        }
    args.output = args.output.expanduser().resolve()
    args.corpus = args.corpus.expanduser().resolve()
    selected = list(dict.fromkeys(args.case or CASES))
    for case in selected:
        paper = args.corpus / f"{case}.md"
        if not paper.is_file() or paper.is_symlink():
            parser.error(f"missing/nonregular synthetic manuscript: {paper}")
    ensure_private_dir(args.output)
    batch = {
        "protocol": PROTOCOL,
        "synthetic_only": True,
        "started_at": now_iso(),
        "model_settings": settings,
        "identity": installed_identity(),
        "harness_sha256": sha256_file(Path(__file__)),
        "runs": [],
        "semantic_quality": "not_assessed_requires_human_review",
        "qualification": "not_qualified",
        "network_isolation": "not_enforced",
        "engineering_passed": False,
    }
    deadline = time.monotonic() + args.total_timeout
    atomic_write_json(args.output / "batch.json", batch)
    for case in selected:
        if time.monotonic() >= deadline:
            batch["stopped"] = "total timeout; remaining cases were not run"
            break
        print(f"Starting {case}: {CASES[case]}", flush=True)
        result = run_case(
            args, case, CASES[case], settings, min(deadline, time.monotonic() + args.timeout)
        )
        batch["runs"].append(result)
        atomic_write_json(args.output / "batch.json", batch)
        print(
            f"{case}: engineering_passed={result['engineering_passed']}; "
            f"{result['elapsed_seconds']}s; {result.get('error', '')}",
            flush=True,
        )
    batch["engineering_passed"] = len(batch["runs"]) == len(selected) and all(
        r["engineering_passed"] for r in batch["runs"]
    )
    batch["finished_at"] = now_iso()
    atomic_write_json(args.output / "batch.json", batch)
    print(f"Results: {args.output / 'batch.json'}; semantic quality NOT assessed", flush=True)
    return 0 if batch["engineering_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
