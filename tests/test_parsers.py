import zipfile
from pathlib import Path

from conftest import write_docx, write_pdf, write_xlsx

from closed_review.parsers import parse_document


def docx_styles(path: Path, definitions: str) -> None:
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr(
            "word/styles.xml",
            '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"{definitions}</w:styles>",
        )


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


def test_docx_numeric_and_localized_heading_styles(tmp_path: Path) -> None:
    path = tmp_path / "localized.docx"
    write_docx(path, [("1", "도입"), (None, "Synthetic body."), ("local", "Discussion")])
    docx_styles(
        path,
        '<w:style w:type="paragraph" w:styleId="1"><w:name w:val="제목 1"/>'
        '<w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="local"><w:name w:val="Heading 2"/></w:style>',
    )
    parsed = parse_document(path)
    assert [s["kind"] for s in parsed.segments] == ["heading", "paragraph", "heading"]
    assert parsed.segments[1]["locator"] == "heading:도입/paragraph:2"
    assert [s["text"] for s in parsed.segments] == ["도입", "Synthetic body.", "Discussion"]


def test_docx_heading_style_inheritance_and_body_override(tmp_path: Path) -> None:
    path = tmp_path / "inherited.docx"
    write_docx(
        path, [("custom", "Methods"), ("body", "Synthetic body."), ("cycle-a", "Not a heading.")]
    )
    docx_styles(
        path,
        '<w:style w:type="paragraph" w:styleId="base"><w:pPr>'
        '<w:outlineLvl w:val="1"/></w:pPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="custom"><w:basedOn w:val="base"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="body"><w:basedOn w:val="base"/>'
        '<w:pPr><w:outlineLvl w:val="9"/></w:pPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="cycle-a"><w:basedOn w:val="cycle-b"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="cycle-b"><w:basedOn w:val="cycle-a"/></w:style>',
    )
    assert [s["kind"] for s in parse_document(path).segments] == [
        "heading",
        "paragraph",
        "paragraph",
    ]


def test_docx_direct_outline_overrides_paragraph_style(tmp_path: Path) -> None:
    path = tmp_path / "outline.docx"
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="{ns}"><w:body>'
            '<w:p><w:pPr><w:outlineLvl w:val="0"/></w:pPr><w:r><w:t>Methods</w:t></w:r></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/><w:outlineLvl w:val="9"/></w:pPr>'
            "<w:r><w:t>Synthetic body.</w:t></w:r></w:p></w:body></w:document>",
        )
    assert [s["kind"] for s in parse_document(path).segments] == ["heading", "paragraph"]


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


def test_plain_text_keeps_markup_characters_as_text(tmp_path: Path) -> None:
    path = tmp_path / "paper.txt"
    path.write_text("# not a heading\nstill first\n\n\nSecond paragraph.\n")
    parsed = parse_document(path)
    assert parsed.format == "text"
    assert [(s["locator"], s["kind"], s["text"]) for s in parsed.segments] == [
        ("lines:1-2", "paragraph", "# not a heading\nstill first"),
        ("lines:5-5", "paragraph", "Second paragraph."),
    ]
    assert parsed.warnings == []
