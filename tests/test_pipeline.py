from pathlib import Path

import pytest

from closed_review import findings, pipeline
from closed_review.segments import draft_plan

PAPER = (
    "# Abstract\n\nWe show that the tool reduces delay in all wards.\n\n"
    "# Introduction\n\nDelays in referral harm patients, and tools may help clinicians decide.\n\n"
    "# Methods\n\nWe enrolled 120 patients from one ward between 2019 and 2020.\n\n"
    "Of 120 patients, 40 were excluded and 85 were analysed.\n\n"
    "# Results\n\nThe tool reduced median delay from 9 to 4 days.\n\n"
    "# Discussion\n\nThe tool reduces delay in all wards and should be adopted everywhere.\n\n"
    "## Limitations\n\nThis was a single-ward study.\n\n"
    "# References\n\nSmith J. A study. 2019.\n"
)
FLAWS = [
    {"id": "general/self-contradiction", "flaw": "two incompatible statements"},
    {"id": "quantitative/causal-from-association", "flaw": "causal claims from association"},
]


@pytest.fixture
def document(tmp_path: Path) -> dict:
    path = tmp_path / "paper.md"
    path.write_text(PAPER)
    return findings.open_document(path)


@pytest.fixture
def review(document) -> dict:
    """A review after orientation: one unit per section, the Abstract last."""
    plan = draft_plan([{"source_id": "manuscript", "segments": document["segments"]}])["segments"]
    ids = [s["id"] for s in plan]
    roles = ["abstract", "introduction", "methods", "results"]
    proposed = [{"role": r, "parts": [[i]]} for r, i in zip(roles, ids, strict=False)]
    proposed += [
        {"role": "discussion", "parts": [[ids[5]], [ids[4]]]},
        {"role": "references", "parts": [[ids[6]]]},
    ]
    return {
        "id": "r",
        "doc_id": "d",
        "findings": [],
        "plan": plan,
        "units": pipeline.make_units(plan, proposed),
        "profiles": ["quantitative"],
        "orientation": {"considerations": []},
    }


def part(review: dict, role: str) -> dict:
    return next(p for p in pipeline.all_parts(review) if p["unit"]["role"] == role)


def new_concern(**fields) -> dict:
    concern = {
        "title": "Generalisation beyond one ward",
        "issue": "One ward cannot show all wards.",
        "why": "The conclusion is broader than the sample.",
        "type": "unsupported",
        "severity": "major",
        "flaw": "none",
        "target": "The tool reduces delay in all wards",
        "quotes": ["should be adopted everywhere"],
    }
    return {**concern, **fields}


def test_units_read_in_order_with_the_abstract_last_and_no_references(review) -> None:
    assert [u["role"] for u in review["units"]] == [
        "introduction",
        "methods",
        "results",
        "discussion",
        "abstract",
    ]
    assert review["units"][3]["parts"] == [["ls-05"], ["ls-06"]]


def test_parts_are_consecutive_and_sized() -> None:
    plan = [{"id": f"s{n}", "title": str(n), "block_ids": []} for n in range(6)]
    words = {"s0": 100, "s1": 700, "s2": 200, "s3": 200, "s4": 600, "s5": 50}

    def problems(*parts: list[str]) -> list[str]:
        units = [
            {"role": r, "parts": [p]}
            for r, p in zip(["introduction", "methods"], parts[:2], strict=True)
        ]
        units += [{"role": "results", "parts": list(parts[2:])}]
        return pipeline.unit_problems(plan, units, words)

    assert problems(["s0"], ["s1"], ["s2", "s3"], ["s4"], ["s5"]) == [
        "part s5 has 50 words, fewer than 300: join it with the part s4 in the results unit, "
        "whichever it belongs with"
    ]
    assert any("more than 800" in p for p in problems(["s0"], ["s1"], ["s2", "s3", "s4"], ["s5"]))
    assert any("not consecutive" in p for p in problems(["s0"], ["s1"], ["s2", "s4"], ["s3", "s5"]))
    assert "segments in no unit: s5" in problems(["s0"], ["s1"], ["s2", "s3"], ["s4"])


