"""Deep scan for the Hermes host: creview's analysis pipeline (pipeline.py), one task at a time.

`/journal-article-review deep` runs this before the conversation surfaces findings. The stages and
their rules are the ones a host app runs through the sidecar: orientation (the initial summary and
the reading units, each in parts), one read per part in order with the register of concerns found so
far, a check of each listed major flaw a read flagged, the sweep, a second check of majors on
judgement, and screening. Here the Hermes agent is the only model: `scan next` gives the current
task with its instructions and answer template, and `scan submit` checks the answer with the
pipeline and either records it and returns the next task or refuses it with what to fix. Code does
the steps between.

The conversation then opens with the initial summary and draws the findings one at a time, majors
first, in creview's order; the reviewer's response to each is recorded with their own words. The
findings are never listed or counted to the reviewer.

The scan stores its review state (plan, units, orientation, findings, checks) in its private
directory. The manuscript is re-read from the attached file on every step, and the scan stops if the
file changed.
"""

from __future__ import annotations

import re
import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from filelock import FileLock

from . import findings as rules
from . import pipeline
from .cases import now_iso
from .designs import general_major_flaws, load_profiles
from .errors import ReviewError
from .hermes import agent_max_turns, inspect_profile
from .io import atomic_write_json, data_home, ensure_private_dir, read_json, sha256_file
from .literature import label_citations, lookup_candidates, lookup_query
from .lookups import create_lookup, purge_scan_lookups
from .parsers import parse_document
from .segments import draft_plan
from .session import preflight_summary, record_profiles, session_key
from .settings import trusted_gateway
from .transcript import reviewer_words

SCAN_ID_RE = re.compile(r"^scan-\d{8}T\d{6}Z-[0-9a-f]{8}$")
SCHEMA_VERSION = "2"
# Recorded reviewer responses to surfaced findings; an unrecorded one is still `candidate`.
DISPOSITIONS = ("accepted", "developing", "deferred", "dismissed")
MAX_MINOR_BATCH = 3
# The sweep is refused until every item is placed; after this many refusals the scan goes on
# without it, as a host app does when its sweep fails: the findings as the reads found them.
MAX_SWEEP_REFUSALS = 5
# About three tool calls per task (write, submit, an occasional read), and a few for the rest.
CALLS_PER_TASK = 3
CALLS_OUTSIDE_TASKS = 12
# Before the reads, the checks and the second checks are not known; this many is typical.
EXPECTED_LATER_TASKS = 10
ANSWER = "a JSON object written at answer_path"
REPLACED = {
    "plan": "the reading units are part of orientation",
    "overview": "the initial summary is part of orientation",
    "synthesize": "the tasks after the reads come one by one",
    "sweep": "the sweep is a task like the others",
}


def _scan_root(scan_id: str) -> Path:
    if not SCAN_ID_RE.fullmatch(scan_id):
        raise ReviewError("invalid scan id")
    root = data_home() / "scans" / scan_id
    if not (root / "scan.json").is_file():
        raise ReviewError(f"scan does not exist: {scan_id}")
    return root


def _read(root: Path) -> dict[str, Any]:
    scan = read_json(root / "scan.json")
    if scan.get("schema_version") != SCHEMA_VERSION:
        raise ReviewError(
            "this scan was started by an earlier closed-review, whose deep scan worked "
            "differently; purge it and start a new scan"
        )
    return scan


def _parse_sources(paths: list[tuple[str, Path]]) -> list[dict[str, Any]]:
    sources = []
    for source_id, path in paths:
        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            raise ReviewError(f"input is not a file: {resolved}")
        parsed = parse_document(resolved)
        sources.append(
            {
                "source_id": source_id,
                "path": str(resolved),
                "sha256": sha256_file(resolved),
                "format": parsed.format,
                "warnings": parsed.warnings,
                "segments": parsed.segments,
            }
        )
    return sources


