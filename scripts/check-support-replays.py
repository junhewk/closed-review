"""Reproduce saved synthetic source snapshots/calculations in a copied evaluator packet.

No model/network calls, private-key or judgment import, new dossier rendering, or changes to
the packet. This is record consistency using byte-matched code, not independent mathematical
validation, scientific interpretation, completeness certification or qualification.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
from importlib.metadata import version
from pathlib import Path, PurePosixPath

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, read_json, sha256_file
from closed_review.receipts import installed_identity, verify_receipt
from closed_review.support import PROTOCOL
from closed_review.support.calculators import calculate
from closed_review.support.methods import MODULES
from closed_review.support.sources import FORMATS, snapshot

SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
REPLAY_CODE = {
    "support/__init__.py",
    "support/calculators.py",
    "support/sources.py",
    "parsers.py",
    "errors.py",
    "io.py",
    "receipts.py",
}
SUBJECTS = {"dossier.html", "dossier.md", "reviewer-notes.md", "support.json"}


def sums_map(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        if "  " not in line:
            raise ReviewError("invalid independent package sums")
        digest, relative = line.split("  ", 1)
        path = PurePosixPath(relative)
        if (
            not SHA256.fullmatch(digest)
            or not relative
            or path.is_absolute()
            or ".." in path.parts
            or relative in result
        ):
            raise ReviewError("invalid independent package sums")
        result[relative] = digest
    return result


def local_file(root: Path, relative: str) -> Path:
    path = root / relative
    if (
        not path.resolve().is_relative_to(root)
        or not path.is_file()
        or any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(root))
    ):
        raise ReviewError("use regular artifact files inside the copied packet")
    return path


def encoded(value) -> str:
    # JSON comparison distinguishes booleans from 0/1 and never coerces or repairs a record.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def compare_sources(saved: dict, fresh: dict) -> dict:
    """Describe strict differences without leaking text or accepting geometry tolerances."""
    missing = object()

    def differences(a, b, path=""):
        if type(a) is not type(b):
            yield path, a, b
        elif isinstance(a, dict):
            for key in sorted(set(a) | set(b)):
                if not path and key == "path":
                    continue
                pointer = path + "/" + key.replace("~", "~0").replace("/", "~1")
                if key not in a or key not in b:
                    yield pointer, a.get(key, missing), b.get(key, missing)
                else:
                    yield from differences(a[key], b[key], pointer)
        elif isinstance(a, list):
            if len(a) != len(b):
                yield path, a, b
            for index, (first, second) in enumerate(zip(a, b, strict=False)):
                yield from differences(first, second, path + "/" + str(index))
        elif encoded(a) != encoded(b):
            yield path, a, b

    def coordinate(value):
        try:
            return type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            return False

    changed = list(differences(saved, fresh))
    bbox_only = (
        bool(changed)
        and saved.get("format") == fresh.get("format") == "pdf"
        and all(
            re.fullmatch(r"/tables/[0-9]+/bbox/[0-3]", path)
            and coordinate(first)
            and coordinate(second)
            for path, first, second in changed
        )
    )
    result = {
        "matches": not changed,
        "differing_fields_total": len(changed),
        "differing_fields": [path for path, _, _ in changed[:24]],
        "differing_fields_truncated": len(changed) > 24,
        "only_table_bbox_coordinates_differ": bbox_only,
    }
    if bbox_only:
        result["runtime_note"] = (
            "Strict mismatch retained. PDF bounding-box arithmetic can depend on the Python/"
            "dependency runtime. Inspect the original runtime before inferring a manuscript "
            "change. This diagnostic does not establish that the coordinate difference is harmless."
        )
    return result


def check(packet: Path, runner_sums: Path) -> dict:
    if os.environ.get("HERMES_SESSION_ID"):
        raise ReviewError("check copied artifacts offline on the evaluator machine, not in Hermes")
    if packet.is_symlink() or not packet.is_dir():
        raise ReviewError("use a regular copied evaluator packet directory")
    packet = packet.resolve()
    if runner_sums.is_symlink() or not runner_sums.is_file():
        raise ReviewError("supply independent sums from the original trusted wheel")
    reference = sums_map(runner_sums.read_text(encoding="utf-8"))
    evaluator = installed_identity()
    installed = sums_map(evaluator["sums"])
    if not all(
        name in reference and reference[name] == installed.get(name) for name in REPLAY_CODE
    ):
        raise ReviewError("replay/parser code differs from this artifact's trusted build")
    runner = sha256_file(runner_sums)
    batch_path = local_file(packet, "evaluation-batch.json")
    batch = read_json(batch_path)
    if (
        not isinstance(batch, dict)
        or batch.get("protocol") != PROTOCOL
        or type(batch.get("synthetic_only")) is not bool
        or batch.get("identity", {}).get("sums_sha256") != runner
    ):
        raise ReviewError("packet batch must identify its source kind, protocol and trusted build")
    rows = batch.get("runs")
    if not isinstance(rows, list) or not rows:
        raise ReviewError("packet has no saved support runs")
    seen = set()
    results = []
    for row in rows:
        label = row.get("artifact_id", row.get("case_id")) if isinstance(row, dict) else None
        if (
            not isinstance(label, str)
            or not SAFE_ID.fullmatch(label)
            or label in seen
            or row.get("module") not in MODULES
        ):
            raise ReviewError("packet needs distinct safe artifact IDs and known modules")
        seen.add(label)
        directory = packet / label
        artifact = local_file(packet, label + "/support.json")
        receipt_path = local_file(packet, label + "/receipt.json")
        run = read_json(artifact)
        receipt = read_json(receipt_path)
        if not isinstance(run, dict) or not isinstance(receipt, dict):
            raise ReviewError("run and receipt must be saved objects")
        subjects = receipt.get("subjects", [])
        if (
            not isinstance(subjects, list)
            or len(subjects) != len(SUBJECTS)
            or any(not isinstance(s, dict) for s in subjects)
            or {s.get("file") for s in subjects} != SUBJECTS
        ):
            raise ReviewError("receipt must name exactly the four local dossier files")
        for name in SUBJECTS:
            local_file(packet, label + "/" + name)
        if (
            run.get("protocol") != PROTOCOL
            or set(run.get("modules", {})) != {row["module"]}
            or run.get("identity", {}).get("runner") != runner
            or receipt.get("tool", {}).get("sums_sha256") != runner
            or row.get("artifact_sha256") != sha256_file(artifact)
            or not verify_receipt(receipt_path, runner_sums)["verified"]
        ):
            raise ReviewError("run, batch or receipt integrity differs from the trusted build")
        papers = list(directory.glob("manuscript.*"))
        if len(papers) != 1 or papers[0].suffix.lower() not in FORMATS:
            raise ReviewError("include one original supported manuscript per case")
        paper = local_file(packet, label + "/" + papers[0].name)
        digest = sha256_file(paper)
        source = run.get("source", {})
        if not isinstance(source, dict):
            raise ReviewError("saved source must be an object")
        if (
            digest != source.get("sha256")
            or digest != row.get("manuscript_sha256")
            or digest != receipt.get("source_sha256")
        ):
            raise ReviewError("original manuscript identity differs from the saved run")
        source_check = {"matches": False}
        try:
            fresh = snapshot(paper)
            # Relocation is the only omitted field. No quote/layout/numeric normalization.
            source_check = compare_sources(source, fresh)
        except (ReviewError, OSError, ValueError, KeyError, TypeError) as exc:
            source_check["error_type"] = type(exc).__name__
        calculations = []
        identifiers = set()
        saved_calculations = run["modules"][row["module"]].get("calculations", [])
        if not isinstance(saved_calculations, list):
            raise ReviewError("saved calculations must be a list")
        for saved in saved_calculations:
            if not isinstance(saved, dict):
                raise ReviewError("saved calculation must be an object")
            identifier = saved.get("id")
            if (
                not isinstance(identifier, str)
                or not SAFE_ID.fullmatch(identifier)
                or identifier in identifiers
            ):
                raise ReviewError("saved calculations need distinct safe IDs")
            identifiers.add(identifier)
            result = {"id": identifier, "accepted": False, "matches_saved": False}
            try:
                raw = {
                    key: saved[key]
                    for key in (
                        "method",
                        "inputs",
                        "parameters",
                        "method_evidence",
                        "assumptions",
                    )
                }
                comparison = saved["comparison"]
                if comparison.get("reported"):
                    raw["reported"] = {**comparison["reported"], "output": comparison["output"]}
                replayed = calculate(raw, source)
                original = {k: v for k, v in saved.items() if k != "id"}
                result.update(
                    accepted=True,
                    matches_saved=encoded(replayed) == encoded(original),
                    differing_fields=[
                        key
                        for key in sorted(set(replayed) | set(original))
                        if encoded(replayed.get(key)) != encoded(original.get(key))
                    ],
                )
            except (ReviewError, ValueError, KeyError, TypeError) as exc:
                result["error_type"] = type(exc).__name__
            calculations.append(result)
        results.append(
            {
                "artifact_id": label,
                "module": row["module"],
                "original_sha256": digest,
                "receipt_verified": True,
                "source_snapshot": source_check,
                "saved_module_status": run["modules"][row["module"]]["status"],
                "calculations": calculations,
                "checks_passed": source_check["matches"]
                and all(c["matches_saved"] for c in calculations),
            }
        )
    return {
        "protocol": PROTOCOL,
        "artifact_runner": runner,
        "evaluator_runner": evaluator["sums_sha256"],
        "checker_sha256": sha256_file(Path(__file__)),
        "evaluation_batch_sha256": sha256_file(batch_path),
        "python": platform.python_version(),
        "dependencies": {
            name: version(name)
            for name in (
                "scipy",
                "numpy",
                "pdfminer.six",
                "pdfplumber",
                "pypdfium2",
                "defusedxml",
            )
        },
        "replay_code_matches_reference": True,
        "cases": results,
        "calculations_checked": sum(len(c["calculations"]) for c in results),
        "all_checks_passed": all(c["checks_passed"] for c in results),
        "qualification": "not_qualified",
        "audit_template_or_private_keys_read": False,
        "human_judgments_created": False,
        "original_artifacts_changed": False,
        "model_or_network_calls": False,
        "note": (
            "Deterministic record reproduction with byte-matched code, not independent formula "
            "validation or proof of extraction completeness, input roles, scientific validity "
            "or concern correctness. Dependency versions are observed, not historical attestation. "
            "A reproduced calculation may record a numerical difference from the manuscript; "
            "reproduction is not numerical agreement. "
            "No existing run/pass/failure or human judgment is reclassified."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--runner-sums", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if (
        args.output.exists()
        or args.output.is_symlink()
        or args.output.resolve().is_relative_to(args.packet.resolve())
    ):
        parser.error("choose a NEW report outside the immutable copied packet")
    try:
        report = check(args.packet, args.runner_sums)
    except (ReviewError, OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"cannot check saved replay records: {type(exc).__name__}\n")
    atomic_write_json(args.output, report)
    print(
        json.dumps(
            {
                "all_checks_passed": report["all_checks_passed"],
                "cases": len(report["cases"]),
                "calculations_checked": report["calculations_checked"],
                "report": str(args.output),
                "qualification": "not_qualified",
            }
        )
    )
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
