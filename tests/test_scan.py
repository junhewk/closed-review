import json
import re
from pathlib import Path

import pytest
import yaml
from conftest import reviewer_says

from closed_review import hermes, scan
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
    "main_conclusions": [{"quote": "described consent as a formality"}],
}


def start(paper: Path) -> dict:
    return scan.start_scan(paper, profiles=["qualitative"], confirmation="Yes, qualitative only.")


def confirm_plan(started: dict, plan_path: Path, words: str = "The tiers look right.") -> dict:
    """Propose the plan, have the reviewer answer, and store it with their words."""
    scan.set_plan(started["scan_id"], plan_path)
    paper = Path(started["sources"][0]["path"])
    reviewer_says(paper.parent / "hermes", "session-under-test", words)
    return scan.set_plan(started["scan_id"], plan_path, words)


def plan_and_summarize(started: dict) -> dict:
    """Store the draft plan and the initial summary, which come before any pass."""
    planned = confirm_plan(started, Path(started["plan_draft_path"]))
    path = Path(planned["overview_path"])
    path.write_text(json.dumps(SUMMARY))
    scan.set_overview(started["scan_id"], path)
    return planned


def candidate(quote: str, issue: str = "Gatekeepers filter views.", **fields) -> dict:
    key = fields.pop("key", None) or re.sub(r"[^a-z0-9]+", "-", issue.lower()).strip("-")
    return {
        "potential_issue": issue,
        "why_it_matters": "It shapes whose experiences appear.",
        "severity": "minor",
        "type": "method",
        "evidence": [{"quote": quote}],
        "concern_key": key,
        "concern_label": issue,
        "major_flaw": "none",
    } | fields


def say(paper: Path, text: str) -> None:
    reviewer_says(paper.parent / "hermes", "session-under-test", text)


def answer_sweep(
    scan_id: str,
    request: dict,
    *,
    drops: list | None = None,
    concerns: list | None = None,
    merges: list | None = None,
    found: dict | None = None,
) -> dict:
    """Write the sweep: `drops`, `concerns` (by default each preliminary major on its own), and
    `merges` as given, `found` mapping flaw ids to answers."""
    template = request["sweep_template"]
    answer = {
        "drops": drops or [],
        "concerns": template["concerns"] if concerns is None else concerns,
        "merges": merges or [],
        "flaws": [item | (found or {}).get(item["flaw"], {}) for item in template["flaws"]],
    }
    path = Path(request["sweep_path"])
    path.write_text(json.dumps(answer))
    return scan.sweep(scan_id, path)


def pool_of(scan_id: str) -> dict[str, dict]:
    stored = json.loads((scan._scan_root(scan_id) / "scan.json").read_text())
    return {p["id"]: p for p in stored["pool"]}


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


