from __future__ import annotations

import copy
import json
import os
import zipfile
from pathlib import Path

import pytest
from conftest import assert_mode, reviewer_says, write_docx, write_pdf

from closed_review.cli import main
from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, read_json
from closed_review.receipts import verify_receipt
from closed_review.support import PROTOCOL
from closed_review.support.calculators import calculate
from closed_review.support.methods import MODULES
from closed_review.support.render import export
from closed_review.support.sources import resolve_evidence, snapshot
from closed_review.support.workflow import (
    LABELS,
    _load,
    _root,
    next_task,
    read,
    record,
    report,
    start,
    status,
    submit,
)


@pytest.fixture
def support_env(isolated_env, monkeypatch):
    from closed_review.support import workflow

    key = "a" * 32
    atomic_write_json(
        isolated_env / "data/preflights" / f"{key}.json",
        {"ready": True, "checked_at": "2026-10-28T00:00:00+00:00"},
    )
    monkeypatch.setattr(
        workflow,
        "_profile",
        lambda: {
            "ready": True,
            "model": "local-test",
            "base_url": "http://127.0.0.1/v1",
            "routes": [],
            "profile_root": "test-profile",
        },
    )
    paper = isolated_env / "paper.md"
    paper.write_text(
        "# Methods\n\nWe enrolled 100 patients. There were 20 events (30%).\n\n"
        "# Results\n\nThe unweighted event denominator was 100.\n",
        encoding="utf-8",
    )
    return paper, key


def begin(support_env, modules=None, **kwargs):
    paper, key = support_env
    return start(paper, modules or ["statistics"], session=key, **kwargs)["run_id"]


def finish(
    run_id,
    *,
    concern=False,
    withdraw=False,
    language="en",
    calculations=None,
    withdraw_calculations=False,
):
    while status(run_id)["phase"] == "running":
        issued = next_task(run_id)
        task, context = issued["task"], issued["context"]
        answer = copy.deepcopy(context["answer_template"])
        if task["stage"] == "extract":
            block = next(b for b in context["blocks"] if "100 patients" in b["text"])
            answer["facts"] = [
                {
                    "role": context["guide"]["roles"][0],
                    "label": "Population",
                    "value": "100 patients",
                    "evidence": [{"block_id": block["id"], "quote": "100 patients"}],
                }
            ]
        elif task["stage"] == "appraise":
            source = _load(_root(run_id))["source"]
            block = next(b for b in source["blocks"] if "100 patients" in b["text"])
            answer["assessments"] = [
                {
                    "criterion": c,
                    "status": "concern" if concern else "supported",
                    "analysis": "Source-grounded test assessment.",
                    "why_matters": "A specific consequence." if concern else "",
                    "evidence": [{"block_id": block["id"], "quote": "100 patients"}],
                    "counterevidence": [],
                    "limits": "Interpretation is provisional.",
                }
                for c in task["criteria"]
            ]
            if calculations and "calculation" in task["criteria"]:
                answer["calculations"] = calculations
        else:
            candidates = [a["id"] for a in context["assessments"] if a["status"] == "concern"]
            answer.update(
                language=language,
                title="Module",
                summary="A bounded module summary.",
                labels={k: f"검토 {k}" if language == "ko" else k for k in LABELS},
                groups=[]
                if withdraw or not candidates
                else [
                    {
                        "criteria": candidates,
                        "title": "One consolidated concern",
                        "explanation": "Provisional appraisal.",
                    }
                ],
                withdrawn=[
                    {
                        "criterion": c,
                        "reason": "Counterevidence resolves this concern.",
                        "evidence": [],
                    }
                    for c in candidates
                ]
                if withdraw
                else [],
                priority=[] if withdraw or not candidates else [candidates[0]],
            )
            mismatches = [
                c["id"] for c in context["calculations"] if c["comparison"]["status"] == "mismatch"
            ]
            if mismatches:
                if withdraw_calculations:
                    answer["withdrawn"] += [
                        {
                            "calculation_id": c,
                            "reason": "Input roles cannot be justified.",
                            "evidence": [],
                        }
                        for c in mismatches
                    ]
                elif answer["groups"]:
                    answer["groups"][0]["calculations"] = mismatches
                else:
                    answer["groups"].append(
                        {
                            "criteria": [],
                            "calculations": mismatches,
                            "title": "Calculated reporting discrepancy",
                            "explanation": "Arithmetic differs under chosen inputs.",
                        }
                    )
        atomic_write_json(Path(issued["answer_path"]), answer)
        result = submit(run_id, Path(issued["answer_path"]))
        assert result["accepted"], result
    return _load(_root(run_id))


def numeric_source(text="20 events among 100 patients; unweighted percentage 30%."):
    return {
        "blocks": [{"id": "b1", "locator": "paragraph:1", "kind": "paragraph", "text": text}],
        "tables": [],
    }


def number(token, quote=None):
    return {"value": token, "evidence": [{"block_id": "b1", "quote": quote or token}]}