def test_a_different_from_in_the_wrong_shape_is_refused_not_a_crash(document, review) -> None:
    """Live TUI run, 2026-10-27: a string different_from on an otherwise accepted answer raised
    AttributeError, and the traceback sent the model to undo a correct fix elsewhere."""
    discussion = part(review, "discussion")
    answer = {
        "concerns": [new_concern(different_from="F1: a different problem")],
        "flaws_to_check": [],
        "number_checks": [],
    }
    refused = pipeline.read_answer(document, review, discussion, FLAWS, answer)
    assert len(refused["problems"]) == 1
    assert "concern 1 different_from must be one object {id:" in refused["problems"][0]
    fixed = {"id": "F1", "reason": "A different problem."}
    answer["concerns"][0]["different_from"] = fixed
    assert pipeline.read_answer(document, review, discussion, FLAWS, answer)["problems"] == []


def test_a_declaration_with_the_methods_may_stay_a_short_part() -> None:
    """The task puts declarations with the methods; joining one to a methods part could never be
    consecutive, so creview must not ask for it (live ms5, 2026-10-27)."""
    plan = [{"id": f"s{n}", "title": str(n), "block_ids": []} for n in range(7)]
    words = {"s0": 400, "s1": 400, "s2": 350, "s3": 350, "s4": 350, "s5": 350, "s6": 51}
    units = [
        {"role": "introduction", "parts": [["s0"]]},
        {"role": "methods", "parts": [["s1"], ["s6"]]},
        {"role": "results", "parts": [["s2"], ["s3"]]},
        {"role": "discussion", "parts": [["s4"], ["s5"]]},
    ]
    assert pipeline.unit_problems(plan, units, words) == []


def test_a_read_links_known_concerns_and_raises_new_ones_with_a_target(document, review) -> None:
    discussion = part(review, "discussion")
    first = pipeline.read_answer(
        document,
        review,
        discussion,
        FLAWS,
        {
            "concerns": [new_concern()],
            "flaws_to_check": ["quantitative/causal-from-association"],
            "number_checks": [],
        },
    )
    assert first["problems"] == [] and first["added"] == 1
    review = first["review"]
    (f,) = review["findings"]
    assert f["target"]["quote"] == "The tool reduces delay in all wards"
    assert f["unit"] == discussion["unit"]["id"] and "flaw" not in f

    abstract = part(review, "abstract")
    link = {"link": "F1", "role": "restates", "note": "The Abstract says it again.", "quotes": []}
    refused = pipeline.read_answer(
        document,
        review,
        abstract,
        FLAWS,
        {
            "concerns": [
                {**link, "quotes": ["should be adopted everywhere"]},
                {**link, "link": "F9"},
                new_concern(target="The tool reduces delay in all wards", quotes=["in all wards"]),
            ],
            "flaws_to_check": ["general/none"],
            "number_checks": [{"expression": "120", "stated": "120", "quote": "120 patients"}],
        },
    )
    text = "; ".join(refused["problems"])
    assert "links to F1 with quotes from outside this unit" in text
    assert "concern 2 links to F9, which is not a concern found so far" in text
    assert "concern 2 has no quote" in text
    assert (
        'concern 3 ("Generalisation beyond one ward") is about the same passage as F1 '
        '("Generalisation beyond one ward")' in text
    )
    assert 'number check "120" has no arithmetic' in text
    assert "flaws_to_check names unlisted flaws: general/none" in text

    linked = pipeline.read_answer(
        document,
        review,
        abstract,
        FLAWS,
        {"concerns": [{**link, "quotes": ["We show that the tool"]}], "number_checks": []},
    )
    assert linked["linked"] == 1
    (f,) = linked["review"]["findings"]
    assert f["updates"][0]["role"] == "restates" and f["linked_from"] == [abstract["unit"]["id"]]
    assert len(f["evidence"]) == 2


