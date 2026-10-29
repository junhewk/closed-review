"""Unreviewed source delivery/integrity, never author-intent medical judgments."""

from collections import Counter
from pathlib import Path

import pytest

from closed_review.support.budgets import TASK_CHARS
from closed_review.support.evaluation import load_manifest
from closed_review.support.methods import MODULES
from closed_review.support.paging import payload_chars
from closed_review.support.sources import snapshot
from closed_review.support.workflow import _chunks, _instructions

ROOT = Path(__file__).resolve().parents[1] / "evals/support-ordinary-candidates"
ORIGINAL = ROOT.parent / "support-ordinary-draft"
CASE_IDS = ["b09", "c74", "d86", "g51", "h36", "j23", "k65", "l62", "n54", "q28", "r17", "s43"]


def test_candidates_remain_key_free_unreviewed_and_preserve_the_original_six():
    manifest, rows = load_manifest(ROOT / "manifest.json", ROOT / "manuscripts")
    original_manifest, originals = load_manifest(
        ORIGINAL / "manifest.json", ORIGINAL / "manuscripts"
    )
    assert (
        manifest["independently_reviewed"] is original_manifest["independently_reviewed"] is False
    )
    assert manifest["synthetic_only"] is True
    assert manifest["corpus_id"] != original_manifest["corpus_id"]
    assert {row["case_id"] for row in rows} == set(CASE_IDS)
    assert len({row["sha256"] for row in rows}) == 12
    assert Counter(row["module"] for row in rows) == Counter({name: 2 for name in MODULES})
    by_id = {row["case_id"]: row for row in rows}
    for row in originals:
        assert by_id[row["case_id"]]["sha256"] == row["sha256"]
    assert {p.name for p in ROOT.iterdir()} == {"README.md", "manifest.json", "manuscripts"}


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_each_candidate_is_source_only_parseable_and_fully_deliverable(case_id):
    _, rows = load_manifest(ROOT / "manifest.json", ROOT / "manuscripts")
    row = next(row for row in rows if row["case_id"] == case_id)
    source = snapshot(row["path"])
    assert len(row["path"].read_text().split()) >= 3000
    assert len(source["tables"]) == 3 and not source["warnings"]
    chunks = _chunks(source["blocks"])
    assert len(chunks) > 1
    module = row["module"]
    run_id = "support-" + "a" * 32
    run = {
        "id": run_id,
        "language": "ko",
        "resolved_language": None,
        "source": source,
        "modules": {module: {"facts": [], "criteria": [], "calculations": []}},
    }
    delivered = []
    for index, block_ids in enumerate(chunks, 1):
        task = {
            "id": f"task-{index:04d}",
            "module": module,
            "stage": "extract",
            "block_ids": block_ids,
        }
        instructions, context = _instructions(run, task)
        answer = "/tmp/full-length-candidate/" + "profile/" * 12 + f"answers/{task['id']}.json"
        payload = {
            "phase": "task",
            "task": task,
            "answer_path": answer,
            "instructions": instructions,
            "context": context,
            "submit": f"creview support submit {run_id} {answer}",
        }
        assert payload_chars(payload) <= TASK_CHARS
        assert context["blocks"] == [b for b in source["blocks"] if b["id"] in block_ids]
        delivered.extend(context["blocks"])
    assert delivered == source["blocks"]
