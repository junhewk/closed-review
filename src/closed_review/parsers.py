from __future__ import annotations

import posixpath
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from defusedxml import ElementTree

from .errors import ReviewError

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".md", ".markdown", ".txt"}
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
OFFICE_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PACKAGE_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
MAX_OFFICE_UNCOMPRESSED = 200 * 1024 * 1024


@dataclass(frozen=True)
class ParsedDocument:
    format: str
    segments: list[dict[str, Any]]
    warnings: list[str]
    page_count: int | None = None


def _clean(value: str) -> str:
    return re.sub(r"[ \t]+", " ", value.replace("\r\n", "\n").replace("\r", "\n")).strip()


def _segment(index: int, locator: str, text: str, kind: str = "paragraph") -> dict[str, Any]:
    return {
        "segment_id": f"seg-{index:05d}",
        "locator": locator,
        "kind": kind,
        "text": text,
    }


def parse_pdf(path: Path) -> ParsedDocument:
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LTImage, LTTextContainer
    except ImportError as exc:
        raise ReviewError("PDF support requires pdfminer.six") from exc

    segments: list[dict[str, Any]] = []
    warnings: list[str] = []
    page_lengths: list[int] = []
    try:
        for page_number, layout in enumerate(extract_pages(str(path)), start=1):
            blocks: list[str] = []
            image_count = 0
            pending = list(layout)
            while pending:
                element = pending.pop()
                if isinstance(element, LTImage):
                    image_count += 1
                elif hasattr(element, "__iter__"):
                    pending.extend(list(element))
            for element in layout:
                if isinstance(element, LTTextContainer):
                    text = _clean(element.get_text())
                    if text:
                        blocks.append(text)
            page_lengths.append(sum(len(block) for block in blocks))
            if not blocks:
                warnings.append(f"page {page_number} has no extractable text; inspect it visually")
            if image_count:
                warnings.append(
                    f"page {page_number} contains {image_count} embedded image(s) that require "
                    "human inspection"
                )
            for block_number, text in enumerate(blocks, start=1):
                segments.append(
                    _segment(
                        len(segments) + 1,
                        f"page:{page_number}/block:{block_number}",
                        text,
                        "page_block",
                    )
                )
    except Exception as exc:
        raise ReviewError(f"cannot parse PDF {path.name}: {exc}") from exc

    if not page_lengths:
        raise ReviewError("PDF contains no pages")
    if sum(page_lengths) < max(200, 40 * len(page_lengths)):
        warnings.append("PDF extraction produced very little text; the document may be scanned")
    return ParsedDocument("pdf", segments, warnings, len(page_lengths))


def _word_text(element: ElementTree.Element) -> str:
    parts: list[str] = []
    for node in element.iter():
        if node.tag == f"{WORD_NS}t" and node.text:
            parts.append(node.text)
        elif node.tag == f"{WORD_NS}tab":
            parts.append("\t")
        elif node.tag in {f"{WORD_NS}br", f"{WORD_NS}cr"}:
            parts.append("\n")
    return _clean("".join(parts))


def _paragraph_style(element: ElementTree.Element) -> str | None:
    props = element.find(f"{WORD_NS}pPr")
    style = props.find(f"{WORD_NS}pStyle") if props is not None else None
    if style is None:
        return None
    return style.attrib.get(f"{WORD_NS}val")


def _outline_heading(element: ElementTree.Element) -> bool | None:
    level = element.find(f"{WORD_NS}pPr/{WORD_NS}outlineLvl")
    if level is None:
        return None
    return level.attrib.get(f"{WORD_NS}val") in {str(n) for n in range(9)}


