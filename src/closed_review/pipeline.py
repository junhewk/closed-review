"""The deep analysis as pure rules over a review's state, for any host that runs the model calls.

A host (an app through the sidecar, or the Hermes deep scan in scan.py) keeps the review and
makes the model calls; this module says what each call is asked, checks each answer, and applies
what is accepted. Every function takes the review state as plain data and returns problems to send
back to the model, or the changed state. Nothing here reads files, calls
a model, or keeps state between calls.

The stages:

- **Orientation** groups the plan's segments into 4 to 5 reading units by the manuscript's
  structure (the Abstract last, the references not read), each in parts at its own logical breaks
  of PART_MIN_WORDS to PART_WORDS words.
- **Reads**, one per part, in order. Each sees the register of concerns found so far, each with the
  passage it is about. What a read finds about one of them it adds as typed evidence (restates,
  relies-on, contradicts, answers), quoting only its own part; a new concern names its target, and
  a second concern about the same passage must say how it is a different problem.
- **Checks**: each listed major flaw a read flagged is asked once, of every approved model, against
  the register; an answer that shows the flaw names the concern it is an instance of.
- **The sweep** sorts every finding and every check answer on no concern, each as a short card, into
  the concerns a reviewer would report; every item is placed exactly once.
- **Confirmation**: a concern rated major on judgement and tagged with a listed flaw is asked that
  flaw's question about its own passage; shown by no model, it becomes minor.
- **Screening** sets aside, still available to the reviewer, a concern whose only evidence is the
  authors' statement of a limitation, or that every model says asks for the same listed common
  false alarm with no passage making it apply.

Severity itself stays in findings.severity: major on a check with verified quotes or a recurring
computed mismatch, otherwise the model's rating as judgement.
"""

from __future__ import annotations

import copy
import re
from decimal import Decimal
from typing import Any

from . import findings as rules

PART_WORDS = 800
"""At most this many words in a part of several segments, so a detail is not lost in a long span (a
single section longer than that is still one part)."""
PART_MIN_WORDS = 300
"""At least this many words in a part, so a short section is read with the one it belongs with (a
short part stays when joining either neighbour would pass PART_WORDS). The Abstract is always one
part, whatever its size."""
SHORT_SEGMENT_CHARS = 300
"""A plan segment shorter than this (a heading-only fragment) joins the next one."""

CANDIDATE_TYPES = ("inconsistency", "unsupported", "argument", "method", "reporting", "other")
UPDATE_ROLES = ("restates", "relies-on", "contradicts", "answers")
UNIT_ROLES = (
    "abstract",
    "introduction",
    "methods",
    "results",
    "discussion",
    "argument",
    "objections",
    "law",
    "analysis",
    "proposals",
    "conclusion",
    "references",
    "other",
)
SCREEN_KINDS = ("false-alarm", "acknowledged")

_QUOTES = "verbatim quotes from the manuscript, one passage per item, never joined"
_DIFFERENT_FROM = (
    "only when a concern already found is about the same passage and this is a different problem: "
    "{id: the concern about the same passage, reason: in one sentence, how this is a different "
    "problem}"
)
ANSWER_FIELDS: dict[str, dict[str, str]] = {
    "orient": {
        "summary": "what the article asks, does, and concludes",
        "analysis": (
            "design, data or sources, methods, and frameworks, as the authors describe them"
        ),
        "considerations": (
            "up to five, each {kind: scope, limitation, ethics, context, or choice; "
            "consideration; quote: the authors' words, verbatim}"
        ),
        "main_conclusions": "one to four central conclusions, each quoted verbatim",
        "units": (
            "the manuscript in 4 to 5 reading units by its structure, plus the Abstract and the "
            "references as units of their own; each {role: one of " + ", ".join(UNIT_ROLES) + "; "
            "parts: the unit's parts in order, each a list of consecutive segment ids}; every "
            "segment in exactly one part of one unit"
        ),
    },
    "report": {
        "concerns": (
            "each either a link to a concern already found {link: its id, such as F3; role: "
            + ", ".join(UPDATE_ROLES)
            + "; note: one sentence on what this part adds; quotes: from this part only}, or a "
            "new concern {target: the passage it is about, verbatim (the claim, choice, or figure "
            "it questions; not its evidence); different_from; title: at most 12 neutral words; "
            "issue: a falsifiable, proportionate concern, not a verdict; why: why it matters for "
            "validity, interpretation, ethics, or use; solutions: a list; type: one of "
            + ", ".join(CANDIDATE_TYPES)
            + "; severity: major or minor; flaw: the id of the listed major flaw it is an "
            f"instance of, or none; quotes: {_QUOTES}}}"
        ),
        "flaws_to_check": "ids of listed major flaws this part could show",
        "number_checks": (
            "each {expression: the arithmetic the manuscript implies, e.g. 112 - 74; stated: the "
            "figure the manuscript states for it; quote: a verbatim quote containing the stated "
            "figure}"
        ),
    },
    "check": {
        "shown": "true or false",
        "quotes": _QUOTES,
        "reason": "one sentence why",
        "concern": (
            "when shown: the id of the concern already found that it is an instance of, or none"
        ),
        "target": "when shown and no concern fits: the passage the flaw is about, verbatim",
        "different_from": _DIFFERENT_FROM,
    },
    "sweep": {
        "concerns": (
            "each {concern: the distinct problem in one neutral, specific sentence, what and "
            "where; target: the passage it is about, verbatim; items: the ids of the items "
            "listed in the task that raise it, findings (F…) and any check items (C…) listed "
            "there; never a task id; severity: major or minor; flaw: the id of the listed "
            "major flaw it is an instance of, or none}"
        ),
    },
    "screen": {
        "answers": (
            "one per concern, each {id: the concern's id (F…); false_alarm: the id of the common "
            "false alarm it asks for (such as quantitative/fa4), or none; applies: only when "
            "false_alarm is not none, the verbatim passage that makes the request apply here "
            "anyway; omit if there is none}"
        ),
    },
}
"""Each answer's fields, for a host that has no tool schemas to carry them (an app's tool schemas
describe the same fields)."""

Review = dict[str, Any]
Finding = dict[str, Any]
Evidence = dict[str, Any]


# Text, as the host's JavaScript wrote it before these rules moved here.


