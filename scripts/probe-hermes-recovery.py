"""Exercise real Hermes recovery using synthetic data in a disposable profile.

Run after, not concurrently with, the timed qualification batch. The compression test lowers
the token threshold in its temporary profile; it does not modify the deployment profile.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
import time
from pathlib import Path

import yaml

from closed_review import smoke
from closed_review.deployment import PROFILE_MANIFEST, setup_profile
from closed_review.errors import ReviewError
from closed_review.hermes import inspect_profile, profile_root
from closed_review.io import atomic_write_json, atomic_write_text
from closed_review.parsers import parse_document


def write_image_only_pdf(path: Path) -> None:
    """Create a page with visible synthetic text as pixels, but no extractable text layer."""
    glyphs = {
        "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
        "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
        "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
        "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
        "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
        " ": ("00000",) * 7,
    }
    width, height, scale = 220, 80, 4
    pixels = bytearray([255] * (width * height))
    for column, character in enumerate("DATA 42"):
        for row, pattern in enumerate(glyphs[character]):
            for x, bit in enumerate(pattern):
                if bit == "1":
                    for dy in range(scale):
                        for dx in range(scale):
                            px, py = 20 + column * 6 * scale + x * scale + dx, 22 + row * scale + dy
                            pixels[py * width + px] = 0
    drawing = b"q 440 0 0 160 72 300 cm /Im0 Do Q"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /XObject << /Im0 5 0 R >> >> /Contents 4 0 R >>"
        ),
        f"<< /Length {len(drawing)} >>\nstream\n".encode() + drawing + b"\nendstream",
        (
            (
                f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} "
                f"/ColorSpace /DeviceGray /BitsPerComponent 8 /Length {len(pixels)} >>\nstream\n"
            ).encode()
            + bytes(pixels)
            + b"\nendstream"
        ),
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    path.write_bytes(pdf)


def unreadable_pdf_probe(profile: str, *, hermes: str | None, timeout: int) -> dict:
    """Check the model tells the reviewer when a synthetic PDF has no extractable text."""
    executable = shutil.which(hermes or "hermes")
    if not executable:
        raise ReviewError("Hermes executable not found")
    source = profile_root(profile)
    report = inspect_profile(profile)
    if not (source / PROFILE_MANIFEST).is_file() or not report["ready"]:
        raise ReviewError("a ready managed review profile is required")
    config = yaml.safe_load((source / "config.yaml").read_text(encoding="utf-8"))
    problems = [
        *report.get("compatibility", {}).get("deployment_problems", []),
        *smoke.review_profile_problems(config),
    ]
    if problems or report["skill_changes"]:
        raise ReviewError("review profile has drifted; inspect it before this probe")
    started = time.monotonic()
    temporary = Path(tempfile.mkdtemp(prefix="creview-pdf-probe-"))
    base = temporary / "hermes"
    env = smoke._child_environment(base)
    result: dict = {"passed": False, "synthetic_only": True, "artifacts": str(temporary)}
    try:
        with smoke.environment(env):
            setup = setup_profile(
                "pdf-probe",
                gateway_url=report["base_url"],
                model=report["model"],
                context_length=config.get("model", {}).get("context_length"),
                apply=True,
            )
        root = Path(setup["profile_root"])
        local = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
        config["terminal"] = local["terminal"]
        atomic_write_text(root / "config.yaml", yaml.safe_dump(config, sort_keys=False))
        env["HERMES_HOME"] = str(root)
        env["CREVIEW_HOME"] = str(root / "review-data")
        work = root / "work"
        paper = work / "manuscript.pdf"
        write_image_only_pdf(paper)
        warnings = parse_document(paper).warnings
        query = work / "query.txt"
        atomic_write_text(
            query,
            "This is a synthetic deployment test. The journal permits local AI assistance. "
            "I confirm the quantitative design profile. Follow journal-article-review on "
            + str(paper)
            + ". Tell me what you can review and do not use external tools or purge records.",
        )
        log = temporary / "turn-0.log"
        smoke._run_turn(
            [
                executable,
                "chat",
                "--query-file",
                str(query),
                "--oneshot",
                "-Q",
                "--skills",
                "journal-article-review",
                "--max-turns",
                "30",
            ],
            env,
            work,
            log,
            started + timeout,
        )
        answer = log.read_text(encoding="utf-8")
        warning_pattern = (
            r"(?:no|little|lack(?:s|ing)?|without|not|unable|cannot|can't|could not|failed)"
            r"[^.\n]{0,90}(?:extract|read|text|content)|"
            r"(?:extract|read|text)[^.\n]{0,90}(?:no|little|not|unable|cannot|can't|empty)"
        )
        result["checks"] = {
            "parser_warned_no_text": any("no extractable text" in w for w in warnings),
            "parser_warned_image": any("embedded image" in w for w in warnings),
            "reviewer_warned": bool(re.search(warning_pattern, answer, re.IGNORECASE)),
        }
        result["passed"] = all(result["checks"].values())
        result["warnings"] = warnings
        result["manual_audit"] = "check the answer for invented content and misleading assurances"
    except (OSError, ReviewError, ValueError) as exc:
        result["error"] = str(exc)
    finally:
        result["elapsed_seconds"] = round(time.monotonic() - started, 2)
        atomic_write_json(temporary / "result.json", result)
    return result


def recovery_probe(
    mode: str, profile: str, *, hermes: str | None = None, timeout: int = 1800
) -> dict:
    if mode not in {"turn-limit", "compression"}:
        raise ReviewError("unknown recovery mode")
    original = smoke._run_turn
    observed: dict[str, object] = {"forced_turn_budget_exhausted": False}

    def instrument(command, env, work, log, deadline):
        command = list(command)
        agent_log = Path(env["HERMES_HOME"]) / "logs/agent.log"
        before = agent_log.read_text(encoding="utf-8") if agent_log.is_file() else ""
        if mode == "compression" and log.name == "turn-0.log":
            config_path = Path(env["HERMES_HOME"]) / "config.yaml"
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            # An absolute cap is needed: the pinned Hermes version floors the percentage trigger.
            config.setdefault("compression", {})["threshold_tokens"] = 20000
            atomic_write_text(config_path, yaml.safe_dump(config, sort_keys=False))
        if mode == "turn-limit" and log.name == "turn-1.log":
            command[command.index("--max-turns") + 1] = "3"
        try:
            return original(command, env, work, log, deadline)
        finally:
            if mode == "turn-limit" and log.name == "turn-1.log" and agent_log.is_file():
                new_log = agent_log.read_text(encoding="utf-8")[len(before) :]
                observed["forced_turn_budget_exhausted"] = bool(
                    re.search(
                        r"Turn ended: reason=(?:max_iterations_reached|budget_exhausted)", new_log
                    )
                )

    smoke._run_turn = instrument
    try:
        result = smoke.run_smoke(profile, hermes=hermes, timeout=timeout, keep=True)
    finally:
        smoke._run_turn = original
    root = Path(result["artifacts"]) / "hermes/profiles/smoke"
    log = root / "logs/agent.log"
    content = log.read_text(encoding="utf-8") if log.is_file() else ""
    observed["compression_completed"] = bool(re.search(r"Compression #\d+ complete", content))
    event = (
        observed["forced_turn_budget_exhausted"]
        if mode == "turn-limit"
        else observed["compression_completed"]
    )
    return {
        "mode": mode,
        "passed": bool(result["passed"] and event),
        "forced_test_setting": {"max_turns": 3}
        if mode == "turn-limit"
        else {"compression.threshold_tokens": 20000},
        "observed": observed,
        "smoke": result,
        "limitation": "synthetic recovery probe; draft meaning still requires independent review",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["turn-limit", "compression", "unreadable-pdf"])
    parser.add_argument("--profile", default="closed-review")
    parser.add_argument("--hermes")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    try:
        if args.mode == "unreadable-pdf":
            result = unreadable_pdf_probe(args.profile, hermes=args.hermes, timeout=args.timeout)
        else:
            result = recovery_probe(
                args.mode, args.profile, hermes=args.hermes, timeout=args.timeout
            )
    except ReviewError as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
