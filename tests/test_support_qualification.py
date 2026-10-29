import copy
from pathlib import Path

import pytest

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, atomic_write_text, read_json, sha256_file
from closed_review.support import PROTOCOL
from closed_review.support.evaluation import BASELINE_CHECKS
from closed_review.support.methods import MODULES
from closed_review.support.qualification import WORKFLOW_CHECKS, score

BUILD = "c" * 64


def route():
    return {
        "model": "local-test",
        "base_url": "http://127.0.0.1:8091/v1",
        "configured_context_length": 65536,
        "runtime": {
            "status": "verified",
            "provider": "custom",
            "model": "local-test",
            "base_url": "http://127.0.0.1:8091/v1",
        },
    }


def audit_fixture(tmp_path):
    # Deliberately simulated schema fixtures, never evidence of human/medical qualification.
    runs, cases = [], []
    for module in MODULES:
        for control in (True, False):
            for repetition in (1, 2, 3):
                case = module + ("-clean" if control else "-seeded")
                path = tmp_path / f"{module}-{case}-{repetition}.json"
                source_hash = ("a" if control else "b") * 64
                if repetition == 1:
                    cases.append(
                        {
                            "case_id": case,
                            "module": module,
                            "file": case + ".md",
                            "sha256": source_hash,
                        }
                    )
                observations = [] if control else [{"id": "o1", "kind": "methodological_concern"}]
                atomic_write_json(
                    path,
                    {
                        "protocol": PROTOCOL,
                        "id": f"{module}-{case}-{repetition}",
                        "source": {"sha256": source_hash},
                        "identity": {"runner": BUILD},
                        "route": route(),
                        "modules": {module: {"status": "complete", "observations": observations}},
                    },
                )
                baseline = path.with_suffix(".baseline.md")
                atomic_write_text(
                    baseline, "Synthetic plain-baseline schema fixture, not evidence.\n"
                )
                record = path.with_suffix(".baseline.json")
                atomic_write_json(
                    record,
                    {
                        "protocol": PROTOCOL,
                        "kind": "ordinary_hermes_baseline",
                        "case_id": case,
                        "module": module,
                        "repetition": repetition,
                        "identity": BUILD,
                        "manuscript_sha256": source_hash,
                        "artifact_sha256": sha256_file(baseline),
                        "model": "local-test",
                        "configured_context_length": 65536,
                        "runtime": route()["runtime"],
                        "session": f"baseline-{case}-{repetition}",
                        "engineering_passed": True,
                        "checks": dict.fromkeys(BASELINE_CHECKS, True),
                    },
                )
                runs.append(
                    {
                        "case_id": case,
                        "module": module,
                        "control": control,
                        "repetition": repetition,
                        "artifact": str(path),
                        "artifact_sha256": sha256_file(path),
                        "expected_issue_ids": [] if control else ["P1"],
                        "coverage_reviewed": True,
                        "numerical_claims_reviewed": True,
                        "other_numerical_error_claims_supported": True,
                        "judgments": []
                        if control
                        else [
                            {
                                "id": "o1",
                                "valid": True,
                                "matches": ["P1"],
                                "rationale": "Human inspected the exact issue.",
                                "contains_computed_error_claim": False,
                            }
                        ],
                        "checking_seconds": 30,
                        "baseline_checking_seconds": 90,
                        "baseline_model": "local-test",
                        "baseline_artifact": str(baseline),
                        "baseline_artifact_sha256": sha256_file(baseline),
                        "baseline_record": str(record),
                        "baseline_record_sha256": sha256_file(record),
                        "baseline_reviewed": True,
                        "baseline_review_notes": "Simulated scope/independence/usefulness review.",
                    }
                )
    manifest = tmp_path / "corpus-manifest.json"
    atomic_write_json(
        manifest,
        {
            "protocol": PROTOCOL,
            "corpus_id": "unit-schema-only",
            "synthetic_only": True,
            "independently_reviewed": True,
            "cases": cases,
        },
    )
    evaluation = tmp_path / "evaluation-batch.json"
    atomic_write_json(
        evaluation,
        {
            "protocol": PROTOCOL,
            "synthetic_only": True,
            "finished_at": "unit-test-finish",
            "requested_repetitions": 3,
            "identity": {"sums_sha256": BUILD},
            "manifest_sha256": sha256_file(manifest),
            "corpus_independently_reviewed": True,
            "model_settings": {
                "model": "local-test",
                "context_length": 65536,
                "gateway_url": route()["base_url"],
            },
            "runs": [
                {
                    "case_id": row["case_id"],
                    "module": row["module"],
                    "repetition": row["repetition"],
                    "run_id": read_json(Path(row["artifact"]))["id"],
                    "artifact_sha256": row["artifact_sha256"],
                    "identity": BUILD,
                    "manuscript_sha256": read_json(Path(row["artifact"]))["source"]["sha256"],
                }
                for row in runs
            ],
            "baselines": [read_json(Path(row["baseline_record"])) for row in runs],
        },
    )
    return {
        "protocol": PROTOCOL,
        "identity": {"runner": BUILD},
        "reviewer": "Human evaluator",
        "evaluation": {"batch": str(evaluation), "batch_sha256": sha256_file(evaluation)},
        "corpus": {
            "manifest": str(manifest),
            "manifest_sha256": sha256_file(manifest),
            "source_only_validated": True,
            "representative_medical_cases": True,
            "validation_reviewer": "Simulated unit fixture, not an actual review",
        },
        "hardware": dict.fromkeys(
            ["hardware", "weights", "quantization", "runtime", "context_length", "peak_memory"],
            "recorded",
        ),
        "workflow": dict.fromkeys(WORKFLOW_CHECKS, True),
        "runs": runs,
    }


