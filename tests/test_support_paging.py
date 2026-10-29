import json
from pathlib import Path

import pytest
from test_support import begin, bound_percentage, finish
from test_support import support_env as support_env

from closed_review.cli import main
from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, read_json
from closed_review.support.calculators import calculate
from closed_review.support.methods import MODULES
from closed_review.support.paging import READ_CHARS, page_records, payload_chars, unread_records
from closed_review.support.workflow import _instructions, _load, _root, next_task, read, submit


def verbose_consolidation():
    assessments = [
        {
            "id": criterion,
            "status": "concern",
            "analysis": "a" * 4000,
            "why_matters": "b" * 4000,
            "limits": "c" * 4000,
            "evidence": [],
            "counterevidence": [],
        }
        for criterion in MODULES["statistics"]["criteria"]
    ]
    return {
        "id": "support-" + "a" * 32,
        "language": "en",
        "resolved_language": None,
        "source": {"warnings": []},
        "modules": {"statistics": {"facts": [], "criteria": assessments, "calculations": []}},
    }


def test_valid_verbose_assessments_do_not_overflow_consolidation():
    run = verbose_consolidation()
    task = {"id": "task-0004", "stage": "consolidate", "module": "statistics"}
    instructions, context = _instructions(run, task)
    assert len(instructions) + len(json.dumps(context, ensure_ascii=False, indent=2)) <= 60000
    assert context["records_paged"] is True
    assert context["assessment_index"] == [
        {"id": c["id"], "status": c["status"]} for c in run["modules"]["statistics"]["criteria"]
    ]
    assert "--assessments" in context["read_assessments"]
    assert run["modules"]["statistics"]["criteria"][0]["analysis"] == "a" * 4000


def all_pages(records):
    offset, fragment_offset = 0, 0
    restored, fragments, reads = [], {}, []
    for _ in range(1000):
        page = page_records(records, offset, fragment_offset)
        assert payload_chars(page) <= READ_CHARS
        restored.extend(page["items"])
        reads.append(
            {
                "ids": [item["id"] for item in page["items"]],
                "fragments": [
                    {"id": f["id"], "offset": f["offset"], "end": f["offset"] + len(f["text"])}
                    for f in page["fragments"]
                ],
            }
        )
        for fragment in page["fragments"]:
            previous = fragments.get(fragment["id"], "")
            assert len(previous) == fragment["offset"]
            fragments[fragment["id"]] = previous + fragment["text"]
        if page["next_offset"] is None:
            break
        offset, fragment_offset = page["next_offset"], page["next_fragment_offset"]
    else:
        pytest.fail("read pagination did not terminate")
    restored += [json.loads(value) for value in fragments.values()]
    assert sorted(restored, key=lambda x: x["id"]) == sorted(records, key=lambda x: x["id"])
    assert not unread_records(records, reads)
    return reads


@pytest.mark.parametrize("token", ["a", "한", '"', "\\", "\n", "🩺"])
def test_one_oversized_record_is_lossless_and_each_output_is_bounded(token):
    record = {"id": "a1", "text": token * 30000, "counterevidence": "retained"}
    reads = all_pages([record])
    assert len(reads) > 1
    assert unread_records([record], reads[:-1]) == ["a1"]
    assert unread_records([record], reads[1:]) == ["a1"]


def test_mixed_pages_include_all_records_and_stop_at_the_item_limit():
    records = [{"id": f"a{i}", "text": "x" * 50} for i in range(30)]
    assert len(page_records(records)["items"]) == 12
    records.insert(7, {"id": "large", "text": "y" * 25000})
    all_pages(records)


def test_empty_records_have_no_continuation():
    page = page_records([])
    assert page["items"] == [] and page["fragments"] == []
    assert page["next_offset"] is None


@pytest.mark.parametrize("offset,fragment_offset", [(-1, 0), (2, 0), (0, -1), (1, 1), (0, 999)])
def test_invalid_cursors_do_not_silently_skip_records(offset, fragment_offset):
    with pytest.raises(ReviewError):
        page_records([{"id": "a1", "text": "short"}], offset, fragment_offset)


