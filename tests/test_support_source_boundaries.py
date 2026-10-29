"""Row/task boundaries and conservative PDF geometry never invent source evidence."""

import copy
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import write_pdf
from test_support import support_env as support_env

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, read_json, sha256_file
from closed_review.support import sources, workflow
from closed_review.support.evaluation import load_manifest


def cell(table, row, column, text="20"):
    return {
        "id": f"{table}-r{row}-c{column}",
        "kind": "cell",
        "table_id": table,
        "row": row,
        "column": column,
        "text": text,
    }


def test_chunk_boundary_moves_a_whole_row_without_changing_source_or_order(monkeypatch):
    monkeypatch.setattr(workflow, "CHUNK_CHARS", 700)
    blocks = [{"id": "p1", "kind": "paragraph", "text": "A printed paragraph."}]
    blocks += [cell("table-1", row, column) for row in (1, 2) for column in (1, 2, 3)]
    original = copy.deepcopy(blocks)
    chunks = workflow._chunks(blocks)
    assert chunks == [["p1"], [b["id"] for b in blocks[1:4]], [b["id"] for b in blocks[4:]]]
    assert blocks == original


def test_row_grouping_does_not_confuse_different_tables_or_noncell_blocks(monkeypatch):
    monkeypatch.setattr(workflow, "CHUNK_CHARS", 400)
    blocks = [cell("table-1", 1, 1), cell("table-1", 1, 2), cell("table-2", 1, 1)]
    blocks += [{"id": "p1", "kind": "paragraph", "text": "Unchanged."}]
    assert workflow._chunks(blocks) == [
        ["table-1-r1-c1", "table-1-r1-c2"],
        ["table-2-r1-c1", "p1"],
    ]


def test_overbudget_intact_row_is_refused_not_truncated(monkeypatch):
    monkeypatch.setattr(workflow, "CHUNK_CHARS", 400)
    blocks = [cell("table-1", 1, col) for col in (1, 2, 3)]
    with pytest.raises(ReviewError, match="intact table row exceeds.*not a truncated row"):
        workflow._chunks(blocks)


@pytest.mark.parametrize("case_id", ["r17", "q28", "s43", "h36", "n54", "l62"])
def test_actual_full_length_sources_never_split_a_native_row(case_id):
    root = Path(__file__).resolve().parents[1] / "evals/support-ordinary-draft"
    _, rows = load_manifest(root / "manifest.json", root / "manuscripts")
    source = sources.snapshot(next(r["path"] for r in rows if r["case_id"] == case_id))
    chunks = workflow._chunks(source["blocks"])
    positions = {identifier: index for index, chunk in enumerate(chunks) for identifier in chunk}
    assert list(positions) == [b["id"] for b in source["blocks"]]
    for table in source["tables"]:
        for row in range(1, table["rows"] + 1):
            assert len({positions[c["id"]] for c in table["cells"] if c["row"] == row}) == 1


def test_large_markdown_table_schedules_all_native_cells_without_a_giant_duplicate(support_env):
    paper, key = support_env
    original = paper.read_text(encoding="utf-8")
    table = "| Study | Patients | Result | Description |\n|---|---|---|---|\n"
    table += "\n".join(
        f"| Study {i} | 100 | 20 (20%) | " + f"Exact printed detail {i}. " * 12 + "|"
        for i in range(70)
    )
    assert len(table) > workflow.CHUNK_CHARS
    paper.write_text(original + "\n\n" + table + "\n", encoding="utf-8")
    digest = sha256_file(paper)
    source = sources.snapshot(paper)
    assert not any(block["kind"] == "table" for block in source["blocks"])
    native = source["tables"][0]
    assert native["source_text"] == table
    assert native["rows"] == 71 and len(native["cells"]) == 284
    assert all(
        cell
        in [
            {k: v for k, v in b.items() if k not in {"kind", "table_id"}}
            for b in source["blocks"]
            if b["kind"] == "cell"
        ]
        for cell in native["cells"]
    )
    chunks = workflow._chunks(source["blocks"])
    positions = {identifier: i for i, chunk in enumerate(chunks) for identifier in chunk}
    assert list(positions) == [b["id"] for b in source["blocks"]]
    for row in range(1, 72):
        assert len({positions[c["id"]] for c in native["cells"] if c["row"] == row}) == 1
    run = workflow.start(paper, ["systematic-review"], session=key)["run_id"]
    issued = workflow.next_task(run)
    assert all("source_text" not in table for table in issued["context"]["tables"])
    assert sha256_file(paper) == digest


