import json
from pathlib import Path

import pytest
import yaml
from conftest import reviewer_says

from closed_review import cli, hermes, scan
from closed_review.errors import ReviewError
from closed_review.lookups import show_lookup
from closed_review.parsers import parse_document
from closed_review.segments import draft_plan, validate_plan
from closed_review.session import start_session

PAPER = (
    "# Fictional consent study\n\n"
    "Abstract text that summarizes a fictional interview study.\n\n"
    "# Introduction\n\n" + "Background on consent practices in fictional wards. " * 40 + "\n\n"
    "# Methods\n\n" + "We interviewed twelve nurses recruited by their ward manager. " * 30 + "\n\n"
    "## 2.1 Analysis\n\nThemes emerged from the data.\n\n"
    "# Results\n\n" + "Most participants described consent as a formality. " * 35 + "\n\n"
    "# References\n\nOkonkwo, M. (1998). Fictional household survey.\n"
)


@pytest.fixture
def session(isolated_env, monkeypatch):
    home = isolated_env / "hermes"
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "model": {"default": "qwen3.8-flash-next", "provider": "local"},
                "providers": {"local": {"base_url": "http://127.0.0.1:8091/v1"}},
                "tools": {"enabled_toolsets": ["terminal", "file"]},
            }
        )
    )
    hermes.install_skill(None, apply=True)
    monkeypatch.setenv("HERMES_SESSION_ID", "session-under-test")
    opening = (
        "/journal-article-review deep\n\nThe journal permits local AI assistance; I confirm that."
    )
    reviewer_says(home, "session-under-test", opening)
    start_session(None, live=False)  # the preflight runs after the opening message
    reviewer_says(home, "session-under-test", "Yes, qualitative only.")
    paper = isolated_env / "paper.md"
    paper.write_text(PAPER)
    return paper


SUMMARY = {
    "summary": "An interview study of how nurses understand consent.",
    "analysis": "Semi-structured interviews with ward nurses, analysed thematically.",
    "considerations": [
        {
            "kind": "context",
            "consideration": "The authors place the study in fictional wards.",
            "quote": "consent practices in fictional wards",
        }
    ],
    "main_conclusions": ["described consent as a formality"],
}
RECRUITMENT = {
    "title": "Recruitment through ward managers",
    "issue": "Recruitment through ward managers may filter which views are heard.",
    "why": (
        "Gatekeeper recruitment shapes whose experiences appear, as Okonkwo (1998) found and "
        "Strech and Sofaer (2012) warn."
    ),
    "solutions": ["Describe recruitment and who declined."],
    "type": "method",
    "severity": "major",
    "flaw": "qualitative/unexamined-power",
    "target": "recruited by their ward manager",
    "quotes": ["recruited by their ward manager"],
}
THEMES = {
    "title": "Analysis described in one sentence",
    "issue": "The analysis says only that themes emerged.",
    "why": "Readers cannot judge how the themes were built.",
    "solutions": ["Describe the coding and theme development."],
    "type": "reporting",
    "severity": "major",
    "flaw": "general/self-contradiction",
    "target": "Themes emerged from the data.",
    "quotes": ["Themes emerged from the data."],
}


def start(paper: Path) -> dict:
    return scan.start_scan(paper, profiles=["qualitative"], confirmation="Yes, qualitative only.")


def say(paper: Path, text: str) -> None:
    reviewer_says(paper.parent / "hermes", "session-under-test", text)


def answer(scan_id: str, task: dict, **fields) -> dict:
    """Write the answer to `task` at its answer_path and submit it."""
    path = Path(task["answer_path"])
    path.write_text(json.dumps(task["answer_template"] | fields))
    return scan.submit_task(scan_id, path)


def units(started: dict) -> list[dict]:
    """One unit per section the plan has (the short reference list joined the Results)."""
    ids = {s["title"]: s["id"] for s in started["segments"]}
    return [
        {"role": "introduction", "parts": [[ids["Introduction"]]]},
        {"role": "methods", "parts": [[ids["Methods"]]]},
        {"role": "results", "parts": [[ids["Results"]]]},
    ]


