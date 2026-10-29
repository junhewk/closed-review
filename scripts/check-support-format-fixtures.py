"""Check locally generated synthetic format fixtures before any live engineering run.

Only the allowlisted invented case-02 and full-length r17 sources are accepted. Preservation is not
independent medical validation, proof of no hidden content, or a quality/control assignment.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, sha256_file
from closed_review.receipts import installed_identity
from closed_review.support import PROTOCOL
from closed_review.support.sources import snapshot

SOURCE = Path(__file__).resolve().parents[1] / "evals/support-pilot/manuscripts/case-02.md"
SOURCES = {
    "case02": SOURCE,
    "r17": Path(__file__).resolve().parents[1] / "evals/support-ordinary-draft/manuscripts/r17.md",
}
FILES = (("f00", "f00.md"), ("f01", "f01.docx"), ("f02", "f01.pdf"))
RETAINED_HYPHEN_WRAP = re.compile(r"([A-Za-z]-)[ \t]*\r?\n[ \t]*(?=[A-Za-z])")
COMPARISON_POLICY = "fixture-pdf-retained-hyphen-layout-v1"


def normalized(text: str) -> str:
    # Layout wrapping only. Do not repair punctuation, numbers, spelling or headers.
    return " ".join(text.split())


def pdf_layout_text(text: str) -> str:
    # Evaluator comparison only: join a line wrap after a RETAINED printed hyphen
    # between letters. Never drop that hyphen, join digits, or change saved source/quotes.
    return normalized(RETAINED_HYPHEN_WRAP.sub(r"\1", text))


def compare_snapshot(actual: dict, expected: dict, *, pdf_layout: bool = True) -> dict:
    is_pdf = actual.get("format") == "pdf" and pdf_layout
    def text_of(block):
        return block.get("extracted_text", block["text"]) if is_pdf else block["text"]

    actual_body = "\n".join(
        text_of(block) for block in actual["blocks"] if block["kind"] not in {"table", "cell"}
    )
    body = pdf_layout_text(actual_body) if is_pdf else normalized(actual_body)
    paragraphs = [
        normalized(block["text"])
        for block in expected["blocks"]
        if block["kind"] not in {"table", "cell"}
    ]
    cursor, ordered = 0, bool(paragraphs)
    for paragraph in paragraphs:
        position = body.find(paragraph, cursor)
        if position < 0:
            ordered = False
            break
        cursor = position + len(paragraph)

    def grids(source, *, pdf_layout=False):
        return [
            {
                "rows": table["rows"],
                "columns": table["columns"],
                "cells": [
                    (cell["row"], cell["column"], cell["row_span"], cell["column_span"],
                     pdf_layout_text(cell.get("extracted_text", cell["text"]))
                     if pdf_layout else normalized(cell["text"]))
                    for cell in table["cells"]
                ],
            }
            for table in source["tables"]
        ]

    return {
        "all_expected_paragraphs_present": bool(paragraphs) and all(
            paragraph in body for paragraph in paragraphs
        ),
        "expected_paragraphs_in_order": ordered,
        "table_grids_equal": bool(expected["tables"]) and (
            grids(actual, pdf_layout=is_pdf) == grids(expected)
        ),
        "no_detected_geometry_ambiguity": not any(
            table["ambiguous"] for table in actual["tables"]
        ),
    }


def inspect(inputs: Path, fixture: str = "case02") -> tuple[dict, dict]:
    if fixture not in SOURCES:
        raise ReviewError("choose an allowlisted synthetic fixture, not an arbitrary manuscript")
    if inputs.is_symlink() or not inputs.is_dir():
        raise ReviewError("format inputs must be a regular local fixture directory")
    source = SOURCES[fixture]
    expected = snapshot(source)
    source_hash = sha256_file(source)
    cases, inspected = [], []
    for case_id, filename in FILES:
        path = inputs / filename
        if path.is_symlink() or not path.is_file():
            raise ReviewError(f"missing/nonregular synthetic format fixture: {filename}")
        actual = snapshot(path)
        checks = compare_snapshot(actual, expected)
        if filename.endswith(".md"):
            checks["original_bytes_unchanged"] = actual["sha256"] == source_hash
        cases.append({
            "case_id": case_id,
            "module": "statistics",
            "file": filename,
            "sha256": actual["sha256"],
        })
        inspected.append({
            "case_id": case_id,
            "format": actual["format"],
            "sha256": actual["sha256"],
            "checks": checks,
            "strict_whitespace_only_checks": compare_snapshot(actual, expected, pdf_layout=False),
            "blocks": len(actual["blocks"]),
            "tables": len(actual["tables"]),
            "warnings": actual["warnings"],
            "scope_limits": actual.get("scope_limits", []),
        })
    if sha256_file(source) != source_hash:
        raise ReviewError("synthetic source changed during inspection")
    manifest = {
        "protocol": PROTOCOL,
        "corpus_id": f"native-format-engineering-{fixture}-20261028",
        "synthetic_only": True,
        "independently_reviewed": False,
        "cases": cases,
    }
    report = {
        "protocol": PROTOCOL,
        "identity": installed_identity(),
        "checker_sha256": sha256_file(Path(__file__)),
        "comparison_policy": COMPARISON_POLICY,
        "original_sha256": source_hash,
        "fixture": fixture,
        "source_words": len(source.read_text(encoding="utf-8").split()),
        "format_probe_ready": all(all(row["checks"].values()) for row in inspected),
        "inputs": inspected,
        "independent_studies": 1,
        "clinical_quality": "not_assessed",
        "qualification": "not_qualified",
        "manual_render_inspection": None,
        "note": (
            "Three formats of the SAME invented article, not independent medical cases. "
            "PDF comparison additionally joins raw-extracted line wraps after a retained hyphen "
            "between letters only; strict whitespace-only results remain alongside it. This does "
            "not rewrite manuscript bytes, source snapshots, quotations or numeric bindings. "
            "Text/grid checks do not prove completeness, absence of hidden content or validity. "
            "Keep generator/build/render metadata on the evaluator; only key-free source files "
            "and the manifest may go to the model host."
        ),
    }
    return manifest, report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--fixture", choices=sorted(SOURCES), default="case02")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.manifest.exists() or args.report.exists() or args.manifest == args.report:
        parser.error("choose NEW distinct manifest/report files; preserve previous evidence")
    manifest, report = inspect(args.inputs, args.fixture)
    atomic_write_json(args.report, report)
    if report["format_probe_ready"]:
        atomic_write_json(args.manifest, manifest)
    print(json.dumps({
        "format_probe_ready": report["format_probe_ready"],
        "report": str(args.report),
        "manifest_written": report["format_probe_ready"],
        "qualification": "not_qualified",
    }))
    return 0 if report["format_probe_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
