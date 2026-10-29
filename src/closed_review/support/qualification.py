"Offline human-audit scoring; no private answer keys belong on the model host."

from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..errors import ReviewError
from ..io import read_json, sha256_file
from ..routes import normalized_endpoint
from . import PROTOCOL
from .evaluation import SHA256
from .methods import MODULES
from .provenance import baseline_provenance, corpus_provenance, evaluation_provenance

GATES = {
    "module_coverage",
    "complete_runs",
    "human_audits",
    "concern_precision",
    "seeded_recall",
    "computed_support",
    "workflow_audited",
    "hardware_recorded",
    "repeated_runs",
    "checking_time_recorded",
    "baseline_recorded",
    "corpus_provenance",
    "evaluation_provenance",
}
WORKFLOW_CHECKS = {
    "source_binding",
    "local_routes",
    "interruption_resume",
    "module_independence",
    "poor_extraction",
    "reviewer_attribution",
    "dossier_fidelity",
    "language_settings",
}


def score(path: Path) -> dict[str, Any]:
    if os.environ.get("HERMES_SESSION_ID"):
        raise ReviewError(
            "score human audits offline on the evaluator's machine, never inside Hermes"
        )
    audit = read_json(path)
    if not isinstance(audit, dict) or audit.get("protocol") != PROTOCOL:
        raise ReviewError("not a medical-methods-v1 human audit")
    identity = audit.get("identity")
    if (
        not isinstance(identity, dict)
        or not isinstance(identity.get("runner"), str)
        or not identity["runner"]
        or not SHA256.fullmatch(identity["runner"])
    ):
        raise ReviewError("audit must identify the exact installed package sums as identity.runner")
    pending = []
    corpus_ok, corpus_cases = corpus_provenance(audit, path.parent)
    evaluation_ok, _reviewed_at_start, evaluated, baselines, model_settings = evaluation_provenance(
        audit,
        path.parent,
        corpus_cases,
    )
    if not corpus_ok:
        pending.append(
            "frozen synthetic corpus and independent source/representativeness audit missing"
        )
    counts: dict[str, dict[str, Any]] = {
        name: {
            "valid": 0,
            "concerns": 0,
            "matched": 0,
            "expected": 0,
            "controls": 0,
            "seeded": 0,
            "runs": 0,
            "checking_seconds": [],
            "baseline_checking_seconds": [],
        }
        for name in MODULES
    }
    if not evaluation_ok:
        pending.append("complete frozen evaluation batch provenance missing")
    repeats: dict[tuple[str, str], set[int]] = defaultdict(set)
    case_definitions = {}
    artifact_runs = set()
    baseline_sessions = set()
    complete, computed_ok, times_ok, baseline_ok = True, True, True, True
    entries = audit.get("runs", [])
    if not isinstance(entries, list):
        raise ReviewError("audit runs must be a list")
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("module") not in MODULES:
            raise ReviewError("audit references an unknown module")
        module, case = entry["module"], entry.get("case_id")
        repetition = entry.get("repetition")
        if (
            not isinstance(case, str)
            or not case
            or type(repetition) is not int
            or repetition not in {1, 2, 3}
        ):
            raise ReviewError("each case needs an ID and repetition 1, 2 or 3")
        group = (module, case)
        if repetition in repeats[group]:
            raise ReviewError("duplicate case repetition")
        repeats[group].add(repetition)
        artifact_path = Path(entry.get("artifact", ""))
        if not artifact_path.is_absolute():
            artifact_path = path.parent / artifact_path
        if not artifact_path.is_file() or entry.get("artifact_sha256") != sha256_file(
            artifact_path
        ):
            pending.append(f"{module}/{case}/{repetition}: missing/changed artifact")
            complete = False
            continue
        run = read_json(artifact_path)
        if run.get("protocol") != PROTOCOL or module not in run.get("modules", {}):
            raise ReviewError("audit artifact has the wrong protocol/module")
        if run.get("identity", {}).get("runner") != audit.get("identity", {}).get("runner"):
            raise ReviewError("qualification artifact and audited build identity differ")
        state = run["modules"][module]
        run_id = run.get("id")
        if not isinstance(run_id, str) or not run_id or (run_id, module) in artifact_runs:
            raise ReviewError("each repetition requires a distinct actual module run")
        artifact_runs.add((run_id, module))
        complete &= (
            state.get("status") == "complete"
            and not state.get("extraction_limits")
            and not state.get("coverage_gaps")
        )
        expected = entry.get("expected_issue_ids")
        if (
            not isinstance(expected, list)
            or any(not isinstance(x, str) or not x for x in expected)
            or len(set(expected)) != len(expected)
        ):
            raise ReviewError(
                "provide distinct expected issue IDs from the evaluator's private key"
            )
        control = entry.get("control")
        if type(control) is not bool or (control and expected) or (not control and not expected):
            raise ReviewError("a case must be a clean control or have known seeded issues")
        source_hash = run.get("source", {}).get("sha256")
        if not isinstance(source_hash, str) or len(source_hash) != 64:
            raise ReviewError("qualification requires the manuscript identity in every artifact")
        if corpus_cases.get(group) != source_hash:
            corpus_ok = False
            pending.append(
                f"{module}/{case}/{repetition}: source is not bound to the frozen corpus"
            )
        case_key = (module, case, repetition)
        evaluated_case = evaluated.get(case_key, {})
        bound_evaluation = (
            evaluated_case.get("run_id") == run_id
            and evaluated_case.get("artifact_sha256") == entry["artifact_sha256"]
            and evaluated_case.get("manuscript_sha256") == source_hash
            and evaluated_case.get("identity") == identity["runner"]
            and model_settings.get("model") == run.get("route", {}).get("model")
            and model_settings.get("context_length")
            == run.get("route", {}).get("configured_context_length")
            and normalized_endpoint(model_settings.get("gateway_url"))
            == normalized_endpoint(run.get("route", {}).get("base_url"))
        )
        evaluation_ok &= bound_evaluation
        if not bound_evaluation:
            pending.append(
                f"{module}/{case}/{repetition}: artifact differs from the frozen evaluation"
            )
        signature = (
            source_hash,
            control,
            tuple(sorted(expected)),
            run.get("route", {}).get("model"),
            run.get("route", {}).get("configured_context_length"),
            normalized_endpoint(run.get("route", {}).get("base_url")),
        )
        if group in case_definitions and case_definitions[group] != signature:
            raise ReviewError(
                "repetitions must use the same source, model, context, endpoint "
                "and private case definition"
            )
        case_definitions[group] = signature
        observed = state.get("observations", [])
        judgments = entry.get("judgments", [])
        if not isinstance(judgments, list) or any(not isinstance(j, dict) for j in judgments):
            raise ReviewError("judgments must be a list of objects")
        by_id = {j.get("id"): j for j in judgments}
        if len(by_id) != len(judgments) or set(by_id) != {o["id"] for o in observed}:
            pending.append(
                f"{module}/{case}/{repetition}: audit every final observation exactly once"
            )
        if entry.get("coverage_reviewed") is not True:
            pending.append(f"{module}/{case}/{repetition}: human coverage review missing")
        numerical_review = (
            entry.get("numerical_claims_reviewed") is True
            and entry.get("other_numerical_error_claims_supported") is True
        )
        computed_ok &= numerical_review
        if not numerical_review:
            pending.append(
                f"{module}/{case}/{repetition}: numerical claims throughout dossier "
                "not audited/supported"
            )
        bucket = counts[module]
        bucket["runs"] += 1
        bucket["controls" if control else "seeded"] += 1
        bucket["expected"] += len(expected)
        matches = set()
        for observation in observed:
            judgment = by_id.get(observation["id"], {})
            valid = judgment.get("valid")
            rationale = judgment.get("rationale")
            if type(valid) is not bool or not isinstance(rationale, str) or not rationale.strip():
                pending.append(f"{observation['id']}: validity/rationale missing")
            bucket["concerns"] += 1
            bucket["valid"] += valid is True
            matched = judgment.get("matches", [])
            if not isinstance(matched, list) or any(i not in expected for i in matched):
                raise ReviewError("judgment matches must name this case's expected issue IDs")
            if valid is True:
                matches.update(matched)
            numerical_claim = judgment.get("contains_computed_error_claim")
            if type(numerical_claim) is not bool:
                computed_ok = False
                pending.append(f"{observation['id']}: numerical-error claim classification missing")
            bound_computation = observation.get("kind") == "calculated_discrepancy" or bool(
                observation.get("calculation_ids")
            )
            if bound_computation and numerical_claim is not True:
                computed_ok = False
                pending.append(
                    f"{observation['id']}: linked computed error must be audited as numerical"
                )
            if numerical_claim is True or bound_computation:
                computed_ok &= valid is True and judgment.get("computed_supported") is True
        bucket["matched"] += len(matches)
        paired = baseline_provenance(
            entry,
            run,
            path.parent,
            baseline_sessions,
            baselines.get(case_key),
        )
        baseline_ok &= paired
        if not paired:
            pending.append(
                f"{module}/{case}/{repetition}: paired baseline output/provenance/"
                "human review missing"
            )
        for key in ("checking_seconds", "baseline_checking_seconds"):
            value = entry.get(key)
            okay = type(value) in (int, float) and 0 <= value < float("inf")
            if key == "checking_seconds":
                times_ok &= okay
            else:
                baseline_ok &= okay and entry.get("baseline_model") == run.get("route", {}).get(
                    "model"
                )
            if okay:
                bucket[key].append(value)
    metrics = {}
    for module, bucket in counts.items():
        metrics[module] = {
            **bucket,
            "precision": bucket["valid"] / bucket["concerns"] if bucket["concerns"] else None,
            "recall": bucket["matched"] / bucket["expected"] if bucket["expected"] else None,
        }
    hardware = audit.get("hardware", {})
    gates = {
        "module_coverage": all(v["controls"] >= 3 and v["seeded"] >= 3 for v in counts.values()),
        "complete_runs": bool(entries) and complete,
        "human_audits": isinstance(audit.get("reviewer"), str)
        and bool(audit["reviewer"].strip())
        and not pending,
        "concern_precision": all(
            v["precision"] is not None and v["precision"] >= 0.9 for v in metrics.values()
        ),
        "seeded_recall": all(
            v["recall"] is not None and v["recall"] >= 0.8 for v in metrics.values()
        ),
        "computed_support": bool(entries) and computed_ok,
        "repeated_runs": bool(repeats) and all(v == {1, 2, 3} for v in repeats.values()),
        "workflow_audited": all(audit.get("workflow", {}).get(k) is True for k in WORKFLOW_CHECKS),
        "hardware_recorded": all(
            hardware.get(k)
            for k in (
                "hardware",
                "weights",
                "quantization",
                "runtime",
                "context_length",
                "peak_memory",
            )
        ),
        "checking_time_recorded": bool(entries) and times_ok,
        "baseline_recorded": bool(entries) and baseline_ok,
        "corpus_provenance": corpus_ok
        and bool(corpus_cases)
        and set(case_definitions) == set(corpus_cases),
        "evaluation_provenance": evaluation_ok
        and bool(entries)
        and set(evaluated)
        == {(*group, rep) for group, values in repeats.items() for rep in values},
    }
    identity = audit.get("identity", {})
    if not isinstance(identity, dict) or not identity.get("runner"):
        raise ReviewError("audit must identify the exact installed package sums as identity.runner")
    return {
        "protocol": PROTOCOL,
        "identity": identity,
        "qualified": all(gates.values()),
        "gates": gates,
        "metrics": metrics,
        "pending": pending,
        "note": (
            "Human assertions are self-reported, not independent or authenticated certification."
        ),
    }