def _current_sources(scan: dict[str, Any]) -> list[dict[str, Any]]:
    """Re-read the attached files; refuse if any changed since the scan started."""
    sources = _parse_sources([(s["source_id"], Path(s["path"])) for s in scan["sources"]])
    for stored, current in zip(scan["sources"], sources, strict=True):
        if stored["sha256"] != current["sha256"]:
            raise ReviewError(
                f"{stored['source_id']} changed since the scan started; start a new scan"
            )
    return sources


def _document(scan: dict[str, Any]) -> dict[str, Any]:
    """The manuscript, as the pipeline reads it (quotes are checked against it alone)."""
    return next(s for s in _current_sources(scan) if s["source_id"] == "manuscript")


def _require_profile() -> None:
    report = inspect_profile(None, live=False)
    if not report["ready"]:
        raise ReviewError(
            "the host no longer satisfies the privacy gate: " + "; ".join(report["problems"])
        )


def _knowledge(profiles: list[str]) -> dict[str, Any]:
    return {"general_major_flaws": general_major_flaws(), "profiles": load_profiles(profiles)}


def _flaws(scan: dict[str, Any]) -> list[dict[str, str]]:
    return pipeline.listed_flaws(_knowledge(scan["profiles"]), scan["profiles"])


def _alarms(scan: dict[str, Any]) -> dict[str, str]:
    return pipeline.false_alarms(_knowledge(scan["profiles"]), scan["profiles"])


def _model() -> str:
    """Who answers: the Hermes agent, on the trusted gateway's model."""
    return trusted_gateway()["model"] or "hermes-agent"


def start_scan(
    manuscript: Path,
    supplements: list[Path] | None = None,
    session: str | None = None,
    *,
    profiles: list[str],
    confirmation: str,
) -> dict[str, Any]:
    """`profiles` are the design profiles the reviewer confirmed (none means the general rubric
    alone); `confirmation` is the reviewer's own words confirming that choice."""
    key, source = session_key(session)
    preflight = preflight_summary(key, source)
    if preflight["status"] != "passed":
        raise ReviewError("run `creview session start` in this session before a deep scan")
    confirmed = load_profiles(profiles)
    # Only a reply sent after `creview session start` counts: the opening message's policy
    # confirmation ("I confirm that") is not a confirmation of the design profiles.
    confirmed_by = reviewer_words(
        confirmation,
        hermes_session=source == "hermes_session",
        what="the design-profile confirmation",
        since=preflight["checked_at"],
        min_chars=8,
    )
    if key is not None:
        record_profiles(key, [p["id"] for p in confirmed], confirmed_by)
    paths = [("manuscript", manuscript)] + [
        (f"supplement-{index}", path) for index, path in enumerate(supplements or [], start=1)
    ]
    sources = _parse_sources(paths)
    scan_id = f"scan-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"
    root = ensure_private_dir(
        ensure_private_dir(ensure_private_dir(data_home()) / "scans") / scan_id
    )
    ensure_private_dir(root / "answers")
    document = sources[0]
    drafted = draft_plan([{"source_id": "manuscript", "segments": document["segments"]}])
    plan = pipeline.merge_short(
        pipeline.blocks_of(document),
        [
            {"id": s["id"], "title": s["title"], "block_ids": s["block_ids"]}
            for s in drafted["segments"]
        ],
    )
    chosen = [p["id"] for p in confirmed]
    scan = {
        "schema_version": SCHEMA_VERSION,
        "scan_id": scan_id,
        "created_at": now_iso(),
        "session_id": key,
        "session_source": source,
        "sources": [
            {k: s[k] for k in ("source_id", "path", "sha256", "format", "warnings")}
            | {"block_count": len(s["segments"])}
            for s in sources
        ],
        "profiles": chosen,
        "profile_confirmation": confirmed_by,
        "model": _model(),
        "phase": "orient",
        "step": 0,
        "review": {
            "id": scan_id,
            "doc_id": "manuscript",
            "findings": [],
            "plan": plan,
            "profiles": chosen,
        },
        "flagged": [],
        "results": [],
        "confirm": {"asked": [], "answers": {}},
        "screen": {"asked": []},
        "sweep_refusals": 0,
        "surfaced": {},
    }
    atomic_write_json(root / "scan.json", scan)
    return {
        "scan_id": scan_id,
        "sources": scan["sources"],
        "profiles": chosen,
        "segments": [{"id": s["id"], "title": s["title"]} for s in plan],
        "next": f"creview scan next {scan_id}",
    }