def test_a_computed_mismatch_is_a_finding_titled_as_javascript_prints_numbers(
    document, review
) -> None:
    accepted = pipeline.read_answer(
        document,
        review,
        part(review, "methods"),
        FLAWS,
        {
            "concerns": [],
            "number_checks": [
                {"expression": "120 - 40", "stated": "85", "quote": "85 were analysed"}
            ],
        },
    )
    (f,) = accepted["review"]["findings"]
    assert f["title"] == "The stated 85 does not follow from 120 - 40 (80)"
    assert pipeline.js_number(0.26) == "0.26" and pipeline.js_number(5e-05) == "0.00005"


def test_a_check_names_its_concern_or_a_passage_no_concern_is_about(document, review) -> None:
    review = pipeline.read_answer(
        document, review, part(review, "discussion"), FLAWS, {"concerns": [new_concern()]}
    )["review"]
    flaw = "quantitative/causal-from-association"
    shown = {"shown": True, "quotes": ["The tool reduces delay in all wards"], "reason": "causal"}
    on = pipeline.check_answer(document, review, flaw, "m", {**shown, "concern": "F1"})
    assert on["answer"]["concern"] == "F1" and on["answer"]["quotes_verified"]
    owned = pipeline.check_answer(
        document,
        review,
        flaw,
        "m",
        {**shown, "concern": "none", "target": "should be adopted everywhere"},
    )
    assert "F1 is about this passage" in owned["problems"][0]
    assert pipeline.check_answer(document, review, flaw, "m", {"shown": True, "concern": "F1"})[
        "problems"
    ] == ["a flaw shown needs at least one verbatim quote"]

    no = pipeline.check_answer(document, review, flaw, "n", {"shown": False, "reason": "no"})
    attached = pipeline.attach_checks(review, [on["answer"], no["answer"]])
    assert [a["model"] for a in attached["findings"][0]["flaw_checks"]] == ["m", "n"]
    assert findings.severity(attached["findings"][0])["basis"] == "evidence"


@pytest.mark.parametrize("flaw", ["general/misread-source", "legal-analysis/misread-provision"])
def test_misread_source_checks_need_the_source_words_as_well_as_the_claim(tmp_path, flaw) -> None:
    paper = tmp_path / "source-claim.md"
    paper.write_text(
        "# Claim\n\nThe authors say the guideline prohibits treatment.\n\n"
        '# Source quotation\n\nThe manuscript quotes the guideline: "Treatment may be offered."\n'
    )
    document = findings.open_document(paper)
    review = {"findings": [{"id": "F1"}]}
    answer = {
        "shown": True,
        "quotes": ["The authors say the guideline prohibits treatment."],
        "concern": "F1",
        "reason": "The quoted guideline permits what the authors say it prohibits.",
    }
    refused = pipeline.check_answer(document, review, flaw, "m", answer)
    assert "source_quote" in refused["problems"][0]
    refused_confirm = pipeline.confirm_answer(document, "F1", flaw, "m", answer)
    assert "source_quote" in refused_confirm["problems"][0]

    same = {**answer, "source_quote": answer["quotes"][0]}
    assert (
        "separate quote" in pipeline.check_answer(document, review, flaw, "m", same)["problems"][0]
    )
    subset = {**answer, "source_quote": "guideline prohibits treatment"}
    assert (
        "separate quote"
        in pipeline.check_answer(document, review, flaw, "m", subset)["problems"][0]
    )
    invented = {**answer, "source_quote": "Treatment is always forbidden."}
    assert (
        "not verbatim"
        in pipeline.check_answer(document, review, flaw, "m", invented)["problems"][0]
    )

    source = {**answer, "source_quote": {"quote": "Treatment may be offered."}}
    checked = pipeline.check_answer(document, review, flaw, "m", source)
    assert checked["problems"] == []
    assert checked["answer"]["source_quote"]["quote"] == "Treatment may be offered."
    assert pipeline.confirm_answer(document, "F1", flaw, "m", source)["problems"] == []
    assert pipeline.check_answer(document, review, flaw, "m", {"shown": False})["problems"] == []


