"""Synthetic-only early-checkpoint regression, followed by genuine turn-limit recovery.

Run serially in a fresh disposable profile. This wrapper keeps the ordinary evaluator intact,
uses a separately saved start-only first prompt, and fails unless the one bounded same-session
checkpoint-completion branch actually executes before the forced interruption.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_text, sha256_file

CHECKPOINT_PROMPT = (
    "Start exactly one support run, then call `creview support next RUN`. STOP at that "
    "point without writing/submitting an answer or exporting. I will ask you to resume. "
)
START_ONLY_PROMPT = (
    "Start exactly one support run, then STOP immediately after start. Do NOT call "
    "`creview support next RUN` yet. Do not write or submit an answer or export. "
    "I will explicitly ask you to complete the first checkpoint in this SAME session. "
)


def load_recovery():
    path = Path(__file__).with_name("probe-support-recovery.py")
    spec = importlib.util.spec_from_file_location("bootstrap_recovery", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def install_wrapper(probe):
    original_load = probe.load_pilot
    original_recovery = probe.recovery
    evidence = {"start_only_prompt_used": False, "actual_initial_checkpoint_state": None}

    def load_pilot():
        pilot = original_load()
        original_turn = pilot._run_turn
        calls = 0

        def bootstrap(command, env, work, log, deadline):
            nonlocal calls
            first = calls == 0
            calls += 1
            if first:
                if "--resume" in command or pilot.saved_run(Path(env["HERMES_HOME"])):
                    raise ReviewError("bootstrap regression requires a fresh session/run")
                command = list(command)
                index = command.index("--query-file") + 1
                query = Path(command[index])
                prompt = query.read_text(encoding="utf-8")
                if prompt.count(CHECKPOINT_PROMPT) != 1:
                    raise ReviewError("checkpoint prompt changed; do not guess a replacement")
                override = work / "bootstrap-start-only-query.txt"
                if override.exists():
                    raise ReviewError("preserve the previous bootstrap prompt")
                atomic_write_text(override, prompt.replace(CHECKPOINT_PROMPT, START_ONLY_PROMPT))
                command[index] = str(override)
                evidence.update(
                    start_only_prompt_used=True,
                    original_query=str(query),
                    original_query_sha256=sha256_file(query),
                    bootstrap_query=str(override),
                    bootstrap_query_sha256=sha256_file(override),
                )
            result = original_turn(command, env, work, log, deadline)
            if first:
                evidence["actual_initial_checkpoint_state"] = pilot.checkpoint_state(
                    pilot.saved_run(Path(env["HERMES_HOME"]))
                )
            return result

        pilot._run_turn = bootstrap
        return pilot

    def recovery(mode, args, settings):
        if mode != "turn-limit":
            raise ReviewError("bootstrap wrapper supports only the turn-limit regression")
        result = original_recovery(mode, args, settings)
        case = result.get("case", {})
        observed = result.get("observed", {})
        branch_executed = (
            evidence["start_only_prompt_used"]
            and evidence["actual_initial_checkpoint_state"] == "unissued"
            and case.get("initial_checkpoint_state") == "unissued"
            and case.get("checkpoint_completion_requests") == 1
            and case.get("checkpoint_reached") is True
            and 4 <= case.get("turns", 0) <= 6
            and observed.get("instrumented_invocation") == 3
        )
        result.update(
            mode="bootstrap-turn-limit",
            bootstrap=evidence.copy(),
            bootstrap_branch_executed=branch_executed,
            bootstrap_harness_sha256=sha256_file(Path(__file__)),
            probe_passed=result["probe_passed"] and branch_executed,
        )
        return result

    probe.load_pilot = load_pilot
    probe.recovery = recovery


def main(argv=None):
    probe = load_recovery()
    install_wrapper(probe)
    return probe.main(["turn-limit", *(sys.argv[1:] if argv is None else argv)])


if __name__ == "__main__":
    raise SystemExit(main())