def _text(value: Any) -> str:
    """JavaScript's String(value ?? "")."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return js_number(value)
    return str(value)


def js_number(value: float | int) -> str:
    """A number as JavaScript prints it: 38 rather than 38.0, 0.00005 rather than 5e-05."""
    if isinstance(value, int):
        return str(value)
    if value != value:
        return "NaN"
    if value in (float("inf"), float("-inf")):
        return "Infinity" if value > 0 else "-Infinity"
    if value.is_integer() and abs(value) < 1e21:
        return str(int(value))
    if 1e-6 <= abs(value) < 1e21:
        return format(Decimal(repr(value)), "f")
    mantissa, exponent = f"{Decimal(repr(value)):e}".split("e")
    mantissa = mantissa.rstrip("0").rstrip(".") if "." in mantissa else mantissa
    sign = "-" if int(exponent) < 0 else "+"
    return f"{mantissa}e{sign}{abs(int(exponent))}"


def short(text: str, n: int) -> str:
    return text if len(text) <= n else f"{text[: n - 1]}…"


def quoted(quotes: list[Evidence], n: int = 3) -> str:
    """Up to `n` distinct quotes, each with its locator."""
    distinct: dict[tuple[str, str], Evidence] = {}
    for q in quotes:
        distinct.setdefault((q["locator"], q["quote"]), q)
    return " | ".join(
        f'[{q["locator"]}] "{short(q["quote"], 200)}"' for q in list(distinct.values())[:n]
    )


def _strip_period(title: str) -> str:
    return title[:-1] if title.endswith(".") else title


# The review's state.


def live(review: Review) -> list[Finding]:
    return [f for f in review["findings"] if f.get("status") not in ("dismissed", "screened")]


def finding_by_id(review: Review, finding_id: str) -> Finding | None:
    return next((f for f in review["findings"] if f["id"] == finding_id), None)


def add_finding(review: Review, fields: dict[str, Any]) -> Finding:
    made = {"flaw_checks": [], "linked_from": [], "discussion": []}
    made.update({k: v for k, v in fields.items() if v is not None})
    made["id"] = f"F{len(review['findings']) + 1}"
    review["findings"].append(made)
    return made


def _add_evidence(f: Finding, quotes: list[Evidence]) -> None:
    seen = {(e["locator"], e["quote"]) for e in f["evidence"]}
    for e in quotes:
        if (e["locator"], e["quote"]) not in seen:
            f["evidence"].append(e)


def _distinct(items: list[Any]) -> list[Any]:
    out: list[Any] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def confirmed(f: Finding) -> bool:
    """A concern a check confirmed: the check is its evidence."""
    return any(a.get("shown") and a.get("quotes_verified") for a in f.get("flaw_checks") or [])


def listed_flaws(knowledge: dict[str, Any], profiles: list[str]) -> list[dict[str, str]]:
    """The listed major flaws for a review: those in any design, then the confirmed profiles'."""
    general = [
        {"id": f"general/{f['id']}", "flaw": f["flaw"]} for f in knowledge["general_major_flaws"]
    ]
    chosen = [
        {"id": f"{p['id']}/{f['id']}", "flaw": f["flaw"]}
        for p in knowledge["profiles"]
        if p["id"] in profiles
        for f in p["major_flaws"]
    ]
    return general + chosen


def _flaw_ids(flaws: list[dict[str, str]]) -> list[str]:
    return [f["id"] for f in flaws]


# Plan, units, and parts.


def merge_short(
    blocks: list[dict[str, Any]], plan: list[dict[str, Any]], min_chars: int = SHORT_SEGMENT_CHARS
) -> list[dict[str, Any]]:
    """The plan without heading-only fragments: a segment shorter than `min_chars` joins the
    next."""
    length = {b["block_id"]: len(b["text"]) for b in blocks}
    merged: list[dict[str, Any]] = []
    carry: dict[str, Any] | None = None
    for segment in plan:
        current = (
            {**segment, "block_ids": [*carry["block_ids"], *segment["block_ids"]]}
            if carry
            else segment
        )
        size = sum(length.get(i, 0) for i in current["block_ids"])
        if size < min_chars:
            carry = current
        else:
            merged.append(current)
            carry = None
    if carry:
        if merged:
            merged[-1]["block_ids"].extend(carry["block_ids"])
        else:
            merged.append(carry)
    return merged


def segment_words(blocks: list[dict[str, Any]], plan: list[dict[str, Any]]) -> dict[str, int]:
    size = {b["block_id"]: len(b["text"].split()) for b in blocks}
    return {s["id"]: sum(size.get(i, 0) for i in s["block_ids"]) for s in plan}


def unit_problems(
    plan: list[dict[str, Any]], proposed: list[dict[str, Any]], words: dict[str, int]
) -> list[str]:
    """What is wrong with a proposed grouping: every segment in exactly one part of one unit, 4 to 5
    units besides the Abstract and the references (3 to 6 accepted), each part consecutive segments
    of PART_MIN_WORDS to PART_WORDS words: a single segment may be longer, and a short part may stay
    when joining either neighbour would pass the most. The Abstract is not checked: it is made one
    part."""
    problems: list[str] = []
    known = {s["id"] for s in plan}
    position = {s["id"]: n for n, s in enumerate(plan)}
    placed = [i for u in proposed for p in (u.get("parts") or []) for i in p]
    unknown = [i for i in placed if i not in known]
    twice = [i for n, i in enumerate(placed) if placed.index(i) != n]
    missing = [s["id"] for s in plan if s["id"] not in placed]
    if unknown:
        problems.append(f"units name unknown segments {', '.join(unknown)}")
    if twice:
        problems.append(f"segments in more than one unit: {', '.join(dict.fromkeys(twice))}")
    if missing:
        problems.append(f"segments in no unit: {', '.join(missing)}")
    reading = [u for u in proposed if u.get("role") not in ("abstract", "references")]
    if len(reading) < 3 or len(reading) > 6:
        problems.append(
            f"{len(reading)} reading units besides the Abstract and the references; make 4 to 5"
        )
    if len([u for u in proposed if u.get("role") == "abstract"]) > 1:
        problems.append("more than one abstract unit")
    if unknown:
        return problems
    for u in reading:
        given = u.get("parts") or []
        parts = [p for p in given if p]
        if len(parts) < len(given):
            problems.append(f"an empty part in the {u['role']} unit")
        sizes = [sum(words[i] for i in part) for part in parts]
        for n, part in enumerate(parts):
            at = [position[i] for i in part]
            if any(k > 0 and p != at[k - 1] + 1 for k, p in enumerate(at)):
                problems.append(
                    f"part {', '.join(part)} is not consecutive segments in the manuscript's order"
                )
            if len(part) > 1 and sizes[n] > PART_WORDS:
                problems.append(
                    f"part {', '.join(part)} has {sizes[n]} words, more than {PART_WORDS}: break "
                    "it at a logical break"
                )
            neighbours = [sizes[k] for k in (n - 1, n + 1) if 0 <= k < len(sizes)]
            joinable = any(m + sizes[n] <= PART_WORDS for m in neighbours)
            if len(parts) > 1 and sizes[n] < PART_MIN_WORDS and joinable:
                problems.append(
                    f"part {', '.join(part)} has {sizes[n]} words, fewer than {PART_MIN_WORDS}: "
                    f"join it with the part before or after it in the {u['role']} unit, whichever "
                    "it belongs with"
                )
    return problems