def oriented(paper: Path) -> tuple[str, dict]:
    started = start(paper)
    task = scan.next_task(started["scan_id"])
    done = answer(started["scan_id"], task, **SUMMARY, units=units(started))
    return started["scan_id"], done["next_task"]


def stored(scan_id: str) -> dict:
    return json.loads((scan._scan_root(scan_id) / "scan.json").read_text())


def test_draft_plan_follows_headings_and_folds_short_subsections(isolated_env) -> None:
    paper = isolated_env / "paper.md"
    paper.write_text(PAPER)
    blocks = parse_document(paper).segments
    plan = draft_plan([{"source_id": "manuscript", "segments": blocks}])
    titles = [s["title"] for s in plan["segments"]]
    assert titles == ["Fictional consent study", "Introduction", "Methods", "Results", "References"]
    assert {s["title"]: s["tier"] for s in plan["segments"]}["Methods"] == "high"
    assert {s["title"]: s["tier"] for s in plan["segments"]}["Introduction"] == "light"
    validated = validate_plan(plan, [{"source_id": "manuscript", "segments": blocks}])
    covered = {b for s in validated["segments"] for b in s["block_ids"]}
    assert covered == {b["segment_id"] for b in blocks}


def test_pdf_style_blocks_recognize_section_names() -> None:
    blocks = [
        {
            "segment_id": f"seg-{i:05d}",
            "locator": f"page:1/block:{i}",
            "kind": "page_block",
            "text": text,
        }
        for i, text in enumerate(
            [
                "A fictional title",
                "Keywords: consent, wards",
                "Introduction",
                "Long intro. " * 200,
                "Keywords: not a heading here either",
                "2. Methods",
                "1. We asked participants to describe their experience of consent.",
                "Method text. " * 200,
                "Narrative construction and genres",
                "Body text. " * 50,
                "References 1. Okonkwo M. Fictional survey. 1998.",
                "2. Halvorsen C. Fictional routines",
            ],
            start=1,
        )
    ]
    titles = [
        s["title"]
        for s in draft_plan([{"source_id": "manuscript", "segments": blocks}])["segments"]
    ]
    assert titles == [
        "Opening",
        "Introduction",
        "2. Methods",
        "Narrative construction and genres",
        "References",
    ]