def run_passes(scan_id: str, found: dict[str, list[dict]]) -> int:
    """Answer every task; `found` maps a segment title to its first-pass candidates, and
    "TITLE N" to the candidates of pass N."""
    passes = 0
    while "task" in (task := scan.next_task(scan_id)):
        passes += 1
        path = Path(task["proposal_path"])
        assert not path.exists()  # Hermes refuses to overwrite files it has not read
        proposal = task["proposal_template"]
        title, number = task["segment"]["title"], task["task"]["pass"]
        if number == 1:
            proposal["summary"] = f"The {title} segment, summarized."
            proposal["candidates"] = found.get(title, [])
        else:
            proposal["candidates"] = found.get(f"{title} {number}", [])
        proposal["no_number_checks_reason"] = "No figure depends on another."
        path.write_text(json.dumps(proposal))
        submitted = scan.submit_task(scan_id, path)
        if submitted["state"] == "scanning":
            assert submitted["next_task"]["task"]["id"] == scan.next_task(scan_id)["task"]["id"]
    return passes


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
    assert "sampling and adequacy" in started["monitoring_areas"]
    with pytest.raises(ReviewError, match="set the segment plan first"):
        scan.next_task(scan_id)
    draft = Path(started["plan_draft_path"])
    # The reviewer sees the tiers, and so how many passes run, before the plan is stored.
    with pytest.raises(ReviewError, match="show the reviewer the tiers first"):
        scan.set_plan(scan_id, draft, "Yes, qualitative only.")
    proposed = scan.set_plan(scan_id, draft)
    assert proposed["state"] == "plan proposed" and "end your turn" in proposed["instructions"]
    tiers = {s["title"]: s["tier"] for s in proposed["segments"]}
    expected = sum({"light": 1, "medium": 2, "high": 3}[t] for t in tiers.values())
    assert proposed["passes"] == expected
    with pytest.raises(ReviewError, match="set the segment plan first"):
        scan.next_task(scan_id)
    with pytest.raises(ReviewError, match="sent after it was asked"):
        scan.set_plan(scan_id, draft, "Yes, qualitative only.")
    say(session, "Fine, keep those tiers.")
    planned = scan.set_plan(scan_id, draft, "keep those tiers")
    assert planned["passes"] == expected

    # The initial summary comes before any pass, so it cannot preview a candidate.
    with pytest.raises(ReviewError, match="write the initial summary first"):
        scan.next_task(scan_id)
    overview_path = Path(planned["overview_path"])
    assert not overview_path.exists()
    overview_path.write_text(json.dumps({"summary": "An interview study."}))
    with pytest.raises(ReviewError, match="needs analysis"):
        scan.set_overview(scan_id, overview_path)
    wrong = SUMMARY | {
        "considerations": [{"kind": "validity", "consideration": "Is it biased?", "quote": "x"}]
    }
    overview_path.write_text(json.dumps(wrong))
    with pytest.raises(ReviewError, match="kind must be one of scope"):
        scan.set_overview(scan_id, overview_path)
    unquoted = SUMMARY | {
        "considerations": [
            {"kind": "scope", "consideration": "Only nurses.", "quote": "only nurses were asked"}
        ]
    }
    overview_path.write_text(json.dumps(unquoted))
    with pytest.raises(ReviewError, match="quote the authors' own words"):
        scan.set_overview(scan_id, overview_path)
    overview_path.write_text(json.dumps(SUMMARY | {"main_conclusions": []}))
    with pytest.raises(ReviewError, match="needs main_conclusions"):
        scan.set_overview(scan_id, overview_path)
    overview_path.write_text(json.dumps(SUMMARY))
    assert scan.set_overview(scan_id, overview_path)["state"] == "scanning"
    with pytest.raises(ReviewError, match="written once"):
        scan.set_overview(scan_id, overview_path)

    concern = candidate(
        "recruited by their ward manager",
        "Recruitment through ward managers may filter views.",
        severity="major",
        profile_area="sampling and adequacy",
        major_flaw="unexamined-power",
        why_it_matters=(
            "Gatekeeper recruitment shapes whose experiences appear, as Okonkwo (1998) found "
            "and Strech and Sofaer (2012) warn."
        ),
        solution_candidates=["Describe recruitment and who declined."],
    )
    found = {"Methods": [concern]}
    assert run_passes(scan_id, found) == expected
    status = scan.scan_status(scan_id)
    assert status["phase"] == "synthesis"
    assert "pool" not in status and "candidates" not in status

    request = scan.synthesize(scan_id)
    assert request["state"] == "sweep"
    (entry,) = request["entries"]
    assert entry["tagged_flaws"] == ["qualitative/unexamined-power"]
    assert answer_sweep(scan_id, request)["state"] == "ready"

    first = scan.next_candidate(scan_id)
    assert first["overview"]["considerations"][0]["evidence"]["quote"] == (
        "consent practices in fictional wards"
    )
    (presented,) = first["candidates"]
    # The pass tagged a listed major flaw; creview sets the severity from it.
    assert presented["severity"] == "major"
    assert presented["severity_basis"] == ["listed major flaw qualitative/unexamined-power"]
    assert "strongest reply the authors could make" in first["instructions"]
    labels = {item["citation"]: item["label"] for item in presented["literature"]}
    assert labels == {"Okonkwo 1998": "manuscript_reported", "Strech 2012": "model_lead"}
    assert all(item["content_claim"] for item in presented["literature"])
    # creview prepares the lookups, unverified recollections first; nothing runs unapproved.
    assert [item["citation"] for item in presented["lookups"]] == ["Strech 2012", "Okonkwo 1998"]
    assert presented["lookups"][1]["query"].startswith("Okonkwo, M. (1998)")
    stored = show_lookup(None, presented["lookups"][0]["request_id"])
    assert stored["status"] == "pending_approval" and stored["query"] == "Strech 2012"
    assert presented["context"] == [
        {
            "id": presented["segments"][0]["id"],
            "title": "Methods",
            "summary": "The Methods segment, summarized.",
        }
    ]
    assert first["more_available"] is False
    assert scan.next_candidate(scan_id)["candidates"] == []
    assert scan.scan_status(scan_id)["surfaced"] == 1

    assert scan.purge_scan(scan_id, scan_id)["lookups_removed"] == 2
    with pytest.raises(ReviewError, match="does not exist"):
        scan.scan_status(scan_id)
    with pytest.raises(ReviewError, match="does not exist"):
        show_lookup(None, presented["lookups"][0]["request_id"])


