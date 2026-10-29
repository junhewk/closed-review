import pytest

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, read_json, sha256_file
from closed_review.qualification import check_release_gate, score_qualification


def fixture(tmp_path, *, valid=True, matches=None, confirmed=True, words=7000):
    output = tmp_path / "output"
    keys = tmp_path / "keys"
    manifest = tmp_path / "manifest.json"
    atomic_write_json(manifest, {"repetitions": 1, "cases": [{"id": "ms1"}]})
    atomic_write_json(
        output / "results.json",
        {
            "identity": {"manifest": sha256_file(manifest)},
            "smoke": {"passed": True},
            "runs": {
                "ms1-r1": {"passed": True, "manuscript_words": words, "scan_elapsed_seconds": 899}
            },
        },
    )
    atomic_write_json(keys / "ms1.json", {"planted": [{"id": "P1", "severity": "major"}]})
    atomic_write_json(
        output / "ms1-r1/scan.json",
        {
            "review": {
                "findings": [
                    {
                        "id": "F1",
                        "model_severity": "major",
                        "evidence": [{"quote": "shared anchor"}],
                        "flaw_checks": [
                            {
                                "shown": True,
                                "quotes_verified": True,
                                "flaw": "general/self-contradiction",
                            }
                        ],
                    }
                ]
            }
        },
    )
    atomic_write_json(
        output / "ms1-r1/audit.json",
        {
            "reviewer": "test assessor",
            "findings": [
                {
                    "id": "F1",
                    "valid": valid,
                    "matches": matches or [],
                    "confirmed_supported": confirmed,
                    "rationale": "Semantic assessment of the actual claim.",
                }
            ],
        },
    )
    atomic_write_json(
        output / "hardware.json",
        dict.fromkeys(
            [
                "hardware",
                "model_weights",
                "quantization",
                "runtime_version",
                "context_length",
                "peak_memory",
                "reviewer",
            ],
            "recorded",
        ),
    )
    atomic_write_json(
        output / "workflow-audit.json",
        {
            "reviewer": "test assessor",
            **dict.fromkeys(
                [
                    "accepted_only",
                    "reviewer_attribution",
                    "unsurfaced_hidden",
                    "compression_resume",
                    "turn_limit_resume",
                    "long_document",
                    "poor_pdf_extraction",
                ],
                True,
            ),
        },
    )
    return output, keys, manifest


def test_shared_quote_does_not_earn_recall(tmp_path):
    result = score_qualification(*fixture(tmp_path))
    assert result["major_recall"] == 0
    assert not result["qualified"]


def test_scoring_refuses_a_changed_manifest(tmp_path):
    output, keys, manifest = fixture(tmp_path)
    atomic_write_json(manifest, {"repetitions": 1, "cases": []})
    with pytest.raises(ReviewError, match="manifest differs"):
        score_qualification(output, keys, manifest)


def test_explicit_match_scores_but_small_sample_cannot_qualify(tmp_path):
    result = score_qualification(*fixture(tmp_path, matches=["P1"]))
    assert result["major_recall"] == result["major_precision"] == 1
    assert not result["gates"]["required_design_coverage"]
    assert not result["qualified"]


def test_unsupported_confirmations_block_even_with_perfect_recall(tmp_path):
    result = score_qualification(*fixture(tmp_path, matches=["P1"], confirmed=False))
    assert result["major_recall"] == 1
    assert result["unsupported_confirmations"] == 1
    assert not result["qualified"]


def test_short_manuscripts_do_not_establish_normal_length_latency(tmp_path):
    result = score_qualification(*fixture(tmp_path, matches=["P1"], words=2000))
    assert result["within_15_minutes"] is None
    assert not result["qualified"]


def test_timing_only_cases_count_latency_without_duplicate_quality_credit(tmp_path):
    output, keys, manifest = fixture(tmp_path, matches=["P1"], words=2000)
    cases = [{"id": "ms1"}] + [
        {"id": f"long-{i}", "timing_only": True, "control": True, "profiles": ["legal-analysis"]}
        for i in range(3)
    ]
    atomic_write_json(manifest, {"repetitions": 1, "cases": cases})
    report = read_json(output / "results.json")
    report["identity"]["manifest"] = sha256_file(manifest)
    for i in range(3):
        run_id = f"long-{i}-r1"
        report["runs"][run_id] = {
            "passed": True,
            "manuscript_words": 7000,
            "scan_elapsed_seconds": 899,
        }
        # No private key or semantic audit: this case is deliberately excluded from quality.
        atomic_write_json(output / run_id / "scan.json", {"review": {"findings": []}})
    atomic_write_json(output / "results.json", report)
    result = score_qualification(output, keys, manifest)
    assert result["major_recall"] == result["major_precision"] == 1
    assert result["normal_length_runs"] == 3
    assert result["gates"]["normal_length_latency"]
    assert not result["gates"]["required_design_coverage"]
    assert result["pending"] == []


def test_unfilled_semantic_audit_never_passes(tmp_path):
    result = score_qualification(*fixture(tmp_path, matches=["P1"], valid=None))
    assert result["pending"]
    assert not result["qualified"]


def test_release_requires_complete_score_for_exact_build(tmp_path):
    from closed_review.support import PROTOCOL
    from closed_review.support.qualification import GATES

    score = {
        "protocol": PROTOCOL,
        "qualified": True,
        "gates": dict.fromkeys(GATES, True),
        "identity": {"runner": "qualified-build"},
    }
    gate = tmp_path / "release.json"
    atomic_write_json(
        gate,
        {
            "version": "beta",
            "protocol": PROTOCOL,
            "configurations": [{"label": "Linux/local", "score": score}],
        },
    )
    assert check_release_gate(gate, "beta", "qualified-build") == ["Linux/local"]
    with pytest.raises(ReviewError, match="blocked"):
        check_release_gate(gate, "beta", "different-build")
    score["gates"]["workflow_audited"] = False
    atomic_write_json(
        gate,
        {
            "version": "beta",
            "protocol": PROTOCOL,
            "configurations": [{"label": "Linux/local", "score": score}],
        },
    )
    with pytest.raises(ReviewError, match="blocked"):
        check_release_gate(gate, "beta", "qualified-build")


def test_legacy_scan_score_cannot_qualify_new_default(tmp_path):
    output, keys, manifest = fixture(tmp_path, matches=["P1"])
    score = score_qualification(output, keys, manifest)
    score.update(qualified=True, identity={"runner": "build"})
    gate = tmp_path / "release.json"
    atomic_write_json(
        gate, {"version": "beta", "configurations": [{"label": "legacy", "score": score}]}
    )
    with pytest.raises(ReviewError, match="legacy scan"):
        check_release_gate(gate, "beta", "build")
