"""Synthetic scope/language/long-source probes; no automatic medical-quality judgments.

Run serially after the ordinary candidate matrix. No services or regular profiles are changed.
The generated long source stresses traversal, not corpus realism or clinical correctness.
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

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, atomic_write_text, ensure_private_dir, sha256_file
from closed_review.receipts import installed_identity
from closed_review.smoke import environment
from closed_review.support import PROTOCOL, workflow


def load_pilot():
    path = Path(__file__).with_name("test-support-hermes.py")
    spec = importlib.util.spec_from_file_location("scope_pilot", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def long_source(original: str, minimum_words: int = 6500) -> str:
    """Deterministic neutral expansion: never counted as independently authored quality cases."""
    paragraphs = [original, "## Synthetic source-traversal stress material"]
    topics = [
        ("population", "eligibility, recruitment and the population represented by the estimate"),
        ("measurement", "instrument naming, timing, units and the meaning of the reported outcome"),
        (
            "analysis",
            "analysis populations, missingness and the distinction between counts and estimates",
        ),
        (
            "interpretation",
            "uncertainty, limitations and the boundary between association and causation",
        ),
        (
            "presentation",
            "table labels, denominator definitions and links between results and prose",
        ),
    ]
    index = 0
    words = len(" ".join(paragraphs).split())
    while words < minimum_words:
        topic, description = topics[index % len(topics)]
        paragraph = (
            f"### Stress passage {index + 1}: {topic}\n\n"
            f"This fictional manuscript's source-traversal note addresses {description}. "
            "It adds no participants, measurements, effect estimates, claims of benefit or "
            "external evidence to the preceding synthetic study. Repeated contextual material "
            "is intentionally used to test bounded extraction and resumption across source "
            "chunks, not to simulate a representative medical article. No new calculation "
            "inputs or checklist obligations should be inferred from this passage. The original "
            "study's stated methods and results remain the sole basis for its appraisal. "
            "These passages are not separate studies, supplementary files or reviewer instructions."
        )
        paragraphs.append(paragraph)
        words += len(paragraph.split())
        index += 1
    return "\n\n".join(paragraphs) + "\n"


def inject_module_failure(root: Path, env: dict, pilot) -> dict:
    """Deliberately refuse one module twice, only after a disposable run's initial pause."""
    run = pilot.saved_run(root)
    if (
        not run
        or run.get("cursor") != 0
        or not run.get("issued_task")
        or set(run.get("modules", {})) != {"statistics", "logic"}
        or Path(env["HERMES_HOME"]) != root
    ):
        raise ReviewError("fault injection requires the paused disposable two-module run")
    session = pilot._session(root)
    if not session:
        raise ReviewError("fault injection requires the original persisted Hermes session")
    # Hermes 0.21.5 mirrors auxiliary vision provider/model from config to its terminal.
    # Its terminal removes endpoint/credential variables. Reproduce only the two public
    # route selectors for this evaluator-side submission; do not copy secrets, alter
    # the saved route or bypass workflow._guard. A real route change must still fail.
    config = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
    injection_env = dict(env, HERMES_SESSION_ID=session)
    for field in ("provider", "model"):
        value = config.get("auxiliary", {}).get("vision", {}).get(field)
        if isinstance(value, str) and value.strip() and value != "auto":
            injection_env[f"AUXILIARY_VISION_{field.upper()}"] = value.strip()
    with environment(injection_env):
        task = workflow.next_task(run["id"])
        if task["task"]["module"] != "statistics" or task["task"]["stage"] != "extract":
            raise ReviewError("refuse only the initial statistics extraction, never another task")
        answer = Path(task["answer_path"])
        atomic_write_json(
            answer,
            {
                "task_id": task["task"]["id"],
                "facts": "DELIBERATE SYNTHETIC SCHEMA FAULT",
                "scope_limits": [],
                "coverage_gaps": [],
            },
        )
        refused = [workflow.submit(run["id"], answer) for _ in range(2)]
    return {
        "run_id": run["id"],
        "module": "statistics",
        "task": task["task"]["id"],
        "deliberate_test_fault": True,
        "two_refusals_observed": all(r.get("accepted") is False for r in refused)
        and refused[-1].get("module_failed") is True,
    }


def run_probe(args, case: str, settings: dict, pilot) -> dict:
    if args.mode != "module-failure":
        return pilot.run_case(args, case, "statistics", settings, time.monotonic() + args.timeout)
    original = pilot._run_turn
    calls = 0
    injection = {}

    def instrument(command, env, work, log, deadline):
        nonlocal calls, injection
        if (
            calls >= 1 and not injection and "--resume" in command
            and pilot.checkpoint_state(pilot.saved_run(Path(env["HERMES_HOME"]))) == "issued"
        ):
            injection = inject_module_failure(Path(env["HERMES_HOME"]), env, pilot)
            injection["instrumented_invocation"] = calls + 1
            atomic_write_json(args.output / "fault-injection.json", injection)
        result = original(command, env, work, log, deadline)
        calls += 1
        return result

    pilot._run_turn = instrument
    try:
        result = pilot.run_case(args, case, "statistics", settings, time.monotonic() + args.timeout)
    finally:
        pilot._run_turn = original
    result["injected_fault"] = injection
    return result


