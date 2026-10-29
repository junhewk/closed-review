"""Fresh answer paths preserve old work without bypassing source/refusal checks."""

from pathlib import Path

import pytest
from test_support import begin
from test_support import support_env as support_env

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, read_json, sha256_file
from closed_review.support import workflow


def test_resume_issues_a_new_draft_without_editing_or_accepting_the_old_file(support_env):
    run = begin(support_env)
    first = workflow.next_task(run)
    old = Path(first["answer_path"])
    atomic_write_json(old, {"task_id": "stale draft; not submitted"})
    original = old.read_bytes()
    resumed = workflow.next_task(run)
    new = Path(resumed["answer_path"])
    assert new != old and not new.exists()
    assert resumed["previous_answer_path"] == str(old)
    assert old.read_bytes() == original
    with pytest.raises(ReviewError, match="issued answer_path"):
        workflow.submit(run, old)
    assert workflow._load(workflow._root(run))["attempts"] == {}
    atomic_write_json(new, resumed["context"]["answer_template"])
    assert workflow.submit(run, new)["accepted"]
    assert old.read_bytes() == original
    assert workflow._load(workflow._root(run))["cursor"] == 1
    accepted = read_json(new.with_name("task-0001-accepted.json"))
    assert accepted == resumed["context"]["answer_template"]


def test_reissuing_drafts_never_resets_the_two_refusal_stop(support_env):
    run = begin(support_env, ["statistics", "logic"])
    first = workflow.next_task(run)
    old = Path(first["answer_path"])
    atomic_write_json(old, {"task_id": "wrong"})
    original = sha256_file(old)
    assert workflow.submit(run, old)["attempts"] == 1
    second = workflow.next_task(run)
    new = Path(second["answer_path"])
    atomic_write_json(new, {"task_id": "wrong again"})
    result = workflow.submit(run, new)
    assert result["attempts"] == 2 and result["module_failed"]
    assert sha256_file(old) == original
    state = workflow._load(workflow._root(run))
    assert state["modules"]["statistics"]["status"] == "failed"
    assert state["modules"]["statistics"]["facts"] == []
    assert workflow.next_task(run)["task"]["module"] == "logic"


def test_existing_symlink_is_not_followed_or_overwritten(support_env, tmp_path):
    run = begin(support_env)
    first = workflow.next_task(run)
    outside = tmp_path / "keep.json"
    outside.write_text("keep my work")
    Path(first["answer_path"]).symlink_to(outside)
    with pytest.raises(ReviewError, match="private regular file"):
        workflow.next_task(run)
    assert outside.read_text() == "keep my work"


def test_all_retained_drafts_are_distinct_and_no_refusal_is_invented(support_env):
    run = begin(support_env)
    paths = []
    for _ in range(5):
        issued = workflow.next_task(run)
        path = Path(issued["answer_path"])
        atomic_write_json(path, issued["context"]["answer_template"])
        paths.append(path)
    assert len(set(paths)) == 5
    assert all(path.is_file() for path in paths)
    assert workflow._load(workflow._root(run))["attempts"] == {}
    assert workflow.status(run)["task"] == 0