def test_all_six_branches_and_three_repetitions_are_required(tmp_path):
    audit = audit_fixture(tmp_path)
    path = tmp_path / "audit.json"
    atomic_write_json(path, audit)
    result = score(path)
    assert result["qualified"] and all(result["gates"].values())
    audit["runs"] = audit["runs"][:-1]
    atomic_write_json(path, audit)
    assert not score(path)["qualified"]
    assert not score(path)["gates"]["repeated_runs"]


def test_empty_or_unjudged_outputs_never_qualify(tmp_path):
    audit = audit_fixture(tmp_path)
    path = tmp_path / "audit.json"
    seeded = next(x for x in audit["runs"] if not x["control"])
    seeded["judgments"][0]["valid"] = None
    atomic_write_json(path, audit)
    result = score(path)
    assert not result["qualified"] and result["pending"]


def test_structured_coverage_gap_blocks_even_a_mislabelled_complete_artifact(tmp_path):
    audit = audit_fixture(tmp_path)
    entry = audit["runs"][0]
    artifact = Path(entry["artifact"])
    run = read_json(artifact)
    run["modules"][entry["module"]]["coverage_gaps"] = [
        {
            "kind": "unreadable_content",
            "block_ids": ["b1"],
            "role": "population",
            "detail": "A participant description could not be read.",
        }
    ]
    atomic_write_json(artifact, run)
    entry["artifact_sha256"] = sha256_file(artifact)
    batch_path = Path(audit["evaluation"]["batch"])
    batch = read_json(batch_path)
    batch["runs"][0]["artifact_sha256"] = entry["artifact_sha256"]
    atomic_write_json(batch_path, batch)
    audit["evaluation"]["batch_sha256"] = sha256_file(batch_path)
    path = tmp_path / "audit.json"
    atomic_write_json(path, audit)
    result = score(path)
    assert result["gates"]["evaluation_provenance"]
    assert not result["qualified"] and not result["gates"]["complete_runs"]


def test_changed_artifact_or_different_runner_blocks_qualification(tmp_path):
    audit = audit_fixture(tmp_path)
    path = tmp_path / "audit.json"
    audit["runs"][0]["artifact_sha256"] = "wrong"
    atomic_write_json(path, audit)
    assert not score(path)["qualified"]
    audit = audit_fixture(tmp_path)
    audit["identity"]["runner"] = "d" * 64
    atomic_write_json(path, audit)
    with pytest.raises(ReviewError, match="build identity differ"):
        score(path)


def test_unsupported_computed_discrepancy_blocks_qualification(tmp_path):
    audit = audit_fixture(tmp_path)
    path = tmp_path / "audit.json"
    seeded = next(x for x in audit["runs"] if not x["control"])
    artifact = tmp_path / "computed.json"
    run = read_json(Path(seeded["artifact"]))
    run["id"] = "computed-run"
    run["modules"][seeded["module"]]["observations"][0]["kind"] = "calculated_discrepancy"
    atomic_write_json(artifact, run)
    seeded.update(artifact=str(artifact), artifact_sha256=sha256_file(artifact))
    seeded["judgments"][0]["computed_supported"] = False
    seeded["judgments"][0]["contains_computed_error_claim"] = True
    atomic_write_json(path, audit)
    assert not score(path)["gates"]["computed_support"]


