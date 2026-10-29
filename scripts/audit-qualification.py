"""Human-led semantic audit of one synthetic qualification run, entirely offline.

Run on the evaluator's machine, never on the model host. The script displays private answer keys
and saves the evaluator's decisions; it makes no model or network calls and does not grade them.
"""

from __future__ import annotations

import argparse
import json
import runpy
from pathlib import Path

from closed_review.errors import ReviewError
from closed_review.findings import confirmed_check
from closed_review.io import atomic_write_json, read_json, sha256_file


def _answer(prompt: str, choices: set[str]) -> str:
    while True:
        answer = input(prompt).strip().lower()
        if answer in choices:
            return answer
        print("Choose one of: " + ", ".join(sorted(choices)))


def audit_run(
    output: Path,
    keys: Path,
    manifest: Path,
    run_id: str,
    reviewer: str,
    *,
    revisit: bool = False,
    corpus: Path | None = None,
) -> dict:
    reviewer = reviewer.strip()
    if not reviewer:
        raise ReviewError("name the human evaluator")
    report = read_json(output / "results.json")
    if report.get("identity", {}).get("manifest") != sha256_file(manifest):
        raise ReviewError("manifest differs from the executed batch")
    run = report.get("runs", {}).get(run_id)
    if not run or not run.get("passed") or "/" in run_id or "\\" in run_id:
        raise ReviewError("select a completed, successful run from results.json")
    definition = read_json(manifest)
    case = next((c for c in definition["cases"] if c["id"] == run.get("case")), None)
    if not case or case.get("timing_only"):
        raise ReviewError("this run has no semantic audit; timing-only runs are scored separately")
    run_path = output / run_id
    audit_path = run_path / "audit.json"
    audit = read_json(audit_path)
    previous_reviewer = audit.get("reviewer", "").strip()
    if previous_reviewer and previous_reviewer != reviewer:
        raise ReviewError(f"this audit already belongs to {previous_reviewer}")
    scan = read_json(run_path / "scan.json")
    findings = {
        f["id"]: f
        for f in scan["review"]["findings"]
        if f.get("status") not in {"screened", "dismissed"}
    }
    decisions = audit.get("findings", [])
    if len(decisions) != len(findings) or {f.get("id") for f in decisions} != set(findings):
        raise ReviewError("audit template does not match the saved scan")
    key = (
        {"planted": [], "decoys": []}
        if case.get("control")
        else read_json(keys / f"{case['id']}.json")
    )
    packet = runpy.run_path(str(Path(__file__).with_name("prepare-audit-packet.py")))
    if corpus is not None:
        packet["prepare_packet"](output, corpus, manifest, run_id, keys)
    else:
        packet["_create_or_verify"](
            run_path / "answer-key.html", packet["key_page"](key, run_id).encode("utf-8")
        )
    valid_ids = {p["id"] for p in key.get("planted", [])}
    print("Assess the full meaning and evidence; shared quotes are not credit.")
    print(f"Readable finding and manuscript view: {run_path / 'review.html'}")
    print(f"Private answer-key view: {run_path / 'answer-key.html'}")
    if not (run_path / "review.html").is_file():
        print("The manuscript view is missing: rerun with --corpus /path/to/manuscripts.")
    print("The private key view stays on this machine and must not be shared with a model.")
    if valid_ids:
        print("Planted issue IDs in your private key: " + ", ".join(sorted(valid_ids)))
    if not decisions:
        print(
            f"No retained findings. Inspect the saved scan at {run_path / 'scan.json'} "
            "alongside the manuscript before recording your review."
        )
        signed_off = bool(previous_reviewer)
        if not previous_reviewer or revisit:
            choice = _answer("Record your review of this empty result? [y/n] ", {"y", "n"})
            if choice == "y":
                audit["reviewer"] = reviewer
                atomic_write_json(audit_path, audit)
                signed_off = True
                print("Saved.")
        return {
            "run": run_id,
            "reviewer": reviewer if signed_off else "",
            "decisions_saved": 0,
            "empty_result_reviewed": signed_off,
        }
    completed = 0
    stopped = False
    for entry in decisions:
        finding = findings[entry["id"]]
        confirmed = any(confirmed_check(item) for item in finding.get("flaw_checks", []))
        done = (
            type(entry.get("valid")) is bool
            and isinstance(entry.get("matches"), list)
            and bool(entry.get("rationale", "").strip())
            and (not confirmed or type(entry.get("confirmed_supported")) is bool)
        )
        if done and not revisit:
            continue
        print(f"\nFinding {entry['id']}:")
        print(finding.get("issue") or finding.get("title") or "See the readable finding view.")
        print("Read its cited passages, the full manuscript, and the private key before deciding.")
        choice = _answer(
            "Is the entire concern accurate and sufficiently supported? [y/n/unsure/quit] ",
            {"y", "n", "unsure", "skip", "quit"},
        )
        if choice == "quit":
            stopped = True
            break
        if choice in {"skip", "unsure"}:
            continue
        matches = []
        if choice == "y" and valid_ids:
            while True:
                text = input(
                    "Matching planted IDs, comma-separated (blank if none; unsure to skip): "
                ).strip()
                if text.lower() in {"unsure", "skip"}:
                    break
                matches = [part.strip() for part in text.split(",") if part.strip()]
                if len(matches) == len(set(matches)) and set(matches) <= valid_ids:
                    break
                print("Use unique IDs from the key; leave blank for a valid additional concern.")
            if text.lower() in {"unsure", "skip"}:
                continue
        supported = None
        if confirmed:
            check = _answer(
                "Are ALL tool-marked confirmed checks supported? [y/n/unsure] ",
                {"y", "n", "unsure", "skip"},
            )
            if check in {"unsure", "skip"}:
                continue
            supported = check == "y"
        rationale = ""
        while not rationale:
            rationale = input("Specific rationale: ").strip()
        entry.update(
            valid=choice == "y", matches=matches, confirmed_supported=supported, rationale=rationale
        )
        audit["reviewer"] = reviewer
        atomic_write_json(audit_path, audit)
        completed += 1
        print("Saved.")
    return {
        "run": run_id,
        "reviewer": audit.get("reviewer", ""),
        "decisions_saved": completed,
        "stopped": stopped,
    }