def percentage():
    return {
        "method": "percentage",
        "inputs": {"numerator": number("20"), "denominator": number("100")},
        "method_evidence": [{"block_id": "b1", "quote": "unweighted"}],
        "assumptions": ["The manuscript explicitly identifies the unweighted denominator."],
        "reported": number("30"),
    }


def test_three_families_are_explicit_and_no_auto_all(support_env):
    with pytest.raises(ReviewError, match="select known"):
        begin(support_env, ["all"])
    run_id = begin(support_env, ["statistics", "qualitative-study", "logic"])
    run = _load(_root(run_id))
    assert set(run["modules"]) == {"statistics", "qualitative-study", "logic"}
    assert run["language"] == "inherit"
    assert run["qualification"] == "not_qualified"
    assert not list(_root(run_id).parent.parent.glob("scans/*"))
    assert {MODULES[m]["family"] for m in MODULES} == {"statistical", "qualitative", "logic"}


@pytest.mark.parametrize("module", list(MODULES))
def test_each_branch_completes_without_a_concern_quota(support_env, module):
    run_id = begin(support_env, [module])
    run = finish(run_id)
    assert status(run_id)["phase"] == "complete"
    assert not run["modules"][module]["observations"]
    assert len(run["modules"][module]["criteria"]) == len(MODULES[module]["criteria"])
    assert all(not x["semantic_correctness_verified"] for x in run["modules"][module]["criteria"])


def test_resume_reissues_same_task_and_retains_evidence(support_env):
    run_id = begin(support_env)
    first = next_task(run_id)
    assert next_task(run_id)["task"] == first["task"]
    assert status(run_id)["task"] == 0
    finish(run_id)
    assert report(run_id)["total_observations"] == 0


def test_model_criticism_can_be_withdrawn_not_forced_into_final_report(support_env):
    run_id = begin(support_env)
    run = finish(run_id, concern=True, withdraw=True)
    assert not run["modules"]["statistics"]["observations"]
    assert len(run["modules"]["statistics"]["withdrawn"]) == 6


def test_summary_is_compact_but_full_counts_are_visible(support_env):
    run_id = begin(support_env, ["statistics", "qualitative-study", "logic"])
    finish(run_id, concern=True)
    summary = report(run_id)
    assert summary["total_observations"] == 3
    assert len(summary["priority_observations"]) <= 3


def test_two_refusals_stop_module_without_retrying_or_blocking_other_modules(support_env):
    run_id = begin(support_env, ["statistics", "logic"])
    issued = next_task(run_id)
    atomic_write_json(Path(issued["answer_path"]), {"task_id": "wrong"})
    assert submit(run_id, Path(issued["answer_path"]))["attempts"] == 1
    assert submit(run_id, Path(issued["answer_path"]))["module_failed"]
    assert next_task(run_id)["task"]["module"] == "logic"
    finish(run_id)
    assert status(run_id)["phase"] == "partial"
    assert status(run_id)["modules"]["statistics"]["failures"]


def test_partial_validation_rolls_back_all_facts(support_env):
    run_id = begin(support_env)
    issued = next_task(run_id)
    block = next(b for b in issued["context"]["blocks"] if "100 patients" in b["text"])
    good = {
        "role": "population",
        "label": "Sample",
        "value": "100 patients",
        "evidence": [{"block_id": block["id"], "quote": "100 patients"}],
    }
    bad = {**good, "evidence": [{"block_id": block["id"], "quote": "1000 patients"}]}
    atomic_write_json(
        Path(issued["answer_path"]),
        {
            "task_id": issued["task"]["id"],
            "facts": [good, bad],
            "scope_limits": [],
            "coverage_gaps": [],
        },
    )
    assert not submit(run_id, Path(issued["answer_path"]))["accepted"]
    assert not _load(_root(run_id))["modules"]["statistics"]["facts"]
    rejected = read_json(_root(run_id) / "answers/task-0001-rejected-1.json")
    assert rejected["facts"][1]["evidence"][0]["quote"] == "1000 patients"


def test_quote_and_numeric_errors_share_one_refusal_not_two_repair_cycles(support_env):
    run_id = begin(support_env)
    extraction = next_task(run_id)
    atomic_write_json(Path(extraction["answer_path"]), extraction["context"]["answer_template"])
    assert submit(run_id, Path(extraction["answer_path"]))["accepted"]
    appraisal = next_task(run_id)
    answer = copy.deepcopy(appraisal["context"]["answer_template"])
    for assessment in answer["assessments"]:
        assessment.update(analysis="Not assessable in this fixture.", limits="No inference.")
    raw = bound_percentage(run_id)
    raw["inputs"]["numerator"]["value"] = "4"
    raw["inputs"]["numerator"]["evidence"][0]["quote"] = "Four events."
    answer["calculations"] = [raw]
    path = Path(appraisal["answer_path"])
    atomic_write_json(path, answer)
    refused = submit(run_id, path)
    assert refused["accepted"] is False and refused["attempts"] == 1
    assert "answer source-reference errors" in refused["error"]
    assert "answer numeric-binding errors" in refused["error"]
    assert "omit the ENTIRE calculation" in refused["error"]
    assert not _load(_root(run_id))["modules"]["statistics"]["criteria"]
    answer["calculations"] = []
    atomic_write_json(path, answer)
    assert submit(run_id, path)["accepted"]