def test_duplicate_repetitions_and_inference_host_scoring_are_refused(tmp_path, monkeypatch):
    audit = audit_fixture(tmp_path)
    audit["runs"].append(copy.deepcopy(audit["runs"][0]))
    path = tmp_path / "audit.json"
    atomic_write_json(path, audit)
    with pytest.raises(ReviewError, match="duplicate"):
        score(path)
    monkeypatch.setenv("HERMES_SESSION_ID", "model-session")
    with pytest.raises(ReviewError, match="never inside Hermes"):
        score(path)


def test_same_artifact_cannot_count_as_independent_repetitions(tmp_path):
    audit = audit_fixture(tmp_path)
    first, second = audit["runs"][:2]
    second.update(artifact=first["artifact"], artifact_sha256=first["artifact_sha256"])
    path = tmp_path / "audit.json"
    atomic_write_json(path, audit)
    with pytest.raises(ReviewError, match="distinct actual module run"):
        score(path)


@pytest.mark.parametrize("kind", ["methodological_concern", "reporting_question"])
def test_numerical_error_claim_cannot_evade_support_gate_by_its_label(tmp_path, kind):
    audit = audit_fixture(tmp_path)
    seeded = next(row for row in audit["runs"] if not row["control"])
    artifact = read_json(Path(seeded["artifact"]))
    artifact["modules"][seeded["module"]]["observations"][0]["kind"] = kind
    atomic_write_json(Path(seeded["artifact"]), artifact)
    seeded["artifact_sha256"] = sha256_file(Path(seeded["artifact"]))
    seeded["judgments"][0].update(contains_computed_error_claim=True, computed_supported=False)
    path = tmp_path / "audit.json"
    atomic_write_json(path, audit)
    result = score(path)
    assert not result["qualified"] and not result["gates"]["computed_support"]


def test_unreviewed_numerical_claims_outside_observations_block_qualification(tmp_path):
    audit = audit_fixture(tmp_path)
    audit["runs"][0]["other_numerical_error_claims_supported"] = None
    path = tmp_path / "audit.json"
    atomic_write_json(path, audit)
    assert not score(path)["gates"]["computed_support"]


@pytest.mark.parametrize(
    "problem",
    [
        "missing-output",
        "changed-output",
        "cloud-route",
        "wrong-context",
        "missing-trace-check",
        "no-human-review",
    ],
)
def test_baseline_requires_real_matching_output_route_context_and_review(tmp_path, problem):
    audit = audit_fixture(tmp_path)
    row = audit["runs"][0]
    record_path = Path(row["baseline_record"])
    record = read_json(record_path)
    if problem == "missing-output":
        row["baseline_artifact"] = "not-created.md"
    elif problem == "changed-output":
        atomic_write_text(Path(row["baseline_artifact"]), "changed")
    elif problem == "cloud-route":
        record["runtime"]["base_url"] = "https://api.example.com/v1"
    elif problem == "wrong-context":
        record["configured_context_length"] = 262144
    elif problem == "missing-trace-check":
        record["checks"]["ordinary_tools_only"] = None
    else:
        row["baseline_reviewed"] = None
    atomic_write_json(record_path, record)
    row["baseline_record_sha256"] = sha256_file(record_path)
    path = tmp_path / "audit.json"
    atomic_write_json(path, audit)
    assert not score(path)["gates"]["baseline_recorded"]


def test_reusing_a_baseline_session_is_not_an_independent_repetition(tmp_path):
    audit = audit_fixture(tmp_path)
    first, second = audit["runs"][:2]
    record = read_json(Path(second["baseline_record"]))
    record["session"] = read_json(Path(first["baseline_record"]))["session"]
    atomic_write_json(Path(second["baseline_record"]), record)
    second["baseline_record_sha256"] = sha256_file(Path(second["baseline_record"]))
    path = tmp_path / "audit.json"
    atomic_write_json(path, audit)
    assert not score(path)["gates"]["baseline_recorded"]