def _word_heading_styles(archive: zipfile.ZipFile) -> dict[str, bool]:
    """Resolve Word styles, whose IDs may be localized or numeric, without changing the DOCX."""
    if "word/styles.xml" not in archive.namelist():
        return {}
    root = ElementTree.fromstring(archive.read("word/styles.xml"))
    styles = {
        style.attrib[f"{WORD_NS}styleId"]: style
        for style in root.findall(f"{WORD_NS}style")
        if style.attrib.get(f"{WORD_NS}type") == "paragraph" and f"{WORD_NS}styleId" in style.attrib
    }

    def heading(style_id: str) -> bool:
        seen: set[str] = set()
        while style_id and style_id not in seen:
            seen.add(style_id)
            style = styles.get(style_id)
            if style is None:
                return style_id.lower().startswith(("heading", "title"))
            outlined = _outline_heading(style)
            if outlined is not None:
                return outlined
            name = style.find(f"{WORD_NS}name")
            label = name.attrib.get(f"{WORD_NS}val", "") if name is not None else ""
            if style_id.lower().startswith(("heading", "title")) or label.lower().startswith(
                ("heading", "title")
            ):
                return True
            parent = style.find(f"{WORD_NS}basedOn")
            style_id = parent.attrib.get(f"{WORD_NS}val", "") if parent is not None else ""
        return False

    return {style_id: heading(style_id) for style_id in styles}


def _word_paragraph_heading(element: ElementTree.Element, styles: dict[str, bool]) -> bool:
    outlined = _outline_heading(element)
    if outlined is not None:
        return outlined
    style_id = _paragraph_style(element) or ""
    return styles.get(style_id, style_id.lower().startswith(("heading", "title")))


def _safe_office_members(archive: zipfile.ZipFile, format_name: str) -> None:
    total = 0
    for info in archive.infolist():
        total += info.file_size
        if total > MAX_OFFICE_UNCOMPRESSED:
            raise ReviewError(f"{format_name} expands beyond the 200 MB safety limit")
        path = Path(info.filename)
        if path.is_absolute() or ".." in path.parts:
            raise ReviewError(f"{format_name} contains an unsafe archive path")


def parse_docx(path: Path) -> ParsedDocument:
    segments: list[dict[str, Any]] = []
    warnings: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            _safe_office_members(archive, "DOCX")
            if "word/document.xml" not in archive.namelist():
                raise ReviewError("DOCX has no word/document.xml")
            root = ElementTree.fromstring(archive.read("word/document.xml"))
            body = root.find(f"{WORD_NS}body")
            if body is None:
                raise ReviewError("DOCX has no document body")
            heading_styles = _word_heading_styles(archive)
            paragraph_number = 0
            table_number = 0
            current_heading = "Document"
            for child in body:
                if child.tag == f"{WORD_NS}p":
                    text = _word_text(child)
                    if not text:
                        continue
                    paragraph_number += 1
                    kind = (
                        "heading" if _word_paragraph_heading(child, heading_styles) else "paragraph"
                    )
                    if kind == "heading":
                        current_heading = text[:160]
                    locator = f"heading:{current_heading}/paragraph:{paragraph_number}"
                    segments.append(_segment(len(segments) + 1, locator, text, kind))
                elif child.tag == f"{WORD_NS}tbl":
                    table_number += 1
                    for row_number, row in enumerate(child.findall(f"{WORD_NS}tr"), start=1):
                        cells = [_word_text(cell) for cell in row.findall(f"{WORD_NS}tc")]
                        text = " | ".join(cell for cell in cells if cell)
                        if text:
                            locator = f"table:{table_number}/row:{row_number}"
                            segments.append(_segment(len(segments) + 1, locator, text, "table_row"))

            if any(name.startswith("word/media/") for name in archive.namelist()):
                warnings.append("DOCX contains embedded images that require human inspection")
            if "word/footnotes.xml" in archive.namelist():
                footnotes = ElementTree.fromstring(archive.read("word/footnotes.xml"))
                for note in footnotes.findall(f"{WORD_NS}footnote"):
                    note_id = note.attrib.get(f"{WORD_NS}id", "unknown")
                    if note_id.startswith("-"):
                        continue
                    text = _word_text(note)
                    if text:
                        segments.append(
                            _segment(len(segments) + 1, f"footnote:{note_id}", text, "footnote")
                        )
    except zipfile.BadZipFile as exc:
        raise ReviewError(f"invalid DOCX: {path.name}") from exc
    except ElementTree.ParseError as exc:
        raise ReviewError(f"invalid DOCX XML: {exc}") from exc

    if not segments:
        warnings.append("DOCX contains no extractable paragraphs or table rows")
    return ParsedDocument("docx", segments, warnings)