def test_source_mutation_and_route_changes_block_resume(support_env, monkeypatch):
    from closed_review.support import workflow

    run_id = begin(support_env)
    paper, _ = support_env
    original = paper.read_text(encoding="utf-8")
    paper.write_text(original + "\nChanged", encoding="utf-8")
    with pytest.raises(ReviewError, match="manuscript changed"):
        next_task(run_id)
    paper.write_text(original, encoding="utf-8")
    monkeypatch.setattr(workflow, "_profile", lambda: {"ready": True, "model": "cloud"})
    with pytest.raises(ReviewError, match="routes changed"):
        next_task(run_id)


def test_original_hermes_session_is_required(support_env, monkeypatch):
    run_id = begin(support_env)
    path = _root(run_id) / "run.json"
    run = read_json(path)
    run["session_source"] = "hermes_session"
    atomic_write_json(path, run)
    monkeypatch.setenv("HERMES_SESSION_ID", "another-session")
    with pytest.raises(ReviewError, match="original Hermes session"):
        next_task(run_id)


def test_task_budget_is_explicit_and_scanned_pdf_is_not_clean(support_env, tmp_path):
    with pytest.raises(ReviewError, match="exceeds"):
        begin(support_env, max_tasks=1)
    pytest.importorskip("pdfplumber")
    paper, key = support_env
    write_pdf(paper.with_suffix(".pdf"), "")
    run_id = start(paper.with_suffix(".pdf"), ["statistics"], session=key)["run_id"]
    assert status(run_id)["phase"] == "not_assessable"
    assert not _load(_root(run_id))["tasks"]


def test_read_is_source_bound_paginated_and_module_private(support_env):
    run_id = begin(support_env)
    found = read(run_id, "statistics", query="patients")
    assert found["total"] == 1
    assert "100 patients" in found["items"][0]["text"]
    with pytest.raises(ReviewError, match="unknown evidence"):
        read(run_id, "statistics", fact_ids=["logic-f0001"])
    with pytest.raises(ReviewError, match="select a module"):
        read(run_id, "logic", query="Methods")


def test_docx_cells_preserve_empty_positions(support_env, tmp_path):
    paper = tmp_path / "table.docx"
    write_docx(paper, [("Heading1", "Table 1")], [["Group", "N", "Value"], ["A", "", "20"]])
    source = snapshot(paper)
    cells = source["tables"][0]["cells"]
    assert [(c["column"], c["text"]) for c in cells if c["row"] == 2] == [
        (1, "A"),
        (2, ""),
        (3, "20"),
    ]
    assert all(b["kind"] != "table_row" for b in source["blocks"])


def test_docx_merged_headers_and_vertical_merge_are_preserved(tmp_path):
    path = tmp_path / "merged.docx"
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="{ns}"><w:body><w:tbl>'
            '<w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/><w:vMerge w:val="restart"/></w:tcPr>'
            "<w:p><w:r><w:t>Both groups</w:t></w:r></w:p></w:tc></w:tr>"
            '<w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/><w:vMerge/></w:tcPr><w:p/></w:tc></w:tr>'
            "</w:tbl></w:body></w:document>",
        )
    table = snapshot(path)["tables"][0]
    assert table["cells"][0]["column_span"] == 2
    assert table["cells"][0]["row_span"] == 2
    assert table["cells"][1]["merged_into"] == table["cells"][0]["id"]


def test_markdown_table_keeps_empty_cells_and_marks_ragged_rows(tmp_path):
    path = tmp_path / "table.md"
    path.write_text("| A | B | C |\n|---|---|---|\n| a | | 20 |\n", encoding="utf-8")
    table = snapshot(path)["tables"][0]
    assert table["cells"][4]["text"] == ""
    assert not table["ambiguous"]
    path.write_text("| A | B | C |\n|---|---|---|\n| a | 20 |\n", encoding="utf-8")
    assert snapshot(path)["tables"][0]["ambiguous"]


def test_unsupported_raw_data_format_is_refused(tmp_path):
    path = tmp_path / "data.xlsx"
    path.write_text("not a manuscript", encoding="utf-8")
    with pytest.raises(ReviewError, match="one manuscript"):
        snapshot(path)


def test_evidence_does_not_fuzzy_relocate_a_wrong_block():
    with pytest.raises(ReviewError, match="exact substring"):
        resolve_evidence([{"block_id": "invented", "quote": "20"}], numeric_source())


def test_percentage_recalculation_has_source_bound_inputs_and_no_semantic_badge():
    result = calculate(percentage(), numeric_source())
    assert result["outputs"]["value"] == 20
    assert result["comparison"]["status"] == "mismatch"
    assert result["arithmetic_verified"] and not result["input_interpretation_verified"]


def test_rounding_does_not_make_ordinary_percentages_errors():
    raw = percentage()
    raw["inputs"] = {"numerator": number("1"), "denominator": number("3")}
    raw["reported"] = number("33.3")
    assert (
        calculate(raw, numeric_source("1 of 3; unweighted 33.3%"))["comparison"]["status"]
        == "match"
    )


