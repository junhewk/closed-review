from pathlib import Path

from conftest import write_docx, write_pdf, write_xlsx

from closed_review.parsers import parse_document


def test_markdown_has_stable_heading_and_line_locators(tmp_path: Path) -> None:
    path = tmp_path / "paper.md"
    path.write_text("# Introduction\n\nFirst claim.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n")
    parsed = parse_document(path)
    assert parsed.format == "markdown"
    assert parsed.segments[0]["locator"] == "heading:Introduction/line:1"
    assert parsed.segments[1]["text"] == "First claim."
    assert parsed.segments[2]["kind"] == "table"


def test_docx_preserves_paragraphs_and_table_rows(tmp_path: Path) -> None:
    path = tmp_path / "paper.docx"
    write_docx(
        path,
        [("Heading1", "Methods"), (None, "We sampled 42 records.")],
        [["Group", "n"], ["A", "21"]],
    )
    parsed = parse_document(path)
    assert [item["kind"] for item in parsed.segments] == [
        "heading",
        "paragraph",
        "table_row",
        "table_row",
    ]
    assert parsed.segments[1]["locator"].startswith("heading:Methods/paragraph:")
    assert parsed.segments[-1]["text"] == "A | 21"
    assert parsed.warnings == []


def test_pdf_has_page_locator(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    write_pdf(path)
    parsed = parse_document(path)
    assert parsed.page_count == 1
    assert parsed.segments[0]["locator"].startswith("page:1/block:")
    assert "Confidential review fixture" in parsed.segments[0]["text"]


def test_pdf_with_no_text_is_marked_for_human_inspection(tmp_path: Path) -> None:
    path = tmp_path / "scan.pdf"
    write_pdf(path, "")
    parsed = parse_document(path)
    assert any("no extractable text" in warning for warning in parsed.warnings)
    assert any("very little text" in warning for warning in parsed.warnings)


def test_xlsx_preserves_sheet_rows_cells_and_formulas(tmp_path: Path) -> None:
    path = tmp_path / "supplement.xlsx"
    write_xlsx(path)
    parsed = parse_document(path)
    assert parsed.format == "xlsx"
    assert [item["locator"] for item in parsed.segments] == [
        "sheet:Data/row:1",
        "sheet:Data/row:2",
    ]
    assert parsed.segments[0]["text"] == "A1=Group | B1=n"
    assert "C2==B2*2 => 42" in parsed.segments[1]["text"]
    assert any("display formatting" in warning for warning in parsed.warnings)
