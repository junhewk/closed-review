"""Repeat support and ordinary-Hermes baselines from a key-free corpus manifest.

All work is serial in new disposable profiles. No medical scoring, control assignment,
expected-issue generation or human checking times are supplied by this scheduler.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import time
from pathlib import Path
from types import SimpleNamespace

from closed_review.errors import ReviewError
from closed_review.io import (
    atomic_write_json,
    ensure_private_dir,
    now_iso,
    secure_file,
    sha256_file,
)
from closed_review.receipts import installed_identity
from closed_review.support import PROTOCOL
from closed_review.support.evaluation import load_manifest


def load_script(filename: str):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cases_from_manifest(path: Path, corpus: Path) -> tuple[dict, list[dict]]:
    return load_manifest(path, corpus)


def run(args) -> dict:
    manifest_hash = sha256_file(args.manifest)
    manifest, cases = cases_from_manifest(args.manifest, args.corpus)
    if sha256_file(args.manifest) != manifest_hash:
        raise ReviewError("corpus manifest changed while it was read")
    if args.output.exists():
        raise ReviewError("choose a NEW output directory; preserve all previous failures")
    pilot = load_script("test-support-hermes.py")
    baseline = load_script("test-support-baseline.py")
    ensure_private_dir(args.output)
    manifest_copy = args.output / "corpus-manifest.json"
    shutil.copyfile(args.manifest, manifest_copy)
    secure_file(manifest_copy)
    if sha256_file(manifest_copy) != manifest_hash:
        raise ReviewError("corpus manifest changed while it was copied")
    settings = {
        "gateway_url": args.gateway_url,
        "model": args.model,
        "context_length": args.context_length,
    }
    batch = {
        "protocol": PROTOCOL,
        "synthetic_only": manifest["synthetic_only"],
        "evaluation_scope": (
            "synthetic_diagnostic"
            if manifest["synthetic_only"]
            else "published_article_engineering_not_seeded_quality_evidence"
        ),
        "started_at": now_iso(),
        "corpus_id": manifest["corpus_id"],
        "corpus_independently_reviewed": manifest["independently_reviewed"],
        "manifest_sha256": manifest_hash,
        "model_settings": settings,
        "identity": installed_identity(),
        "harness_sha256": sha256_file(Path(__file__)),
        "pilot_harness_sha256": sha256_file(Path(pilot.__file__)),
        "baseline_harness_sha256": sha256_file(Path(baseline.__file__)),
        "requested_repetitions": args.repetitions,
        "runs": [],
        "baselines": [],
        "qualification": "not_qualified",
        "semantic_quality": "not_assessed_requires_human_review",
        "engineering_passed": False,
    }
    atomic_write_json(args.output / "batch.json", batch)
    deadline = time.monotonic() + args.total_timeout
    expected = len(cases) * args.repetitions
    for repetition in range(1, args.repetitions + 1):
        for row in cases:
            if time.monotonic() >= deadline:
                batch["stopped"] = "total time budget; unexecuted cases are not passes"
                break
            if sha256_file(row["path"]) != row["sha256"]:
                batch["stopped"] = "corpus changed during evaluation"
                break
            artifact = f"{row['case_id']}-r{repetition}"
            common = dict(
                corpus=args.corpus,
                hermes=args.hermes,
                language=args.language,
                paper_override=row["path"],
                timeout=args.timeout,
                synthetic_only=manifest["synthetic_only"],
            )
            print(f"Support {artifact}: {row['module']}", flush=True)
            result = pilot.run_case(
                SimpleNamespace(**common, output=args.output / "support"),
                artifact,
                row["module"],
                settings,
                min(deadline, time.monotonic() + args.timeout),
            )
            save_result(batch, result, row, artifact, repetition, args.output, "support")
            if time.monotonic() >= deadline:
                batch["stopped"] = "total time budget before matched baseline"
                break
            common["timeout"] = min(args.timeout, max(1, int(deadline - time.monotonic())))
            print(f"Ordinary Hermes baseline {artifact}: {row['module']}", flush=True)
            result = baseline.run_case(
                SimpleNamespace(**common, output=args.output / "baselines"),
                artifact,
                row["module"],
                settings,
            )
            save_result(batch, result, row, artifact, repetition, args.output, "baselines")
        if batch.get("stopped"):
            break
    batch["finished_at"] = now_iso()
    batch["engineering_passed"] = len(batch["runs"]) == len(batch["baselines"]) == expected and all(
        row["engineering_passed"] for row in batch["runs"] + batch["baselines"]
    )
    atomic_write_json(args.output / "batch.json", batch)
    return batch


def save_result(batch, result, row, artifact, repetition, output, kind):
    result.update(case_id=row["case_id"], artifact_id=artifact, repetition=repetition)
    if result.get("manuscript_sha256") != row["sha256"]:
        result["engineering_passed"] = False
        result["source_manifest_mismatch"] = True
    batch["runs" if kind == "support" else "baselines"].append(result)
    destination = ensure_private_dir(output / kind / artifact)
    atomic_write_json(destination / "result.json", result)
    atomic_write_json(output / "batch.json", batch)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="key-free corpus manifest")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gateway-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--context-length", type=int, required=True)
    parser.add_argument("--hermes", default="hermes")
    parser.add_argument("--language", default="en")
    parser.add_argument("--repetitions", type=int, choices=[1, 2, 3], default=3)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--total-timeout", type=int, default=21600)
    args = parser.parse_args(argv)
    if os.environ.get("HERMES_SESSION_ID"):
        parser.error("run the evaluator outside Hermes; never provide private keys")
    args.hermes = shutil.which(args.hermes)
    if not args.hermes or min(args.timeout, args.total_timeout) < 30:
        parser.error("a Hermes executable and timeouts of at least 30 seconds are required")
    for name in ("manifest", "corpus", "output"):
        setattr(args, name, getattr(args, name).expanduser().resolve())
    try:
        result = run(args)
    except (ReviewError, OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"{exc}\n")
    print(
        f"Results: {args.output / 'batch.json'}; semantic qualification remains closed", flush=True
    )
    return 0 if result["engineering_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