@pytest.mark.parametrize("bad", ["200", "2+18", "NaN", "inf"])
def test_invented_or_executable_numeric_inputs_are_refused(bad):
    raw = percentage()
    raw["inputs"]["numerator"] = number(bad)
    with pytest.raises(ReviewError):
        calculate(raw, numeric_source())


def test_ambiguous_table_and_flattened_page_inputs_are_refused():
    source = numeric_source()
    source["blocks"][0].update(locator="page:1/block:1")
    source["tables"] = [{"page": 1, "ambiguous": True}]
    with pytest.raises(ReviewError, match="ambiguous table"):
        calculate(percentage(), source)
    source = numeric_source()
    source["blocks"][0]["ambiguous"] = True
    with pytest.raises(ReviewError, match="ambiguous source"):
        calculate(percentage(), source)


def test_declared_tests_are_conditional_comparisons_not_confirmed_errors():
    pytest.importorskip("scipy")
    raw = {
        "method": "p_from_z",
        "inputs": {"statistic": number("1.96")},
        "parameters": {"alternative": "two-sided"},
        "method_evidence": [{"block_id": "b1", "quote": "two-sided"}],
        "assumptions": ["The manuscript declares the standard-normal reference."],
        "reported": {**number(".01"), "output": "p_value"},
    }
    result = calculate(raw, numeric_source("two-sided z=1.96, p=.01"))
    assert result["outputs"]["p_value"] == pytest.approx(0.05, abs=0.0001)
    assert result["comparison"]["status"] == "conditional"
    assert result["comparison"]["numerical_match"] is False
    raw["parameters"] = {}
    with pytest.raises(ReviewError, match="parameters must contain exactly: alternative"):
        calculate(raw, numeric_source("two-sided z=1.96, p=.01"))


@pytest.mark.parametrize(
    "method,inputs,params,output,expected",
    [
        ("count_sum", {"part_1": "20", "part_2": "30"}, {}, "value", 50),
        ("ratios_2x2", {"a": "20", "b": "80", "c": "10", "d": "90"}, {}, "odds_ratio", 2.25),
        (
            "pearson_2x2",
            {"a": "20", "b": "80", "c": "10", "d": "90"},
            {"correction": False},
            "statistic",
            3.92156862745,
        ),
        (
            "fisher_2x2",
            {"a": "20", "b": "80", "c": "10", "d": "90"},
            {"alternative": "two-sided"},
            "odds_ratio",
            2.25,
        ),
        (
            "student_t",
            {"mean1": "10", "sd1": "2", "n1": "20", "mean2": "8", "sd2": "2", "n2": "20"},
            {"alternative": "two-sided"},
            "statistic",
            3.16227766,
        ),
        (
            "welch_t",
            {"mean1": "10", "sd1": "2", "n1": "20", "mean2": "8", "sd2": "2", "n2": "20"},
            {"alternative": "two-sided"},
            "statistic",
            3.16227766,
        ),
        ("p_from_t", {"statistic": "0", "df": "20"}, {"alternative": "two-sided"}, "p_value", 1),
        ("p_from_chi2", {"statistic": "0", "df": "1"}, {}, "p_value", 1),
        ("p_from_f", {"statistic": "0", "dfn": "1", "dfd": "20"}, {}, "p_value", 1),
        (
            "normal_ci",
            {"estimate": "10", "se": "1", "confidence_percent": "95"},
            {},
            "lower",
            8.04003601546,
        ),
        (
            "t_ci",
            {"estimate": "10", "se": "1", "df": "20", "confidence_percent": "95"},
            {},
            "lower",
            7.91403655273,
        ),
    ],
)
def test_registered_calculators_against_known_values(method, inputs, params, output, expected):
    if method != "count_sum":
        pytest.importorskip("scipy")
    text = "Declared method. " + " ".join(inputs.values())
    raw = {
        "method": method,
        "inputs": {k: number(v) for k, v in inputs.items()},
        "parameters": params,
        "method_evidence": [{"block_id": "b1", "quote": "Declared method"}],
        "assumptions": ["Explicit synthetic fixture assumptions."],
    }
    assert calculate(raw, numeric_source(text))["outputs"][output] == pytest.approx(expected)


def test_dossier_is_readable_inert_private_and_receipted(support_env, tmp_path):
    paper, _ = support_env
    paper.write_text(
        paper.read_text(encoding="utf-8") + '\n\n<script>alert("secret")</script>\n',
        encoding="utf-8",
    )
    run_id = begin(support_env, ["statistics", "logic"])
    finish(run_id, concern=True, language="ko")
    record(run_id, "run", "note", "My actual reviewer note.")
    result = export(run_id)
    html_text = Path(result["html"]).read_text(encoding="utf-8")
    assert "검토" in html_text
    assert "<script>" not in html_text and "&lt;script&gt;" in html_text
    assert "default-src 'none'" in html_text
    assert "<input" not in html_text and "<script src" not in html_text
    assert "My actual reviewer note." in html_text
    assert verify_receipt(Path(result["receipt"]))["verified"]
    assert_mode(Path(result["directory"]), 0o700)
    for path in Path(result["directory"]).iterdir():
        assert_mode(path, 0o600)
    with pytest.raises(ReviewError, match="existing material"):
        export(run_id, Path(result["directory"]))


