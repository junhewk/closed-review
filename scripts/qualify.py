"""Run a pinned synthetic batch, or score it offline with privately held answer keys."""

import argparse
import json
from pathlib import Path

from closed_review.errors import ReviewError
from closed_review.qualification import run_qualification, score_qualification

parser = argparse.ArgumentParser(description=__doc__)
commands = parser.add_subparsers(dest="command", required=True)
run = commands.add_parser("run")
run.add_argument("--profile", default="closed-review")
run.add_argument("--corpus", type=Path, required=True, help="synthetic manuscripts only; no keys")
run.add_argument("--output", type=Path, required=True)
run.add_argument("--hermes")
run.add_argument("--timeout", type=int, default=1800)
score = commands.add_parser("score")
score.add_argument("--output", type=Path, required=True)
score.add_argument("--keys", type=Path, required=True, help="private evaluator-only answer keys")
for command in (run, score):
    command.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "evals/deployment/manifest.json",
    )
args = parser.parse_args()
try:
    if args.command == "run":
        result = run_qualification(
            args.profile,
            args.corpus,
            args.manifest,
            args.output,
            hermes=args.hermes,
            timeout=args.timeout,
        )
    else:
        result = score_qualification(args.output, args.keys, args.manifest)
    print(json.dumps(result, indent=2))
    if args.command == "score" and not result["qualified"]:
        raise SystemExit(1)
    if args.command == "run" and (
        not result.get("smoke", {}).get("passed")
        or any(not r.get("passed") for r in result["runs"].values())
    ):
        raise SystemExit(1)
except ReviewError as exc:
    parser.exit(2, f"{exc}\n")
