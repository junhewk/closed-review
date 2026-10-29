"""Actionable references are explicit; matching checks must not become observations."""

import copy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from test_support import begin, bound_percentage, finish
from test_support import support_env as support_env

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, read_json
from closed_review.support.budgets import TASK_CHARS
from closed_review.support.contracts import (
    answer_schema,
    consolidation_references,
    validate_shape,
)
from closed_review.support.methods import MODULES
from closed_review.support.paging import payload_chars
from closed_review.support.render import export
from closed_review.support.workflow import _instructions, _load, _root, next_task, read, submit


def answer():
    return {
        "task_id": "task-0008",
        "language": "en",
        "title": "Bounded support",
        "summary": "Reconstruction and arithmetic checks are not scientific validation.",
        "labels": {},
        "groups": [],
        "withdrawn": [],
        "priority": [],
    }


@pytest.mark.parametrize("module", MODULES)
@pytest.mark.parametrize(
    "references",
    [
        {"criteria": [], "calculations": []},
        {"criteria": ["criterion-1"], "calculations": []},
        {"criteria": [], "calculations": ["calculation-1"]},
        {"criteria": ["criterion-1"], "calculations": ["calculation-1"]},
    ],
)
def test_each_branch_has_a_valid_task_bound_consolidation_schema(module, references):
    schema = answer_schema("consolidate", module, references=references)
    Draft202012Validator.check_schema(schema)
    assert Draft202012Validator(schema).is_valid(answer())


def test_reference_catalogue_matches_existing_actionable_record_rules():
    state = {
        "criteria": [
            {"id": "concern", "status": "concern", "why_matters": ""},
            {"id": "positive", "status": "supported", "why_matters": "positive rationale"},
            {"id": "important-gap", "status": "not_located", "why_matters": "Why it matters"},
            {"id": "ordinary-gap", "status": "not_located", "why_matters": ""},
            {"id": "unassessable", "status": "not_assessable", "why_matters": "A limit"},
            {"id": "inapplicable", "status": "not_applicable", "why_matters": "A limit"},
        ],
        "calculations": [
            {"id": status, "comparison": {"status": status}}
            for status in ("match", "conditional", "mismatch", "not_compared")
        ],
    }
    assert consolidation_references(state) == {
        "criteria": ["concern", "important-gap"],
        "calculations": ["mismatch"],
    }


@pytest.mark.parametrize("field", ["groups", "withdrawn", "priority"])
def test_no_candidates_requires_empty_arrays_without_echoing_positive_text(field):
    raw = answer()
    raw[field] = (
        [{"criteria": ["population"], "title": "PRIVATE-POSITIVE", "explanation": "PRIVATE"}]
        if field == "groups"
        else ["PRIVATE-POSITIVE"]
    )
    with pytest.raises(ReviewError) as error:
        validate_shape(
            raw,
            "consolidate",
            "statistics",
            None,
            references={"criteria": [], "calculations": []},
        )
    message = str(error.value)
    assert f"{field}: must be []" in message
    assert "PRIVATE" not in message
    assert "positive checks" in message


@pytest.mark.parametrize("field", ["criteria", "calculations", "priority"])
def test_only_listed_candidate_ids_can_be_grouped_or_prioritized(field):
    refs = {"criteria": ["tables"], "calculations": ["statistics-c0002"]}
    raw = answer()
    raw["groups"] = [
        {
            "criteria": ["tables"],
            "calculations": ["statistics-c0002"],
            "title": "One provisional discrepancy",
            "explanation": "Provisional interpretation",
        }
    ]
    raw["priority"] = ["tables"]
    validate_shape(raw, "consolidate", "statistics", None, references=refs)
    if field == "priority":
        raw["priority"] = ["PRIVATE-TITLE-NOT-AN-ID"]
    else:
        raw["groups"][0][field] = ["PRIVATE-UNSUPPORTED-ID"]
    with pytest.raises(ReviewError) as error:
        validate_shape(raw, "consolidate", "statistics", None, references=refs)
    assert field in str(error.value) and "choose one of" in str(error.value)
    assert "PRIVATE" not in str(error.value)


@pytest.mark.parametrize("field", ["criterion", "calculation_id"])
def test_withdrawals_are_limited_to_actual_actionable_candidates(field):
    refs = {"criteria": ["tables"], "calculations": ["statistics-c0002"]}
    raw = answer()
    raw["withdrawn"] = [
        {
            field: "tables" if field == "criterion" else "statistics-c0002",
            "reason": "A documented provisional interpretation was not defensible.",
            "evidence": [],
        }
    ]
    validate_shape(raw, "consolidate", "statistics", None, references=refs)
    raw["withdrawn"][0][field] = "not-a-candidate"
    with pytest.raises(ReviewError):
        validate_shape(raw, "consolidate", "statistics", None, references=refs)


def test_a_group_still_needs_at_least_one_actionable_reference():
    raw = answer()
    raw["groups"] = [{"criteria": [], "title": "Positive result", "explanation": "Not a concern"}]
    with pytest.raises(ReviewError):
        validate_shape(
            raw,
            "consolidate",
            "statistics",
            None,
            references={"criteria": ["tables"], "calculations": []},
        )