def test_reviewer_decision_cannot_be_manufactured(support_env, monkeypatch, isolated_env):
    from closed_review.io import sha256_bytes

    session_id = "support-human-session"
    monkeypatch.setenv("HERMES_SESSION_ID", session_id)
    key = sha256_bytes(session_id.encode())[:32]
    atomic_write_json(isolated_env / "data/preflights" / f"{key}.json", {"ready": True})
    paper, _ = support_env
    run_id = start(paper, ["statistics"])["run_id"]
    finish(run_id, concern=True)
    observation = report(run_id)["priority_observations"][0]["id"]
    reviewer_says(isolated_env / "hermes", session_id, "I reject this concern.")
    with pytest.raises(ReviewError, match="reviewer's own words"):
        record(run_id, observation, "accepted", "I accept this concern.")
    assert record(run_id, observation, "rejected", "I reject this concern.")["verified"]


def test_cli_catalogue_and_task_commands(support_env, capsys):
    assert main(["support", "modules"]) == 0
    assert json.loads(capsys.readouterr().out)["protocol"] == PROTOCOL
    paper, key = support_env
    assert main(["support", "start", str(paper), "--session", key, "--module", "logic"]) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]
    assert main(["support", "next", run_id]) == 0
    assert json.loads(capsys.readouterr().out)["phase"] == "task"


def test_native_pdf_grid_retains_geometry_and_cell_values(tmp_path):
    pytest.importorskip("pdfplumber")
    paper = tmp_path / "grid.pdf"
    write_pdf(
        paper,
        content=(
            "72 700 m 280 700 l S 72 680 m 280 680 l S 72 660 m 280 660 l S "
            "72 660 m 72 700 l S 180 660 m 180 700 l S 280 660 m 280 700 l S "
            "BT /F1 10 Tf 80 686 Td (N) Tj ET BT /F1 10 Tf 190 686 Td (Events) Tj ET "
            "BT /F1 10 Tf 80 666 Td (100) Tj ET BT /F1 10 Tf 190 666 Td (20) Tj ET"
        ),
    )
    source = snapshot(paper)
    table = source["tables"][0]
    assert table["page"] == 1 and len(table["bbox"]) == 4
    assert [c["text"] for c in table["cells"]] == ["N", "Events", "100", "20"]
    assert not table["ambiguous"]


def test_calculated_discrepancy_dossier_has_readable_inputs_and_outputs(support_env):
    run_id = begin(support_env)
    source = _load(_root(run_id))["source"]
    population = next(b for b in source["blocks"] if "100 patients" in b["text"])
    method = next(b for b in source["blocks"] if "unweighted" in b["text"])

    def bind(value):
        return {"value": value, "evidence": [{"block_id": population["id"], "quote": value}]}

    raw = {
        "method": "percentage",
        "inputs": {"numerator": bind("20"), "denominator": bind("100")},
        "method_evidence": [
            {"block_id": method["id"], "quote": "unweighted event denominator was 100"}
        ],
        "assumptions": ["Explicit unweighted denominator."],
        "reported": bind("30"),
    }
    run = finish(run_id, calculations=[raw])
    assert run["modules"]["statistics"]["observations"][0]["kind"] == "calculated_discrepancy"
    result = export(run_id)
    document = Path(result["html"]).read_text(encoding="utf-8")
    assert "<td>numerator</td><td>20</td>" in document
    # Computed outputs now retain their saved representation rather than display-rounding.
    assert "<dt>value</dt><dd>20.0</dd>" in document
    assert "<summary>JSON</summary>" in document
    assert "arithmetic_verified" not in Path(result["markdown"]).read_text(encoding="utf-8")


def test_explicit_language_setting_cannot_be_silently_changed(support_env):
    run_id = begin(support_env, language="ko")
    with pytest.raises(AssertionError, match="configured language"):
        finish(run_id, language="en")


def test_legacy_extraction_limits_remain_partial_in_historical_reports(support_env):
    run_id = begin(support_env)
    run = finish(run_id)
    run["contract_version"] = 5
    run["modules"]["statistics"]["extraction_limits"] = ["Some table headers were not resolved."]
    run["modules"]["statistics"]["status"] = "partial"
    atomic_write_json(_root(run_id) / "run.json", run)
    assert report(run_id)["phase"] == "partial"
    assert "Some table headers" in Path(export(run_id)["markdown"]).read_text(encoding="utf-8")


