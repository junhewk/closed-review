import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, read_json, sha256_file
from closed_review.support import PROTOCOL

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/evaluate-support-hermes.py"
SPEC = importlib.util.spec_from_file_location("support_evaluation", SCRIPT)
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


def inputs(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    paper = corpus / "study.md"
    paper.write_text("# Synthetic manuscript\n\nA test of scheduling, not medical quality.")
    manifest = tmp_path / "manifest.json"
    value = {
        "protocol": PROTOCOL,
        "corpus_id": "synthetic-diagnostic",
        "synthetic_only": True,
        "independently_reviewed": False,
        "cases": [
            {
                "case_id": "article-a",
                "module": "statistics",
                "file": paper.name,
                "sha256": sha256_file(paper),
            }
        ],
    }
    atomic_write_json(manifest, value)
    args = SimpleNamespace(
        corpus=corpus,
        manifest=manifest,
        output=tmp_path / "evaluation",
        repetitions=3,
        hermes="fake",
        language="en",
        timeout=30,
        total_timeout=900,
        gateway_url="http://127.0.0.1:8091/v1",
        model="local-test",
        context_length=262144,
    )
    return args, value


@pytest.mark.parametrize("field", ["expected_issue_ids", "control", "keys", "private_answer"])
def test_manifest_refuses_evaluator_keys_and_control_metadata(tmp_path, field):
    args, value = inputs(tmp_path)
    value["cases"][0][field] = ["PRIVATE"]
    atomic_write_json(args.manifest, value)
    with pytest.raises(ReviewError, match="never expected issues"):
        evaluation.cases_from_manifest(args.manifest, args.corpus)
    value = read_json(args.manifest)
    del value["cases"][0][field]
    value[field] = "PRIVATE"
    atomic_write_json(args.manifest, value)
    with pytest.raises(ReviewError, match="never private answer keys"):
        evaluation.cases_from_manifest(args.manifest, args.corpus)


@pytest.mark.parametrize("problem", ["changed", "escape", "duplicate", "symlink"])
def test_manifest_rejects_changed_and_out_of_corpus_inputs(tmp_path, problem):
    args, value = inputs(tmp_path)
    row = value["cases"][0]
    if problem == "changed":
        row["sha256"] = "wrong"
    elif problem == "escape":
        outside = tmp_path / "outside.md"
        outside.write_text("never copy this outside source")
        row["file"] = "../outside.md"
    elif problem == "duplicate":
        value["cases"].append(copy.deepcopy(row))
    else:
        link = args.corpus / "link.md"
        link.symlink_to(args.corpus / "study.md")
        row["file"] = link.name
    atomic_write_json(args.manifest, value)
    with pytest.raises(ReviewError):
        evaluation.cases_from_manifest(args.manifest, args.corpus)
    assert not args.output.exists()


@pytest.mark.parametrize("baseline_passed", [False, True])
@pytest.mark.parametrize("synthetic", [False, True])
def test_three_repetitions_use_distinct_profiles_and_match_model_and_source(
    tmp_path,
    monkeypatch,
    baseline_passed,
    synthetic,
):
    args, value = inputs(tmp_path)
    value["synthetic_only"] = synthetic
    atomic_write_json(args.manifest, value)
    calls = []

    def fake_module(filename):
        kind = "support" if filename == "test-support-hermes.py" else "baseline"

        def run_case(settings, case, module, model, *extra):
            assert settings.synthetic_only is synthetic
            calls.append((kind, case, settings.output, settings.paper_override, model))
            return {
                "engineering_passed": kind == "support" or baseline_passed,
                "manuscript_sha256": sha256_file(settings.paper_override),
            }

        return SimpleNamespace(run_case=run_case, __file__=SCRIPT)

    monkeypatch.setattr(evaluation, "load_script", fake_module)
    result = evaluation.run(args)
    assert [row[0] for row in calls] == ["support", "baseline"] * 3
    assert len({(row[0], row[1], row[2]) for row in calls}) == 6
    assert {row[3] for row in calls} == {args.corpus / "study.md"}
    assert all(row[4]["model"] == "local-test" for row in calls)
    assert len(result["runs"]) == len(result["baselines"]) == 3
    assert [r["repetition"] for r in result["runs"]] == [1, 2, 3]
    assert {r["case_id"] for r in result["runs"]} == {"article-a"}
    assert result["engineering_passed"] is baseline_passed
    assert result["synthetic_only"] is synthetic
    assert ("published_article" in result["evaluation_scope"]) is not synthetic
    assert (
        result["qualification"] == "not_qualified"
        and result["corpus_independently_reviewed"] is False
    )
    assert result == read_json(args.output / "batch.json")
    assert (args.output / "support/article-a-r1/result.json").is_file()
    assert (args.output / "baselines/article-a-r3/result.json").is_file()


@pytest.mark.parametrize("value", [None, 0, 1, "true", "false", [], {}])
def test_source_kind_must_not_be_coerced_to_synthetic_or_real(tmp_path, value):
    args, manifest = inputs(tmp_path)
    manifest["synthetic_only"] = value
    atomic_write_json(args.manifest, manifest)
    with pytest.raises(ReviewError, match="explicit source kind"):
        evaluation.cases_from_manifest(args.manifest, args.corpus)


def test_time_budget_never_turns_an_empty_batch_into_a_pass(tmp_path, monkeypatch):
    args, _ = inputs(tmp_path)
    args.total_timeout = 0
    monkeypatch.setattr(evaluation, "load_script", lambda _: SimpleNamespace(__file__=SCRIPT))
    result = evaluation.run(args)
    assert not result["engineering_passed"] and not result["runs"]
    assert "total time budget" in result["stopped"]


def test_scheduler_never_overwrites_previous_results(tmp_path):
    args, _ = inputs(tmp_path)
    args.output.mkdir()
    marker = args.output / "reviewer-work.txt"
    marker.write_text("keep my work")
    with pytest.raises(ReviewError, match="NEW output"):
        evaluation.run(args)
    assert marker.read_text() == "keep my work"