def make_units(plan: list[dict[str, Any]], proposed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The units in reading order: by the manuscript, the Abstract last; the references are not
    read. The Abstract is one part."""
    position = {s["id"]: n for n, s in enumerate(plan)}

    def first(ids: list[str]) -> float:
        return min((position[i] for i in ids), default=float("inf"))

    shaped = []
    for u in proposed:
        parts = sorted([p for p in (u.get("parts") or []) if p], key=first)
        if u["role"] == "abstract" and parts:
            parts = [[i for p in parts for i in p]]
        shaped.append({"role": u["role"], "parts": parts})
    shaped = [u for u in shaped if u["role"] != "references" and u["parts"]]
    shaped.sort(key=lambda u: (u["role"] == "abstract", first([i for p in u["parts"] for i in p])))
    return [
        {
            "id": f"U{n + 1}",
            "role": u["role"],
            "segment_ids": sorted((i for p in u["parts"] for i in p), key=lambda i: position[i]),
            "parts": u["parts"],
        }
        for n, u in enumerate(shaped)
    ]


def units_of(review: Review) -> list[dict[str, Any]]:
    """The units of a review; one from before reading units has one per segment of the plan."""
    if review.get("units") is not None:
        return review["units"]
    return [
        {"id": s["id"], "role": "other", "segment_ids": [s["id"]]} for s in review.get("plan") or []
    ]


def parts_of(review: Review, unit: dict[str, Any]) -> list[dict[str, Any]]:
    """A unit's parts as orientation marked them; a unit from before parts is one part."""
    plan = {s["id"]: s for s in review.get("plan") or []}
    groups = unit.get("parts") or [unit["segment_ids"]]
    return [
        {
            "unit": unit,
            "index": n,
            "count": len(groups),
            "block_ids": [b for i in ids for b in (plan[i]["block_ids"] if i in plan else [])],
        }
        for n, ids in enumerate(groups)
    ]


def all_parts(review: Review) -> list[dict[str, Any]]:
    """Every part to read, in order, each with its label and the plan segments it touches."""
    parts = [p for u in units_of(review) for p in parts_of(review, u)]
    return [
        {
            **p,
            "label": part_label(review, p),
            "segments": [s["id"] for s in part_segments(review, p)],
        }
        for p in parts
    ]


def part_label(review: Review, part: dict[str, Any]) -> str:
    titles: dict[str, None] = {}
    for block in part["block_ids"]:
        owner = next((s for s in review.get("plan") or [] if block in s["block_ids"]), None)
        if owner and owner.get("title"):
            titles.setdefault(owner["title"], None)
    joined = ", ".join(titles)
    role = part["unit"]["role"]
    return (
        f"{role} part {part['index'] + 1} of {part['count']} ({joined})"
        if part["count"] > 1
        else f"{role} ({joined})"
    )


def part_segments(review: Review, part: dict[str, Any]) -> list[dict[str, Any]]:
    """The plan segments a part touches."""
    return [
        s for s in review.get("plan") or [] if any(b in part["block_ids"] for b in s["block_ids"])
    ]


def segment_of(review: Review, blocks: list[dict[str, Any]], e: Evidence | None) -> str | None:
    """The plan segment holding a quote: where a concern sits in the manuscript's order."""
    if not e:
        return None
    block = next((b for b in blocks if b["locator"] == e["locator"]), None)
    if not block:
        return None
    owner = next((s for s in review.get("plan") or [] if block["block_id"] in s["block_ids"]), None)
    return owner["id"] if owner else None


def blocks_of(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"block_id": b["segment_id"], "locator": b["locator"], "text": b["text"]}
        for b in document["segments"]
    ]


# Orientation.


def orient_task(
    plan: list[dict[str, Any]],
    words: dict[str, int],
    answer: str = "orient",
    propose_profiles: bool = True,
) -> str:
    """The orientation task. A host whose reviewer confirmed the profiles before it (Hermes) leaves
    out the profile proposal."""
    profiles = (
        "the design profiles that fit (at most three, from the listed profiles), each with a "
        "one-line reason citing what shows the design, "
        if propose_profiles
        else ""
    )
    return "\n\n".join(
        [
            f"Task: read the whole manuscript, then answer with {answer}: the initial summary "
            "(summary, analysis, up to five of the authors' own special considerations each "
            "with a verbatim quote, one to four main conclusions quoted verbatim), "
            f"{profiles}and the reading units. Describe; do not evaluate.",
            "Reading units: group the segments below into 4 to 5 units by the manuscript's "
            "structure, each with its role: for an empirical study or a review, introduction, "
            "methods, results, discussion (with the conclusion); for a normative argument, "
            "introduction, argument (one or two units), objections, conclusion; for a legal "
            "analysis, introduction, law (the provisions and cases as stated), analysis, proposals "
            "(with the conclusion). Use the structure the manuscript has. The Abstract is a "
            "unit of its own, and so are the references. Declarations (ethics, funding, interests) "
            "go with the methods, or with the introduction when there are no methods. Every "
            "segment is in exactly one unit.",
            "Parts: break each unit into parts where the manuscript itself breaks: a subsection, "
            "a theme, a case or a provision, an objection with its reply, a table with the "
            "text that reports it. A part is one coherent piece that one close read can hold: "
            f"consecutive segments, together {PART_MIN_WORDS} to {PART_WORDS} words (a single "
            "segment may be longer). A short section (a declaration, a brief subsection, a "
            "short conclusion) joins the part before or after it that it belongs with. A unit "
            "that is one such piece is one part. Do not break a piece of argument to fit the "
            "size. The Abstract is always one part.",
            "Segments (words):\n"
            + "\n".join(f"- {s['id']}: {s['title']} ({words[s['id']]})" for s in plan),
        ]
    )


def orient_answer(
    document: dict[str, Any],
    plan: list[dict[str, Any]],
    available: list[str],
    params: dict[str, Any],
) -> dict[str, Any]:
    """Check an orientation; accepted, it gives the orientation and the units."""
    considerations = (params.get("considerations") or [])[:5]
    conclusions = (params.get("main_conclusions") or [])[:4]
    checked = rules.check_quotes(document, [c.get("quote") for c in considerations] + conclusions)
    problems = list(checked["problems"])
    unknown = [p.get("id") for p in params.get("profiles") or [] if p.get("id") not in available]
    if unknown:
        problems.append(f"unknown profiles: {', '.join(map(_text, unknown))}")
    words = segment_words(blocks_of(document), plan)
    problems += unit_problems(plan, params.get("units") or [], words)
    if problems:
        return {"problems": problems}
    verified = checked["verified"]
    return {
        "problems": [],
        "units": make_units(plan, params.get("units") or []),
        "orientation": {
            "summary": params.get("summary"),
            "analysis": params.get("analysis"),
            "considerations": [
                {
                    "kind": c.get("kind"),
                    "consideration": c.get("consideration"),
                    "quote": verified[i],
                }
                for i, c in enumerate(considerations)
            ],
            "main_conclusions": verified[len(considerations) :],
            "proposed_profiles": (params.get("profiles") or [])[:3],
        },
    }


# Reads.


def register(review: Review) -> str:
    """The concerns found so far, each with the unit that found it and the passage it is about."""
    roles = {u["id"]: u["role"] for u in units_of(review)}
    open_ = [f for f in live(review) if not f.get("number_check")]
    if not open_:
        return "(none yet)"
    lines = []
    for f in open_:
        target = f.get("target")
        about = f' · about [{target["locator"]}] "{short(target["quote"], 140)}"' if target else ""
        lines.append(f"- {f['id']} ({roles.get(f.get('unit') or '', '?')}): {f['title']}{about}")
    return "\n".join(lines)


def _owner_of(review: Review, target: Evidence) -> Finding | None:
    """The concern already found about the same passage (the same block) as `target`, if any."""
    return next(
        (
            f
            for f in live(review)
            if not f.get("number_check")
            and (f.get("target") or {}).get("locator") == target["locator"]
        ),
        None,
    )