def _parts(scan: dict[str, Any]) -> list[dict[str, Any]]:
    return pipeline.all_parts(scan["review"])


def _wire(part: dict[str, Any]) -> dict[str, Any]:
    return {k: part[k] for k in ("unit", "index", "count", "block_ids")}


def _budget_warnings(scan: dict[str, Any]) -> list[str]:
    """Hermes caps tool calls per turn; tell the reviewer when the scan will pause part-way."""
    calls = CALLS_PER_TASK * (len(_parts(scan)) + EXPECTED_LATER_TASKS) + CALLS_OUTSIDE_TASKS
    max_turns = agent_max_turns()
    if max_turns and calls > max_turns:
        return [
            f"the scan needs about {calls} tool calls, more than the profile's agent.max_turns "
            f"({max_turns}), so Hermes will pause it part-way. Tell the reviewer that they may "
            "need to reply 'continue'; the scan resumes from creview scan next"
        ]
    return []


def _task_id(scan: dict[str, Any]) -> str:
    return f"{scan['phase']}-{scan['step'] + 1}"


def _template(stage: str) -> dict[str, Any]:
    empty = {"shown": False, "reason": "", "concern": "none", "summary": "", "analysis": ""}
    return {name: empty.get(name, []) for name in pipeline.ANSWER_FIELDS[stage]}


def _task(
    scan: dict[str, Any], root: Path, document: dict[str, Any], flaws: list[dict[str, str]]
) -> dict[str, Any]:
    """The current task: what to answer, with its instructions, template, and fields."""
    stage = scan["phase"]
    review = scan["review"]
    extra: dict[str, Any] = {}
    if stage == "orient":
        words = pipeline.segment_words(pipeline.blocks_of(document), review["plan"])
        text = pipeline.orient_task(review["plan"], words, ANSWER, propose_profiles=False)
        tool, total = "orient", 1
    elif stage == "read":
        parts = _parts(scan)
        part = parts[scan["step"]]
        text = pipeline.read_task(document, review, _wire(part), flaws, ANSWER)
        tool, total = "report", len(parts)
        blocks = {b["segment_id"]: b for b in document["segments"]}
        extra = {
            "part": part["label"],
            "content": [
                {"locator": blocks[i]["locator"], "text": blocks[i]["text"]}
                for i in part["block_ids"]
                if i in blocks
            ],
            "major_flaws": flaws,
            "false_alarms": _alarms(scan),
        }
    elif stage == "check":
        item = scan["flagged"][scan["step"]]
        flaw = next(f for f in flaws if f["id"] == item["flaw"])
        titles = {s["id"]: s["title"] for s in review["plan"]}
        segments = [titles.get(s, s) for s in item["segments"]]
        text = pipeline.check_task(flaw, segments, scan["register"], ANSWER)
        tool, total = "check", len(scan["flagged"])
    elif stage == "sweep":
        text = pipeline.sweep_task(review, scan["results"], ANSWER)
        tool, total = "sweep", 1
        extra = {"major_flaws": flaws}
    elif stage == "confirm":
        asked = scan["confirm"]["asked"]
        f = pipeline.finding_by_id(review, asked[scan["step"]])
        flaw = next(x for x in flaws if x["id"] == f["flaw"])
        text = pipeline.confirm_task(f, flaw, ANSWER)
        tool, total = "check", len(asked)
    elif stage == "screen":
        text = pipeline.screen_task(review, scan["screen"]["asked"], _alarms(scan), ANSWER)
        tool, total = "screen", 1
    else:
        raise ReviewError(f"the scan is in {stage}; {_phase_next(scan)}")
    task_id = _task_id(scan)
    answer_path = root / "answers" / f"{task_id}.json"
    return {
        "scan_id": scan["scan_id"],
        "task": {"id": task_id, "stage": stage, "number": scan["step"] + 1, "of": total},
        **extra,
        "answer_path": str(answer_path),
        "answer_template": {"task_id": task_id, **_template(tool)},
        "answer_fields": pipeline.ANSWER_FIELDS[tool],
        "instructions": text,
        "how_to_answer": (
            f"Write answer_template, filled in, as a new file at {answer_path}, then run "
            f"creview scan submit {scan['scan_id']} {answer_path}; it returns the next task. "
            "The manuscript is the attached file; read any part of it you need. Do not tell the "
            "reviewer about concerns, their number, or their content during the scan; report "
            "progress only as the stage and task number."
        ),
    }