def consolidation_fixture(support_env):
    """Rewind a fixture to consolidation with valid-length but deliberately verbose records."""
    run_id = begin(support_env)
    run = finish(run_id, concern=True)
    state = run["modules"]["statistics"]
    for criterion in state["criteria"]:
        criterion.update(analysis="a" * 4000, why_matters="b" * 4000, limits="c" * 4000)
    state.update(status="running", observations=[], withdrawn=[])
    run["cursor"] = len(run["tasks"]) - 1
    atomic_write_json(_root(run_id) / "run.json", run)
    issued = next_task(run_id)
    assert issued["context"]["records_paged"] is True
    answer = issued["context"]["answer_template"]
    answer.update(
        title="Bounded consolidation",
        summary="Provisional support; source matching is not medical validity.",
        groups=[
            {
                "criteria": [c["id"] for c in state["criteria"]],
                "title": "One grouped proposal",
                "explanation": "Fixture only; not a validated medical judgment.",
            }
        ],
    )
    answer_path = Path(issued["answer_path"])
    atomic_write_json(answer_path, answer)
    return run_id, answer_path, issued


def test_consolidation_requires_all_fragments_without_spending_repair_attempts(support_env):
    run_id, answer_path, issued = consolidation_fixture(support_env)
    with pytest.raises(ReviewError, match="Read all consolidation"):
        submit(run_id, answer_path)
    offset, fragment_offset = 0, 0
    for _ in range(100):
        page = read(
            run_id, "statistics", assessments=True, offset=offset, fragment_offset=fragment_offset
        )
        assert payload_chars(page) <= READ_CHARS
        if page["next_offset"] is None:
            break
        with pytest.raises(ReviewError, match="not an answer refusal"):
            submit(run_id, answer_path)
        assert _load(_root(run_id))["attempts"] == {}
        offset, fragment_offset = page["next_offset"], page["next_fragment_offset"]
    else:
        pytest.fail("consolidation pagination did not terminate")
    refreshed = next_task(run_id)
    assert refreshed["task"] == issued["task"]
    assert refreshed["previous_answer_path"] == str(answer_path)
    fresh_answer = Path(refreshed["answer_path"])
    atomic_write_json(fresh_answer, read_json(answer_path))
    assert submit(run_id, fresh_answer)["accepted"]
    state = _load(_root(run_id))["modules"]["statistics"]
    assert state["status"] == "complete" and len(state["observations"]) == 1
    assert all(c["analysis"] == "a" * 4000 for c in state["criteria"])
    assert all(not c["semantic_correctness_verified"] for c in state["criteria"])


def test_prior_task_reads_do_not_authorize_a_later_consolidation(support_env):
    run_id, answer_path, _ = consolidation_fixture(support_env)
    path = _root(run_id) / "run.json"
    run = read_json(path)
    run["modules"]["statistics"]["reads"] = [
        {
            "task_id": "task-0001",
            "section": "criteria",
            "ids": [c["id"] for c in run["modules"]["statistics"]["criteria"]],
        }
    ]
    atomic_write_json(path, run)
    with pytest.raises(ReviewError, match="Read all consolidation"):
        submit(run_id, answer_path)


def test_paged_collections_are_module_scoped_and_cli_accessible(support_env, capsys):
    run_id, _, _ = consolidation_fixture(support_env)
    assert main(["support", "read", run_id, "--module", "statistics", "--assessments"]) == 0
    page = json.loads(capsys.readouterr().out)
    assert page["fragments"] and page["next_fragment_offset"] > 0
    with pytest.raises(ReviewError, match="select a module"):
        read(run_id, "logic", assessments=True)
    with pytest.raises(ReviewError, match="exactly one"):
        read(run_id, "statistics", facts=True, calculations=True)


def test_full_calculation_assumptions_must_also_be_supplied(support_env):
    run_id, answer_path, _ = consolidation_fixture(support_env)
    path = _root(run_id) / "run.json"
    run = read_json(path)
    raw = bound_percentage(run_id)
    raw["assumptions"] = ["x" * 4000] * 8
    calculation = calculate(raw, run["source"])
    calculation["id"] = "statistics-c0001"
    run["modules"]["statistics"]["calculations"] = [calculation]
    atomic_write_json(path, run)
    answer = read_json(answer_path)
    answer["groups"][0]["calculations"] = [calculation["id"]]
    atomic_write_json(answer_path, answer)
    for section in ("assessments", "calculations"):
        offset, fragment_offset = 0, 0
        while True:
            page = read(
                run_id,
                "statistics",
                **{section: True},
                offset=offset,
                fragment_offset=fragment_offset,
            )
            if page["next_offset"] is None:
                break
            offset, fragment_offset = page["next_offset"], page["next_fragment_offset"]
        if section == "assessments":
            with pytest.raises(ReviewError, match="--calculations"):
                submit(run_id, answer_path)
    assert submit(run_id, answer_path)["accepted"]
    assert _load(_root(run_id))["modules"]["statistics"]["calculations"][0] == calculation