def test_scan_requires_a_passing_preflight(isolated_env, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_SESSION_ID", "never-checked")
    paper = isolated_env / "paper.md"
    paper.write_text(PAPER)
    with pytest.raises(ReviewError, match="creview session start"):
        start(paper)


def test_deep_scan_end_to_end(session) -> None:
    with pytest.raises(ReviewError, match="unknown design profile"):
        scan.start_scan(session, profiles=["ethnography"], confirmation="Yes, that one.")
    with pytest.raises(ReviewError, match="reviewer's own words"):
        scan.start_scan(session, profiles=["qualitative"], confirmation="")
    # A confirmation the reviewer never wrote is refused, however it is worded.
    with pytest.raises(ReviewError, match="not in any of those messages"):
        scan.start_scan(
            session,
            profiles=["qualitative"],
            confirmation="Prompt unanswered; proceeding with the indexed profiles.",
        )
    with pytest.raises(ReviewError, match="not in any of those messages"):
        scan.start_scan(session, profiles=["qualitative"], confirmation="/journal-article-review")
    # The opening message's policy confirmation is not a profile confirmation.
    with pytest.raises(ReviewError, match="sent after it was asked"):
        scan.start_scan(session, profiles=["qualitative"], confirmation="I confirm that")
    started = start(session)
    scan_id = started["scan_id"]
    # Heading-only fragments join the section after them.
    assert [s["title"] for s in started["segments"]] == [
        "Introduction",
        "Methods",
        "Results",
    ]

    # Orientation: the initial summary and the reading units; the profiles are already confirmed.
    task = scan.next_task(scan_id)
    assert task["task"] == {"id": "orient-1", "stage": "orient", "number": 1, "of": 1}
    assert "design profiles that fit" not in task["instructions"]
    assert "a JSON object written at answer_path" in task["instructions"]
    assert set(task["answer_template"]) == {"task_id", *scan.pipeline.ANSWER_FIELDS["orient"]}
    with pytest.raises(ReviewError, match="reading units besides the Abstract"):
        answer(scan_id, task, **SUMMARY, units=units(started)[:2])
    read = answer(scan_id, task, **SUMMARY, units=units(started))["next_task"]

    # One read per part, in order; each sees the concerns found before it.
    assert read["task"]["id"] == "read-1" and read["task"]["of"] == 3
    assert "Concerns found so far:\n(none yet)" in read["instructions"]
    assert any("kappa" in alarm for alarm in read["false_alarms"].values())
    read = answer(scan_id, read, concerns=[])["next_task"]
    assert read["part"].startswith("methods")
    assert any(block["text"].startswith("We interviewed") for block in read["content"])
    read = answer(
        scan_id,
        read,
        concerns=[RECRUITMENT],
        flaws_to_check=["qualitative/unexamined-power"],
    )["next_task"]
    assert "F1 (methods): Recruitment through ward managers" in read["instructions"]
    link = {
        "link": "F1",
        "role": "relies-on",
        "note": "The results rest on the recruited sample.",
        "quotes": ["described consent as a formality"],
    }
    check = answer(scan_id, read, concerns=[link, THEMES])["next_task"]

    # Each flagged flaw is checked once, against the concerns found.
    assert check["task"]["id"] == "check-1"
    assert "Flaw qualitative/unexamined-power" in check["instructions"]
    sweep = answer(
        scan_id,
        check,
        shown=True,
        quotes=["recruited by their ward manager"],
        reason="The manager recruited the participants.",
        concern="F1",
    )["next_task"]
    assert (scan._scan_root(scan_id) / "presweep.json").is_file()

    # The sweep places every finding once.
    assert sweep["task"]["stage"] == "sweep"
    with pytest.raises(ReviewError, match="not placed: F2"):
        answer(
            scan_id,
            sweep,
            concerns=[
                {
                    "concern": "Recruitment",
                    "target": "recruited by their ward manager",
                    "items": ["F1"],
                    "severity": "major",
                }
            ],
        )
    confirm = answer(
        scan_id,
        sweep,
        concerns=[
            {
                "concern": "Recruitment through ward managers may filter which views are heard.",
                "target": "recruited by their ward manager",
                "items": ["F1"],
                "severity": "major",
                "flaw": "qualitative/unexamined-power",
            },
            {
                "concern": "The analysis is described in one sentence.",
                "target": "Themes emerged from the data.",
                "items": ["F2"],
                "severity": "major",
                "flaw": "general/self-contradiction",
            },
        ],
    )["next_task"]

    # A major on judgement tagged with a listed flaw is asked that flaw's question again.
    assert confirm["task"]["id"] == "confirm-1"
    assert "Concern F2" in confirm["instructions"]
    screen = answer(scan_id, confirm, shown=False, reason="No two statements conflict.")
    screen = screen["next_task"]
    assert stored(scan_id)["review"]["findings"][1]["model_severity"] == "minor"

    # Screening asks about the concerns no check confirmed.
    assert screen["task"]["stage"] == "screen" and "F2:" in screen["instructions"]
    done = answer(scan_id, screen, answers=[{"id": "F2", "false_alarm": "none"}])
    assert done["state"] == "ready" and done["next"] == f"creview scan candidate {scan_id}"
    status = scan.scan_status(scan_id)
    assert status["phase"] == "ready" and "findings" not in status

    first = scan.next_candidate(scan_id)
    assert first["overview"]["considerations"][0]["quote"]["quote"] == (
        "consent practices in fictional wards"
    )
    (presented,) = first["candidates"]
    assert presented["id"] == "F1" and presented["severity"] == "major"
    assert presented["basis"] == "evidence"
    assert presented["severity_basis"] == [
        "listed major flaw qualitative/unexamined-power, confirmed by qwen3.8-flash-next"
    ]
    assert presented["later_units"][0]["role"] == "relies-on"
    assert "strongest reply the authors could make" in first["instructions"]
    labels = {item["citation"]: item["label"] for item in presented["literature"]}
    assert labels == {"Okonkwo 1998": "manuscript_reported", "Strech 2012": "model_lead"}
    # creview prepares the lookups, unverified recollections first; nothing runs unapproved.
    assert [item["citation"] for item in presented["lookups"]] == ["Strech 2012", "Okonkwo 1998"]
    pending = show_lookup(None, presented["lookups"][0]["request_id"])
    assert pending["status"] == "pending_approval"
    assert first["next_severity"] == "minor"

    with pytest.raises(ReviewError, match="record the reviewer's response to F1 first"):
        scan.next_candidate(scan_id)
    with pytest.raises(ReviewError, match="sent after it was asked|not in any"):
        scan.record_response(scan_id, "F1", "accepted", "Accept that one.")
    say(session, "Accept that one.")
    recorded = scan.record_response(scan_id, "F1", "accepted", "Accept that one.")
    assert recorded["records"]["accepted"] == 1
    (minor,) = scan.next_candidate(scan_id)["candidates"]
    assert minor["id"] == "F2" and minor["severity"] == "minor"
    assert scan.scan_status(scan_id)["surfaced"] == 2

    assert scan.purge_scan(scan_id, scan_id)["lookups_removed"] == 2
    with pytest.raises(ReviewError, match="does not exist"):
        scan.scan_status(scan_id)


def test_scan_refuses_answers_it_cannot_check_and_changed_files(session) -> None:
    scan_id, read = oriented(session)
    path = Path(read["answer_path"])
    path.write_text(json.dumps({"task_id": "read-2", "concerns": []}))
    with pytest.raises(ReviewError, match="not for the current task \\(read-1\\)"):
        scan.submit_task(scan_id, path)
    unquoted = RECRUITMENT | {"quotes": ["words the manuscript never says"], "type": ""}
    with pytest.raises(ReviewError, match="answer refused") as refused:
        answer(scan_id, read, concerns=[unquoted])
    assert "not verbatim" in str(refused.value)
    assert "needs title, issue, why, type, severity, and target" in str(refused.value)
    assert stored(scan_id)["phase"] == "read" and stored(scan_id)["step"] == 0

    session.write_text(PAPER + "\nAn added sentence.\n")
    with pytest.raises(ReviewError, match="changed since the scan started"):
        scan.next_task(scan_id)


def test_the_scan_goes_on_without_a_sweep_it_cannot_check(session) -> None:
    scan_id, task = oriented(session)
    task = answer(scan_id, task, concerns=[])["next_task"]
    task = answer(scan_id, task, concerns=[RECRUITMENT | {"flaw": "none"}])["next_task"]
    sweep = answer(scan_id, task, concerns=[])["next_task"]
    for _ in range(scan.MAX_SWEEP_REFUSALS - 1):
        with pytest.raises(ReviewError, match="not placed: F1"):
            answer(scan_id, sweep, concerns=[])
    done = answer(scan_id, sweep, concerns=[])
    assert "refused too often" in done["recorded"]
    # F1 is major on judgement with no listed flaw: kept as the read rated it.
    assert done["next_task"]["task"]["stage"] == "screen"


def test_the_earlier_deep_scan_says_what_replaced_it(session, capsys) -> None:
    for command in ("plan", "overview", "synthesize", "sweep"):
        assert cli.main(["scan", command, "scan-x", "plan.json", "--confirmation", "ok"]) == 2
        assert "no longer part of the deep scan" in capsys.readouterr().err
    scan_id, _ = oriented(session)
    path = scan._scan_root(scan_id) / "scan.json"
    path.write_text(json.dumps(stored(scan_id) | {"schema_version": "1"}))
    with pytest.raises(ReviewError, match="earlier closed-review"):
        scan.next_task(scan_id)


def test_the_scan_warns_about_the_turn_budget(session) -> None:
    config_path = session.parent / "hermes" / "config.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["agent"] = {"max_turns": 10}
    config_path.write_text(yaml.safe_dump(config))
    started = start(session)
    task = scan.next_task(started["scan_id"])
    done = answer(started["scan_id"], task, **SUMMARY, units=units(started))
    assert any("agent.max_turns (10)" in warning for warning in done["warnings"])
    # Once: the next submission does not repeat it.
    assert "warnings" not in answer(started["scan_id"], done["next_task"], concerns=[])