def next_task(scan_id: str) -> dict[str, Any]:
    _require_profile()
    root = _scan_root(scan_id)
    scan = _read(root)
    if scan["phase"] == "ready":
        return {"scan_id": scan_id, "state": "ready", "next": _phase_next(scan)}
    return _task(scan, root, _document(scan), _flaws(scan))


def submit_task(scan_id: str, answer_path: Path) -> dict[str, Any]:
    """Check the answer to the current task with the pipeline; record it and advance, or refuse
    it with what to fix."""
    _require_profile()
    root = _scan_root(scan_id)
    answer = read_json(answer_path)
    if not isinstance(answer, dict):
        raise ReviewError("the answer must be a JSON object")
    with FileLock(str(root / ".lock")):
        scan = _read(root)
        if scan["phase"] == "ready":
            raise ReviewError("the scan is finished; " + _phase_next(scan))
        if answer.get("task_id") != _task_id(scan):
            raise ReviewError(
                f"the answer is not for the current task ({_task_id(scan)}): creview scan next "
                f"{scan_id}"
            )
        params = {k: v for k, v in answer.items() if k != "task_id"}
        # Parsed once per submission: a PDF is slow to parse.
        document, flaws = _document(scan), _flaws(scan)
        try:
            recorded = _accept(scan, root, params, document, flaws)
        finally:
            # A refused sweep still counts toward MAX_SWEEP_REFUSALS.
            scan["updated_at"] = now_iso()
            warnings = scan.pop("warnings", None)
            atomic_write_json(root / "scan.json", scan)
    result: dict[str, Any] = {"scan_id": scan_id, "recorded": recorded, "state": scan["phase"]}
    if warnings:
        # Once, with the reading units: the reviewer hears it before the reads start.
        result["warnings"] = warnings
    if scan["phase"] == "ready":
        result["next"] = _phase_next(scan)
    else:
        result["next_task"] = _task(scan, root, document, flaws)
    return result


def _refuse(problems: list[str]) -> None:
    raise ReviewError("answer refused: " + "; ".join(problems))