def test_task_reference_constraints_do_not_mutate_other_schemas_or_caller_lists():
    refs = {"criteria": ["tables"], "calculations": []}
    first = answer_schema("consolidate", "statistics", references=refs)
    before = copy.deepcopy(first)
    refs["criteria"].append("population")
    answer_schema("consolidate", "logic", references={"criteria": [], "calculations": []})
    assert first == before


def read_all(run_id, section):
    offset = fragment = 0
    while True:
        page = read(
            run_id, "statistics", offset=offset, fragment_offset=fragment, **{section: True}
        )
        if page["next_offset"] is None:
            return
        offset, fragment = page["next_offset"], page["next_fragment_offset"]


def test_fourteen_matching_replays_need_no_observation_and_are_never_silently_dropped(support_env):
    paper, _ = support_env
    paper.write_text(
        "# Methods\n\nWe enrolled 100 patients. There were 20 events (20%).\n\n"
        "# Results\n\nThe unweighted event denominator was 100.\n"
    )
    run_id = begin(support_env)
    replay = bound_percentage(run_id)
    replay["reported"].update(
        value="20",
        evidence=[
            {
                "block_id": replay["reported"]["evidence"][0]["block_id"],
                "quote": "20%",
            }
        ],
    )
    run = finish(run_id, calculations=[copy.deepcopy(replay) for _ in range(14)])
    state = run["modules"]["statistics"]
    assert len(state["calculations"]) == 14 and not state["observations"]
    assert all(c["comparison"]["numerical_match"] for c in state["calculations"])
    expected_calculations = copy.deepcopy(state["calculations"])
    # Fresh unit fixture rewind, not a migration or promotion of the failed workstation run.
    run["cursor"] = len(run["tasks"]) - 1
    state["status"] = "running"
    atomic_write_json(_root(run_id) / "run.json", run)
    issued = next_task(run_id)
    context = issued["context"]
    assert context["candidate_criterion_ids"] == context["mismatch_calculation_ids"] == []
    assert "MUST all be []" in issued["instructions"]
    if context.get("records_paged"):
        read_all(run_id, "assessments")
        read_all(run_id, "calculations")
    bad = copy.deepcopy(context["answer_template"])
    bad.update(
        title="Unit fixture",
        summary="Positive checks are not observations.",
        groups=[
            {
                "criteria": ["population"],
                "calculations": [state["calculations"][0]["id"]],
                "title": "PRIVATE POSITIVE CHECK",
                "explanation": "Not a candidate concern.",
            }
        ],
        priority=["PRIVATE POSITIVE CHECK"],
    )
    path = Path(issued["answer_path"])
    atomic_write_json(path, bad)
    refused = submit(run_id, path)
    assert refused["accepted"] is False and refused["attempts"] == 1
    assert "groups: must be []" in refused["error"] and "priority: must be []" in refused["error"]
    assert "PRIVATE" not in refused["error"]
    assert read_json(path.with_name(issued["task"]["id"] + "-rejected-1.json")) == bad
    assert _load(_root(run_id))["modules"]["statistics"]["calculations"] == expected_calculations
    good = copy.deepcopy(context["answer_template"])
    good.update(
        title="Bounded statistics support", summary="Checks match conditionally; not validation."
    )
    atomic_write_json(path, good)
    assert submit(run_id, path)["accepted"]
    final = _load(_root(run_id))
    assert final["modules"]["statistics"]["status"] == "complete"
    assert final["modules"]["statistics"]["observations"] == []
    assert final["modules"]["statistics"]["calculations"] == expected_calculations
    exported = read_json(Path(export(run_id)["directory"]) / "support.json")
    assert exported["modules"]["statistics"]["calculations"] == expected_calculations
    assert exported["qualification"] == "not_qualified"


def test_large_actionable_catalogue_keeps_task_delivery_bounded():
    guide = MODULES["statistics"]
    state = {
        "facts": [],
        "criteria": [
            {"id": c, "status": "concern", "analysis": "x" * 4000, "why_matters": "y" * 4000}
            for c in guide["criteria"]
        ],
        "calculations": [
            {
                "id": f"statistics-c{i:04d}",
                "method": "percentage",
                "comparison": {"status": "mismatch"},
                "assumptions": ["a" * 4000],
            }
            for i in range(1, 73)
        ],
    }
    run = {
        "id": "support-" + "a" * 32,
        "language": "ko",
        "resolved_language": None,
        "source": {"warnings": []},
        "modules": {"statistics": state},
    }
    task = {"id": "task-0008", "module": "statistics", "stage": "consolidate"}
    instructions, context = _instructions(run, task)
    assert context["records_paged"] is True
    assert len(context["mismatch_calculation_ids"]) == 72
    assert context["candidate_criterion_ids"] == list(guide["criteria"])
    assert payload_chars({"instructions": instructions, "context": context}) < TASK_CHARS - 1000
