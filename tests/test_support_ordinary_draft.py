"""Draft-source integrity and extraction, not independent medical corpus validation."""

from pathlib import Path

import pytest

from closed_review.support.budgets import TASK_CHARS
from closed_review.support.evaluation import load_manifest
from closed_review.support.methods import MODULES
from closed_review.support.paging import payload_chars
from closed_review.support.sources import snapshot
from closed_review.support.workflow import _chunks, _instructions

ROOT = Path(__file__).resolve().parents[1] / "evals/support-ordinary-draft"


@pytest.mark.parametrize(
    "case_id,module",
    [
        ("r17", "statistics"), ("q28", "qualitative-study"),
        ("s43", "systematic-review"), ("h36", "scoping-review"),
        ("n54", "narrative-review"), ("l62", "logic"),
    ],
)
def test_ordinary_draft_is_hash_bound_parseable_and_still_explicitly_unreviewed(case_id, module):
    manifest, rows = load_manifest(ROOT / "manifest.json", ROOT / "manuscripts")
    assert manifest["independently_reviewed"] is False
    assert manifest["synthetic_only"] is True
    row = next(row for row in rows if row["case_id"] == case_id)
    assert len(rows) == 6 and row["module"] == module
    assert {row["module"] for row in rows} == set(MODULES)
    source = snapshot(row["path"])
    assert len(row["path"].read_text(encoding="utf-8").split()) >= 3000
    assert len(source["tables"]) == 3 and not source["warnings"]
    chunks = _chunks(source["blocks"])
    assert len(chunks) > 1
    assert [identifier for chunk in chunks for identifier in chunk] == [
        block["id"] for block in source["blocks"]
    ]


@pytest.mark.parametrize("case_id", ["r17", "q28", "s43", "h36", "n54", "l62"])
def test_full_draft_extraction_payloads_fit_capture_without_dropping_blocks(case_id):
    _, rows = load_manifest(ROOT / "manifest.json", ROOT / "manuscripts")
    row = next(row for row in rows if row["case_id"] == case_id)
    module = row["module"]
    source = snapshot(row["path"])
    run_id = "support-" + "a" * 32
    run = {
        "id": run_id,
        "language": "ko",
        "resolved_language": None,
        "source": source,
        "modules": {module: {"facts": [], "criteria": [], "calculations": []}},
    }
    delivered = []
    for index, block_ids in enumerate(_chunks(source["blocks"]), 1):
        task = {
            "id": f"task-{index:04d}",
            "module": module,
            "stage": "extract",
            "block_ids": block_ids,
        }
        instructions, context = _instructions(run, task)
        answer_path = (
            "/tmp/ordinary-draft-payload-check/" + "profile/" * 12
            + f"review-data/support/{run_id}/answers/{task['id']}.json"
        )
        payload = {
            "phase": "task",
            "task": task,
            "answer_path": answer_path,
            "instructions": instructions,
            "context": context,
            "submit": f"creview support submit {run_id} {answer_path}",
        }
        assert payload_chars(payload) <= TASK_CHARS
        originals = [block for block in source["blocks"] if block["id"] in block_ids]
        assert context["blocks"] == originals
        assert all("cells" not in table for table in context["tables"])
        delivered.extend(context["blocks"])
    assert delivered == source["blocks"]