def _accept(
    scan: dict[str, Any],
    root: Path,
    params: dict[str, Any],
    document: dict[str, Any],
    flaws: list[dict[str, str]],
) -> str:
    """Apply one accepted answer and move to the next task; what was recorded, in a few words.
    A refused answer changes nothing but the sweep's refusal count."""
    stage = scan["phase"]
    review = scan["review"]
    if stage == "orient":
        r = pipeline.orient_answer(document, review["plan"], [], params)
        if r["problems"]:
            _refuse(r["problems"])
        review.update(units=r["units"], orientation=r["orientation"])
        _advance(scan, "read")
        scan["warnings"] = _budget_warnings(scan)
        return f"the initial summary and {len(_parts(scan))} parts to read"
    if stage == "read":
        part = _parts(scan)[scan["step"]]
        r = pipeline.read_answer(document, review, _wire(part), flaws, params)
        if r["problems"]:
            _refuse(r["problems"])
        scan["review"] = r["review"]
        known = {f["id"] for f in flaws}
        flagged = {k["flaw"]: k for k in scan["flagged"]}
        for flaw in r["to_check"]:
            if flaw in known:
                item = flagged.setdefault(flaw, {"flaw": flaw, "segments": []})
                item["segments"] += [s for s in part["segments"] if s not in item["segments"]]
        scan["flagged"] = list(flagged.values())
        if scan["step"] + 1 < len(_parts(scan)):
            scan["step"] += 1
        else:
            scan["register"] = pipeline.register(scan["review"])
            _after_reads(scan, root)
        return f"{r['added']} new, {r['linked']} linked"
    if stage == "check":
        flaw = scan["flagged"][scan["step"]]["flaw"]
        r = pipeline.check_answer(document, review, flaw, scan["model"], params)
        if r["problems"]:
            _refuse(r["problems"])
        scan["results"].append(r["answer"])
        if scan["step"] + 1 < len(scan["flagged"]):
            scan["step"] += 1
        else:
            _after_checks(scan, root)
        return "recorded"
    if stage == "sweep":
        r = pipeline.sweep_answer(document, review, flaws, scan["flagged"], scan["results"], params)
        if r["problems"]:
            scan["sweep_refusals"] += 1
            if scan["sweep_refusals"] < MAX_SWEEP_REFUSALS:
                _refuse(r["problems"])
            scan["review"] = pipeline.unswept(review, flaws, scan["flagged"], scan["results"])
            _after_sweep(scan, flaws)
            return (
                "the sweep was refused too often: the findings stay as the reads found them, and "
                "each flaw a check showed on no concern is a finding of its own"
            )
        scan["review"] = r["review"]
        _after_sweep(scan, flaws)
        return "the concerns"
    if stage == "confirm":
        fid = scan["confirm"]["asked"][scan["step"]]
        f = pipeline.finding_by_id(review, fid)
        r = pipeline.confirm_answer(document, fid, f["flaw"], scan["model"], params)
        if r["problems"]:
            _refuse(r["problems"])
        scan["confirm"]["answers"][fid] = [r["answer"]]
        if scan["step"] + 1 < len(scan["confirm"]["asked"]):
            scan["step"] += 1
        else:
            asked = scan["confirm"]["asked"]
            answers = {i: scan["confirm"]["answers"].get(i, []) for i in asked}
            scan["review"] = pipeline.apply_confirmations(review, answers)["review"]
            _screen(scan)
        return "recorded"
    if stage == "screen":
        alarms = _alarms(scan)
        asked = scan["screen"]["asked"]
        r = pipeline.screen_answer(document, asked, alarms, params)
        if r["problems"]:
            _refuse(r["problems"])
        applied = pipeline.apply_screening(review, asked, [scan["model"]], [r["answers"]], alarms)
        scan["review"] = applied["review"]
        _finish(scan)
        return "the screening"
    raise ReviewError(f"the scan is in {stage}")


def _advance(scan: dict[str, Any], phase: str) -> None:
    scan.update(phase=phase, step=0)


def _after_reads(scan: dict[str, Any], root: Path) -> None:
    if scan["flagged"]:
        _advance(scan, "check")
    else:
        _after_checks(scan, root)


def _after_checks(scan: dict[str, Any], root: Path) -> None:
    """Each check answer goes on the concern it named; one mismatch written two ways is one
    finding. The state before the sweep is kept beside the scan."""
    review = dict(scan["review"], checks=scan["results"])
    review = pipeline.attach_checks(review, scan["results"])
    scan["review"] = pipeline.merge_number_findings(review)
    presweep = {
        "findings": scan["review"]["findings"],
        "checks": scan["results"],
        "flagged": scan["flagged"],
    }
    atomic_write_json(root / "presweep.json", presweep)
    _advance(scan, "sweep")


def _after_sweep(scan: dict[str, Any], flaws: list[dict[str, str]]) -> None:
    asked = pipeline.to_confirm(scan["review"], flaws)
    scan["confirm"] = {"asked": asked, "answers": {}}
    if asked:
        _advance(scan, "confirm")
    else:
        _screen(scan)