def test_a_target_wrapped_in_a_list_is_read_as_its_passage(document, review) -> None:
    """Live run, 2026-10-27: a verbatim target given as ["..."] was refused four times as not
    verbatim, because it was checked as its printed list."""
    review = pipeline.read_answer(
        document, review, part(review, "discussion"), FLAWS, {"concerns": [new_concern()]}
    )["review"]
    flaw = "quantitative/causal-from-association"
    shown = {"shown": True, "quotes": ["The tool reduces delay in all wards"], "concern": "none"}
    one = {**shown, "target": ["should be adopted everywhere"]}
    assert (
        "F1 is about this passage"
        in pipeline.check_answer(document, review, flaw, "m", one)["problems"][0]
    )
    two = {**shown, "target": ["should be adopted everywhere", "in all wards"]}
    assert pipeline.check_answer(document, review, flaw, "m", two)["problems"] == [
        "with no concern, give target: the passage the flaw is about"
    ]


def test_target_object_preserves_a_locator_in_reads_checks_and_sweep(document, review) -> None:
    """Live TUI run: a correct {quote, locator} target was stringified and repeatedly refused."""
    quote = "tool reduces delay in all wards"
    matching = [s for s in document["segments"] if quote in s["text"]]
    assert len(matching) == 2
    discussion = next(s for s in matching if "Discussion" in s["locator"])
    target = {"quote": quote, "locator": discussion["locator"]}
    read = pipeline.read_answer(
        document,
        review,
        part(review, "discussion"),
        FLAWS,
        {"concerns": [new_concern(target=target)]},
    )
    assert read["problems"] == []
    assert read["review"]["findings"][0]["target"]["locator"] == target["locator"]

    flaw = "quantitative/causal-from-association"
    check = pipeline.check_answer(
        document,
        review,
        flaw,
        "m",
        {"shown": True, "quotes": ["should be adopted everywhere"], "target": [target]},
    )
    assert check["problems"] == []
    assert check["answer"]["target"]["locator"] == target["locator"]

    swept = pipeline.sweep_answer(
        document,
        read["review"],
        FLAWS,
        [],
        [],
        {
            "concerns": [
                {
                    "concern": "Generalisation",
                    "target": target,
                    "severity": "major",
                    "items": ["F1"],
                }
            ]
        },
    )
    assert swept["problems"] == []
    assert swept["review"]["findings"][0]["target"]["locator"] == target["locator"]

    ambiguous = pipeline.read_answer(
        document,
        review,
        part(review, "discussion"),
        FLAWS,
        {"concerns": [new_concern(target={"quote": quote})]},
    )
    assert any("appears at 2 locators" in problem for problem in ambiguous["problems"])
    fabricated = pipeline.read_answer(
        document,
        review,
        part(review, "discussion"),
        FLAWS,
        {
            "concerns": [
                new_concern(target={"quote": "not in the manuscript", "locator": target["locator"]})
            ]
        },
    )
    assert any("not verbatim" in problem for problem in fabricated["problems"])


def test_sweep_refuses_missing_or_invalid_severity(document, review) -> None:
    review = pipeline.read_answer(
        document, review, part(review, "discussion"), FLAWS, {"concerns": [new_concern()]}
    )["review"]
    concern = {
        "concern": "Generalisation",
        "target": "should be adopted everywhere",
        "items": ["F1"],
    }
    for severity in (None, "critical"):
        answer = {"concerns": [{**concern, "severity": severity}]}
        result = pipeline.sweep_answer(document, review, FLAWS, [], [], answer)
        assert "concern 1 needs severity: major or minor" in result["problems"]