def test_outside_chunk_diagnostic_is_actionable_private_atomic_and_not_auto_repaired(
    support_env,
    monkeypatch,
):
    monkeypatch.setattr(workflow, "CHUNK_CHARS", 400)
    paper, key = support_env
    run_id = workflow.start(paper, ["statistics"], session=key)["run_id"]
    issued = workflow.next_task(run_id)
    path = Path(issued["answer_path"])
    run = workflow._load(workflow._root(run_id))
    outside = next(b for b in run["source"]["blocks"] if b["id"] not in issued["task"]["block_ids"])
    answer = copy.deepcopy(issued["context"]["answer_template"])
    answer["facts"] = [
        {
            "role": issued["context"]["guide"]["roles"][0],
            "label": "private-label-not-in-diagnostic",
            "value": "private-value-not-in-diagnostic",
            "evidence": [{"block_id": outside["id"], "quote": outside["text"]}],
        }
    ]
    assert "cross-chunk analysis happens at appraisal" in issued["instructions"]
    for attempt in (1, 2):
        atomic_write_json(path, answer)
        result = workflow.submit(run_id, path)
        assert not result["accepted"] and result["attempts"] == attempt
        assert result["module_failed"] is (attempt == 2)
        assert "facts.0.evidence" in result["error"]
        assert "use this task's block_ids" in result["error"]
        assert "private-label" not in result["error"] and outside["text"] not in result["error"]
        assert read_json(path.with_name(f"task-0001-rejected-{attempt}.json")) == answer
        state = workflow._load(workflow._root(run_id))["modules"]["statistics"]
        assert state["facts"] == [] and state["provided_blocks"] == issued["task"]["block_ids"]


def test_pdf_table_extraction_never_uses_text_alignment_to_invent_cells(monkeypatch, tmp_path):
    import pdfplumber

    calls = []
    candidate = SimpleNamespace(
        bbox=(0, 0, 100, 50),
        extract=lambda: [["N", "Value"], ["100", "20"]],
    )

    class Page:
        def __init__(self, found):
            self.found = found

        def find_tables(self, *args, **kwargs):
            calls.append((args, kwargs))
            assert not args and not kwargs, "prose must not be retried as borderless geometry"
            return self.found

    class PDF:
        pages = [Page([]), Page([candidate]), Page([])]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    monkeypatch.setattr(pdfplumber, "open", lambda _: PDF())
    tables, warnings = sources._pdf_tables(tmp_path / "unused.pdf")
    assert calls == [((), {})] * 3 and warnings == []
    assert len(tables) == 1 and tables[0]["page"] == 2
    assert [c["text"] for c in tables[0]["cells"]] == ["N", "Value", "100", "20"]


def test_real_unruled_prose_retains_text_and_explicit_borderless_limit(tmp_path):
    path = tmp_path / "prose.pdf"
    text = "This synthetic paragraph reports 100 patients and 20 events without a table. " * 4
    write_pdf(path, text)
    source = sources.snapshot(path)
    assert source["blocks"] and not source["tables"]
    assert "100 patients" in source["blocks"][0]["text"]
    assert source["scope_limits"] == [sources.PDF_SCOPE_LIMIT]
    assert "Borderless tables" in sources.PDF_SCOPE_LIMIT
    assert source["extraction_verified"] is False