def test_fisher_keeps_defined_p_value_when_odds_ratio_is_unbounded():
    pytest.importorskip("scipy")
    raw = {
        "method": "fisher_2x2",
        "inputs": {k: number(v) for k, v in {"a": "5", "b": "0", "c": "1", "d": "4"}.items()},
        "parameters": {"alternative": "two-sided"},
        "method_evidence": [{"block_id": "b1", "quote": "Fisher"}],
        "assumptions": [],
    }
    result = calculate(raw, numeric_source("Fisher 5 0 1 4"))
    assert 0 <= result["outputs"]["p_value"] <= 1
    assert "odds_ratio" not in result["outputs"] and result["unavailable_outputs"]


def test_markdown_trailing_empty_cells_are_not_stripped(tmp_path):
    path = tmp_path / "empty.md"
    path.write_text("|A|B|C|\n|---|---|---|\n|x|||\n", encoding="utf-8")
    cells = snapshot(path)["tables"][0]["cells"]
    assert [c["text"] for c in cells if c["row"] == 2] == ["x", "", ""]


def test_scope_boundaries_do_not_masquerade_as_processing_failure(support_env):
    run_id = begin(support_env)
    issued = next_task(run_id)
    answer = issued["context"]["answer_template"]
    answer["scope_limits"] = [
        "Raw data and external originals are outside this manuscript-only scope."
    ]
    atomic_write_json(Path(issued["answer_path"]), answer)
    assert submit(run_id, Path(issued["answer_path"]))["accepted"]
    run = finish(run_id)
    assert run["modules"]["statistics"]["status"] == "complete"
    assert not run["modules"]["statistics"]["extraction_limits"]
    document = Path(export(run_id)["html"]).read_text(encoding="utf-8")
    assert answer["scope_limits"][0] in document
    assert run["qualification"] == "not_qualified"


def test_explicit_coverage_gaps_still_prevent_completeness(support_env):
    paper, _ = support_env
    with paper.open("a") as output:
        output.write("\n| Group | N | Value |\n|---|---|---|\n| A | 20 |\n")
    run_id = begin(support_env)
    issued = next_task(run_id)
    answer = issued["context"]["answer_template"]
    answer["coverage_gaps"] = [
        {
            "kind": "ambiguous_structure",
            "block_ids": issued["context"]["ambiguous_structure_block_ids"],
            "role": "table_definition",
            "detail": "A table header could not be aligned with the displayed outcome column.",
        }
    ]
    atomic_write_json(Path(issued["answer_path"]), answer)
    assert submit(run_id, Path(issued["answer_path"]))["accepted"]
    run = finish(run_id)
    assert run["modules"]["statistics"]["status"] == "partial"
    assert (
        "ambiguous physical table geometry"
        in (run["modules"]["statistics"]["extraction_limits"][0])
    )
    assert (
        report(run_id)["modules"]["statistics"]["coverage_gaps"][0]["kind"] == "ambiguous_structure"
    )
    document = Path(export(run_id)["html"]).read_text(encoding="utf-8")
    assert document.count(answer["coverage_gaps"][0]["detail"]) == 1
    assert f"href='#source-{answer['coverage_gaps'][0]['block_ids'][0]}'" in document


def test_readable_conflict_requires_explicit_repair_then_appraisal(support_env):
    run_id = begin(support_env)
    issued = next_task(run_id)
    assert issued["context"]["ambiguous_structure_block_ids"] == []
    answer = issued["context"]["answer_template"]
    block = next(b for b in issued["context"]["blocks"] if "100 patients" in b["text"])
    answer["facts"] = [
        {
            "role": "table_definition",
            "label": f"Printed value {token}",
            "value": token,
            "evidence": [{"block_id": block["id"], "quote": token}],
        }
        for token in ("20", "100", "30")
    ]
    answer["coverage_gaps"] = [
        {
            "kind": "ambiguous_structure",
            "block_ids": [block["id"]],
            "role": "table_definition",
            "detail": "20/100 cannot reconstruct the printed 30% or intended denominator.",
        }
    ]
    path = Path(issued["answer_path"])
    atomic_write_json(path, answer)
    refused = submit(run_id, path)
    assert not refused["accepted"] and refused["attempts"] == 1
    assert "extractor-flagged" in refused["error"] and "assess" in refused["error"]
    state = _load(_root(run_id))["modules"]["statistics"]
    assert state["status"] == "running" and state["facts"] == []
    assert state["coverage_gaps"] == [] and not state["calculations"]
    rejected = read_json(path.with_name("task-0001-rejected-1.json"))
    assert rejected == answer and rejected["coverage_gaps"]
    answer["coverage_gaps"] = []
    atomic_write_json(path, answer)
    assert submit(run_id, path)["accepted"]
    replay = percentage()
    for binding in [*replay["inputs"].values(), replay["reported"]]:
        binding["evidence"][0]["block_id"] = block["id"]
    replay["method_evidence"] = [{"block_id": block["id"], "quote": "100 patients"}]
    run = finish(run_id, calculations=[replay])
    state = run["modules"]["statistics"]
    assert state["status"] == "complete" and not state["coverage_gaps"]
    assert [fact["value"] for fact in state["facts"]] == ["20", "100", "30"]
    assert state["calculations"][0]["comparison"]["status"] == "mismatch"
    assert not state["calculations"][0]["input_interpretation_verified"]


