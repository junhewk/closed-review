"""New PDF snapshots canonicalize layout whitespace, never model answers or old records."""

import copy
from pathlib import Path

import pytest
from conftest import write_pdf
from test_support import begin, finish
from test_support import support_env as support_env

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, sha256_file
from closed_review.parsers import ParsedDocument
from closed_review.support import sources, workflow
from closed_review.support.calculators import NUMBER
from closed_review.support.render import export


def pdf_snapshot(tmp_path, monkeypatch, text):
    path = tmp_path / "layout.pdf"
    write_pdf(path)
    parsed = ParsedDocument("pdf", [{
        "segment_id": "b1", "kind": "page_block", "locator": "page:1/block:1", "text": text,
    }], [])
    monkeypatch.setattr(sources, "parse_document", lambda _: parsed)
    monkeypatch.setattr(sources, "_pdf_tables", lambda _: ([], []))
    original_hash = sha256_file(path)
    result = sources.snapshot(path)
    assert sha256_file(path) == original_hash == result["sha256"]
    return result


@pytest.mark.parametrize("layout", [" ", "\n", " \n", "\r\n", "\t", "\u00a0", "\u2009"])
def test_pdf_whitespace_policy_keeps_original_and_literal_numeric_tokens(
    tmp_path, monkeypatch, layout
):
    text = f"All 200{layout}patients; p<0.05; CI 0.41–1.09; not 35%."
    source = pdf_snapshot(tmp_path, monkeypatch, text)
    block = source["blocks"][0]
    canonical = "All 200 patients; p<0.05; CI 0.41–1.09; not 35%."
    assert block["text"] == canonical
    assert NUMBER.findall(block["text"]) == NUMBER.findall(text)
    assert source["quote_text_policy"] == sources.PDF_QUOTE_POLICY
    if text != canonical:
        assert block["extracted_text"] == text
        assert block["text_transform"] == sources.PDF_QUOTE_POLICY
    else:
        assert "extracted_text" not in block
    evidence = sources.resolve_evidence([{"block_id": "b1", "quote": canonical}], source)
    assert evidence[0]["quote"] == canonical
    assert not source["extraction_verified"]


@pytest.mark.parametrize("change", ["number", "punctuation", "wrong-block", "dehyphenation"])
def test_canonical_snapshot_still_refuses_changed_content_and_wrong_ids(
    tmp_path, monkeypatch, change
):
    text = "All 200 \npatients were included; follow-\nup; p<0.05."
    source = pdf_snapshot(tmp_path, monkeypatch, text)
    quote = source["blocks"][0]["text"]
    identifier = "b1"
    if change == "number":
        quote = quote.replace("200", "201")
    elif change == "punctuation":
        quote = quote.replace("<", "=")
    elif change == "wrong-block":
        identifier = "b2"
    else:
        quote = quote.replace("follow- up", "follow-up")
    with pytest.raises(ReviewError, match="exact substring"):
        sources.resolve_evidence([{"block_id": identifier, "quote": quote}], source)


def test_old_saved_pdf_text_is_not_normalized_during_reference_validation(tmp_path, monkeypatch):
    text = "All 200 \npatients were included."
    current = pdf_snapshot(tmp_path, monkeypatch, text)
    historical = copy.deepcopy(current)
    historical.pop("quote_text_policy")
    historical["blocks"][0].update(text=text)
    historical["blocks"][0].pop("extracted_text")
    historical["blocks"][0].pop("text_transform")
    evidence = [{"block_id": "b1", "quote": "All 200 patients were included."}]
    with pytest.raises(ReviewError, match="exact substring"):
        sources.resolve_evidence(evidence, historical)
    assert historical["blocks"][0]["text"] == text


def test_pdf_extraction_task_uses_one_quote_text_and_keeps_layout_in_snapshot(
    support_env, monkeypatch
):
    paper, key = support_env
    pdf_snapshot(paper.parent, monkeypatch, "We enrolled 100 \npatients. There were 20 events.")
    paper = paper.parent / "layout.pdf"
    run_id = workflow.start(paper, ["statistics"], session=key)["run_id"]
    issued = workflow.next_task(run_id)
    source = workflow._load(workflow._root(run_id))["source"]
    assert any("extracted_text" in block for block in source["blocks"])
    assert not any("extracted_text" in block for block in issued["context"]["blocks"])
    assert issued["context"]["source_quote_policy"] == sources.PDF_QUOTE_POLICY
    assert len(source["blocks"]) == len(issued["context"]["blocks"])


def test_pdf_original_layout_is_readable_in_safe_static_export(support_env):
    run_id = begin(support_env)
    finish(run_id)
    root = workflow._root(run_id)
    run = workflow._load(root)
    block = run["source"]["blocks"][0]
    block.update(extracted_text="Original \n<script>not executable</script>",
                 text_transform=sources.PDF_QUOTE_POLICY)
    atomic_write_json(root / "run.json", run)
    paths = export(run_id)
    html = Path(paths["html"]).read_text()
    markdown = Path(paths["markdown"]).read_text()
    assert "Original extracted PDF layout" in html
    assert "&lt;script&gt;not executable&lt;/script&gt;" in html
    assert "<script>not executable</script>" not in html
    assert "Original extracted PDF layout" in markdown
    assert block["extracted_text"] == workflow._load(root)["source"]["blocks"][0]["extracted_text"]