def audit_available_runs(
    output: Path,
    keys: Path,
    manifest: Path,
    reviewer: str,
    *,
    revisit: bool = False,
    corpus: Path | None = None,
) -> dict:
    """Walk completed quality runs in manifest order, preserving each human decision."""
    report = read_json(output / "results.json")
    if report.get("identity", {}).get("manifest") != sha256_file(manifest):
        raise ReviewError("manifest differs from the executed batch")
    definition = read_json(manifest)
    expected = [
        f"{case['id']}-r{repetition}"
        for case in definition["cases"]
        if not case.get("timing_only")
        for repetition in range(1, definition.get("repetitions", 3) + 1)
    ]
    available = [
        run_id for run_id in expected if report.get("runs", {}).get(run_id, {}).get("passed")
    ]
    print(f"Completed quality runs available: {len(available)}/{len(expected)}.")
    results = []
    for run_id in available:
        print(f"\n=== {run_id} ===")
        result = audit_run(output, keys, manifest, run_id, reviewer, revisit=revisit, corpus=corpus)
        results.append(result)
        if result.get("stopped"):
            break
    return {
        "quality_runs_available": len(available),
        "quality_runs_expected": len(expected),
        "runs_visited": len(results),
        "decisions_saved": sum(result["decisions_saved"] for result in results),
        "stopped": bool(results and results[-1].get("stopped")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--keys", type=Path, required=True)
    parser.add_argument(
        "--corpus", type=Path, help="synthetic manuscript directory for readable views"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--run", required=True, help="for example ms1-r1, or all available runs")
    parser.add_argument("--reviewer", required=True, help="name of the human evaluator")
    parser.add_argument("--revisit", action="store_true", help="also revisit completed decisions")
    args = parser.parse_args()
    try:
        if args.run == "all":
            result = audit_available_runs(
                args.output,
                args.keys,
                args.manifest,
                args.reviewer,
                revisit=args.revisit,
                corpus=args.corpus,
            )
        else:
            result = audit_run(
                args.output,
                args.keys,
                args.manifest,
                args.run,
                args.reviewer,
                revisit=args.revisit,
                corpus=args.corpus,
            )
    except (ReviewError, EOFError, KeyboardInterrupt) as exc:
        parser.exit(2, f"audit stopped: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
