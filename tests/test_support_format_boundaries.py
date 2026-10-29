"""Detected format failures are not the same thing as general extractor limitations."""

from pathlib import Path

import pytest
from conftest import write_docx, write_pdf
from test_support import begin, finish
from test_support import support_env as support_env

from closed_review.io import atomic_write_json, read_json
from closed_review.support import workflow
from closed_review.support.render import export
from closed_review.support.sources import PDF_SCOPE_LIMIT, snapshot


def readable_pdf(path):
    lines = [
        "We enrolled 100 patients. There were 20 events (30%).",
        "The unweighted event denominator was 100.",
        "Each patient contributed one discharge and one binary outcome.",
        "Patients were analysed in their assigned randomized groups.",
        "No raw records, additional papers or images are supplied.",
    ]
    commands = (
        "BT /F1 10 Tf 72 720 Td "
        + " 0 -16 Td ".join(
            "(" + line.replace("(", r"\(").replace(")", r"\)") + ") Tj" for line in lines
        )
        + " ET"
    )
    write_pdf(path, content=commands)


def test_readable_pdf_keeps_caution_without_inventing_processing_failure(support_env):
    paper, key = support_env
    paper = paper.with_suffix(".pdf")
    readable_pdf(paper)
    source = snapshot(paper)
    assert not source["warnings"] and source["scope_limits"] == [PDF_SCOPE_LIMIT]
    assert source["extraction_verified"] is False
    run_id = workflow.start(paper, ["statistics"], session=key)["run_id"]
    first = workflow.next_task(run_id)
    assert first["context"]["source_warnings"] == []
    assert first["context"]["source_scope_limits"] == [PDF_SCOPE_LIMIT]
    run = finish(run_id)
    state = run["modules"]["statistics"]
    assert state["status"] == "complete"
    assert state["scope_limits"] == [PDF_SCOPE_LIMIT]
    assert not state["extraction_limits"] and not state["coverage_gaps"]
    document = Path(export(run_id)["html"]).read_text()
    assert document.count(PDF_SCOPE_LIMIT) == 1
    assert run["qualification"] == "not_qualified"


@pytest.mark.parametrize("format", ["markdown", "docx"])
def test_detected_geometry_failure_remains_partial_without_model_gap(support_env, format):
    paper, key = support_env
    if format == "markdown":
        with paper.open("a") as output:
            output.write("\n| Group | N | Value |\n|---|---|---|\n|A|20|\n")
    else:
        text = paper.read_text()
        paper = paper.with_suffix(".docx")
        write_docx(paper, [(None, text)], [["Group", "N", "Value"], ["A", "20"]])
    source = snapshot(paper)
    assert source["tables"][0]["ambiguous"]
    assert "ambiguous physical table geometry" in source["warnings"][0]
    run_id = workflow.start(paper, ["statistics"], session=key)["run_id"]
    state = finish(run_id)["modules"]["statistics"]
    assert state["status"] == "partial" and state["extraction_limits"]
    assert not state["coverage_gaps"]


def test_semantic_reconstruction_gap_still_blocks_unflagged_legible_source(support_env):
    run_id = begin(support_env)
    first = workflow.next_task(run_id)
    assert first["context"]["ambiguous_structure_block_ids"] == []
    answer = first["context"]["answer_template"]
    answer["coverage_gaps"] = [{
        "kind": "unreconstructed_content",
        "block_ids": [first["task"]["block_ids"][0]],
        "role": "table_definition",
        "detail": (
            "The mapping between the reported outcome and target population was not "
            "reconstructed in this pass."
        ),
    }]
    path = Path(first["answer_path"])
    atomic_write_json(path, answer)
    assert workflow.submit(run_id, path)["accepted"]
    state = finish(run_id)["modules"]["statistics"]
    assert state["status"] == "partial" and not state["extraction_limits"]
    assert state["coverage_gaps"][0]["kind"] == "unreconstructed_content"


def test_historical_generic_pdf_warning_is_not_reclassified_or_promoted(support_env):
    run_id = begin(support_env)
    run = finish(run_id)
    run["source"]["format"] = "pdf"
    run["source"].pop("scope_limits", None)
    run["source"]["warnings"] = [PDF_SCOPE_LIMIT]
    state = run["modules"]["statistics"]
    state.update(status="partial", extraction_limits=[PDF_SCOPE_LIMIT], scope_limits=[])
    path = workflow._root(run_id) / "run.json"
    atomic_write_json(path, run)
    original = path.read_bytes()
    assert workflow.report(run_id)["phase"] == "partial"
    assert PDF_SCOPE_LIMIT in Path(export(run_id)["html"]).read_text()
    assert path.read_bytes() == original
    assert read_json(path)["modules"]["statistics"]["scope_limits"] == []