def _differs(d: Any, owner: str) -> bool:
    """A different_from that names `owner` with a reason."""
    return isinstance(d, dict) and d.get("id") == owner and bool(_text(d.get("reason")).strip())


def _part_locators(document: dict[str, Any], part: dict[str, Any]) -> list[str]:
    by_block = {b["segment_id"]: b["locator"] for b in document["segments"]}
    return [by_block.get(i, i) for i in part["block_ids"]]


def read_task(
    document: dict[str, Any],
    review: Review,
    part: dict[str, Any],
    flaws: list[dict[str, str]],
    answer: str = "report",
) -> str:
    locators = _part_locators(document, part)
    unit = part["unit"]
    where = "part" if part["count"] > 1 else "unit"
    profiles = ", ".join(review.get("profiles") or []) or "none (general rubric)"
    order = ", ".join(u["role"] for u in units_of(review))
    lines = [
        f"Task: read the {'part of a unit' if part['count'] > 1 else 'unit'} "
        f'"{part_label(review, part)}" '
        f"(blocks {', '.join(locators)}) closely, sentence by sentence and figure by figure, "
        f"with the confirmed design profiles: {profiles}. The manuscript is read in units, in "
        f"this order: {order}; a long unit in parts, in order. Read other parts of the manuscript "
        "when a claim depends on them, and before claiming something is missing, search the "
        "whole manuscript.",
    ]
    if unit["role"] == "abstract":
        lines.append(
            "The Abstract is read last: most of what it says restates claims the concerns below "
            "are about. Link those; write a new concern only for a problem the Abstract itself "
            "has."
        )
    lines += [
        f"Concerns found so far:\n{register(review)}",
        f"Answer with {answer}:",
        f"- concerns: when this {where} bears on a concern above, do not write it again: give "
        f"{{link, role, note, quotes from this {where} only}}. role: restates (this {where} "
        "states the same claim or choice again), relies-on (a claim here depends on it), "
        "contradicts "
        "(a passage here conflicts with it), answers (the authors address it here: a "
        "justification, "
        "a stated limitation, an analysis that meets it). Write a new concern in full: title, "
        "issue, why, solutions, type, severity (your honest judgement), flaw (the listed major "
        "flaw id it is an instance of, or none), target (the passage it is about, verbatim: "
        "the claim, choice, or figure it questions, not its evidence), quotes. One problem "
        "is one concern, however many listed flaws it touches. A concern matching a profile's "
        "common false alarm is not a concern. An empty list is a valid answer.",
        f"- flaws_to_check: the ids of listed major flaws this {where} could show, from: "
        f"{', '.join(_flaw_ids(flaws))}.",
        f"- number_checks: for every total, difference, sum of parts, or percentage the {where} "
        "states: {expression, stated, quote}; for a percentage, write the expression as a "
        "percentage (e.g. 31 / 42 * 100). Do no arithmetic yourself, and do not raise a figure "
        "that may not add up as a concern: the number check is how it is raised. A count that "
        "disagrees with a table or another passage, with nothing to compute, is a concern, "
        "not a number check.",
    ]
    return "\n\n".join(lines)


def read_answer(
    document: dict[str, Any],
    review: Review,
    part: dict[str, Any],
    flaws: list[dict[str, str]],
    params: dict[str, Any],
) -> dict[str, Any]:
    """Check one read's report. A concern already found is not written again: the read links to it
    with a role and quotes from this part, which become typed evidence (a link quoting elsewhere is
    refused). A new concern names its target; a new concern about the same passage as one already
    found is refused unless the read says how it is a different problem. Accepted, the review comes
    back with the links, the new concerns, and a finding per computed mismatch."""
    unit = part["unit"]
    blocks = blocks_of(document)
    known = {f["id"] for f in live(review)}
    flaw_ids = set(_flaw_ids(flaws))
    locators = _part_locators(document, part)
    here = set(locators)
    where = "part" if part["count"] > 1 else "unit"
    problems: list[str] = []
    concerns: list[dict[str, Any]] = params.get("concerns") or []
    for i, c in enumerate(concerns):
        label = f"concern {i + 1}"
        if c.get("link"):
            if c["link"] not in known:
                problems.append(
                    f"{label} links to {c['link']}, which is not a concern found so far"
                )
            if c.get("role") not in UPDATE_ROLES:
                problems.append(
                    f"{label} links to {c['link']}, so it needs role: {', '.join(UPDATE_ROLES)}"
                )
            if not _text(c.get("note")).strip():
                problems.append(
                    f"{label} links to {c['link']}, so it needs a note on what this unit adds"
                )
        elif (
            not c.get("title")
            or not c.get("issue")
            or not c.get("why")
            or c.get("type") not in CANDIDATE_TYPES
            or c.get("severity") not in ("major", "minor")
            or not _text(c.get("target")).strip()
        ):
            problems.append(
                f"{label} is new, so it needs title, issue, why, type, severity, and target"
            )
        elif c.get("flaw") and c["flaw"] != "none" and c["flaw"] not in flaw_ids:
            problems.append(f"{label} names flaw {c['flaw']}, which is not listed")
        if not c.get("quotes"):
            problems.append(f"{label} has no quote")
    quote_sets = [rules.check_quotes(document, c.get("quotes") or []) for c in concerns]
    for i, q in enumerate(quote_sets):
        problems += [f"concern {i + 1}: {p}" for p in q["problems"]]
    # A link is what this part adds: its quotes come from this part.
    for i, q in enumerate(quote_sets):
        elsewhere = (
            [e for e in q["verified"] if e["locator"] not in here]
            if concerns[i].get("link")
            else []
        )
        if elsewhere:
            problems.append(
                f"concern {i + 1} links to {concerns[i]['link']} with quotes from outside this "
                f"{where} ({', '.join('[' + e['locator'] + ']' for e in elsewhere)}): quote only "
                f"blocks {', '.join(locators)}, or leave the link out"
            )
    targets = [
        rules.check_quotes(document, [_text(c.get("target"))])
        if not c.get("link") and _text(c.get("target")).strip()
        else None
        for c in concerns
    ]
    for i, t in enumerate(targets):
        if t:
            problems += [f"concern {i + 1} target: {p}" for p in t["problems"]]
    # One passage, one concern: a second concern about it must say how it is a different problem.
    seen: dict[str, str] = {}
    for i, t in enumerate(targets):
        target = t["verified"][0] if t and t["verified"] else None
        if not target:
            continue
        owner_finding = _owner_of(review, target)
        owner = owner_finding["id"] if owner_finding else seen.get(target["locator"])
        if owner and not _differs(concerns[i].get("different_from"), owner):
            problems.append(
                f"concern {i + 1} is about the same passage as {owner} ([{target['locator']}]): "
                f"link to {owner} with a role, or, if it is a different problem, give "
                "different_from: "
                f'{{id: "{owner}", reason: how it differs, in one sentence}}'
            )
        seen.setdefault(target["locator"], f"concern {i + 1}")
    # A count set against a table's rows has nothing to compute: a concern, not a number check.
    for n in params.get("number_checks") or []:
        if not re.search(r"[-+*/×÷]", _text(n.get("expression"))):
            problems.append(
                f'number check "{_text(n.get("expression"))}" has no arithmetic; raise a count '
                "that disagrees with a table or another passage as a concern"
            )
    numbers = rules.number_checks(document, params.get("number_checks") or [])
    problems += numbers["problems"]
    unknown_flaws = [i for i in params.get("flaws_to_check") or [] if i not in flaw_ids]
    if unknown_flaws:
        problems.append(f"flaws_to_check names unlisted flaws: {', '.join(unknown_flaws)}")
    if problems:
        return {"problems": problems}

    review = copy.deepcopy(review)
    first_segment = (part_segments(review, part) or [{}])[0].get("id")
    added = linked = 0
    for i, c in enumerate(concerns):
        quotes = quote_sets[i]["verified"]
        if c.get("link"):
            target_finding = finding_by_id(review, c["link"])
            target_finding.setdefault("updates", []).append(
                {
                    "unit": unit["id"],
                    "role": c["role"],
                    "note": _text(c.get("note")),
                    "quotes": quotes,
                }
            )
            if c["role"] != "answers":
                _add_evidence(target_finding, quotes)
                target_finding["linked_from"].append(unit["id"])
            linked += 1
        else:
            target = targets[i]["verified"][0]
            fields: dict[str, Any] = {
                "origin": "read",
                "unit": unit["id"],
                "segment_id": segment_of(review, blocks, target) or first_segment,
                "title": c["title"],
                "issue": c["issue"],
                "why": c["why"],
                "solutions": c.get("solutions") or [],
                "type": c["type"],
                "model_severity": c["severity"],
                "target": target,
                "evidence": quotes,
                "flaw": c["flaw"] if c.get("flaw") and c["flaw"] != "none" else None,
                "updates": [],
            }
            if c.get("different_from"):
                d = c["different_from"]
                fields["different_from"] = {
                    "id": _text(d.get("id")),
                    "reason": _text(d.get("reason")),
                }
            add_finding(review, fields)
            added += 1
    for check in numbers["checks"]:
        if check["matches"]:
            continue
        add_finding(
            review,
            {
                "origin": "number",
                "unit": unit["id"],
                "segment_id": segment_of(review, blocks, check["evidence"]) or first_segment,
                "title": (
                    f"The stated {check['stated']} does not follow from {check['expression']} "
                    f"({js_number(check['computed'])})"
                ),
                "issue": (
                    f"The manuscript states {check['stated']}, but {check['expression']} gives "
                    f"{js_number(check['computed'])}."
                ),
                "why": (
                    "A reported figure that does not reconcile with its parts undermines the "
                    "results built on it."
                ),
                "solutions": ["Correct the figure or the numbers it is computed from."],
                "type": "inconsistency",
                "model_severity": "minor",
                "evidence": [check["evidence"]],
                "number_check": check,
            },
        )
        added += 1
    return {
        "problems": [],
        "review": review,
        "added": added,
        "linked": linked,
        "to_check": params.get("flaws_to_check") or [],
    }


