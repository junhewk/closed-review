from pathlib import Path

import pytest

from closed_review import findings

PAPER = (
    "# Methods\n\nOf 1,486 records, 283 were duplicates and 1,203 were screened.\n\n"
    "# Results\n\nThe absolute risk reduction was 6.5 points, a number needed to treat of 9.\n\n"
    "We screened 1,203 records.\n\nAll 1,203 records were coded.\n\n"
    "# Discussion\n\nThe intervention reduces mortality.\n"
)


@pytest.fixture
def document(tmp_path: Path) -> dict:
    path = tmp_path / "paper.md"
    path.write_text(PAPER)
    return findings.open_document(path)


def test_quotes_must_be_verbatim_and_locators_are_found(document) -> None:
    checked = findings.check_quotes(
        document,
        [
            "a number needed to treat of 9",
            {"quote": "reduces mortality", "locator": "wrong"},
            "x y z",
        ],
    )
    assert [q["quote"] for q in checked["verified"]] == [
        "a number needed to treat of 9",
        "reduces mortality",
    ]
    assert checked["verified"][1]["locator"] != "wrong"
    assert len(checked["problems"]) == 1 and "not verbatim" in checked["problems"][0]


def test_arithmetic_is_computed_and_a_reused_figure_recurs(document) -> None:
    result = findings.number_checks(
        document,
        [
            {"expression": "1486 - 283", "stated": "1,203", "quote": "1,203 were screened"},
            {"expression": "100 / 6.5", "stated": "9", "quote": "a number needed to treat of 9"},
        ],
    )
    first, second = result["checks"]
    scaled = findings.number_checks(
        document, [{"expression": "1203 / 1486", "stated": "81.0", "quote": "1,203 were screened"}]
    )["checks"][0]
    assert scaled["matches"] and scaled["scale"] == "percent"
    check = {"expression": "120.3 * 1000", "stated": "1,203", "quote": "1,203 were screened"}
    hundredfold = findings.number_checks(document, [check])["checks"][0]
    assert not hundredfold["matches"]
    assert first["matches"] and not first["recurs"]
    assert not second["matches"] and second["identity"] == [9.0, 15.38]
    assert not second["recurs"]  # 9 appears once
    # A mismatched figure that the manuscript reuses is load-bearing.
    assert findings.recurring_figure(document, "1,203")


def test_a_figure_written_in_words_is_read_as_digits(document) -> None:
    checked = findings.number_checks(
        document,
        [
            {
                "expression": "1486 - 283",
                "stated": "One thousand two hundred and three",
                "quote": "1,203 were screened",
            }
        ],
    )
    assert checked["problems"] == [] and checked["checks"][0]["matches"]
    assert checked["checks"][0]["stated"] == "1203"


def test_a_count_out_of_a_total_is_explained_not_parsed(document) -> None:
    refused = findings.number_checks(
        document,
        [
            {
                "expression": "1203 / 1486 * 100",
                "stated": "1,203 of 1,486",
                "quote": "1,203 were screened",
            }
        ],
    )
    assert refused["checks"] == []
    assert "is a count out of a total" in refused["problems"][0]


def test_severity_follows_the_evidence() -> None:
    confirmed = {
        "flaw_checks": [
            {
                "flaw": "quantitative/immortal-time",
                "model": "qwen",
                "shown": True,
                "quotes_verified": True,
            },
            {
                "flaw": "quantitative/immortal-time",
                "model": "gemma",
                "shown": True,
                "quotes_verified": True,
            },
        ]
    }
    assert findings.severity(confirmed) == {
        "severity": "major",
        "basis": "evidence",
        "reasons": ["listed major flaw quantitative/immortal-time, confirmed by gemma, qwen"],
    }
    # A check whose quotes were not verbatim confirms nothing.
    unverified = {
        "flaw_checks": [{"flaw": "f", "model": "qwen", "shown": True, "quotes_verified": False}]
    }
    assert findings.severity(unverified)["severity"] == "minor"
    assert findings.severity({"model_severity": "major"})["basis"] == "judgement"
    recurring = {"number_check": {"matches": False, "recurs": True, "stated": "1,203"}}
    assert findings.severity(recurring)["severity"] == "major"
    once = {"model_severity": "major", "number_check": {"matches": False, "recurs": False}}
    assert findings.severity(once)["severity"] == "minor"


@pytest.mark.parametrize("flaw", ["general/misread-source", "legal-analysis/misread-provision"])
def test_source_misreading_is_not_confirmed_by_a_claim_quote_alone(flaw) -> None:
    old_check = {"flaw": flaw, "shown": True, "quotes_verified": True}
    finding = {"model_severity": "minor", "flaw_checks": [old_check]}
    assert findings.severity(finding)["basis"] == "judgement"
    assert not findings.confirmed_check(old_check)

    qualified = {
        **old_check,
        "source_quote": {"quote": "the source's reported words", "locator": "heading:Source"},
    }
    assert findings.confirmed_check(qualified)
    assert findings.severity({**finding, "flaw_checks": [qualified]})["basis"] == "evidence"


def test_one_mismatch_written_two_ways_is_one_group() -> None:
    check = lambda e, c: {"number_check": {"expression": e, "stated": "9", "computed": c}}  # noqa: E731
    groups = findings.merge_number_checks(
        [
            {"id": "a", **check("100 / 6.5", 15.384615)},
            {"id": "b", **check("1 / 0.065", 15.384615)},
            {"id": "c", "model_severity": "minor"},
        ]
    )
    assert groups == [["a", "b"]]


def test_order_puts_evidence_first_and_holds_a_reserve() -> None:
    flaw = {"flaw_checks": [{"flaw": "f", "model": "m", "shown": True, "quotes_verified": True}]}
    items = [
        {"id": "judged", "segment_id": "s1", "model_severity": "major"},
        {"id": "evidence", "segment_id": "s2", **flaw},
        {"id": "computed", "segment_id": "s3", "number_check": {"matches": False, "recurs": False}},
    ] + [{"id": f"m{i}", "segment_id": "s1", "model_severity": "minor"} for i in range(10)]
    ordered = findings.order(items, ["s1", "s2", "s3"])
    ids = [o["id"] for o in ordered["order"]]
    assert ids[:3] == ["evidence", "judged", "computed"]
    assert len(ordered["order"]) == 2 + 9 and len(ordered["reserve"]) == 2
