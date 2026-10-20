import json
from pathlib import Path

import pytest

from closed_review import findings
from closed_review.sidecar import Sidecar, handle

PAPER = (
    "# Methods\n\nOf 1,486 records, 283 were duplicates and 1,203 were screened.\n\n"
    "# Results\n\nThe absolute risk reduction was 6.5 points, a number needed to treat of 9.\n\n"
    "We screened 1,203 records.\n\nAll 1,203 records were coded.\n\n"
    "# Discussion\n\nThe intervention reduces mortality.\n"
)
SESSION = "0123456789abcdef0123456789abcdef"


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


def test_sidecar_protocol_lookup_and_export(isolated_env: Path, monkeypatch) -> None:
    paper = isolated_env / "paper.md"
    paper.write_text(PAPER)
    sidecar = Sidecar()
    opened = handle(
        sidecar, json.dumps({"id": 1, "method": "open", "params": {"path": str(paper)}})
    )
    doc_id = opened["result"]["doc_id"]
    quoted = handle(
        sidecar,
        json.dumps(
            {
                "id": 2,
                "method": "check_quotes",
                "params": {"doc_id": doc_id, "quotes": ["reduces mortality"]},
            }
        ),
    )
    assert quoted["result"]["verified"][0]["quote"] == "reduces mortality"
    assert "error" in handle(
        sidecar,
        json.dumps({"id": 3, "method": "check_quotes", "params": {"doc_id": "nope", "quotes": []}}),
    )

    class Reply:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"message": {"items": [{"DOI": "10.1/x", "title": ["Example"]}]}}

    monkeypatch.setattr("closed_review.sidecar.httpx.get", lambda *a, **k: Reply())
    with pytest.raises(Exception, match="approval"):
        sidecar.lookup(SESSION, "crossref", "Braun Clarke 2006", "")
    shown = sidecar.lookup_url("crossref", "Braun Clarke 2006")
    record = sidecar.lookup(SESSION, "crossref", "Braun Clarke 2006", "2026-10-19T00:00:00+00:00")
    assert record["url"] == shown["url"]
    assert record["result"][0]["doi"] == "10.1/x" and record["url"].startswith(
        "https://api.crossref"
    )

    exported = sidecar.export(
        SESSION,
        {"authors": "Define the sample.", "development": "R1 accepted."},
        ["qwen3.8-flash-next", "gemma-4-31b"],
        "http://127.0.0.1:8091/v1",
    )
    receipt = json.loads(Path(exported["receipt_path"]).read_text())
    assert receipt["environment"]["host"] == "pi"
    assert receipt["environment"]["model"] == "qwen3.8-flash-next, gemma-4-31b"
    assert {s["role"] for s in receipt["subjects"]} == {"authors", "development"}
    with pytest.raises(Exception, match="authors"):
        sidecar.export(SESSION, {"editor": "x"}, ["m"], "u")


def test_sidecar_serves_the_review_knowledge() -> None:
    known = Sidecar().knowledge(["qualitative", "normative-argument"])
    assert {a["id"] for a in known["available"]} >= {
        "qualitative",
        "quantitative",
        "legal-analysis",
    }
    assert "Candidate presentation" in known["contract"]
    assert "Major flaws in any design" in known["rubric"]
    assert [p["id"] for p in known["profiles"]] == ["qualitative", "normative-argument"]
    profile = known["profiles"][0]
    assert profile["monitoring_areas"] and profile["false_alarms"] and profile["major_flaws"]
    assert "Monitoring areas" in profile["text"]
    with pytest.raises(Exception, match="unknown design profile"):
        Sidecar().knowledge(["ethnography"])


def test_sidecar_drafts_a_plan_from_headings(tmp_path: Path) -> None:
    paper = tmp_path / "paper.md"
    paper.write_text(PAPER)
    sidecar = Sidecar()
    doc_id = sidecar.open(str(paper))["doc_id"]
    titles = [s["title"] for s in sidecar.plan(doc_id)["segments"]]
    assert titles == ["Methods", "Results", "Discussion"]