def test_scan_refuses_unverbatim_quotes_and_changed_files(session) -> None:
    started = start(session)
    scan_id = started["scan_id"]
    plan_and_summarize(started)
    task = scan.next_task(scan_id)
    path = Path(task["proposal_path"])
    proposal = task["proposal_template"]
    proposal["candidates"] = [candidate("words the manuscript never says", type="")]
    path.write_text(json.dumps(proposal))
    with pytest.raises(ReviewError, match="not verbatim") as refused:
        scan.submit_task(scan_id, path)
    assert "needs summary" in str(refused.value)
    assert "type must be one of" in str(refused.value)

    proposal["summary"] = "The title and abstract."
    proposal["candidates"] = [candidate("consent")]
    path.write_text(json.dumps(proposal))
    with pytest.raises(ReviewError, match="appears at .* locators; give one of"):
        scan.submit_task(scan_id, path)
    # An inconsistency must quote both statements, at two different places.
    proposal["candidates"] = [candidate("recruited by their ward manager", type="inconsistency")]
    path.write_text(json.dumps(proposal))
    with pytest.raises(ReviewError, match="quote both statements"):
        scan.submit_task(scan_id, path)
    # A quote from another segment, without its locator, is found and located.
    methods = next(
        b for b in parse_document(session).segments if b["text"].startswith("We interviewed")
    )
    proposal["candidates"] = [candidate("recruited by their ward manager")]
    path.write_text(json.dumps(proposal))
    scan.submit_task(scan_id, path)
    stored = json.loads((scan._scan_root(scan_id) / "scan.json").read_text())
    assert stored["candidates"][0]["evidence"][0]["locator"] == methods["locator"]

    session.write_text(PAPER + "\nAn added sentence.\n")
    with pytest.raises(ReviewError, match="changed since the scan started"):
        scan.next_task(scan_id)