def _screen(scan: dict[str, Any]) -> None:
    acknowledged = pipeline.screen_acknowledged(scan["review"])
    scan["review"] = acknowledged["review"]
    scan["screen"] = {"asked": acknowledged["asked"]}
    if _alarms(scan) and acknowledged["asked"]:
        _advance(scan, "screen")
    else:
        _finish(scan)


def _finish(scan: dict[str, Any]) -> None:
    scan["review"]["analysed"] = True
    _advance(scan, "ready")


def _phase_next(scan: dict[str, Any]) -> str:
    scan_id = scan["scan_id"]
    if scan["phase"] == "ready":
        return f"creview scan candidate {scan_id}"
    return f"creview scan next {scan_id}"


def replaced(command: str) -> dict[str, Any]:
    """A command of the earlier deep scan, which this one does not have."""
    raise ReviewError(
        f"scan {command} is no longer part of the deep scan ({REPLACED[command]}); run creview "
        "scan next SCAN for the current task"
    )


# The conversation.


def _order(scan: dict[str, Any]) -> dict[str, Any]:
    """creview's order: majors on evidence, then on judgement, each in plan order; then minors,
    verifiable ones first; minors past the first nine wait in a reserve."""
    segments = [s["id"] for s in scan["review"]["plan"]]
    return rules.order(pipeline.live(scan["review"]), segments)


