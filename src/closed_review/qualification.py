"""Repeatable synthetic qualification; semantic judgments are supplied by a reviewer.

The execution path never opens answer keys. Scoring is a separate, offline operation and never
credits a finding merely because it quotes an anchor from a planted flaw.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .errors import ReviewError
from .findings import confirmed_check, severity
from .hermes import inspect_profile, profile_root
from .io import atomic_write_json, atomic_write_text, ensure_private_dir, read_json, sha256_file
from .receipts import installed_identity
from .smoke import run_smoke, run_synthetic_scan


def run_qualification(
    profile: str,
    corpus: Path,
    manifest: Path,
    output: Path,
    *,
    hermes: str | None = None,
    timeout: int = 1800,
) -> dict[str, Any]:
    definition = read_json(manifest)
    cases = definition["cases"]
    paths = {
        case["id"]: (manifest.parent if case.get("control") else corpus) / case["file"]
        for case in cases
    }
    for path in paths.values():
        if not path.is_file():
            raise ReviewError(f"synthetic manuscript is missing: {path}; never copy answer keys")
    identity = {
        "runner": installed_identity()["sums_sha256"],
        "profile_config": sha256_file(profile_root(profile) / "config.yaml"),
        "manifest": sha256_file(manifest),
        "manuscripts": {name: sha256_file(path) for name, path in paths.items()},
    }
    report_path = output / "results.json"
    if report_path.exists():
        report = read_json(report_path)
        if report["identity"] != identity:
            raise ReviewError(
                "configuration, corpus, or runner changed; use a new output directory"
            )
    else:
        if output.exists() and any(output.iterdir()):
            raise ReviewError("qualification output must be empty or contain matching results.json")
        report = {
            "identity": identity,
            "profile": profile,
            "environment": inspect_profile(profile),
            "runs": {},
            "qualification": "pending_semantic_and_hardware_audit",
        }
    ensure_private_dir(output)
    atomic_write_json(report_path, report)
    if not report.get("smoke", {}).get("passed"):
        report["smoke"] = run_smoke(profile, hermes=hermes, timeout=timeout, keep=True)
        atomic_write_json(report_path, report)
        if not report["smoke"]["passed"]:
            return report
    for case in cases:
        for repetition in range(1, definition.get("repetitions", 3) + 1):
            run_id = f"{case['id']}-r{repetition}"
            if run_id in report["runs"]:
                continue  # Completed failures count too; reruns need a new named batch.
            print(f"Qualification: {run_id}", flush=True)
            result = run_synthetic_scan(
                profile, paths[case["id"]], case["profiles"], hermes=hermes, timeout=timeout
            )
            record = {"case": case["id"], "control": bool(case.get("control")), **result}
            directory = ensure_private_dir(output / run_id)
            if result.get("scan_path"):
                scan_path = Path(result["scan_path"])
                atomic_write_text(directory / "scan.json", scan_path.read_text(encoding="utf-8"))
                record["scan_path"] = f"{run_id}/scan.json"
                scan = read_json(scan_path)
                entries = [
                    {
                        "id": f["id"],
                        "title": f.get("title"),
                        "issue": f.get("issue"),
                        "rating": severity(f),
                        "valid": None,
                        "matches": [],
                        "confirmed_supported": None,
                        "rationale": "",
                    }
                    for f in scan["review"]["findings"]
                    if f.get("status") not in {"screened", "dismissed"}
                ]
                atomic_write_json(directory / "audit.json", {"reviewer": "", "findings": entries})
            # Keep lightweight logs for failed runs; the original synthetic runtime is retained
            # at `artifacts` for resume/diagnostics and is never mixed with the reviewer's profile.
            for log in Path(result["artifacts"]).glob("*.log"):
                shutil.copyfile(log, directory / log.name)
                (directory / log.name).chmod(0o600)
            report["runs"][run_id] = record
            atomic_write_json(report_path, report)
    return report


def score_qualification(output: Path, keys: Path, manifest: Path) -> dict[str, Any]:
    """Run on the evaluator's machine, after bringing back results. No model calls."""
    report = read_json(output / "results.json")
    if report.get("identity", {}).get("manifest") != sha256_file(manifest):
        raise ReviewError("scoring manifest differs from the executed batch")
    definition = read_json(manifest)
    expected = {
        f"{case['id']}-r{i}": case
        for case in definition["cases"]
        for i in range(1, definition.get("repetitions", 3) + 1)
    }
    missing = []
    planted_total = found_total = major_total = valid_major = unsupported = 0
    fast = normal = 0
    workflow_ok = report.get("smoke", {}).get("passed") is True
    for run_id, case in expected.items():
        run = report["runs"].get(run_id)
        scan_path = output / run_id / "scan.json"
        audit_path = output / run_id / "audit.json"
        if not run or not run.get("passed") or not scan_path.is_file():
            missing.append(run_id)
            workflow_ok = False
            continue
        if 6000 <= run.get("manuscript_words", 0) <= 10000:
            normal += 1
            fast += int(run.get("scan_elapsed_seconds", float("inf")) <= 900)
        # Derived long manuscripts can establish latency without counting the same planted
        # issues twice in the independent quality score. They need no model-visible answer key.
        if case.get("timing_only"):
            continue
        if not audit_path.is_file():
            missing.append(f"{run_id}: missing semantic audit")
            continue
        key = {"planted": []} if case.get("control") else read_json(keys / f"{case['id']}.json")
        planted = {x["id"] for x in key["planted"] if x.get("severity") == "major"}
        all_planted = {x["id"] for x in key["planted"]}
        scan = read_json(scan_path)
        findings = {
            f["id"]: f
            for f in scan["review"]["findings"]
            if f.get("status") not in {"screened", "dismissed"}
        }
        audit = read_json(audit_path)
        decisions = audit.get("findings", [])
        if (
            not audit.get("reviewer")
            or len(decisions) != len(findings)
            or {f.get("id") for f in decisions} != set(findings)
        ):
            missing.append(f"{run_id}: incomplete semantic audit")
            continue
        found = set()
        for entry in decisions:
            f = findings[entry["id"]]
            confirmed = any(confirmed_check(c) for c in f.get("flaw_checks", []))
            if (
                type(entry.get("valid")) is not bool
                or not entry.get("rationale", "").strip()
                or not isinstance(entry.get("matches"), list)
                or not set(entry["matches"]) <= all_planted
                or (confirmed and type(entry.get("confirmed_supported")) is not bool)
            ):
                missing.append(f"{run_id}/{entry['id']}: incomplete semantic judgment")
                continue
            if entry["valid"]:
                found.update(set(entry["matches"]) & planted)
            if severity(f)["severity"] == "major":
                major_total += 1
                valid_major += int(entry["valid"])
            if confirmed and (not entry["valid"] or not entry["confirmed_supported"]):
                unsupported += 1
        planted_total += len(planted)
        found_total += len(found)
    recall = found_total / planted_total if planted_total else None
    precision = valid_major / major_total if major_total else None
    performance = fast / normal if normal else None
    hardware_path = output / "hardware.json"
    hardware = read_json(hardware_path) if hardware_path.is_file() else {}
    hardware_fields = (
        "hardware",
        "model_weights",
        "quantization",
        "runtime_version",
        "context_length",
        "peak_memory",
        "reviewer",
    )
    workflow_path = output / "workflow-audit.json"
    workflow = read_json(workflow_path) if workflow_path.is_file() else {}
    required_workflow = (
        "accepted_only",
        "reviewer_attribution",
        "unsurfaced_hidden",
        "compression_resume",
        "turn_limit_resume",
        "long_document",
        "poor_pdf_extraction",
    )
    quality_cases = [case for case in definition["cases"] if not case.get("timing_only")]
    covered = {p for case in quality_cases for p in case.get("profiles", [])}
    required_designs = {
        "qualitative",
        "quantitative",
        "systematic-review",
        "scoping-review",
        "normative-argument",
        "legal-analysis",
    }
    gates = {
        "required_design_coverage": definition.get("repetitions", 3) >= 3
        and len(quality_cases) >= 8
        and required_designs <= covered
        and sum(bool(c.get("control")) for c in quality_cases) >= 2,
        "complete_workflows": workflow_ok and set(report["runs"]) == set(expected),
        "complete_semantic_audits": not missing,
        "major_recall": recall is not None and recall >= 0.8,
        "major_precision": precision is not None and precision >= 0.9,
        "supported_confirmations": unsupported == 0 and not missing,
        "normal_length_latency": normal >= 3 and performance is not None and performance >= 0.9,
        "hardware_recorded": all(hardware.get(field) for field in hardware_fields),
        "workflow_audited": bool(workflow.get("reviewer"))
        and all(workflow.get(field) is True for field in required_workflow),
    }
    return {
        "identity": report.get("identity"),
        "qualified": all(gates.values()),
        "gates": gates,
        "pending": missing,
        "major_recall": recall,
        "major_precision": precision,
        "unsupported_confirmations": unsupported,
        "normal_length_runs": normal,
        "within_15_minutes": performance,
        "note": "Semantic judgments are reviewer-supplied; quote overlap never earns credit.",
    }


def check_release_gate(path: Path, version: str, sums_sha256: str) -> list[str]:
    """Require a qualified configuration tied to the actual release wheel before publishing."""
    gate = read_json(path)
    if gate.get("version") != version:
        raise ReviewError("release qualification version does not match the package")
    from .support import PROTOCOL
    from .support.qualification import GATES

    if gate.get("protocol") != PROTOCOL:
        raise ReviewError(
            "release blocked: legacy scan qualification cannot certify medical support"
        )
    required = GATES
    qualified = []
    for entry in gate.get("configurations", []):
        score = entry.get("score", {})
        if (
            entry.get("label")
            and score.get("protocol") == PROTOCOL
            and score.get("qualified") is True
            and score.get("identity", {}).get("runner") == sums_sha256
            and all(score.get("gates", {}).get(key) is True for key in required)
        ):
            qualified.append(entry["label"])
    if not qualified:
        raise ReviewError(
            "release blocked: no fully qualified configuration for this wheel's identity"
        )
    return qualified