# Checks.


def check_task(
    flaw: dict[str, str], segment_titles: list[str], register_text: str, answer: str = "check"
) -> str:
    return "\n\n".join(
        [
            f"Task: flaw check. Flaw {flaw['id']}: {flaw['flaw']}",
            "Reads flagged it as possible in: "
            + ", ".join(f'"{t}"' for t in segment_titles)
            + ". Look there first, and judge it on the whole manuscript.",
            f"Concerns found so far:\n{register_text}",
            f"Does the manuscript show this flaw? Answer with {answer}: shown; the verbatim "
            "quotes that show it (one passage each); one sentence why; and, when shown, concern: "
            "the id of the concern above that this flaw is an instance of, or none. With none, "
            "give target: the passage the flaw is about (the claim, choice, or figure it "
            "questions), "
            "verbatim. If it is not shown, say shown false with no quotes.",
        ]
    )


def check_answer(
    document: dict[str, Any], review: Review, flaw: str, model: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Check one model's answer to one flaw check, made against the concerns found so far: a flaw
    shown is an instance of one of them, or is about a passage none of them is about."""
    known = {f["id"] for f in live(review) if not f.get("number_check")}
    quotes = params.get("quotes") or []
    checked = rules.check_quotes(document, quotes) if quotes else {"verified": [], "problems": []}
    reason = _text(params.get("reason"))
    if not params.get("shown"):
        return {
            "problems": [],
            "answer": {
                "flaw": flaw,
                "model": model,
                "shown": False,
                "quotes_verified": False,
                "quotes": [],
                "reason": reason,
            },
        }
    problems = list(checked["problems"])
    if not checked["verified"] and not problems:
        problems.append("a flaw shown needs at least one verbatim quote")
    concern = (
        _text(params["concern"]) if params.get("concern") and params["concern"] != "none" else None
    )
    target = None
    if concern:
        if concern not in known:
            problems.append(f"concern {concern} is not one of the concerns found so far")
    elif not _text(params.get("target")).strip():
        problems.append("with no concern, give target: the passage the flaw is about")
    else:
        t = rules.check_quotes(document, [_text(params.get("target"))])
        problems += [f"target: {p}" for p in t["problems"]]
        target = t["verified"][0] if t["verified"] else None
        owner = _owner_of(review, target) if target else None
        if owner and not _differs(params.get("different_from"), owner["id"]):
            problems.append(
                f"{owner['id']} is about this passage ([{target['locator']}]): give concern: "
                f'"{owner["id"]}", or, if this is a different problem, different_from: {{id: '
                f'"{owner["id"]}", reason: how it differs, in one sentence}}'
            )
    if problems:
        return {"problems": problems}
    made: dict[str, Any] = {
        "flaw": flaw,
        "model": model,
        "shown": True,
        "quotes_verified": True,
        "quotes": checked["verified"],
        "reason": reason,
    }
    if concern:
        made["concern"] = concern
    elif target:
        made["target"] = target
    if params.get("different_from"):
        d = params["different_from"]
        made["different_from"] = {"id": _text(d.get("id")), "reason": _text(d.get("reason"))}
    return {"problems": [], "answer": made}


def attach_checks(review: Review, results: list[dict[str, Any]]) -> Review:
    """Each check answer that named a concern goes on that concern, with the other answers for its
    flaw that did not show it."""
    review = copy.deepcopy(review)
    for answer in results:
        if answer.get("shown") and answer.get("concern"):
            finding_by_id(review, answer["concern"])["flaw_checks"].append(answer)
    for f in review["findings"]:
        flaws = {a["flaw"] for a in f["flaw_checks"] if a.get("shown")}
        for answer in results:
            if (
                not answer.get("shown")
                and answer["flaw"] in flaws
                and answer not in f["flaw_checks"]
            ):
                f["flaw_checks"].append(answer)
    return review


def merge_number_findings(review: Review) -> Review:
    """One arithmetic mismatch written different ways is one finding."""
    review = copy.deepcopy(review)
    for keep, *rest in rules.merge_number_checks(live(review)):
        for finding_id in rest:
            _fold(
                finding_by_id(review, finding_id), finding_by_id(review, keep), "the same mismatch"
            )
    return review


def _fold(gone: Finding, kept: Finding, reason: str) -> None:
    """`gone` is shown as part of `kept` from now on."""
    _add_evidence(kept, gone["evidence"])
    kept["linked_from"].extend(
        [*gone["linked_from"], gone.get("unit") or gone.get("segment_id") or ""]
    )
    kept["updates"] = [*(kept.get("updates") or []), *(gone.get("updates") or [])]
    kept["flaw_checks"].extend([a for a in gone["flaw_checks"] if a not in kept["flaw_checks"]])
    gone["status"] = "dismissed"
    gone["discussion"].append(f"merged into {kept['id']}: {reason}")


# The sweep.


def _card(f: Finding, titles: dict[str, str], roles: dict[str, str]) -> str:
    """The sweep's view of a finding: its claim and the passage it is about, its quotes, what later
    units added (by role), and the checks that confirmed it."""
    if f.get("number_check"):
        n = f["number_check"]
        computed = js_number(n["computed"])
        return (
            f"{f['id']} · computed · stated {n['stated']}; {n['expression']} = {computed}\n"
            f"  Quote: {quoted([n['evidence']])}"
        )
    later = []
    for u in f.get("updates") or []:
        first = u["quotes"][0] if u["quotes"] else None
        later.append(
            f"{u['role']} in {roles.get(u['unit'], u['unit'])}"
            + (f' [{first["locator"]}] "{short(first["quote"], 120)}"' if first else "")
        )
    shown = [a for a in f["flaw_checks"] if a.get("shown")]
    confirmations = [
        f"{flaw} shown by {', '.join(a['model'] for a in shown if a['flaw'] == flaw)}"
        for flaw in dict.fromkeys(a["flaw"] for a in shown)
    ]
    title = titles.get(f.get("segment_id") or "", "?")
    role = roles.get(f.get("unit") or "", "?")
    lines = [
        f'{f["id"]} · {f["origin"]} in "{title}" ({role} unit) · rated {f["model_severity"]} · '
        f"tagged {f.get('flaw') or 'none'}"
    ]
    if f.get("target"):
        lines.append(f'  About: [{f["target"]["locator"]}] "{short(f["target"]["quote"], 200)}"')
    lines.append(f"  Claim: {_strip_period(f['title'])}. {short(f['issue'], 300)}")
    lines.append(f"  Quotes: {quoted(f['evidence'])}")
    if later:
        lines.append(f"  Later units: {'; '.join(later)}")
    if f.get("different_from"):
        lines.append(
            f"  Different from {f['different_from']['id']}: {f['different_from']['reason']}"
        )
    if confirmations:
        lines.append(f"  Checks: {'; '.join(confirmations)}")
    return "\n".join(lines)


def _check_card(item_id: str, a: dict[str, Any]) -> str:
    lines = [f"{item_id} · check of {a['flaw']} by {a['model']}"]
    if a.get("target"):
        lines.append(f'  About: [{a["target"]["locator"]}] "{short(a["target"]["quote"], 200)}"')
    lines.append(f"  Answer: {short(a['reason'], 300)}")
    lines.append(f"  Quotes: {quoted(a['quotes'])}")
    return "\n".join(lines)


def _sweep_items(
    review: Review, answers: list[dict[str, Any]]
) -> tuple[list[Finding], list[tuple[str, dict[str, Any]]], list[dict[str, Any]]]:
    findings = live(review)
    shown = [
        (f"C{i + 1}", a)
        for i, a in enumerate(a for a in answers if a.get("shown") and not a.get("concern"))
    ]
    not_shown = [a for a in answers if not a.get("shown")]
    return findings, shown, not_shown


def sweep_task(review: Review, answers: list[dict[str, Any]], answer: str = "sweep") -> str:
    """One call over every finding and every check answer that showed a flaw on no concern already
    found, each as a card."""
    findings, shown, not_shown = _sweep_items(review, answers)
    titles = {s["id"]: s["title"] for s in review.get("plan") or []}
    roles = {u["id"]: u["role"] for u in units_of(review)}
    listing = [
        "Findings:",
        "\n\n".join(_card(f, titles, roles) for f in findings),
        "Check answers that showed a listed major flaw on no finding above:"
        if shown
        else "No check answer showed a listed major flaw apart from those on the findings above.",
    ]
    if shown:
        listing.append("\n\n".join(_check_card(i, a) for i, a in shown))
    if not_shown:
        failed = ", ".join(f"{a['flaw']} ({a['model']})" for a in not_shown)
        listing.append(f"Checks that did not show their flaw: {failed}")
    return "\n\n".join(
        [
            "Task: sweep. Reads of the manuscript's units and major-flaw checks produced the "
            "items below, each with the passage it is about, its claim, its quotes, what later "
            "units added, and the checks that confirmed it. Sort them into the distinct concerns "
            "a careful reviewer would put in a report. Keep every item: whether a concern belongs "
            f"in the report is decided later. Answer with {answer}:",
            "- concerns: one per distinct problem. State it in one neutral, specific sentence "
            "(what, and where); give its target, the passage of the manuscript it is about "
            "(the claim, choice, or figure it questions), verbatim; list the items that raise "
            "it; rate it major or minor as the rubric defines severity (judge it yourself; "
            "a read's rating is only its own); and name the listed major flaw it is an instance "
            "of, if any. Items belong together when one sentence honestly describes all of "
            "them and the reviewer would answer them with one response, even when they touch "
            "different listed flaws or quote different places (a choice in the Methods and "
            "the conclusion built on it); sharing a flaw label or a passage alone is not enough. "
            "Put a check item with the concern it shows; check items that show a problem no "
            "finding raises form a new concern.",
            "Every item appears in exactly one concern. A computed item is a concern of its "
            "own, joined only by findings that restate the same mismatch in words. Use the "
            "manuscript to judge.",
            "\n\n".join(listing),
        ]
    )


def sweep_answer(
    document: dict[str, Any],
    review: Review,
    flaws: list[dict[str, str]],
    flagged: list[dict[str, Any]],
    answers: list[dict[str, Any]],
    params: dict[str, Any],
) -> dict[str, Any]:
    """Check the sweep: every item placed exactly once, each target verbatim, each computed
    mismatch a concern of its own. Accepted, the review has one finding per concern. Severity
    still comes from creview's rules: a check answer the sweep places on a concern is the
    evidence; otherwise the sweep's rating, as judgement. `flagged` is [{flaw, segments}], the
    plan segments where reads flagged each flaw."""
    findings, shown, not_shown = _sweep_items(review, answers)
    by_item: dict[str, Any] = {f["id"]: f for f in findings}
    by_item.update(dict(shown))
    checks = {i for i, _ in shown}
    flaw_ids = set(_flaw_ids(flaws))
    problems: list[str] = []
    concerns: list[dict[str, Any]] = params.get("concerns") or []
    placed: dict[str, int] = {}
    for n, c in enumerate(concerns):
        label = f"concern {n + 1}"
        items = c.get("items") or []
        for i in items:
            placed[i] = placed.get(i, 0) + 1
        if not _text(c.get("concern")).strip():
            problems.append(f"{label} has no statement")
        if not _text(c.get("target")).strip():
            problems.append(f"{label} has no target")
        if not items:
            problems.append(f"{label} has no items")
        unknown = [i for i in items if i not in by_item]
        if unknown:
            problems.append(f"{label} names unknown items {', '.join(unknown)}")
        computed = [
            i for i in items if i in by_item and i not in checks and by_item[i].get("number_check")
        ]
        if len(computed) > 1:
            problems.append(
                f"{label} holds two computed items; each mismatch is a concern of its own"
            )
        if computed and any(i in checks for i in items):
            problems.append(f"{label} puts a check item with a computed item")
        if c.get("flaw") and c["flaw"] != "none" and c["flaw"] not in flaw_ids:
            problems.append(f"{label} names {c['flaw']}, which is not a listed major flaw")
    targets = [
        rules.check_quotes(document, [_text(c.get("target"))])
        if _text(c.get("target")).strip()
        else None
        for c in concerns
    ]
    for n, t in enumerate(targets):
        if t:
            problems += [f"concern {n + 1} target: {p}" for p in t["problems"]]
    missing = [i for i in by_item if i not in placed]
    twice = [i for i, count in placed.items() if count > 1]
    if missing:
        problems.append(f"not placed: {', '.join(missing)}")
    if twice:
        problems.append(f"placed more than once: {', '.join(twice)}")
    if problems:
        return {"problems": problems}

    review = copy.deepcopy(review)
    by_item = {i: (finding_by_id(review, i) if i not in checks else a) for i, a in by_item.items()}
    for n, c in enumerate(concerns):
        _apply(review, c, targets[n]["verified"][0], by_item, checks, not_shown, flagged)
    review["sweep"] = params
    return {"problems": [], "review": review}


def _apply(
    review: Review,
    c: dict[str, Any],
    target: Evidence,
    by_item: dict[str, Any],
    checks: set[str],
    not_shown: list[dict[str, Any]],
    flagged: list[dict[str, Any]],
) -> None:
    """One finding per concern: its computed item, else its first finding, else a new one (a concern
    only checks showed)."""
    members = sorted(
        (by_item[i] for i in c["items"] if i not in checks), key=lambda f: int(f["id"][1:])
    )
    shown = [by_item[i] for i in c["items"] if i in checks]
    attached = [a for f in members for a in f["flaw_checks"] if a.get("shown")]
    flaw = (
        c["flaw"]
        if c.get("flaw") and c["flaw"] != "none"
        else next((a["flaw"] for a in [*attached, *shown]), None)
    )
    kept = next((f for f in members if f.get("number_check")), members[0] if members else None)
    if not kept:
        segments = next((k["segments"] for k in flagged if k["flaw"] == flaw), [])
        kept = add_finding(
            review,
            {
                "origin": "check",
                "segment_id": segments[0] if segments else None,
                "title": c["concern"],
                "issue": " ".join(a["reason"] for a in shown),
                "why": (
                    "It is a listed major flaw for this design "
                    f"({_text(flaw) if flaw else 'undefined'})."
                ),
                "solutions": [],
                "type": "method",
                "model_severity": c["severity"],
                "evidence": [q for a in shown for q in a["quotes"]],
            },
        )
    for gone in members:
        if gone is not kept:
            _fold(gone, kept, c["concern"])
    kept["target"] = target
    if kept.get("number_check"):
        return  # a computed mismatch keeps its own title and rule
    if kept["title"] != c["concern"]:
        kept["discussion"].append(f"the read's title: {kept['title']}")
    kept["title"] = c["concern"]
    kept["model_severity"] = c["severity"]
    if flaw is None:
        kept.pop("flaw", None)
    else:
        kept["flaw"] = flaw
    # The checks its members carried, the check items placed on it, and the other answers for
    # those flaws.
    given = [*kept["flaw_checks"], *shown]
    flaws = {a["flaw"] for a in given if a.get("shown")}
    kept["flaw_checks"] = _distinct([*given, *(a for a in not_shown if a["flaw"] in flaws)])


def unswept(
    review: Review,
    flaws: list[dict[str, str]],
    flagged: list[dict[str, Any]],
    answers: list[dict[str, Any]],
) -> Review:
    """Without any sweep: the findings as the reads found them, and each flaw a check showed on no
    concern a finding of its own, so nothing a model's check showed is lost."""
    review = copy.deepcopy(review)
    text = {f["id"]: f["flaw"] for f in flaws}
    for k in flagged:
        given = [a for a in answers if a["flaw"] == k["flaw"]]
        shown = [a for a in given if a.get("shown") and not a.get("concern")]
        if not shown:
            continue
        made = add_finding(
            review,
            {
                "origin": "check",
                "segment_id": k["segments"][0] if k["segments"] else None,
                "title": text[k["flaw"]],
                "issue": " ".join(a["reason"] for a in shown),
                "why": f"It is a listed major flaw for this design ({k['flaw']}).",
                "solutions": [],
                "type": "method",
                "model_severity": "major",
                "evidence": [q for a in shown for q in a["quotes"]],
                "flaw": k["flaw"],
            },
        )
        made["flaw_checks"].extend(given)
    return review


# Confirmation of majors on judgement.


def to_confirm(review: Review, flaws: list[dict[str, str]]) -> list[str]:
    """The concerns rated major with no check confirming them, tagged with a listed major flaw."""
    flaw_ids = set(_flaw_ids(flaws))
    return [
        f["id"]
        for f in live(review)
        if not f.get("number_check")
        and f.get("model_severity") == "major"
        and not confirmed(f)
        and f.get("flaw") in flaw_ids
    ]


def confirm_task(f: Finding, flaw: dict[str, str], answer: str = "check") -> str:
    about = (
        [f'About: [{f["target"]["locator"]}] "{f["target"]["quote"]}"'] if f.get("target") else []
    )
    return "\n\n".join(
        [
            f"Task: flaw check of one concern. Flaw {flaw['id']}: {flaw['flaw']}",
            "\n".join(
                [
                    f"Concern {f['id']}: {f['title']}",
                    *about,
                    f"Issue: {f['issue']}",
                    f"Quotes: {quoted(f['evidence'], 4)}",
                ]
            ),
            "Does the manuscript, at the passage this concern is about, show this flaw? Answer "
            f"with {answer}: shown; the verbatim quotes that show it (one passage each); and "
            "one sentence why. Judge the flaw as listed, not the concern's wording; if the "
            "passage shows a different problem, or the flaw only in a weaker form, say shown "
            "false with no quotes.",
        ]
    )


def confirm_answer(
    document: dict[str, Any], finding_id: str, flaw: str, model: str, params: dict[str, Any]
) -> dict[str, Any]:
    """One model's answer to whether a concern's own passage shows the listed flaw it is tagged
    with; the answer is evidence for that concern."""
    reason = _text(params.get("reason"))
    if not params.get("shown"):
        return {
            "problems": [],
            "answer": {
                "flaw": flaw,
                "model": model,
                "shown": False,
                "quotes_verified": False,
                "quotes": [],
                "reason": reason,
                "concern": finding_id,
            },
        }
    quotes = params.get("quotes") or []
    checked = (
        rules.check_quotes(document, quotes)
        if quotes
        else {"verified": [], "problems": ["a flaw shown needs at least one verbatim quote"]}
    )
    if checked["problems"]:
        return {"problems": checked["problems"]}
    return {
        "problems": [],
        "answer": {
            "flaw": flaw,
            "model": model,
            "shown": True,
            "quotes_verified": True,
            "quotes": checked["verified"],
            "reason": reason,
            "concern": finding_id,
        },
    }


def apply_confirmations(
    review: Review, answers: dict[str, list[dict[str, Any] | None]]
) -> dict[str, Any]:
    """Shown with verified quotes by any model: major on evidence (creview's rule). Shown by none of
    the models that answered: minor, with the earlier rating kept in its discussion. `answers` maps
    each concern asked to its answers, in the order they came (None for a model that gave none)."""
    review = copy.deepcopy(review)
    up = down = 0
    for finding_id, given in answers.items():
        f = finding_by_id(review, finding_id)
        given = [a for a in given if a is not None]
        f["flaw_checks"].extend(given)
        if confirmed(f):
            up += 1
        elif given:
            # Every model that answered said no: the rating was judgement alone.
            f["model_severity"] = "minor"
            f["discussion"].append(
                f"rated major on judgement; the check of {f['flaw']} on its passage did not "
                f"show it ({', '.join(a['model'] for a in given)})"
            )
            down += 1
    return {"review": review, "confirmed": up, "minor": down}


# Screening.


def _acknowledging(review: Review, e: Evidence) -> bool:
    """The authors' own statement of a limitation: under a limitations heading, or recorded as one
    in the orientation."""
    match = re.match(r"^heading:([^/]*)", e["locator"])
    heading = match.group(1) if match else ""
    stated = [
        c["quote"]["quote"]
        for c in (review.get("orientation") or {}).get("considerations") or []
        if c.get("kind") == "limitation"
    ]
    return bool(re.search(r"limitation|weakness", heading, re.I)) or any(
        q in e["quote"] or e["quote"] in q for q in stated
    )


def _open_to_screen(review: Review) -> list[Finding]:
    return [f for f in live(review) if not f.get("number_check") and not confirmed(f)]


def false_alarms(knowledge: dict[str, Any], profiles: list[str]) -> dict[str, str]:
    """The confirmed profiles' common false alarms, by id (such as quantitative/fa4)."""
    return {
        f"{p['id']}/fa{n + 1}": text
        for p in knowledge["profiles"]
        if p["id"] in profiles
        for n, text in enumerate(p["false_alarms"])
    }


def screen_acknowledged(review: Review) -> dict[str, Any]:
    """Set aside each concern whose every quote, and the passage it is about, is the authors' own
    statement of a limitation; then the concerns left for the false-alarm question."""
    review = copy.deepcopy(review)
    for f in _open_to_screen(review):
        quotes = [*f["evidence"], *([f["target"]] if f.get("target") else [])]
        if quotes and all(_acknowledging(review, e) for e in quotes):
            f["status"] = "screened"
            f["screened"] = {
                "kind": "acknowledged",
                "reason": (
                    "its only evidence is the authors' own statement of this limitation; no "
                    "claim it undermines is quoted"
                ),
            }
    return {"review": review, "asked": [f["id"] for f in _open_to_screen(review)]}


def screen_task(
    review: Review, asked: list[str], alarms: dict[str, str], answer: str = "screen"
) -> str:
    concerns = []
    for finding_id in asked:
        f = finding_by_id(review, finding_id)
        about = (
            [f'  About: [{f["target"]["locator"]}] "{short(f["target"]["quote"], 200)}"']
            if f.get("target")
            else []
        )
        concerns.append(
            "\n".join([f"{f['id']}: {f['title']}", *about, f"  Quotes: {quoted(f['evidence'], 2)}"])
        )
    return "\n\n".join(
        [
            "Task: screen. For each concern below, say whether it asks for one of these common "
            "false alarms of the confirmed design profiles:",
            "\n".join(f"- {i}: {text}" for i, text in alarms.items()),
            f"Answer with {answer}, one answer per concern:",
            "- false_alarm: the id of the false alarm the concern asks for, or none. Name one "
            "only when the concern is that request itself, not when it touches the same topic.",
            "- applies: when you name one, the passage of the manuscript, verbatim, that makes "
            "the request apply here anyway (a false alarm often names its condition: a causal "
            "claim, a hypothesis tested, a review type). Omit it when the manuscript has none.",
            "\n\n".join(concerns),
        ]
    )


def screen_answer(
    document: dict[str, Any], asked: list[str], alarms: dict[str, str], params: dict[str, Any]
) -> dict[str, Any]:
    """Check one model's screening answers: for each concern, the false alarm it asks for and what
    makes it apply anyway."""
    ids = set(asked)
    problems: list[str] = []
    given: dict[str, dict[str, Any]] = {}
    for a in params.get("answers") or []:
        if a.get("id") not in ids:
            problems.append(f"{_text(a.get('id'))} is not one of the concerns")
        elif a["id"] in given:
            problems.append(f"{a['id']} is answered twice")
        else:
            given[a["id"]] = a
        if a.get("false_alarm") != "none" and a.get("false_alarm") not in alarms:
            problems.append(
                f"{_text(a.get('id'))} names {_text(a.get('false_alarm'))}, which is not a listed "
                "false alarm"
            )
    missing = [i for i in asked if i not in given]
    if missing:
        problems.append(f"not answered: {', '.join(missing)}")
    entries = list(given.values())
    applies = [
        rules.check_quotes(document, [_text(a.get("applies"))])
        if a.get("false_alarm") != "none" and _text(a.get("applies")).strip()
        else None
        for a in entries
    ]
    for n, q in enumerate(applies):
        if q:
            problems += [f"{entries[n]['id']} applies: {p}" for p in q["problems"]]
    if problems:
        return {"problems": problems}
    result = {}
    for n, a in enumerate(entries):
        answer: dict[str, Any] = {"false_alarm": a.get("false_alarm")}
        if applies[n] and applies[n]["verified"]:
            answer["applies"] = applies[n]["verified"][0]
        result[a["id"]] = answer
    return {"problems": [], "answers": result}


def apply_screening(
    review: Review,
    asked: list[str],
    models: list[str],
    answers: list[dict[str, Any] | None],
    alarms: dict[str, str],
) -> dict[str, Any]:
    """Set aside each concern every model says asks for the same listed false alarm, none quoting a
    passage that makes it apply. `answers` holds each model's answers in the order of `models`
    (None for a model that gave none); with any missing, nothing is set aside."""
    review = copy.deepcopy(review)
    review["screening"] = dict(zip(models, answers, strict=True))
    if all(a is not None for a in answers):
        for finding_id in asked:
            each = [a[finding_id] for a in answers]
            alarm = each[0]["false_alarm"]
            if alarm != "none" and all(
                a["false_alarm"] == alarm and not a.get("applies") for a in each
            ):
                f = finding_by_id(review, finding_id)
                f["status"] = "screened"
                by = f" (named by {' and '.join(models)})" if len(models) > 1 else ""
                f["screened"] = {"kind": "false-alarm", "reason": f"{alarm}: {alarms[alarm]}{by}"}
    return {"review": review}