@pytest.mark.parametrize(
    "problem",
    [
        "unreviewed-inputs-without-audit",
        "missing-manifest",
        "changed-manifest",
        "no-source-review",
        "unrepresentative",
    ],
)
def test_corpus_requires_frozen_independent_validation_not_a_label(tmp_path, problem):
    audit = audit_fixture(tmp_path)
    corpus = audit["corpus"]
    manifest_path = Path(corpus["manifest"])
    manifest = read_json(manifest_path)
    if problem == "unreviewed-inputs-without-audit":
        manifest["independently_reviewed"] = False
        atomic_write_json(manifest_path, manifest)
        corpus["manifest_sha256"] = sha256_file(manifest_path)
        corpus["source_only_validated"] = None
    elif problem == "missing-manifest":
        corpus["manifest"] = "missing.json"
    elif problem == "changed-manifest":
        atomic_write_json(manifest_path, {**manifest, "corpus_id": "changed"})
    elif problem == "no-source-review":
        corpus["source_only_validated"] = None
    else:
        corpus["representative_medical_cases"] = False
    path = tmp_path / "audit.json"
    atomic_write_json(path, audit)
    assert not score(path)["gates"]["corpus_provenance"]


def test_original_input_review_label_cannot_be_rewritten_after_evaluation(tmp_path):
    audit = audit_fixture(tmp_path)
    batch_path = Path(audit["evaluation"]["batch"])
    batch = read_json(batch_path)
    batch["corpus_independently_reviewed"] = False
    atomic_write_json(batch_path, batch)
    audit["evaluation"]["batch_sha256"] = sha256_file(batch_path)
    path = tmp_path / "audit.json"
    atomic_write_json(path, audit)
    assert not score(path)["gates"]["evaluation_provenance"]


def test_input_preapproval_is_not_required_but_actual_offline_audit_still_is(tmp_path):
    # Simulated complete human audit schema, not real quality evidence.
    audit = audit_fixture(tmp_path)
    corpus = audit["corpus"]
    manifest_path = Path(corpus["manifest"])
    manifest = read_json(manifest_path)
    manifest["independently_reviewed"] = False
    atomic_write_json(manifest_path, manifest)
    corpus["manifest_sha256"] = sha256_file(manifest_path)
    batch_path = Path(audit["evaluation"]["batch"])
    batch = read_json(batch_path)
    batch.update(corpus_independently_reviewed=False, manifest_sha256=corpus["manifest_sha256"])
    atomic_write_json(batch_path, batch)
    audit["evaluation"]["batch_sha256"] = sha256_file(batch_path)
    path = tmp_path / "audit.json"
    atomic_write_json(path, audit)
    assert score(path)["qualified"]
    corpus["source_only_validated"] = None
    atomic_write_json(path, audit)
    assert not score(path)["qualified"]


def test_real_papers_cannot_be_qualified_as_seeded_or_clean_synthetic_cases(tmp_path):
    audit = audit_fixture(tmp_path)
    corpus = audit["corpus"]
    manifest_path = Path(corpus["manifest"])
    manifest = read_json(manifest_path)
    manifest["synthetic_only"] = False
    atomic_write_json(manifest_path, manifest)
    corpus["manifest_sha256"] = sha256_file(manifest_path)
    batch_path = Path(audit["evaluation"]["batch"])
    batch = read_json(batch_path)
    batch.update(synthetic_only=False, manifest_sha256=corpus["manifest_sha256"])
    atomic_write_json(batch_path, batch)
    audit["evaluation"]["batch_sha256"] = sha256_file(batch_path)
    path = tmp_path / "audit.json"
    atomic_write_json(path, audit)
    result = score(path)
    assert not result["gates"]["corpus_provenance"]
    assert not result["gates"]["evaluation_provenance"]
    assert not result["qualified"]


@pytest.mark.parametrize(
    "problem", ["missing-batch", "changed-batch", "omitted-run", "substituted-run"]
)
def test_evaluation_must_bind_every_actual_output_to_the_original_batch(tmp_path, problem):
    audit = audit_fixture(tmp_path)
    meta = audit["evaluation"]
    batch_path = Path(meta["batch"])
    batch = read_json(batch_path)
    if problem == "missing-batch":
        meta["batch"] = "missing.json"
    elif problem == "changed-batch":
        atomic_write_json(batch_path, {**batch, "finished_at": "changed"})
    elif problem == "omitted-run":
        batch["runs"].pop()
        atomic_write_json(batch_path, batch)
        meta["batch_sha256"] = sha256_file(batch_path)
    else:
        batch["runs"][0]["run_id"] = "different-source-execution"
        atomic_write_json(batch_path, batch)
        meta["batch_sha256"] = sha256_file(batch_path)
    path = tmp_path / "audit.json"
    atomic_write_json(path, audit)
    assert not score(path)["gates"]["evaluation_provenance"]
