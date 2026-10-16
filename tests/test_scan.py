import json
from pathlib import Path

import pytest
import yaml

from closed_review import hermes, scan
from closed_review.errors import ReviewError
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
    start_session(None, live=False)
    paper = isolated_env / "paper.md"
    paper.write_text(PAPER)
    return paper


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


def run_passes(scan_id: str, quote: str, locator: str) -> int:
    passes = 0
    while True:
        task = scan.next_task(scan_id)
        if "task" not in task:
            return passes
        passes += 1
        proposal_path = Path(task["proposal_path"])
        proposal = json.loads(proposal_path.read_text())
        if task["task"]["pass"] == 1:
            proposal["summary"] = f"The {task['segment']['title']} segment, summarized."
        if task["segment"]["title"] == "Methods":
            proposal["candidates"] = [
                {
                    "potential_issue": "Recruitment through ward managers may filter views.",
                    "why_it_matters": "Gatekeeper recruitment shapes whose experiences appear.",
                    "severity": "major",
                    "profile_area": "Sampling and information power",
                    "evidence": [{"source_id": "manuscript", "locator": locator, "quote": quote}],
                    "solution_candidates": ["Describe recruitment and who declined."],
                }
            ]
        proposal_path.write_text(json.dumps(proposal))
        scan.submit_task(scan_id, proposal_path)


def test_deep_scan_end_to_end(session) -> None:
    started = scan.start_scan(session)
    scan_id = started["scan_id"]
    with pytest.raises(ReviewError, match="set the segment plan first"):
        scan.next_task(scan_id)
    planned = scan.set_plan(scan_id, Path(started["plan_draft_path"]))
    tiers = {s["title"]: s["tier"] for s in planned["segments"]}
    expected = sum({"light": 1, "medium": 2, "high": 3}[t] for t in tiers.values())
    assert planned["passes"] == expected

    methods = next(
        b for b in parse_document(session).segments if b["text"].startswith("We interviewed")
    )
    passes = run_passes(scan_id, "recruited by their ward manager", methods["locator"])
    assert passes == expected

    status = scan.scan_status(scan_id)
    assert status["phase"] == "synthesis"
    assert "pool" not in status and "candidates" not in status

    merged = scan.synthesize(scan_id)
    assert len(merged["pool"]) == 1  # three Methods passes quoting one passage merge
    assert len(merged["pool"][0]["members"]) == 3
    screening = Path(merged["screening_path"])
    entries = json.loads(screening.read_text())
    entries[0] |= {"decision": "keep", "author_reply": "The ward manager only passed on letters."}
    entries[0]["survives"] = "Who declined is still not reported."
    screening.write_text(json.dumps(entries))
    with pytest.raises(ReviewError, match="without affected_conclusion"):
        scan.screen(scan_id, screening)
    entries[0]["affected_conclusion"] = "That consent is experienced as a formality."
    screening.write_text(json.dumps(entries))
    screened = scan.screen(scan_id, screening)
    assert {s["title"] for s in screened["segment_summaries"]} == set(tiers)
    with pytest.raises(ReviewError, match="creview scan overview"):
        scan.next_candidate(scan_id)
    overview_path = Path(screened["overview_path"])
    with pytest.raises(ReviewError, match="needs analysis"):
        overview_path.write_text(json.dumps({"summary": "An interview study."}))
        scan.set_overview(scan_id, overview_path)
    overview = {
        "summary": "An interview study of how nurses understand consent.",
        "analysis": "Semi-structured interviews analysed thematically.",
        "considerations": ["How does this extend earlier consent studies?"],
    }
    overview_path.write_text(json.dumps(overview))
    scan.set_overview(scan_id, overview_path)

    first = scan.next_candidate(scan_id)
    assert first["overview"] == overview
    assert first["candidate"]["severity"] == "major"
    assert first["candidate"]["segments"][0]["title"] == "Methods"
    assert first["candidate"]["author_reply"] == "The ward manager only passed on letters."
    assert first["context"] == [
        {
            "id": first["candidate"]["segments"][0]["id"],
            "title": "Methods",
            "summary": "The Methods segment, summarized.",
        }
    ]
    assert first["more_available"] is False
    last = scan.next_candidate(scan_id)
    assert last["candidate"] is None and "overview" not in last
    with pytest.raises(ReviewError, match="already presented"):
        scan.set_overview(scan_id, overview_path)
    assert scan.scan_status(scan_id)["surfaced"] == 1

    scan.purge_scan(scan_id, scan_id)
    with pytest.raises(ReviewError, match="does not exist"):
        scan.scan_status(scan_id)