def test_scan_requires_a_passing_preflight(isolated_env, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_SESSION_ID", "never-checked")
    paper = isolated_env / "paper.md"
    paper.write_text(PAPER)
    with pytest.raises(ReviewError, match="creview session start"):
        start(paper)


def test_plan_accepts_agent_segment_ids_and_warns_about_the_turn_budget(session) -> None:
    started = start(session)
    scan_id = started["scan_id"]
    plan_path = Path(started["plan_path"])
    assert plan_path.parent.name == scan_id and not plan_path.exists()
    plan = json.loads(Path(started["plan_draft_path"]).read_text())
    for number, segment in enumerate(plan["segments"], start=1):
        segment["id"] = f"S{number}_part"
    plan["segments"][0]["id"] = "../escape"
    plan_path.write_text(json.dumps(plan))
    with pytest.raises(ReviewError, match="unique id"):
        scan.set_plan(scan_id, plan_path)
    plan["segments"][0]["id"] = "abstract"
    plan["segments"][1]["profile_areas"] = ["structure and validity"]
    plan_path.write_text(json.dumps(plan))
    with pytest.raises(ReviewError, match="confirmed profiles do not have: structure"):
        scan.set_plan(scan_id, plan_path)
    plan["segments"][1]["profile_areas"] = ["Sampling and adequacy"]
    plan_path.write_text(json.dumps(plan))
    planned = scan.set_plan(scan_id, plan_path)
    assert planned["segments"][0]["id"] == "abstract"
    assert not any("max_turns" in warning for warning in planned["warnings"])

    config_path = session.parent / "hermes" / "config.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["agent"] = {"max_turns": 10}
    config_path.write_text(yaml.safe_dump(config))
    planned = scan.set_plan(scan_id, plan_path)
    assert any("agent.max_turns (10)" in warning for warning in planned["warnings"])
    planned = confirm_plan(started, plan_path)
    summary_path = Path(planned["overview_path"])
    summary_path.write_text(json.dumps(SUMMARY))
    scan.set_overview(scan_id, summary_path)
    task = scan.next_task(scan_id)
    assert task["task"]["id"] == "abstract-p1"
    # creview supplies the confirmed profiles' false alarms from its own package copy.
    alarms = [item["false_alarm"] for item in task["false_alarms"]]
    assert any("kappa" in alarm for alarm in alarms)
    assert {item["profile"] for item in task["false_alarms"]} == {"qualitative"}


def test_concern_keys_merge_candidates_and_pass_votes_set_severity(session) -> None:
    started = start(session)
    scan_id = started["scan_id"]
    plan_and_summarize(started)
    first = candidate("recruited by their ward manager", severity="major", key="gatekeeping")
    # A later pass reuses the key for the same concern, in other words and another place.
    again = candidate(
        "Background on consent practices",
        "Managers chose who was interviewed.",
        severity="major",
        key="gatekeeping",
        concern_label="",
    )
    lone = candidate("We interviewed twelve nurses", "Sample is small.", severity="major")
    run_passes(scan_id, {"Methods": [first, lone], "Methods 2": [again]})
    request = scan.synthesize(scan_id)
    by_concern = {e["concern"]: e for e in request["entries"]}
    assert set(by_concern) == {"Gatekeepers filter views.", "Sample is small."}
    answer_sweep(scan_id, request)
    pool = {p["label"]: p for p in pool_of(scan_id).values()}
    # Two of the Methods segment's three passes rated it major; one of three is not enough.
    assert pool["Gatekeepers filter views."]["severity"] == "major"
    assert pool["Gatekeepers filter views."]["severity_basis"] == [
        "rated major in 2 of 3 passes over Methods"
    ]
    assert len(pool["Gatekeepers filter views."]["member_ids"]) == 2
    assert pool["Sample is small."]["severity"] == "minor"


def test_tags_are_checked_when_a_pass_is_submitted(session) -> None:
    started = start(session)
    scan_id = started["scan_id"]
    plan_and_summarize(started)
    task = scan.next_task(scan_id)
    assert task["concern_register"] == []
    proposal = task["proposal_template"] | {"summary": "The title and abstract."}
    path = Path(task["proposal_path"])
    untagged = candidate("Background on consent practices")
    del untagged["major_flaw"]
    proposal["candidates"] = [
        untagged,
        candidate("Background on consent practices", major_flaw="power-imbalance"),
        candidate("Background on consent practices", key="another-concern", concern_label=""),
    ]
    path.write_text(json.dumps(proposal))
    with pytest.raises(ReviewError) as refused:
        scan.submit_task(scan_id, path)
    assert "candidate 1 needs major_flaw" in str(refused.value)
    assert "'power-imbalance' is not listed; use none or one of general/" in str(refused.value)
    assert "new concern_key 'another-concern' without concern_label" in str(refused.value)
    proposal["candidates"] = [candidate("Background on consent practices", major_flaw="none")]
    path.write_text(json.dumps(proposal))
    scan.submit_task(scan_id, path)
    later = scan.next_task(scan_id)
    assert later["concern_register"] == [
        {"key": "gatekeepers-filter-views", "label": "Gatekeepers filter views."}
    ]


def test_sweep_drops_entries_and_looks_up_each_flaw(session) -> None:
    started = start(session)
    scan_id = started["scan_id"]
    plan_and_summarize(started)
    run_passes(
        scan_id,
        {
            "Methods": [candidate("recruited by their ward manager", "Recruitment is unclear.")],
            "Results": [candidate("described consent as a formality", "Wording is vague.")],
        },
    )
    request = scan.synthesize(scan_id)
    methods, results = (e["id"] for e in request["entries"])
    assert scan.synthesize(scan_id)["sweep_path"] == request["sweep_path"]  # resumable
    with pytest.raises(ReviewError, match="the scan is in sweep"):
        scan.next_candidate(scan_id)
    path = Path(request["sweep_path"])
    path.write_text(json.dumps({"drops": [], "flaws": request["sweep_template"]["flaws"][:1]}))
    with pytest.raises(ReviewError, match="answer every listed major flaw"):
        scan.sweep(scan_id, path)
    with pytest.raises(ReviewError, match="dropped without a reason"):
        answer_sweep(scan_id, request, drops=[{"id": results}])
    power = {
        "qualitative/unexamined-power": {
            "entries": [methods],
            "quote": {"quote": "Background on consent practices"},
            "reason": "The ward manager recruited the participants.",
        }
    }
    with pytest.raises(ReviewError, match="not from the evidence of"):
        answer_sweep(scan_id, request, found=power)
    power["qualitative/unexamined-power"]["quote"] = {"quote": "recruited by their ward manager"}
    power["general/self-contradiction"] = {"entries": [results], "reason": "x", "quote": "Most"}
    drop = [{"id": results, "reason": "A wording preference."}]
    with pytest.raises(ReviewError, match="not kept entries"):
        answer_sweep(scan_id, request, drops=drop, found=power)
    del power["general/self-contradiction"]
    assert answer_sweep(scan_id, request, drops=drop, found=power)["state"] == "ready"

    pool = pool_of(scan_id)
    # The sweep found a listed flaw the pass had not tagged: creview makes the entry major.
    assert pool[methods]["severity"] == "major"
    assert pool[methods]["major_flaws"] == ["qualitative/unexamined-power"]
    assert pool[results]["decision"] == "drop"
    (shown,) = scan.next_candidate(scan_id)["candidates"]
    assert shown["pool_id"] == methods
    assert shown["major_flaws"] == ["qualitative/unexamined-power"]
    assert scan.next_candidate(scan_id)["candidates"] == []


def test_number_checks_are_computed_by_creview(session) -> None:
    session.write_text(
        PAPER.replace(
            "Themes emerged from the data.",
            "Of 112 full texts, 74 were excluded and 42 were included; 31 of 42 (74%) agreed."
            "\n\nAll 42 were coded. Of 20 wards, 8 declined and 10 took part.",
        ).replace("summarizes a fictional interview study", "summarizes 42 publications")
    )
    started = start(session)
    scan_id = started["scan_id"]
    plan_and_summarize(started)
    task = scan.next_task(scan_id)
    assert "number_check_fields" in task
    proposal = task["proposal_template"] | {"summary": "The title and abstract."}
    proposal["number_checks"] = [{"expression": "__import__('os')", "stated": "1", "quote": "x"}]
    path = Path(task["proposal_path"])
    path.write_text(json.dumps(proposal))
    with pytest.raises(ReviewError, match="only numbers"):
        scan.submit_task(scan_id, path)
    proposal["number_checks"] = [
        {"expression": "112 - 74", "stated": "42", "quote": "74 were excluded and 42 were"},
        {"expression": "31 / 42 * 100", "stated": "74%", "quote": "31 of 42 (74%) agreed"},
        {"expression": "112 - 74", "stated": "74", "quote": "74 were excluded and 42 were"},
    ]
    path.write_text(json.dumps(proposal))
    with pytest.raises(ReviewError, match="not one of its operands"):
        scan.submit_task(scan_id, path)
    del proposal["number_checks"][2]
    proposal["number_checks"].append(
        {"expression": "20 - 8", "stated": "10", "quote": "8 declined and 10 took part"}
    )
    path.write_text(json.dumps(proposal))
    submitted = scan.submit_task(scan_id, path)
    assert [(c["computed"], c["matches"]) for c in submitted["number_checks"]] == [
        (38, False),
        (73.809524, True),
        (12, False),
    ]

    # The model's restatement joins the check, whatever key it was given; a major tag or vote on
    # it cannot raise the check, whose severity comes from how often the figure recurs.
    restated = candidate(
        "Of 20 wards",
        "20 wards minus 8 that declined gives 12, but the paper says 10 took part.",
        severity="major",
        major_flaw="self-contradiction",
    )
    broad = candidate("31 of 42 (74%) agreed", "Selection is poorly reported.")
    while "task" in (task := scan.next_task(scan_id)):
        proposal = task["proposal_template"] | {"summary": "What the segment says."}
        if task["segment"]["title"] == "Methods" and task["task"]["pass"] == 1:
            proposal["candidates"] = [restated, broad]
            proposal["no_number_checks_reason"] = "Checked in the first pass."
        path = Path(task["proposal_path"])
        path.write_text(json.dumps(proposal))
        scan.submit_task(scan_id, path)
    request = scan.synthesize(scan_id)
    checks = [e for e in request["entries"] if "computed_check" in e]
    assert sorted(e["computed_check"]["stated"] for e in checks) == ["10", "42"]
    wards = next(e for e in checks if e["computed_check"]["stated"] == "10")
    flaw = {
        "general/self-contradiction": {
            "entries": [wards["id"]],
            "quote": "8 declined and 10 took part",
            "reason": "The counts disagree.",
        }
    }
    with pytest.raises(ReviewError, match="hold a computed number check"):
        answer_sweep(scan_id, request, found=flaw)
    broad_id = next(
        e["id"] for e in request["entries"] if e["concern"] == "Selection is poorly reported."
    )
    fold = [{"into": broad_id, "ids": [wards["id"]], "reason": "Both are about selection."}]
    with pytest.raises(ReviewError, match="joins a computed number check"):
        answer_sweep(scan_id, request, merges=fold)
    answer_sweep(scan_id, request)
    pool = pool_of(scan_id)
    flow = next(
        p for p in pool.values() if p["id"] != wards["id"] and p["id"] in [c["id"] for c in checks]
    )
    # 42 recurs in the abstract and two paragraphs: other results rest on it, so it is major.
    assert pool[flow["id"]]["severity"] == "major"
    assert pool[flow["id"]]["severity_basis"] == [
        "mismatched figure 42 recurs across the manuscript"
    ]
    assert len(pool[wards["id"]]["member_ids"]) == 2
    assert pool[wards["id"]]["severity"] == "minor"


def test_candidates_wait_for_responses_and_verifiable_minors_are_never_held(
    session, monkeypatch
) -> None:
    started = start(session)
    scan_id = started["scan_id"]
    plan_and_summarize(started)
    contradiction = candidate(
        "Background on consent practices",
        "Consent framing is thin.",
        type="inconsistency",
        evidence=[{"quote": "Background on consent practices"}, {"quote": "Most participants"}],
    )
    major = candidate("recruited by their ward manager", severity="major", key="gatekeeping")
    run_passes(
        scan_id,
        {
            "Introduction": [contradiction],
            "Methods": [major],
            "Methods 2": [major | {"concern_label": ""}],
            "Results": [
                candidate("described consent as a formality", "Consent framing is thin here.")
            ],
        },
    )
    request = scan.synthesize(scan_id)
    intro, methods, results = (e["id"] for e in request["entries"])
    answer_sweep(scan_id, request)

    shown = scan.next_candidate(scan_id)
    assert [c["pool_id"] for c in shown["candidates"]] == [methods]
    assert shown["next_severity"] == "minor"
    with pytest.raises(ReviewError, match="record the reviewer's response"):
        scan.next_candidate(scan_id)
    with pytest.raises(ReviewError, match="has not been surfaced"):
        scan.record_response(scan_id, intro, "accepted", "Accept it.")
    with pytest.raises(ReviewError, match="disposition must be"):
        scan.record_response(scan_id, methods, "candidate", "Accept it.")
    # The reviewer's words must come from a message sent after the candidate was shown.
    with pytest.raises(ReviewError, match="sent after it was asked"):
        scan.record_response(scan_id, methods, "accepted", "Yes, qualitative only.")
    say(session, "Accept it as a major comment.")
    with pytest.raises(ReviewError, match="not in any of those messages"):
        scan.record_response(scan_id, methods, "accepted", "Accept both.")
    recorded = scan.record_response(scan_id, methods, "accepted", "accept it as a major")
    assert recorded["records"]["accepted"] == 1

    # A failure while building the presentation must not mark the batch as shown.
    original = scan._current_sources
    monkeypatch.setattr(scan, "_current_sources", lambda _: (_ for _ in ()).throw(ReviewError("x")))
    with pytest.raises(ReviewError):
        scan.next_candidate(scan_id)
    monkeypatch.setattr(scan, "_current_sources", original)
    assert scan.scan_status(scan_id)["surfaced"] == 1

    # Minors past the active limit are held, except a verifiable one.
    monkeypatch.setattr(scan, "MAX_ACTIVE_MINORS", 0)
    minors = scan.next_candidate(scan_id)
    assert [c["pool_id"] for c in minors["candidates"]] == [intro]
    assert minors["candidates"][0]["verifiable"] is True
    assert scan.scan_status(scan_id)["records"] == {
        "accepted": 1,
        "developing": 0,
        "candidate": 1,
        "deferred": 0,
        "dismissed": 0,
    }
    say(session, "Accepted.")
    scan.record_response(scan_id, intro, "accepted", "Accepted.")
    held = scan.next_candidate(scan_id)
    assert held["candidates"] == [] and held["reserve_available"] is True
    reserve = scan.next_candidate(scan_id, reserve=True)
    assert [c["pool_id"] for c in reserve["candidates"]] == [results]


def test_one_key_is_one_entry_and_majors_on_one_conclusion_come_together(session) -> None:
    started = start(session)
    scan_id = started["scan_id"]
    plan_and_summarize(started)
    # The model gave the contradiction the broader concern's key: it is one entry, verifiable.
    contradiction = candidate(
        "recruited by their ward manager",
        "Methods and Results disagree about who recruited participants.",
        type="inconsistency",
        key="gatekeeping",
        evidence=[{"quote": "recruited by their ward manager"}, {"quote": "Most participants"}],
    )
    flawed = {"major_flaw": "unexamined-power"}
    run_passes(
        scan_id,
        {
            "Methods": [
                candidate("recruited by their ward manager", key="gatekeeping"),
                contradiction | {"concern_label": ""},
            ],
            "Results": [
                candidate("described consent as a formality", "Formality is overstated.", **flawed),
                candidate("consent as a formality", "Finding rests on few voices.", **flawed),
            ],
        },
    )
    request = scan.synthesize(scan_id)
    entries = {e["concern"]: e["id"] for e in request["entries"]}
    assert len(request["entries"]) == 3
    answer_sweep(scan_id, request)
    first = scan.next_candidate(scan_id)
    # Both majors quote the same main conclusion: they come together, as one batch.
    assert [c["pool_id"] for c in first["candidates"]] == [
        entries["Formality is overstated."],
        entries["Finding rests on few voices."],
    ]
    assert first["candidates"][0]["main_conclusion"] == "described consent as a formality"
    assert "same main conclusion" in first["instructions"]


def test_sweep_merges_entries_the_passes_keyed_apart(session) -> None:
    started = start(session)
    scan_id = started["scan_id"]
    plan_and_summarize(started)
    run_passes(
        scan_id,
        {
            "Introduction": [candidate("Background on consent practices", "Framing is thin.")],
            "Methods": [candidate("recruited by their ward manager", "Managers chose voices.")],
            "Results": [candidate("described consent as a formality", "Gatekeeping skews it.")],
        },
    )
    request = scan.synthesize(scan_id)
    intro, methods, results = (e["id"] for e in request["entries"])
    one = {"into": methods, "ids": [results], "reason": "Both are gatekeeping."}
    with pytest.raises(ReviewError, match="has no reason"):
        answer_sweep(scan_id, request, merges=[one | {"reason": ""}])
    with pytest.raises(ReviewError, match="names a dropped entry"):
        answer_sweep(scan_id, request, merges=[one], drops=[{"id": results, "reason": "Vague."}])
    chained = [one, {"into": results, "ids": [intro], "reason": "Framing too."}]
    with pytest.raises(ReviewError, match="overlaps another merge"):
        answer_sweep(scan_id, request, merges=chained)
    # A flaw found in a merged entry counts for the entry that remains, with its quotes.
    power = {
        "qualitative/unexamined-power": {
            "entries": [results],
            "quote": "described consent as a formality",
            "reason": "Managers shaped what was said.",
        }
    }
    answer_sweep(scan_id, request, merges=[one], found=power)
    pool = pool_of(scan_id)
    assert pool[results]["decision"] == "merge" and pool[results]["merged_into"] == methods
    assert len(pool[methods]["member_ids"]) == 2
    assert pool[methods]["major_flaws"] == ["qualitative/unexamined-power"]
    shown = scan.next_candidate(scan_id)["candidates"]
    assert [c["pool_id"] for c in shown] == [methods]
    assert [s["title"] for s in shown[0]["segments"]] == ["Methods", "Results"]


def test_sweep_must_place_every_preliminary_major_in_one_concern(session) -> None:
    started = start(session)
    scan_id = started["scan_id"]
    plan_and_summarize(started)
    flawed = {"major_flaw": "unexamined-power"}
    run_passes(
        scan_id,
        {
            "Methods": [
                candidate("recruited by their ward manager", "Managers chose voices.", **flawed)
            ],
            "Results": [
                candidate("described consent as a formality", "Gatekeeping skews it.", **flawed),
                candidate("Most participants", "Wording is vague."),
            ],
        },
    )
    request = scan.synthesize(scan_id)
    methods, results, vague = (e["id"] for e in request["entries"])
    assert [m["id"] for m in request["preliminary_majors"]] == [results, methods]
    with pytest.raises(ReviewError, match="every preliminary major .*: " + methods):
        answer_sweep(scan_id, request, concerns=[{"ids": [results]}])
    with pytest.raises(ReviewError, match="more than once"):
        answer_sweep(scan_id, request, concerns=[{"ids": [results, methods]}, {"ids": [methods]}])
    with pytest.raises(ReviewError, match="has no reason"):
        answer_sweep(scan_id, request, concerns=[{"ids": [results, methods]}])
    one = [{"ids": [methods, results], "reason": "Both are about gatekeeping."}]
    answer_sweep(scan_id, request, concerns=one)
    pool = pool_of(scan_id)
    assert pool[results]["merged_into"] == methods and len(pool[methods]["member_ids"]) == 2
    assert pool[methods]["severity"] == "major" and pool[vague]["severity"] == "minor"