def inspect_probe(mode: str, result: dict) -> dict:
    checks = dict(result.get("checks", {}))
    root = Path(result["profile_root"]) if result.get("profile_root") else None
    pilot = load_pilot()
    run = pilot.saved_run(root) if root else None
    if mode in {"multi-module", "module-failure"}:
        checks["two_modules_explicitly_selected"] = bool(run) and set(run["modules"]) == {
            "statistics",
            "logic",
        }
        checks["module_context_ids_isolated"] = bool(run)
        if run:
            source_ids = {b["id"] for b in run["source"]["blocks"]}
            for state in run["modules"].values():
                own_facts = {f["id"] for f in state["facts"]}
                own_records = {
                    record["id"]
                    for section in ("criteria", "calculations")
                    for record in state.get(section, [])
                    if "id" in record
                }
                checks["module_context_ids_isolated"] &= all(
                    set(read["ids"] + [f["id"] for f in read.get("fragments", [])])
                    <= own_facts | own_records | source_ids
                    for read in state["reads"]
                ) and all(
                    set(connection["from"] + connection["to"]) <= own_facts
                    for connection in state["connections"]
                )
        if mode == "module-failure":
            # Ordinary completion must still be false. This is a separate, deliberately
            # failed-module probe, never a way to reclassify a failed ordinary matrix case.
            checks.pop("module_completed", None)
            checks["injected_fault_observed"] = (
                result.get("injected_fault", {}).get("two_refusals_observed") is True
            )
            checks["expected_module_states"] = bool(run) and {
                name: state["status"] for name, state in run["modules"].items()
            } == {"statistics": "failed", "logic": "complete"}
            checks["no_execution_error"] = "error" not in result
    elif mode == "korean":
        checks["explicit_korean_language"] = bool(run) and run.get("resolved_language") == "ko"
        prose = []
        if run:
            for state in run["modules"].values():
                prose += [state.get("title", ""), state.get("summary", "")]
                prose += [c["analysis"] for c in state["criteria"]]
                prose += [o["explanation"] for o in state["observations"]]
        # A necessary smoke signal, NOT a translation or semantic-fidelity verdict.
        checks["korean_prose_smoke_signal"] = bool(prose) and all(
            re.search(r"[가-힣]", value) is not None for value in prose
        )
    else:
        checks["multiple_extraction_chunks"] = (
            bool(run) and sum(task["stage"] == "extract" for task in run["tasks"]) >= 3
        )
        checks["every_source_block_issued"] = bool(run) and all(
            set(state["provided_blocks"]) == {b["id"] for b in run["source"]["blocks"]}
            for state in run["modules"].values()
        )
        checks["long_source_words"] = (
            bool(run)
            and len(Path(run["source"]["path"]).read_text(encoding="utf-8").split()) >= 6500
        )
    return {
        "mode": mode,
        "checks": checks,
        "probe_passed": all(checks.values())
        and (mode == "module-failure" or result.get("engineering_passed", False)),
        "case": result,
        "synthetic_only": True,
        "qualification": "not_qualified",
        "semantic_quality": "not_assessed_requires_human_review",
        "manual_audit": (
            "Inspect module independence, original-quote fidelity, translation, attention and "
            "usefulness. Issued blocks and Korean characters do not prove those properties. "
            "This probe is not a realistic-corpus or medical-accuracy benchmark."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["multi-module", "module-failure", "korean", "long-source"])
    parser.add_argument("--gateway-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--context-length", type=int, required=True)
    parser.add_argument("--hermes", default="hermes")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "evals/support-pilot/manuscripts",
    )
    args = parser.parse_args(argv)
    if os.environ.get("HERMES_SESSION_ID"):
        parser.error("run the evaluator outside Hermes")
    args.hermes = shutil.which(args.hermes)
    if not args.hermes or args.timeout < 30:
        parser.error("a Hermes executable and timeout of at least 30 seconds are required")
    args.output = args.output.expanduser().resolve()
    args.corpus = args.corpus.expanduser().resolve()
    if args.output.exists():
        parser.error("choose a NEW output directory")
    ensure_private_dir(args.output)
    args.language = "ko" if args.mode == "korean" else "en"
    args.requested_modules = (
        ["statistics", "logic"]
        if args.mode in {"multi-module", "module-failure"}
        else ["statistics"]
    )
    case = "case-01" if args.mode == "long-source" else "case-02"
    if args.mode == "long-source":
        args.paper_override = args.output / "synthetic-long-source.md"
        atomic_write_text(
            args.paper_override,
            long_source((args.corpus / f"{case}.md").read_text(encoding="utf-8")),
        )
    pilot = load_pilot()
    result = run_probe(
        args,
        case,
        {
            "gateway_url": args.gateway_url,
            "model": args.model,
            "context_length": args.context_length,
        },
        pilot,
    )
    report = inspect_probe(args.mode, result)
    report.update(
        protocol=PROTOCOL,
        identity=installed_identity()["sums_sha256"],
        harness_sha256=sha256_file(Path(__file__)),
        pilot_harness_sha256=sha256_file(Path(pilot.__file__)),
    )
    atomic_write_json(args.output / "probe.json", report)
    print(json.dumps(report, indent=2))
    return 0 if report["probe_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
