"""Format-preservation diagnostics are not medical truth labels."""

import copy
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check-support-format-fixtures.py"
SPEC = importlib.util.spec_from_file_location("support_formats", SCRIPT)
formats = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(formats)


def fixture():
    cell = {
        "row": 1, "column": 1, "row_span": 1, "column_span": 1, "text": "35",
    }
    return {
        "blocks": [
            {"kind": "paragraph", "text": "An exact claim with p<0.05."},
            {"kind": "cell", "text": "35"},
        ],
        "tables": [{"rows": 1, "columns": 1, "ambiguous": False, "cells": [cell]}],
    }


@pytest.mark.parametrize("change", ["paragraph", "number", "header-alignment", "ambiguous"])
def test_format_check_rejects_lost_or_rewritten_text_and_geometry(change):
    expected = fixture()
    actual = copy.deepcopy(expected)
    assert all(formats.compare_snapshot(actual, expected).values())
    if change == "paragraph":
        actual["blocks"][0]["text"] = "An exact claim with p=0.05."
    elif change == "number":
        actual["tables"][0]["cells"][0]["text"] = "20"
    elif change == "header-alignment":
        actual["tables"][0]["cells"][0]["column"] = 2
    else:
        actual["tables"][0]["ambiguous"] = True
    assert not all(formats.compare_snapshot(actual, expected).values())


def test_format_check_allows_line_wrapping_not_numeric_correction():
    expected = fixture()
    actual = copy.deepcopy(expected)
    actual["blocks"][0]["text"] = "An exact claim\nwith p<0.05."
    assert all(formats.compare_snapshot(actual, expected).values())
    assert actual["tables"][0]["cells"][0]["text"] == "35"


def test_format_check_cannot_read_an_arbitrary_or_symlinked_source(tmp_path):
    with pytest.raises(formats.ReviewError, match="missing/nonregular"):
        formats.inspect(tmp_path)
    (tmp_path / "f00.md").symlink_to(formats.SOURCE)
    with pytest.raises(formats.ReviewError, match="missing/nonregular"):
        formats.inspect(tmp_path)


def test_format_check_rejects_reordered_body_even_when_all_paragraphs_exist():
    expected = fixture()
    expected["blocks"].append({"kind": "paragraph", "text": "Second exact paragraph."})
    actual = copy.deepcopy(expected)
    actual["blocks"].reverse()
    checks = formats.compare_snapshot(actual, expected)
    assert checks["all_expected_paragraphs_present"]
    assert not checks["expected_paragraphs_in_order"]


def test_format_check_accepts_only_two_fixed_synthetic_sources(tmp_path):
    assert set(formats.SOURCES) == {"case02", "r17"}
    assert formats.SOURCES["r17"].is_file()
    with pytest.raises(formats.ReviewError, match="allowlisted"):
        formats.inspect(tmp_path, str(tmp_path / "private.md"))


def test_pdf_comparison_joins_only_layout_after_a_retained_hyphen_without_rewriting_snapshot():
    expected = fixture()
    expected["blocks"][0]["text"] = "The follow-up uses p<0.05."
    actual = copy.deepcopy(expected)
    actual["format"] = "pdf"
    actual["blocks"][0].update(
        text="The follow- up uses p<0.05.", extracted_text="The follow-\nup uses p<0.05.",
    )
    before = copy.deepcopy(actual)
    assert all(formats.compare_snapshot(actual, expected).values())
    assert not formats.compare_snapshot(actual, expected, pdf_layout=False)[
        "all_expected_paragraphs_present"
    ]
    assert actual == before


@pytest.mark.parametrize(
    "actual,expected",
    [
        ("follow- up", "follow-up"),  # ordinary space is not a verified line wrap
        ("follow\nup", "follow-up"),  # never invent a missing printed hyphen
        ("range 1-\n2", "range 1-2"),
        ("p=0.\n05", "p=0.05"),
        ("IL-\n6", "IL-6"),
        ("code 2-\narm", "code 2-arm"),
        ("folow-\nup", "follow-up"),  # no spelling correction
    ],
)
def test_pdf_fixture_comparison_refuses_numeric_punctuation_or_word_repairs(actual, expected):
    assert formats.pdf_layout_text(actual) != expected