def _xlsx_text(element: ElementTree.Element) -> str:
    return _clean("".join(node.text or "" for node in element.iter(f"{SHEET_NS}t")))


def _xlsx_target(target: str) -> str:
    normalized = posixpath.normpath(
        target.lstrip("/") if target.startswith("/xl/") else posixpath.join("xl", target)
    )
    if normalized == ".." or normalized.startswith("../") or not normalized.startswith("xl/"):
        raise ReviewError("XLSX contains an unsafe worksheet relationship")
    return normalized


def _xlsx_cell_value(cell: ElementTree.Element, shared: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    formula_node = cell.find(f"{SHEET_NS}f")
    value_node = cell.find(f"{SHEET_NS}v")
    raw = value_node.text if value_node is not None and value_node.text is not None else ""
    if cell_type == "inlineStr":
        inline = cell.find(f"{SHEET_NS}is")
        value = _xlsx_text(inline) if inline is not None else ""
    elif cell_type == "s":
        try:
            value = shared[int(raw)]
        except (ValueError, IndexError):
            value = f"[invalid shared string {raw}]"
    elif cell_type == "b":
        value = "TRUE" if raw == "1" else "FALSE"
    else:
        value = raw
    value = _clean(value)
    if formula_node is not None and formula_node.text:
        formula = _clean(formula_node.text)
        return f"={formula}" + (f" => {value}" if value else "")
    return value


def parse_xlsx(path: Path) -> ParsedDocument:
    segments: list[dict[str, Any]] = []
    warnings = [
        "XLSX values are extracted without display formatting; inspect date/time and "
        "formatting-dependent evidence in a spreadsheet application"
    ]
    try:
        with zipfile.ZipFile(path) as archive:
            _safe_office_members(archive, "XLSX")
            names = set(archive.namelist())
            required = {"xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
            if not required.issubset(names):
                raise ReviewError("XLSX is missing workbook metadata")

            shared: list[str] = []
            if "xl/sharedStrings.xml" in names:
                shared_root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
                shared = [_xlsx_text(item) for item in shared_root.findall(f"{SHEET_NS}si")]

            relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            targets = {
                item.attrib.get("Id", ""): _xlsx_target(item.attrib.get("Target", ""))
                for item in relationships.findall(f"{PACKAGE_REL_NS}Relationship")
                if item.attrib.get("Id") and item.attrib.get("Target")
            }
            workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
            sheets = workbook.find(f"{SHEET_NS}sheets")
            if sheets is None:
                raise ReviewError("XLSX workbook contains no sheets")
            for sheet_number, sheet in enumerate(sheets.findall(f"{SHEET_NS}sheet"), start=1):
                sheet_name = _clean(sheet.attrib.get("name", f"Sheet {sheet_number}"))[:160]
                if sheet.attrib.get("state", "visible") != "visible":
                    warnings.append(
                        f"worksheet {sheet_name!r} is hidden and requires human inspection"
                    )
                relation_id = sheet.attrib.get(f"{OFFICE_REL_NS}id", "")
                target = targets.get(relation_id)
                if not target or target not in names:
                    warnings.append(f"worksheet {sheet_name!r} could not be extracted")
                    continue
                sheet_root = ElementTree.fromstring(archive.read(target))
                sheet_data = sheet_root.find(f"{SHEET_NS}sheetData")
                if sheet_data is None:
                    continue
                for fallback_row, row in enumerate(sheet_data.findall(f"{SHEET_NS}row"), start=1):
                    row_number = row.attrib.get("r", str(fallback_row))
                    values: list[str] = []
                    for fallback_column, cell in enumerate(row.findall(f"{SHEET_NS}c"), start=1):
                        value = _xlsx_cell_value(cell, shared)
                        if value:
                            reference = cell.attrib.get("r", f"column-{fallback_column}")
                            values.append(f"{reference}={value}")
                    if values:
                        locator = f"sheet:{sheet_name}/row:{row_number}"
                        segments.append(
                            _segment(
                                len(segments) + 1,
                                locator,
                                " | ".join(values),
                                "spreadsheet_row",
                            )
                        )

            if any(name.startswith(("xl/media/", "xl/charts/")) for name in names):
                warnings.append("XLSX contains images or charts that require human inspection")
            if any(name.startswith("xl/externalLinks/") for name in names):
                warnings.append("XLSX contains external links that require human inspection")
    except zipfile.BadZipFile as exc:
        raise ReviewError(f"invalid XLSX: {path.name}") from exc
    except ElementTree.ParseError as exc:
        raise ReviewError(f"invalid XLSX XML: {exc}") from exc

    if not segments:
        warnings.append("XLSX contains no extractable cell values")
    return ParsedDocument("xlsx", segments, warnings)


def parse_markdown(path: Path) -> ParsedDocument:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ReviewError("Markdown input must be UTF-8") from exc
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    segments: list[dict[str, Any]] = []
    heading = "Document"
    buffer: list[str] = []
    start_line = 1

    def flush(end_line: int) -> None:
        nonlocal buffer, start_line
        value = _clean("\n".join(buffer))
        if value:
            kind = "table" if all("|" in line for line in buffer if line.strip()) else "paragraph"
            locator = f"heading:{heading}/lines:{start_line}-{end_line}"
            segments.append(_segment(len(segments) + 1, locator, value, kind))
        buffer = []

    for number, line in enumerate(lines, start=1):
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if match:
            flush(number - 1)
            heading = match.group(1).strip()[:160]
            segments.append(
                _segment(len(segments) + 1, f"heading:{heading}/line:{number}", heading, "heading")
            )
            start_line = number + 1
        elif not line.strip():
            flush(number - 1)
            start_line = number + 1
        else:
            if not buffer:
                start_line = number
            buffer.append(line)
    flush(len(lines))
    warnings = [] if segments else ["Markdown contains no extractable text"]
    if re.search(r"!\[[^\]]*\]\([^)]+\)", text):
        warnings.append("Markdown references images that require human inspection")
    return ParsedDocument("markdown", segments, warnings)


def parse_text(path: Path) -> ParsedDocument:
    """Plain UTF-8 text: blank-line paragraphs; no line is treated as Markdown markup."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ReviewError("text input must be UTF-8") from exc
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    segments: list[dict[str, Any]] = []
    buffer: list[str] = []
    start_line = 1
    for number, line in enumerate([*lines, ""], start=1):
        if line.strip():
            if not buffer:
                start_line = number
            buffer.append(line)
        elif buffer:
            value = _clean("\n".join(buffer))
            if value:
                locator = f"lines:{start_line}-{number - 1}"
                segments.append(_segment(len(segments) + 1, locator, value))
            buffer = []
    return ParsedDocument("text", segments, [] if segments else ["text contains no paragraphs"])


def parse_document(path: Path) -> ParsedDocument:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ReviewError(f"unsupported file format: {suffix or '(none)'}")
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix == ".docx":
        return parse_docx(path)
    if suffix == ".xlsx":
        return parse_xlsx(path)
    if suffix == ".txt":
        return parse_text(path)
    return parse_markdown(path)