@pytest.mark.parametrize("historical", [False, True])
def test_flattened_markdown_cannot_bypass_ambiguous_native_geometry(tmp_path, historical):
    path = tmp_path / "ragged.md"
    path.write_text(
        "| Events | N | Percentage |\n|---|---|---|\n|20|100|30|extra|\n", encoding="utf-8"
    )
    source = snapshot(path)
    # Older saved snapshots retained the whole flattened table as well as its cells.
    # Preserve both historical ambiguity-link forms without restoring that duplication
    # to new extraction tasks.
    source["blocks"].insert(
        0,
        {
            "id": source["tables"][0]["source_block_ids"][0],
            "kind": "table",
            "text": source["tables"][0]["source_text"],
            "locator": source["tables"][0]["caption_context"],
        },
    )
    if historical:
        source["tables"][0].pop("source_block_ids")
    original = next(b for b in source["blocks"] if b["kind"] == "table")
    replay = percentage()
    for binding in [*replay["inputs"].values(), replay["reported"]]:
        binding["evidence"][0]["block_id"] = original["id"]
    replay["method_evidence"] = [{"block_id": original["id"], "quote": "Events"}]
    with pytest.raises(ReviewError, match="ambiguous source"):
        calculate(replay, source)
    evidence = resolve_evidence([{"block_id": original["id"], "quote": "20"}], source)
    assert evidence[0]["ambiguous"]


@pytest.mark.parametrize(
    "disclaimer",
    [
        "Quotation matching does not certify the authors' intended meaning.",
        "No formal validity certificate, moral verdict or independent factual validation.",
    ],
)
def test_unlocalized_disclaimers_need_explicit_repair_not_silent_promotion(support_env, disclaimer):
    run_id = begin(support_env, ["logic"])
    issued = next_task(run_id)
    answer = issued["context"]["answer_template"]
    answer["coverage_gaps"] = [disclaimer]
    path = Path(issued["answer_path"])
    atomic_write_json(path, answer)
    refused = submit(run_id, path)
    assert refused["accepted"] is False and refused["attempts"] == 1
    assert "kind/block_ids/role/detail" in refused["error"]
    assert "scope_limits" in refused["error"]
    state = _load(_root(run_id))["modules"]["logic"]
    assert state["status"] == "running" and state["scope_limits"] == []
    assert read_json(path.with_name("task-0001-rejected-1.json"))["coverage_gaps"] == [disclaimer]
    answer.update(scope_limits=[disclaimer], coverage_gaps=[])
    atomic_write_json(path, answer)
    assert submit(run_id, path)["accepted"]
    completed = finish(run_id)["modules"]["logic"]
    assert completed["status"] == "complete" and disclaimer in completed["scope_limits"]


@pytest.mark.parametrize("problem", ["foreign-block", "unreached-cap", "old-limits"])
def test_gap_contract_does_not_hide_real_coverage_or_allow_legacy_bypass(support_env, problem):
    run_id = begin(support_env)
    issued = next_task(run_id)
    answer = issued["context"]["answer_template"]
    if problem == "old-limits":
        answer["limits"] = ["PRIVATE: uncertain interpretation"]
    else:
        answer["coverage_gaps"] = [
            {
                "kind": "fact_cap" if problem == "unreached-cap" else "unreadable_content",
                "block_ids": ["other-block"]
                if problem == "foreign-block"
                else issued["task"]["block_ids"],
                "role": "population",
                "detail": "PRIVATE: an eligibility description could not be reconstructed.",
            }
        ]
    path = Path(issued["answer_path"])
    atomic_write_json(path, answer)
    result = submit(run_id, path)
    assert result["accepted"] is False
    assert "PRIVATE" not in result["error"]
    assert not _load(_root(run_id))["modules"]["statistics"]["coverage_gaps"]


def test_reached_fact_cap_stays_partial_and_gap_text_is_inert(support_env):
    run_id = begin(support_env)
    issued = next_task(run_id)
    block = next(b for b in issued["context"]["blocks"] if "100 patients" in b["text"])
    answer = issued["context"]["answer_template"]
    answer["facts"] = [
        {
            "role": "population",
            "label": f"Fixture {i}",
            "value": "100 patients",
            "evidence": [{"block_id": block["id"], "quote": "100 patients"}],
        }
        for i in range(24)
    ]
    answer["coverage_gaps"] = [
        {
            "kind": "fact_cap",
            "block_ids": [block["id"]],
            "role": "outcome",
            "detail": "Fixture cap: an outcome remained unrecorded. <script>bad()</script>",
        }
    ]
    path = Path(issued["answer_path"])
    atomic_write_json(path, answer)
    assert submit(run_id, path)["accepted"]
    state = finish(run_id)["modules"]["statistics"]
    assert state["status"] == "partial" and len(state["facts"]) == 24
    document = Path(export(run_id)["html"]).read_text(encoding="utf-8")
    assert "<script>bad()" not in document and "&lt;script&gt;bad()" in document