def test_scan_refuses_unverbatim_quotes_and_changed_files(session) -> None:
    started = scan.start_scan(session)
    scan_id = started["scan_id"]
    scan.set_plan(scan_id, Path(started["plan_draft_path"]))
    task = scan.next_task(scan_id)
    proposal_path = Path(task["proposal_path"])
    proposal = json.loads(proposal_path.read_text())
    proposal["candidates"] = [
        {
            "potential_issue": "Invented concern.",
            "why_it_matters": "It quotes text that is not there.",
            "severity": "minor",
            "evidence": [
                {
                    "source_id": "manuscript",
                    "locator": task["content"][0]["locator"],
                    "quote": "words the manuscript never says",
                }
            ],
        }
    ]
    proposal_path.write_text(json.dumps(proposal))
    with pytest.raises(ReviewError, match="not verbatim") as refused:
        scan.submit_task(scan_id, proposal_path)
    assert "needs summary" in str(refused.value)

    session.write_text(PAPER + "\nAn added sentence.\n")
    with pytest.raises(ReviewError, match="changed since the scan started"):
        scan.next_task(scan_id)


def test_scan_requires_a_passing_preflight(isolated_env, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_SESSION_ID", "never-checked")
    paper = isolated_env / "paper.md"
    paper.write_text(PAPER)
    with pytest.raises(ReviewError, match="creview session start"):
        scan.start_scan(paper)


def test_screening_merges_the_same_concern_raised_elsewhere(session) -> None:
    started = scan.start_scan(session)
    scan_id = started["scan_id"]
    scan.set_plan(scan_id, Path(started["plan_draft_path"]))
    blocks = parse_document(session).segments
    methods = next(b for b in blocks if b["text"].startswith("We interviewed"))
    results = next(b for b in blocks if b["text"].startswith("Most participants"))
    quotes = {
        "Methods": (methods, "recruited by their ward manager", "major"),
        "Results": (results, "described consent as a formality", "minor"),
    }
    while "task" in (task := scan.next_task(scan_id)):
        path = Path(task["proposal_path"])
        proposal = json.loads(path.read_text())
        found = quotes.get(task["segment"]["title"])
        if task["task"]["pass"] == 1:
            proposal["summary"] = "What the segment says."
        if found and task["task"]["pass"] == 1:
            block, quote, severity = found
            proposal["candidates"] = [
                {
                    "potential_issue": "Gatekeeper recruitment shapes the findings.",
                    "why_it_matters": "Whose views appear depends on the manager.",
                    "severity": severity,
                    "evidence": [
                        {"source_id": "manuscript", "locator": block["locator"], "quote": quote}
                    ],
                }
            ]
        path.write_text(json.dumps(proposal))
        scan.submit_task(scan_id, path)
    pool = scan.synthesize(scan_id)["pool"]
    assert len(pool) == 2
    entries = [
        {
            "id": pool[0]["id"],
            "decision": "keep",
            "severity": "minor",
            "author_reply": "Recruitment is described.",
            "survives": "Its effect on the findings is not discussed.",
        },
        {"id": pool[1]["id"], "decision": "merge", "into": pool[0]["id"]},
    ]
    path = session.parent / "screening.json"
    path.write_text(json.dumps(entries))
    with pytest.raises(ReviewError, match="not kept"):
        bad = [entries[0] | {"decision": "drop", "reason": "x"}, entries[1]]
        path.write_text(json.dumps(bad))
        scan.screen(scan_id, path)
    path.write_text(json.dumps(entries))
    overview_path = Path(scan.screen(scan_id, path)["overview_path"])
    overview_path.write_text(json.dumps({"summary": "S.", "analysis": "A."}))
    scan.set_overview(scan_id, overview_path)

    candidate = scan.next_candidate(scan_id)["candidate"]
    assert [s["title"] for s in candidate["segments"]] == ["Methods", "Results"]
    assert len(candidate["evidence"]) == 2
    assert scan.next_candidate(scan_id)["candidate"] is None