def _literature(
    scan: dict[str, Any], f: dict[str, Any], blocks: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """creview's labels for the works a finding cites, and pending lookups for them."""
    texts = [f["title"], f["issue"], f["why"], *(f.get("solutions") or [])]
    labelled = label_citations([t for t in texts if t], blocks)
    lookups = []
    for item in lookup_candidates(labelled):
        request = create_lookup(
            None,
            "crossref",
            lookup_query(item),
            session=scan["session_id"],
            scan_id=scan["scan_id"],
        )
        lookups.append(
            {
                "request_id": request["request_id"],
                "citation": item["citation"],
                "label": item["label"],
                "query": request["query"],
                "url": request["url"],
            }
        )
    return labelled, lookups


def _presented(scan: dict[str, Any], f: dict[str, Any], rated: dict[str, Any]) -> dict[str, Any]:
    """A finding as the agent presents it: the concern, the passage it is about, its evidence,
    what later units added (the authors' own answers among them), and why creview rated it."""
    review = scan["review"]
    roles = {u["id"]: u["role"] for u in pipeline.units_of(review)}
    titles = {s["id"]: s["title"] for s in review["plan"]}
    later = [
        {
            "unit": roles.get(u["unit"], u["unit"]),
            "role": u["role"],
            "note": u["note"],
            "quotes": u["quotes"],
        }
        for u in f.get("updates") or []
    ]
    return {
        "id": f["id"],
        "concern": f["title"],
        "potential_issue": f["issue"],
        "why_it_matters": f["why"],
        "solution_candidates": f.get("solutions") or [],
        "type": f["type"],
        "severity": rated["severity"],
        "severity_basis": rated["reasons"],
        "basis": rated["basis"],
        "major_flaw": f.get("flaw"),
        "about": f.get("target"),
        "found_in": {
            "unit": roles.get(f.get("unit") or ""),
            "segment": titles.get(f.get("segment_id") or ""),
        },
        "evidence": f["evidence"],
        "later_units": [u for u in later if u["role"] != "answers"],
        "authors_answers": [u for u in later if u["role"] == "answers"],
        "checks": [
            {k: a[k] for k in ("flaw", "model", "shown", "reason")} for a in f["flaw_checks"]
        ],
        "verifiable": rules._verifiable(f),
        **({"computed_check": f["number_check"]} if f.get("number_check") else {}),
    }


OVERVIEW_INSTRUCTIONS = (
    "Before anything else, present this initial summary to the reviewer as stored: the summary, "
    "the analysis (methods, models, and frameworks), and the article's own special "
    "considerations with their quotes. It was written before the scan; do not add findings or "
    "evaluation to it. Tell the reviewer once that you can propose literature lookups (Crossref "
    "or OpenAlex, each exact query run only with their approval) where a point depends on "
    "literature, and that they can ask for one at any time. Then continue."
)


def _instructions(shape: str, ids: str, scan_id: str) -> str:
    return (
        f"{shape}, following the development contract, and present only what is returned here, "
        "never other findings from memory. Open each with its context: in one or two sentences, "
        "what the authors do at the passage it is about (`about`, in the unit and segment named "
        "by `found_in`). In why it matters, give the strongest reply the authors could make from "
        "their own manuscript, starting from `authors_answers` (passages where the authors "
        "address it) when there are any, citing where it says so, and why the concern survives "
        "it, so the reviewer can judge it quickly; if the reply answers the concern, say so "
        "plainly. Say what each check found. For a computed_check, show the expression and the "
        "stated figure, and ask the reviewer to confirm the expression is what the manuscript "
        "implies. literature gives creview's label for each work the record cites; use exactly "
        "those labels, and label any content_claim (what a work argues or requires) model_lead, "
        "since only the source itself can confirm it. lookups are prepared Crossref requests, "
        "not yet run: show each one's exact query and URL in the literature context and ask "
        "whether to run it; run one only after the reviewer approves it, with creview lookup "
        "run REQUEST_ID --approval-statement and their words. Anything else you say about what a "
        "named source argues is model_lead. Do not mention how many candidates remain or what "
        "they concern, and never refer to one not yet surfaced, not even to suggest combining it "
        "with this one. Then ask for the reviewer's view and end your turn. When the reviewer "
        f"responds, record each of {ids} with creview scan record {scan_id} ID DISPOSITION "
        f"({', '.join(DISPOSITIONS)}); scan candidate refuses more candidates until every one "
        "shown has a recorded response."
    )


def next_candidate(scan_id: str, *, reserve: bool = False) -> dict[str, Any]:
    """The next findings: one major at a time in creview's order, then minors in batches of up to
    three. Each must have a recorded response before the next call. Minors beyond the first nine
    are a reserve, surfaced only with `reserve`."""
    root = _scan_root(scan_id)
    with FileLock(str(root / ".lock")):
        scan = _read(root)
        if scan["phase"] != "ready":
            raise ReviewError(f"the scan is in {scan['phase']}; {_phase_next(scan)}")
        surfaced = scan["surfaced"]
        first = not scan.get("overview_presented_at") and not surfaced
        ordered = _order(scan)
        everything = ordered["order"] + ordered["reserve"]
        rated = {o["id"]: o for o in everything}
        held = {o["id"] for o in ordered["reserve"]}
        waiting = [o["id"] for o in everything if o["id"] not in surfaced]
        reserve_left = any(i in held for i in waiting)
        if not reserve:
            waiting = [i for i in waiting if i not in held]
        unanswered = [i for i, s in surfaced.items() if not s.get("disposition")]
        if unanswered and waiting:
            raise ReviewError(
                f"record the reviewer's response to {', '.join(unanswered)} first: creview scan "
                f"record {scan_id} ID {'|'.join(DISPOSITIONS)}. If the reviewer has not answered, "
                "end the turn and wait"
            )
        opening = {}
        if first:
            scan["overview_presented_at"] = now_iso()
            orientation = scan["review"].get("orientation") or {}
            keys = ("summary", "analysis", "considerations", "main_conclusions")
            opening = {
                "overview": {k: orientation.get(k) for k in keys},
                "overview_instructions": OVERVIEW_INSTRUCTIONS,
            }
        if not waiting:
            atomic_write_json(root / "scan.json", scan)
            return {
                "scan_id": scan_id,
                **opening,
                "candidates": [],
                "more_available": False,
                "next_severity": None,
                "reserve_available": reserve_left,
            }
        if rated[waiting[0]]["severity"] == "major":
            batch = waiting[:1]
        else:
            batch = [i for i in waiting if rated[i]["severity"] == "minor"][:MAX_MINOR_BATCH]
        # Build everything first: a failure here must not leave a finding marked as shown.
        blocks = _document(scan)["segments"]
        presented = []
        for fid in batch:
            f = pipeline.finding_by_id(scan["review"], fid)
            record = _presented(scan, f, rated[fid])
            record["literature"], record["lookups"] = _literature(scan, f, blocks)
            presented.append(record)
        for fid in batch:
            surfaced[fid] = {"surfaced_at": now_iso()}
        atomic_write_json(root / "scan.json", scan)
    rest = [i for i in waiting if i not in batch]
    if rated[batch[0]]["severity"] == "minor":
        shape = "Present these minor candidates together as one batch of issue records"
    else:
        shape = "Present this major candidate as the current issue record"
    return {
        "scan_id": scan_id,
        **opening,
        "candidates": presented,
        "more_available": bool(rest),
        "reserve_available": reserve_left and not rest,
        # Lets the agent ask whether to go on to minors before surfacing any.
        "next_severity": rated[rest[0]]["severity"] if rest else None,
        "instructions": _instructions(shape, " ".join(batch), scan_id),
    }


def record_response(scan_id: str, finding_id: str, disposition: str, words: str) -> dict[str, Any]:
    """Record the reviewer's disposition of a surfaced finding; it can be revised later.

    `words` must quote the reviewer's reply, sent after the finding was shown."""
    disposition = disposition.strip().lower()
    if disposition not in DISPOSITIONS:
        raise ReviewError(f"disposition must be one of {', '.join(DISPOSITIONS)}")
    root = _scan_root(scan_id)
    with FileLock(str(root / ".lock")):
        scan = _read(root)
        shown = scan["surfaced"].get(finding_id)
        if shown is None:
            raise ReviewError(f"{finding_id} has not been surfaced to the reviewer")
        reply = reviewer_words(
            words,
            hermes_session=scan.get("session_source") == "hermes_session",
            what=f"the response to {finding_id}",
            since=shown["surfaced_at"],
        )
        shown.update(disposition=disposition, responded_at=now_iso(), response=reply)
        scan["updated_at"] = now_iso()
        atomic_write_json(root / "scan.json", scan)
    return {
        "scan_id": scan_id,
        "id": finding_id,
        "disposition": disposition,
        "records": _record_counts(scan),
    }


def _record_counts(scan: dict[str, Any]) -> dict[str, int]:
    """Status counts over surfaced findings only; unanswered ones count as `candidate`."""
    counts = {name: 0 for name in ("accepted", "developing", "candidate", "deferred", "dismissed")}
    for shown in scan["surfaced"].values():
        counts[shown.get("disposition") or "candidate"] += 1
    return counts


def scan_status(scan_id: str) -> dict[str, Any]:
    """Progress the reviewer may see; never the number or content of the findings not yet
    shown."""
    root = _scan_root(scan_id)
    scan = _read(root)
    phase = scan["phase"]
    total = {
        "orient": 1,
        "read": len(_parts(scan)) if scan["review"].get("units") else 0,
        "check": len(scan["flagged"]),
        "sweep": 1,
        "confirm": len(scan["confirm"]["asked"]),
        "screen": 1,
    }.get(phase, 0)
    return {
        "scan_id": scan_id,
        "phase": phase,
        "task": {"number": scan["step"] + 1, "of": total} if phase != "ready" else None,
        "surfaced": len(scan["surfaced"]),
        "records": _record_counts(scan),
        "next": _phase_next(scan),
    }


def purge_scan(scan_id: str, confirmation: str) -> dict[str, Any]:
    root = _scan_root(scan_id)
    if confirmation != scan_id:
        raise ReviewError("confirm by repeating the scan id")
    session = read_json(root / "scan.json").get("session_id")
    lookups = purge_scan_lookups(session, scan_id) if session else 0
    shutil.rmtree(root)
    return {"scan_id": scan_id, "purged": True, "lookups_removed": lookups}