def test_the_sweep_places_every_item_once_and_folds_each_concern(document, review) -> None:
    review = pipeline.read_answer(
        document,
        review,
        part(review, "discussion"),
        FLAWS,
        {
            "concerns": [
                new_concern(),
                new_concern(
                    title="One ward",
                    target="We enrolled 120 patients from one ward",
                    quotes=["from one ward"],
                ),
            ]
        },
    )["review"]
    answer = {
        "flaw": "general/self-contradiction",
        "model": "m",
        "shown": True,
        "quotes_verified": True,
        "quotes": findings.check_quotes(document, ["one ward"])["verified"],
        "reason": "one ward, all wards",
    }
    assert "sweep" in pipeline.sweep_task(review, [answer])
    concern = {
        "concern": "The conclusion is broader than the single ward studied.",
        "target": "The tool reduces delay in all wards",
        "severity": "major",
    }
    missing = pipeline.sweep_answer(
        document, review, FLAWS, [], [answer], {"concerns": [{**concern, "items": ["F1"]}]}
    )
    assert missing["problems"] == ["not placed: F2, C1"]
    swept = pipeline.sweep_answer(
        document,
        review,
        FLAWS,
        [{"flaw": "general/self-contradiction", "segments": ["ls-03"]}],
        [answer],
        {
            "concerns": [
                {**concern, "items": ["F2", "F1"]},
                {**concern, "concern": "Ward counts conflict.", "items": ["C1"], "flaw": "none"},
            ]
        },
    )["review"]
    kept, gone, made = swept["findings"]
    assert kept["title"] == concern["concern"] and gone["status"] == "dismissed"
    assert made["origin"] == "check" and made["flaw"] == "general/self-contradiction"
    assert made["segment_id"] == "ls-03" and swept["sweep"]["concerns"][0]["items"] == ["F2", "F1"]


def test_a_tagged_major_on_judgement_that_no_model_confirms_becomes_minor(document, review) -> None:
    review = pipeline.read_answer(
        document,
        review,
        part(review, "discussion"),
        FLAWS,
        {"concerns": [new_concern(flaw="quantitative/causal-from-association")]},
    )["review"]
    assert pipeline.to_confirm(review, FLAWS) == ["F1"]
    no = pipeline.confirm_answer(
        document, "F1", review["findings"][0]["flaw"], "m", {"shown": False}
    )
    applied = pipeline.apply_confirmations(review, {"F1": [no["answer"], None]})
    (f,) = applied["review"]["findings"]
    assert applied["minor"] == 1 and f["model_severity"] == "minor"
    assert f["discussion"] == [
        "rated major on judgement; the check of quantitative/causal-from-association on its "
        "passage did not show it (m)"
    ]


def test_screening_sets_aside_only_what_code_can_check(document, review) -> None:
    review = pipeline.read_answer(
        document,
        review,
        part(review, "discussion"),
        FLAWS,
        {
            "concerns": [
                new_concern(),
                new_concern(
                    title="Single ward",
                    target="This was a single-ward study.",
                    quotes=["This was a single-ward study."],
                ),
            ]
        },
    )["review"]
    ack = pipeline.screen_acknowledged(review)
    assert ack["review"]["findings"][1]["screened"]["kind"] == "acknowledged"
    assert ack["asked"] == ["F1"]
    alarms = {"quantitative/fa1": "Asking for a multicentre study."}
    say = {"answers": [{"id": "F1", "false_alarm": "quantitative/fa1"}]}
    first = pipeline.screen_answer(document, ["F1"], alarms, say)["answers"]
    applies = pipeline.screen_answer(
        document,
        ["F1"],
        alarms,
        {"answers": [{**say["answers"][0], "applies": "should be adopted everywhere"}]},
    )["answers"]
    kept = pipeline.apply_screening(ack["review"], ["F1"], ["m", "n"], [first, applies], alarms)
    assert "status" not in kept["review"]["findings"][0]
    gone = pipeline.apply_screening(ack["review"], ["F1"], ["m", "n"], [first, first], alarms)
    assert gone["review"]["findings"][0]["screened"]["reason"].endswith("(named by m and n)")
    assert pipeline.screen_answer(document, ["F1"], alarms, {"answers": []})["problems"] == [
        "not answered: F1"
    ]
