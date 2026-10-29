"""Immutable source snapshots with native table geometry, independent of legacy scans."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

from defusedxml import ElementTree

from ..errors import ReviewError
from ..io import sha256_file
from ..parsers import WORD_NS, _safe_office_members, _word_text, parse_document

FORMATS = {".pdf", ".docx", ".md", ".markdown", ".txt"}
PDF_SCOPE_LIMIT = (
    "Automatic PDF table geometry uses visible ruled grids only. Borderless tables remain "
    "in extracted text and require human layout review; table detection may miss tables. "
    "Figures/scans have not been read. No OCR."
)
PDF_QUOTE_POLICY = "pdf-layout-whitespace-v1"


def snapshot(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in FORMATS:
        raise ReviewError("support accepts one manuscript: PDF, DOCX, Markdown, or text")
    digest = sha256_file(path)
    parsed = parse_document(path)
    blocks = [
        {"id": s["segment_id"], **{k: s[k] for k in ("kind", "locator", "text")}}
        for s in parsed.segments
    ]
    tables: list[dict[str, Any]] = []
    warnings = list(parsed.warnings)
    scope_limits = []
    if path.suffix.lower() == ".docx":
        try:
            tables = _docx_tables(path, warnings)
        except (ValueError, KeyError, ElementTree.ParseError) as exc:
            raise ReviewError(f"invalid DOCX table structure: {exc}") from exc
        # Native cells replace lossy flattened rows in this workflow only.
        blocks = [b for b in blocks if b["kind"] != "table_row"]
    elif parsed.format == "markdown":
        tables = _markdown_tables(blocks)
        # The native cells already retain every header/data cell. Do not also schedule
        # the entire Markdown table as an indivisible extraction block: an ordinary
        # multi-page table can exceed a task even though every intact row fits.
        # Keep its original text in the snapshot for provenance/layout inspection.
        native = {identifier for table in tables for identifier in table["source_block_ids"]}
        blocks = [block for block in blocks if block["id"] not in native]
    elif path.suffix.lower() == ".pdf":
        tables, extra = _pdf_tables(path)
        warnings.extend(extra)
        scope_limits.append(PDF_SCOPE_LIMIT)
    for table in tables:
        if table["ambiguous"]:
            warnings.append(
                f"{table['id']} has ambiguous physical table geometry; "
                "its alignment has not been reconstructed."
            )
        for cell in table["cells"]:
            blocks.append({"kind": "cell", "table_id": table["id"], **cell})
    if parsed.format == "pdf":
        for block in blocks:
            extracted = block["text"]
            canonical = " ".join(extracted.split())
            if canonical != extracted:
                block.update(
                    extracted_text=extracted,
                    text=canonical,
                    text_transform=PDF_QUOTE_POLICY,
                )
    if sha256_file(path) != digest:
        raise ReviewError("manuscript changed while it was being parsed")
    return {
        "schema_version": 1,
        "source_id": "manuscript",
        "path": str(path),
        "sha256": digest,
        "format": parsed.format,
        "blocks": blocks,
        "tables": tables,
        "warnings": warnings,
        "scope_limits": scope_limits,
        "quote_text_policy": (
            PDF_QUOTE_POLICY if parsed.format == "pdf" else "exact-extracted-text-v1"
        ),
        "extraction_verified": False,
        "limitations": "Source matching does not verify table interpretation or completeness.",
    }


def _cell(table: str, row: int, column: int, text: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": f"{table}-r{row}-c{column}",
        "row": row,
        "column": column,
        "row_span": 1,
        "column_span": 1,
        "text": text,
        "locator": f"{table}/row:{row}/column:{column}",
        "ambiguous": False,
        **extra,
    }


def _docx_tables(path: Path, warnings: list[str] | None = None) -> list[dict[str, Any]]:
    tables = []
    with zipfile.ZipFile(path) as archive:
        _safe_office_members(archive, "DOCX")
        document = ElementTree.fromstring(archive.read("word/document.xml"))
        math_namespace = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
        if warnings is not None and any(e.tag.startswith(math_namespace) for e in document.iter()):
            warnings.append(
                "DOCX Office Math expressions were not reconstructed; "
                "do not infer missing values from them."
            )
        body = document.find(f"{WORD_NS}body")
        if body is None:
            return []
        preceding = ""
        for node in body:
            if node.tag == f"{WORD_NS}p":
                preceding = _word_text(node)
            if node.tag != f"{WORD_NS}tbl":
                continue
            tid = f"table-{len(tables) + 1}"
            cells, widths, active = [], [], {}
            grid = len(node.findall(f"{WORD_NS}tblGrid/{WORD_NS}gridCol"))
            for ri, row in enumerate(node.findall(f"{WORD_NS}tr"), 1):
                column = 1
                next_active = {}
                before = row.find(f"{WORD_NS}trPr/{WORD_NS}gridBefore")
                if before is not None:
                    omitted = int(before.attrib.get(f"{WORD_NS}val", "0"))
                    if not 0 <= omitted <= 1000:
                        raise ReviewError("invalid DOCX omitted columns")
                    for _ in range(omitted):
                        cells.append(_cell(tid, ri, column, "", omitted=True))
                        column += 1
                for cell in row.findall(f"{WORD_NS}tc"):
                    span = cell.find(f"{WORD_NS}tcPr/{WORD_NS}gridSpan")
                    width = int(span.attrib.get(f"{WORD_NS}val", "1")) if span is not None else 1
                    if width < 1 or width > 1000:
                        raise ReviewError("invalid DOCX table span")
                    merge = cell.find(f"{WORD_NS}tcPr/{WORD_NS}vMerge")
                    continuation = (
                        merge is not None and merge.attrib.get(f"{WORD_NS}val") != "restart"
                    )
                    text = "\n".join(_word_text(p) for p in cell.findall(f"{WORD_NS}p"))
                    record = _cell(tid, ri, column, text, column_span=width)
                    if (
                        cell.find(f"{WORD_NS}tcPr/{WORD_NS}hMerge") is not None
                        or cell.find(f"{WORD_NS}tbl") is not None
                        or any(e.tag.startswith(math_namespace) for e in cell.iter())
                    ):
                        record["ambiguous"] = True
                    if warnings is not None and cell.find(f"{WORD_NS}tbl") is not None:
                        warnings.append(
                            "Nested DOCX table content was not reconstructed; "
                            "its containing table is ambiguous."
                        )
                    if continuation:
                        origin = active.get(column)
                        if origin is None or origin["column_span"] != width:
                            record["ambiguous"] = True
                        else:
                            record["merged_into"] = origin["id"]
                            origin["row_span"] += 1
                            next_active[column] = origin
                    elif merge is not None:
                        next_active[column] = record
                    cells.append(record)
                    column += width
                after = row.find(f"{WORD_NS}trPr/{WORD_NS}gridAfter")
                if after is not None:
                    omitted = int(after.attrib.get(f"{WORD_NS}val", "0"))
                    if not 0 <= omitted <= 1000:
                        raise ReviewError("invalid DOCX omitted columns")
                    for _ in range(omitted):
                        cells.append(_cell(tid, ri, column, "", omitted=True))
                        column += 1
                widths.append(column - 1)
                active = next_active
            ambiguous = len(set(widths)) > 1 or any(c["ambiguous"] for c in cells)
            ambiguous |= bool(grid and any(w != grid for w in widths))
            if ambiguous:
                for cell in cells:
                    cell["ambiguous"] = True
            tables.append(
                {
                    "id": tid,
                    "structure": "native",
                    "caption_context": preceding,
                    "rows": len(widths),
                    "columns": max(widths, default=0),
                    "cells": cells,
                    "ambiguous": ambiguous,
                    "notes": "Semantic headers, denominators and units require interpretation.",
                }
            )
    return tables


def _markdown_tables(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tables = []
    for block in blocks:
        if block["kind"] != "table":
            continue
        lines = block["text"].splitlines()

        def split(line: str) -> list[str]:
            line = line.strip()
            if line.startswith("|"):
                line = line[1:]
            if line.endswith("|") and not line.endswith("\\|"):
                line = line[:-1]
            return [s.strip() for s in re.split(r"(?<!\\)\|", line)]

        if len(lines) < 2 or not all(re.fullmatch(r":?-+:?", s) for s in split(lines[1])):
            continue
        rows = [split(line) for i, line in enumerate(lines) if i != 1]
        tid = f"table-{len(tables) + 1}"
        ambiguous = len({len(row) for row in rows}) != 1
        cells = [
            _cell(tid, ri, ci, value, ambiguous=ambiguous)
            for ri, row in enumerate(rows, 1)
            for ci, value in enumerate(row, 1)
        ]
        tables.append(
            {
                "id": tid,
                "structure": "native",
                "caption_context": block["locator"],
                "source_block_ids": [block["id"]],
                "source_text": block["text"],
                "rows": len(rows),
                "columns": max(map(len, rows)),
                "cells": cells,
                "ambiguous": ambiguous,
                "notes": "Header roles are not certified.",
            }
        )
    return tables


def _pdf_tables(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise ReviewError("PDF support requires the packaged pdfplumber dependency") from exc
    tables, warnings = [], []
    try:
        with pdfplumber.open(path) as pdf:
            for pi, page in enumerate(pdf.pages, 1):
                found = page.find_tables()
                # Text-alignment guesses can partition ordinary prose into hundreds of
                # apparently unambiguous cells, even splitting printed words/numbers.
                # Never promote those guesses into geometry eligible for numeric bindings.
                # Original page text is retained; the explicit format scope covers
                # borderless tables rather than inventing a processing failure for prose.
                for candidate in found:
                    rows = candidate.extract()
                    if not rows:
                        continue
                    tid = f"table-{len(tables) + 1}"
                    ambiguous = len({len(row) for row in rows}) > 1 or any(
                        value is None for row in rows for value in row
                    )
                    cells = [
                        _cell(
                            tid,
                            ri,
                            ci,
                            value or "",
                            ambiguous=ambiguous,
                            locator=f"page:{pi}/{tid}/row:{ri}/column:{ci}",
                        )
                        for ri, row in enumerate(rows, 1)
                        for ci, value in enumerate(row, 1)
                    ]
                    tables.append(
                        {
                            "id": tid,
                            "structure": "extracted",
                            "page": pi,
                            "bbox": list(candidate.bbox),
                            "rows": len(rows),
                            "columns": max(map(len, rows)),
                            "cells": cells,
                            "ambiguous": ambiguous,
                            "caption_context": "",
                            "notes": "PDF geometry and semantic alignment are not certified.",
                        }
                    )
    except Exception as exc:
        raise ReviewError(f"cannot extract PDF tables: {exc}") from exc
    return tables, warnings


def ambiguous_block_ids(source: dict[str, Any]) -> set[str]:
    """Extractor geometry only, not contradictions or uncertain author intent.

    Retained flattened table/page text must not bypass its native geometry flag. Older
    Markdown snapshots identify their original table block by caption_context locator.
    PDF text has no per-block geometry, so an ambiguous table conservatively affects its page.
    Absence of a flag is not a certificate of semantic alignment or extraction completeness.
    """
    tables = [table for table in source.get("tables", []) if table.get("ambiguous")]
    identifiers = {
        identifier for table in tables for identifier in table.get("source_block_ids", [])
    }
    locators = {table.get("caption_context") for table in tables if table.get("caption_context")}
    pages = {table["page"] for table in tables if table.get("page") is not None}
    table_ids = {table["id"] for table in tables if "id" in table}
    for block in source["blocks"]:
        page = re.match(r"page:(\d+)/", block.get("locator", ""))
        if (
            block.get("ambiguous")
            or block.get("table_id") in table_ids
            or (block.get("kind") == "table" and block.get("locator") in locators)
            or (page and int(page[1]) in pages)
        ):
            identifiers.add(block["id"])
    return identifiers


def resolve_evidence(raw: Any, source: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ReviewError("evidence must be a list of {block_id, quote}")
    blocks = {b["id"]: b for b in source["blocks"]}
    ambiguous = ambiguous_block_ids(source)
    result = []
    for item in raw:
        if not isinstance(item, dict):
            raise ReviewError("evidence item must be an object")
        block = blocks.get(item.get("block_id", ""))
        quote = item.get("quote")
        if (
            block is None
            or not isinstance(quote, str)
            or not quote.strip()
            or quote not in block["text"]
        ):
            raise ReviewError("evidence must quote an exact substring at the specified block_id")
        result.append(
            {
                "block_id": block["id"],
                "locator": block["locator"],
                "quote": quote,
                "ambiguous": block["id"] in ambiguous,
            }
        )
    return result