@pytest.mark.parametrize("modules", [["statistics"], ["statistics", "logic"]])
def test_failure_snapshot_does_not_change_when_rendered_or_reported(support_env, modules):
    from closed_review.support.render import render

    run_id = begin(support_env, modules)
    issued = next_task(run_id)
    atomic_write_json(Path(issued["answer_path"]), {"task_id": "wrong"})
    submit(run_id, Path(issued["answer_path"]))
    assert submit(run_id, Path(issued["answer_path"]))["module_failed"]
    if len(modules) > 1:
        finish(run_id)
    path = _root(run_id) / "run.json"
    before = read_json(path)
    memory = copy.deepcopy(before)
    render(memory)
    assert memory == before
    status(run_id)
    report(run_id)
    result = export(run_id)
    assert read_json(path) == before == read_json(Path(result["directory"]) / "support.json")
    assert before["cursor"] == len(before["tasks"])


def bound_percentage(run_id):
    source = _load(_root(run_id))["source"]
    population = next(b for b in source["blocks"] if "100 patients" in b["text"])
    method = next(b for b in source["blocks"] if "unweighted" in b["text"])

    def bind(value):
        return {"value": value, "evidence": [{"block_id": population["id"], "quote": value}]}

    return {
        "method": "percentage",
        "inputs": {"numerator": bind("20"), "denominator": bind("100")},
        "method_evidence": [{"block_id": method["id"], "quote": "unweighted"}],
        "assumptions": ["Unweighted denominator."],
        "reported": bind("30"),
    }


def test_same_issue_and_its_calculation_are_one_observation(support_env):
    run_id = begin(support_env)
    run = finish(run_id, concern=True, calculations=[bound_percentage(run_id)])
    state = run["modules"]["statistics"]
    assert len(state["observations"]) == len(state["calculations"]) == 1
    observation = state["observations"][0]
    assert observation["kind"] == "calculated_discrepancy"
    assert observation["calculation_ids"] == [state["calculations"][0]["id"]]
    assert observation["criteria"]
    assert "unverified" in observation["limits"][-1]
    assert report(run_id)["total_observations"] == 1


def test_indefensible_input_mapping_can_be_withdrawn_without_hiding_calculation(support_env):
    run_id = begin(support_env)
    run = finish(run_id, calculations=[bound_percentage(run_id)], withdraw_calculations=True)
    state = run["modules"]["statistics"]
    assert not state["observations"]
    assert len(state["calculations"]) == len(state["withdrawn"]) == 1
    assert state["calculations"][0]["comparison"]["status"] == "mismatch"
    assert "Input roles" in Path(export(run_id)["html"]).read_text(encoding="utf-8")


def test_navigation_is_deterministic_and_language_aliases_are_consistent(support_env):
    run_id = begin(support_env, language="English")
    run = finish(run_id)
    state = run["modules"]["statistics"]
    assert state["language"] == "en"
    assert state["labels"]["calculation_note"] != "calculation_note"
    assert "unverified" in state["labels"]["calculation_note"]


def test_article_routing_is_explicit_and_never_starts_a_run(support_env, capsys):
    from closed_review.support.methods import ARTICLE_ROUTES, route_modules

    before = list((_root(begin(support_env))).parent.iterdir())
    for article_type, modules in ARTICLE_ROUTES.items():
        route = route_modules(article_type)
        assert route["suggested_modules"] == modules
        assert not route["starts_run"] and route["reviewer_scope_required"]
    assert main(["support", "route", "meta-analysis"]) == 0
    assert json.loads(capsys.readouterr().out)["suggested_modules"] == [
        "systematic-review",
        "statistics",
    ]
    assert list(before[0].parent.iterdir()) == before
    with pytest.raises(ReviewError, match="unknown article type"):
        route_modules("all")


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink fixture")
def test_answer_symlink_is_refused_before_reading_or_archiving_unrelated_data(
    support_env, monkeypatch
):
    from closed_review.support import workflow

    run_id = begin(support_env)
    issued = next_task(run_id)
    secret = support_env[0].parent / "unrelated-private.json"
    secret.write_text('{"secret":"not-for-this-run"}', encoding="utf-8")
    answer = Path(issued["answer_path"])
    answer.symlink_to(secret)
    original = workflow.read_json

    def checked_read(path):
        assert Path(path).resolve() != secret
        return original(path)

    monkeypatch.setattr(workflow, "read_json", checked_read)
    result = submit(run_id, answer)
    assert not result["accepted"] and "symlink" in result["error"]
    assert not (_root(run_id) / "answers/task-0001-rejected-1.json").exists()
    assert secret.read_text(encoding="utf-8") == '{"secret":"not-for-this-run"}'


def test_changing_configured_context_cannot_silently_resume_a_run(support_env, monkeypatch):
    from closed_review.support import workflow

    profile = workflow._profile()
    profile["capability"] = {"configured_context_length": 262144}
    monkeypatch.setattr(workflow, "_profile", lambda: profile)
    run_id = begin(support_env)
    assert _load(_root(run_id))["route"]["configured_context_length"] == 262144
    profile["capability"]["configured_context_length"] = 65536
    with pytest.raises(ReviewError, match="routes changed"):
        next_task(run_id)
