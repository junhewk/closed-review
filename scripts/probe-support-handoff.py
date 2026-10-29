"""Real Hermes regressions for iteration handoffs and an existing unsubmitted draft.

Synthetic input only, disposable profiles, no private keys or automated medical judgments.
The smaller per-turn iteration bound is a test setting, never a deployment default.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import time
from pathlib import Path

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, ensure_private_dir, sha256_file
from closed_review.support import PROTOCOL


def load_pilot():
    path = Path(__file__).with_name("test-support-hermes.py")
    spec = importlib.util.spec_from_file_location("handoff_pilot", path)
    pilot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pilot)
    return pilot


def probe(args, settings):
    pilot = load_pilot()
    original = pilot._run_turn
    injected = None
    args.analysis_turn_limit = 20 if args.mode == "iteration" else 150

    def instrument(command, env, work, log, deadline):
        nonlocal injected
        root = Path(env["HERMES_HOME"])
        before = pilot.saved_run(root)
        if (
            args.mode == "draft"
            and injected is None
            and "--resume" in command
            and pilot.checkpoint_state(before) == "issued"
        ):
            draft = root / "review-data/support" / before["id"] / "answers/task-0001.json"
            if draft.exists() or draft.is_symlink():
                raise ReviewError("draft regression needs the pristine issued checkpoint")
            atomic_write_json(draft, {"task_id": "task-0001", "unfinished_harness_sentinel": True})
            injected = {"path": str(draft), "sha256": sha256_file(draft)}
        return original(command, env, work, log, deadline)

    pilot._run_turn = instrument
    try:
        case = pilot.run_case(
            args, "case-02", "statistics", settings, time.monotonic() + args.timeout
        )
    finally:
        pilot._run_turn = original
    if args.mode == "iteration":
        observed = bool(case.get("iteration_handoffs"))
        checks = {"actual_host_handoff_recorded": observed}
    else:
        draft = Path(injected["path"]) if injected else None
        fresh = sorted(draft.parent.glob("task-0001-draft-*.json")) if draft else []
        checks = {
            "existing_draft_injected": injected is not None,
            "old_draft_bytes_unchanged": bool(draft and sha256_file(draft) == injected["sha256"]),
            "new_answer_draft_written": bool(fresh),
        }
    return {
        "protocol": PROTOCOL,
        "mode": args.mode,
        "synthetic_only": True,
        "probe_passed": case["engineering_passed"] and all(checks.values()),
        "checks": checks,
        "injected_draft": injected,
        "analysis_turn_limit": args.analysis_turn_limit,
        "case": case,
        "qualification": "not_qualified",
        "semantic_quality": "not_assessed",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["iteration", "draft"])
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gateway-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--context-length", type=int, required=True)
    parser.add_argument("--hermes", default="hermes")
    parser.add_argument("--language", default="en")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    if os.environ.get("HERMES_SESSION_ID"):
        parser.error("run this synthetic regression outside Hermes")
    args.hermes = shutil.which(args.hermes)
    if not args.hermes or args.timeout < 30:
        parser.error("need a Hermes executable and a timeout of at least 30 seconds")
    args.output, args.corpus = (
        args.output.expanduser().resolve(),
        args.corpus.expanduser().resolve(),
    )
    if args.output.exists():
        parser.error("choose a NEW output; preserve every prior failure")
    if not (args.corpus / "case-02.md").is_file():
        parser.error("missing synthetic case-02.md")
    ensure_private_dir(args.output)
    settings = {name: getattr(args, name) for name in ("gateway_url", "model", "context_length")}
    result = probe(args, settings)
    atomic_write_json(args.output / "probe.json", result)
    print(f"{args.mode}: probe_passed={result['probe_passed']}; {args.output / 'probe.json'}")
    return 0 if result["probe_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
