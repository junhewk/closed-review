"""Deep scan: a sequential, segment-by-segment search that builds a private candidate pool.

`/journal-article-review deep` runs this before the conversation surfaces candidates. Each logical
segment is reviewed in independent passes (light 1, medium 2, high 3), one after another, with the
whole manuscript available. Every candidate must quote the manuscript verbatim at a real locator,
or the submission is refused. Each segment's first pass also records a neutral summary of what the
segment says and does. Candidates that cite the same passage are merged, the agent screens the
merged pool for severity and false alarms, and writes an article overview from the segment
summaries. The conversation opens with that overview and then draws one kept candidate at a time,
each with the summaries of the segments it cites as context. The pool is never listed or counted to
the reviewer.

The scan stores only its plan, the segment summaries and overview, and the candidate pool. The
manuscript is re-read from the attached file on every step, and the scan stops if the file changed.
"""

from __future__ import annotations

import ast
import operator
import re
import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from filelock import FileLock

from .cases import now_iso
from .designs import general_major_flaws, load_profiles
from .errors import ReviewError
from .hermes import agent_max_turns, inspect_profile
from .io import atomic_write_json, data_home, ensure_private_dir, read_json, sha256_file
from .literature import label_citations, lookup_candidates, lookup_query
from .lookups import create_lookup, purge_scan_lookups
from .parsers import parse_document
from .segments import TIER_PASSES, draft_plan, outline, segment_blocks, validate_plan
from .session import preflight_summary, record_profiles, session_key
from .transcript import reviewer_words

SCAN_ID_RE = re.compile(r"^scan-\d{8}T\d{6}Z-[0-9a-f]{8}$")
SEVERITIES = ("major", "minor")
CANDIDATE_TYPES = {
    "inconsistency": "two statements in the manuscript contradict each other; quote both",
    "unsupported": "a claim or conclusion the paper's data, sources, or argument do not support",
    "argument": "a gap or error in the reasoning",
    "method": "a problem in the design, analysis, or procedure",
    "reporting": "something needed to judge the work is not reported",
    "other": "anything else",
}
CANDIDATE_FIELDS = {
    "potential_issue": "a falsifiable, proportionate concern, not a verdict",
    "why_it_matters": "the consequence for validity, interpretation, ethics, or use",
    "severity": (
        "major or minor, your judgement; creview counts it as one vote, so be honest rather than "
        "cautious"
    ),
    "type": "one of: " + ", ".join(CANDIDATE_TYPES),
    "profile_area": "the design profile area this falls under, if any",
    "evidence": (
        "one or more {source_id, locator, quote} with the quote copied verbatim; creview finds "
        "the locator of a quote from another segment if it is wrong or left empty"
    ),
    "solution_candidates": "proportionate ways the authors could resolve it",
    "concern_key": (
        "a short slug naming the concern. Use a key from concern_register when this candidate "
        "raises the same concern as that one, wherever it is stated (it then counts as an "
        "independent confirmation); otherwise give a new key with concern_label"
    ),
    "concern_label": "for a new concern_key: the concern in at most 15 neutral words",
    "major_flaw": (
        "the id of the entry in major_flaws this candidate is an instance of, when its evidence "
        "shows that flaw, or none"
    ),
}
MAX_LABEL_WORDS = 15
NUMBER_CHECK_FIELDS = {
    "expression": "the arithmetic the manuscript implies (+ - * /, parentheses), e.g. 112 - 74",
    "stated": "the number the manuscript states for it, e.g. 42 (a percentage without %)",
    "quote": "a verbatim quote containing the stated number (locator optional)",
}
SUMMARY_FIELD = (
    "two or three neutral sentences on what this segment says and does: its claims, data or "
    "sources, and the methods, models, or frameworks it uses; no evaluation"
)
# The initial summary is written before any pass, so it cannot preview a candidate. Its
# considerations are the article's own: what the authors themselves single out, quoted.
SPECIAL_KINDS = {
    "scope": "what the authors include or exclude, and why",
    "limitation": "a limitation the authors acknowledge",
    "ethics": "approvals, safeguards, or ethical issues the authors raise",
    "context": "the setting, jurisdiction, population, or circumstances the authors flag",
    "choice": "a methodological or conceptual choice the authors single out and justify",
}
OVERVIEW_FIELDS = {
    "summary": "what the article asks, what it does, and what it concludes, in a short paragraph",
    "analysis": (
        "the design, the data or sources, the analytic methods, and the theoretical models or "
        "frameworks the analysis uses, as the authors describe them, without evaluating them"
    ),
    "considerations": (
        "up to five of the article's own special considerations, each {kind, consideration, "
        "quote}: what the authors themselves say about it, faithfully, with a verbatim quote; "
        "kind is one of: " + ", ".join(SPECIAL_KINDS)
    ),
    "main_conclusions": (
        "one to four of the article's central conclusions, proposals, or recommendations, each "
        "{quote, locator} quoting the authors verbatim (locator optional): what the article "
        "concludes, as they state it"
    ),
}
MAX_CONSIDERATIONS = 5
MAX_MAIN_CONCLUSIONS = 4
# A mismatched figure that recurs this often (outside the reference list) is load-bearing: totals
# and denominators built on it inherit the error, so the entry is major whatever the screening says.
LOAD_BEARING_BLOCKS = 3
SWEEP_FIELDS = {
    "drops": (
        "entries to drop, each {id, reason}: a concern that matches one of false_alarms, is not "
        "supported by its own quotes, or is something a careful reviewer would not put in a "
        "report; include a computed number check whose expression is not what the manuscript "
        "implies. Leave the list empty if none"
    ),
    "concerns": (
        "every preliminary major, sorted into the concerns they raise, each {ids, reason}: one "
        "item per concern, with all its entries; an item with several entries needs a reason "
        "and becomes one entry. Every preliminary major that is not dropped appears exactly once"
    ),
    "merges": (
        "groups of other entries that raise one concern, each {into, ids, reason}: the passes gave "
        "them different concern keys, but the reviewer would answer them with one response. "
        "into is the entry that remains; never merge a computed number check with anything but "
        "the same check. Leave the list empty if none"
    ),
    "flaws": (
        "one item per listed major flaw, {flaw, entries, quote, reason}: the entries whose "
        "evidence shows that flaw (empty if none), a verbatim quote from those entries' "
        "evidence that shows it, and one sentence on how"
    ),
}
# Recorded reviewer responses to surfaced candidates; an unrecorded one is still `candidate`.
DISPOSITIONS = ("accepted", "developing", "deferred", "dismissed")
MAX_MINOR_BATCH = 3
# Three batches of minors by default; the rest wait until the reviewer asks for more.
MAX_ACTIVE_MINORS = 9
# Measured: about three tool calls per pass (write, submit, an occasional read) and a few for
# planning, the summary, synthesis, and the sweep.
CALLS_PER_PASS = 3
CALLS_OUTSIDE_PASSES = 12


def _scan_root(scan_id: str) -> Path:
    if not SCAN_ID_RE.fullmatch(scan_id):
        raise ReviewError("invalid scan id")
    root = data_home() / "scans" / scan_id
    if not (root / "scan.json").is_file():
        raise ReviewError(f"scan does not exist: {scan_id}")
    return root


def _flat(value: str) -> str:
    return " ".join(value.split())


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


def _require_profile() -> None:
    report = inspect_profile(None, live=False)
    if not report["ready"]:
        raise ReviewError(
            "Hermes profile no longer satisfies the privacy gate: " + "; ".join(report["problems"])
        )


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
        raise ReviewError("run `creview session start` in this Hermes session before a deep scan")
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
    ensure_private_dir(root / "proposals")
    scan = {
        "schema_version": "1",
        "scan_id": scan_id,
        "created_at": now_iso(),
        "session_id": key,
        "phase": "planning",
        "sources": [
            {k: s[k] for k in ("source_id", "path", "sha256", "format", "warnings")}
            | {"block_count": len(s["segments"])}
            for s in sources
        ],
        "session_source": source,
        "profiles": [p["id"] for p in confirmed],
        "profile_confirmation": confirmed_by,
        "plan": None,
        "tasks": [],
        "candidates": [],
        "pool": [],
    }
    atomic_write_json(root / "scan.json", scan)
    draft_path = root / "plan-draft.json"
    atomic_write_json(draft_path, draft_plan(sources))
    plan_path = root / "plan.json"
    return {
        "scan_id": scan_id,
        "plan_draft_path": str(draft_path),
        "plan_path": str(plan_path),
        "sources": scan["sources"],
        "profiles": scan["profiles"],
        "monitoring_areas": _areas(scan),
        "next": (
            f"read the draft plan, write the refined plan as a new file at {plan_path}, then run "
            f"creview scan plan {scan_id} {plan_path} to propose it to the reviewer"
        ),
    }


def _plan_tasks(plan: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = []
    for number in range(1, max(TIER_PASSES.values()) + 1):
        for segment in plan["segments"]:
            total = TIER_PASSES[segment["tier"]]
            if number <= total:
                tasks.append(
                    {
                        "id": f"{segment['id']}-p{number}",
                        "segment_id": segment["id"],
                        "pass": number,
                        "passes": total,
                        "status": "pending",
                    }
                )
    return tasks


def _budget_warnings(plan: dict[str, Any], tasks: list[dict[str, Any]]) -> list[str]:
    warnings = list(plan["warnings"])
    calls = CALLS_PER_PASS * len(tasks) + CALLS_OUTSIDE_PASSES
    max_turns = agent_max_turns()
    if max_turns and calls > max_turns:
        warnings.append(
            f"the scan needs about {calls} tool calls, more than the profile's agent.max_turns "
            f"({max_turns}), so Hermes will pause it mid-way. Tell the reviewer before starting "
            "that they may need to reply 'continue'; the scan resumes from creview scan next"
        )
    return warnings


def set_plan(scan_id: str, plan_path: Path, confirmation: str | None = None) -> dict[str, Any]:
    """Without `confirmation`, propose the plan: the reviewer sees each segment's tier, and so
    how many passes the scan runs, before any pass. With it, store the plan; the confirmation must
    quote the reviewer's reply sent after the proposal."""
    root = _scan_root(scan_id)
    with FileLock(str(root / ".lock")):
        scan = read_json(root / "scan.json")
        if any(task["status"] == "done" for task in scan["tasks"]):
            raise ReviewError("the scan has started; start a new scan to change the plan")
        plan = validate_plan(read_json(plan_path), _current_sources(scan))
        for segment in plan["segments"]:
            segment["profile_areas"] = _check_areas(scan, segment["profile_areas"], segment["id"])
        tasks = _plan_tasks(plan)
        if not confirmation:
            scan.update(plan_proposed_at=now_iso(), phase="planning", updated_at=now_iso())
            atomic_write_json(root / "scan.json", scan)
            return {
                "scan_id": scan_id,
                "state": "plan proposed",
                "segments": outline(plan),
                "passes": len(tasks),
                "tool_calls": CALLS_PER_PASS * len(tasks) + CALLS_OUTSIDE_PASSES,
                "tier_passes": TIER_PASSES,
                "warnings": _budget_warnings(plan, tasks),
                "instructions": (
                    "Show the reviewer every segment with its tier and the total number of "
                    "passes, say what the tiers mean (light 1 pass, medium 2, high 3) and that "
                    "more passes take longer, and pass on any warning. Ask them to confirm the "
                    "tiers, change any segment's tier, or set one tier for all segments. Then end "
                    "your turn and wait. When they answer, write the plan with their tiers and run "
                    f'creview scan plan {scan_id} PLAN_PATH --confirmation "THEIR WORDS".'
                ),
            }
        if not scan.get("plan_proposed_at"):
            raise ReviewError(
                "show the reviewer the tiers first: run creview scan plan without --confirmation"
            )
        confirmed_by = reviewer_words(
            confirmation,
            hermes_session=scan.get("session_source") == "hermes_session",
            what="the tier confirmation",
            since=scan["plan_proposed_at"],
        )
        scan.update(
            plan=plan,
            plan_confirmation=confirmed_by,
            tasks=tasks,
            phase="summary",
            updated_at=now_iso(),
        )
        atomic_write_json(root / "scan.json", scan)
    warnings = _budget_warnings(plan, tasks)
    return {
        "scan_id": scan_id,
        "segments": outline(plan),
        "passes": len(tasks),
        "warnings": warnings,
        **_overview_request(scan, root),
        "next": f"write the initial summary, then creview scan overview {scan_id} OVERVIEW_PATH",
    }


def _profiles(scan: dict[str, Any]) -> list[dict[str, Any]]:
    return load_profiles(scan.get("profiles") or [])


def _areas(scan: dict[str, Any]) -> list[str]:
    return [area for profile in _profiles(scan) for area in profile["monitoring_areas"]]


def _false_alarms(scan: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"profile": profile["id"], "false_alarm": item}
        for profile in _profiles(scan)
        for item in profile["false_alarms"]
    ]


def _major_flaws(scan: dict[str, Any]) -> list[dict[str, str]]:
    """The general rubric's major flaws and the confirmed profiles' own, with qualified ids."""
    flaws = [{"id": f"general/{f['id']}", "flaw": f["flaw"]} for f in general_major_flaws()]
    for profile in _profiles(scan):
        flaws += [
            {"id": f"{profile['id']}/{f['id']}", "flaw": f["flaw"]} for f in profile["major_flaws"]
        ]
    return flaws


def _check_areas(scan: dict[str, Any], areas: list[str], label: str) -> list[str]:
    """Profile areas must be the confirmed profiles' own; with none confirmed, any are allowed."""
    allowed = {area.casefold(): area for area in _areas(scan)}
    if not allowed:
        return [area for area in areas]
    unknown = [area for area in areas if area.casefold() not in allowed]
    if unknown:
        raise ReviewError(
            f"{label} names profile areas the confirmed profiles do not have: "
            f"{', '.join(unknown)}; use one of: {', '.join(allowed.values())}"
        )
    return [allowed[area.casefold()] for area in areas]


def _segment(scan: dict[str, Any], segment_id: str) -> dict[str, Any]:
    return next(s for s in scan["plan"]["segments"] if s["id"] == segment_id)


def next_task(scan_id: str) -> dict[str, Any]:
    _require_profile()
    root = _scan_root(scan_id)
    scan = read_json(root / "scan.json")
    if scan["phase"] == "planning":
        raise ReviewError(f"set the segment plan first: creview scan plan {scan_id} PLAN_PATH")
    if scan["phase"] == "summary":
        raise ReviewError(
            f"write the initial summary first: creview scan overview {scan_id} OVERVIEW_PATH"
        )
    task = next((t for t in scan["tasks"] if t["status"] == "pending"), None)
    if task is None:
        return {"scan_id": scan_id, "state": scan["phase"], "next": _phase_next(scan)}
    sources = {s["source_id"]: s for s in _current_sources(scan)}
    segment = _segment(scan, task["segment_id"])
    proposal_path = root / "proposals" / f"{task['id']}.json"
    template: dict[str, Any] = {
        "task_id": task["id"],
        "note": "",
        "candidates": [],
        "number_checks": [],
        "no_number_checks_reason": "",
    }
    if task["pass"] == 1:
        template["summary"] = ""
    angle = (
        "First pass: read the segment closely against its profile areas, and write summary: "
        + SUMMARY_FIELD
        + "."
        if task["pass"] == 1
        else (
            f"Independent pass {task['pass']} of {task['passes']}: look again from a different "
            "angle, such as the strongest objection a methods expert would raise or how this "
            "segment's claims depend on other segments. Do not try to recall earlier passes; "
            "duplicates are merged later."
        )
    )
    return {
        "scan_id": scan_id,
        "task": task,
        "segment": {k: segment[k] for k in ("id", "title", "source_id", "theme", "tier")}
        | {"profile_areas": segment["profile_areas"]},
        "content": segment_blocks(segment, sources[segment["source_id"]]),
        "outline": outline(scan["plan"]),
        "proposal_path": str(proposal_path),
        "proposal_template": template,
        "candidate_fields": CANDIDATE_FIELDS,
        "number_check_fields": NUMBER_CHECK_FIELDS,
        "false_alarms": _false_alarms(scan),
        "major_flaws": _major_flaws(scan),
        "concern_register": [
            {"key": key, "label": item["label"]} for key, item in scan.get("concerns", {}).items()
        ],
        **({"summary_field": SUMMARY_FIELD} if task["pass"] == 1 else {}),
        "instructions": (
            f"{angle} The whole manuscript is available through the outline and the attached "
            "file; focus on this segment. A concern that matches one of false_alarms (the "
            "confirmed profiles' common false alarms) is not a candidate. major_flaws lists the "
            "flaws that are major in this design: check the segment for each one it could show, "
            "and tag each candidate with the one it shows, or none. Give each candidate a "
            "concern_key: reuse a key from concern_register when it raises the same concern, "
            "even where the manuscript states it in other words or another place; creview merges "
            "candidates by key, so a new key for an old concern makes a duplicate. "
            "Check every candidate against "
            "the rubric's checks before keeping a candidate: before claiming "
            "something is missing or unexplained, search the whole manuscript for it. Do not do "
            "arithmetic yourself: for every total, difference, sum of parts, or percentage the "
            "segment reports, add a number_check; creview computes it and records a candidate "
            "when it does not reconcile. Write proposal_template, filled in, to proposal_path, "
            "then run "
            f"creview scan submit {scan_id} {proposal_path}; it returns the next task. Do not "
            "tell the reviewer about candidates, their number, or their content during the scan."
        ),
    }


def _check_quote(
    label: str, item: Any, sources: dict[str, dict[str, Any]]
) -> tuple[dict[str, str] | None, str]:
    """A verbatim {source_id, locator, quote}; a wrong or empty locator is found from the quote."""
    if not isinstance(item, dict):
        return None, f"{label} must be an object"
    source = sources.get(str(item.get("source_id") or "manuscript"))
    locator = str(item.get("locator") or "")
    quote = str(item.get("quote") or "").strip()
    if source is None:
        return None, f"{label} cites an unknown source"
    if not quote:
        return None, f"{label} has no quote"
    blocks = source["segments"]
    block = next((b for b in blocks if b["locator"] == locator), None)
    if block is None or _flat(quote) not in _flat(block["text"]):
        # A quote from another segment often comes without its locator: find it.
        found = [b for b in blocks if _flat(quote) in _flat(b["text"])]
        if not found:
            where = f"at {locator}" if block else "anywhere in the source"
            return None, f"{label} quote is not verbatim {where}"
        if len(found) > 1:
            return None, (
                f"{label} quote appears at {len(found)} locators; give one of "
                + ", ".join(b["locator"] for b in found[:5])
            )
        locator = found[0]["locator"]
    return {"source_id": source["source_id"], "locator": locator, "quote": quote}, ""


# Counts and percentages, not years, citation numbers, or section numbers like 2.1.
_REPORTED_NUMBER = re.compile(r"(?<![\w.\[])(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?(?![\w.\]])")
MIN_NUMBERS_FOR_CHECKS = 4


def _reported_numbers(blocks: list[dict[str, Any]]) -> int:
    values = [
        match.group(1) for block in blocks for match in _REPORTED_NUMBER.finditer(block["text"])
    ]
    return sum(1 for v in values if not re.fullmatch(r"(?:19|20)\d\d", v))


_ARITHMETIC = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _evaluate(expression: str) -> float:
    """+, -, *, / and parentheses over plain numbers; nothing else is evaluated."""

    def walk(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -walk(node.operand)
        if isinstance(node, ast.BinOp) and type(node.op) in _ARITHMETIC:
            return _ARITHMETIC[type(node.op)](walk(node.left), walk(node.right))
        raise ValueError("only numbers, + - * / and parentheses are allowed")

    if len(expression) > 200:
        raise ValueError("expression is too long")
    return walk(ast.parse(expression.replace(",", ""), mode="eval"))


def _number_checks(
    raw: Any, sources: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Compute the agent's arithmetic: language models misjudge sums, differences, percentages."""
    if raw in (None, []):
        return [], []
    if not isinstance(raw, list):
        return [], ["number_checks must be a list"]
    results, problems = [], []
    for index, item in enumerate(raw, start=1):
        label = f"number check {index}"
        if not isinstance(item, dict):
            problems.append(f"{label} must be an object")
            continue
        expression = str(item.get("expression") or "").strip()
        stated_text = str(item.get("stated") or "").replace(",", "").strip().rstrip("%")
        try:
            computed = _evaluate(expression)
            stated = float(stated_text)
        except (ValueError, SyntaxError, ZeroDivisionError) as exc:
            problems.append(f"{label} needs an expression and a stated number: {exc}")
            continue
        if stated in _numbers_in(expression):
            # "31 - 24" against a stated 31 checks nothing: stated is what the expression gives.
            problems.append(
                f"{label}: stated must be the figure the manuscript gives for the result of the "
                "expression, not one of its operands"
            )
            continue
        evidence, issue_text = _check_quote(label, item, sources)
        if evidence is None:
            problems.append(issue_text)
            continue
        decimals = len(stated_text.split(".")[1]) if "." in stated_text else 0
        matches = abs(computed - stated) <= 0.5 * 10**-decimals + 1e-9
        results.append(
            {
                "expression": expression,
                "stated": stated_text,
                "computed": round(computed, 6),
                "matches": matches,
                "evidence": evidence,
            }
        )
    return results, problems


def _number_candidate(check: dict[str, Any]) -> dict[str, Any]:
    return {
        "potential_issue": (
            f"Reported numbers do not reconcile: {check['expression']} = {check['computed']:g}, "
            f"but the manuscript states {check['stated']}."
        ),
        "why_it_matters": (
            "A count or calculation that does not add up leaves readers unable to tell which "
            "figure is right, and every result that rests on it inherits the doubt."
        ),
        "severity": "minor",
        "type": "inconsistency",
        "profile_area": None,
        "evidence": [check["evidence"]],
        "solution_candidates": ["Correct the figures or explain the difference."],
        "source": "number_check",
        "number_check": {k: check[k] for k in ("expression", "stated", "computed")},
        "concern_key": "number-" + _slug(f"{check['expression']} vs {check['stated']}"),
        "major_flaw": None,
    }


def _validate_candidate(
    index: int, raw: Any, sources: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any] | None, list[str]]:
    problems: list[str] = []
    if not isinstance(raw, dict):
        return None, [f"candidate {index} must be an object"]
    issue = str(raw.get("potential_issue") or "").strip()
    why = str(raw.get("why_it_matters") or "").strip()
    severity = str(raw.get("severity") or "").strip().lower()
    if not issue:
        problems.append(f"candidate {index} needs potential_issue")
    if not why:
        problems.append(f"candidate {index} needs why_it_matters")
    if severity not in SEVERITIES:
        problems.append(f"candidate {index} severity must be major or minor")
    kind = str(raw.get("type") or "").strip().lower()
    if kind not in CANDIDATE_TYPES:
        problems.append(f"candidate {index} type must be one of {', '.join(CANDIDATE_TYPES)}")
    evidence = raw.get("evidence")
    checked: list[dict[str, str]] = []
    if not isinstance(evidence, list) or not evidence:
        problems.append(f"candidate {index} needs at least one evidence quote")
        evidence = []
    for number, item in enumerate(evidence, start=1):
        found, issue_text = _check_quote(f"candidate {index} evidence {number}", item, sources)
        if found:
            checked.append(found)
        else:
            problems.append(issue_text)
    if kind == "inconsistency" and len({(e["source_id"], e["locator"]) for e in checked}) < 2:
        problems.append(
            f"candidate {index} is an inconsistency: quote both statements, at two different "
            "locations"
        )
    solutions = raw.get("solution_candidates") or []
    if not isinstance(solutions, list):
        problems.append(f"candidate {index} solution_candidates must be a list")
        solutions = []
    if problems:
        return None, problems
    return {
        "potential_issue": issue,
        "why_it_matters": why,
        "severity": severity,
        "type": kind,
        "profile_area": str(raw.get("profile_area") or "").strip() or None,
        "evidence": checked,
        "solution_candidates": [str(s).strip() for s in solutions if str(s).strip()],
        "concern_key": _slug(str(raw.get("concern_key") or "")),
        "concern_label": " ".join(str(raw.get("concern_label") or "").split()),
        "major_flaw": str(raw.get("major_flaw") or "").strip().lower(),
    }, []


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def _flaw_id(flaw: str, flaws: list[str]) -> str | None:
    """A listed major-flaw id, accepting the bare slug when it names one flaw; None if unlisted."""
    if flaw in flaws:
        return flaw
    bare = [f for f in flaws if f.split("/", 1)[1] == flaw]
    return bare[0] if len(bare) == 1 else None


def _check_tags(
    index: int, candidate: dict[str, Any], scan: dict[str, Any], new_keys: dict[str, str]
) -> list[str]:
    """Validate a candidate's concern key and major-flaw tag; register a new key."""
    problems = []
    flaws = [f["id"] for f in _major_flaws(scan)]
    if candidate["major_flaw"] in ("", "none"):
        if not candidate["major_flaw"]:
            problems.append(f"candidate {index} needs major_flaw: a listed id or none")
        candidate["major_flaw"] = None
    else:
        found = _flaw_id(candidate["major_flaw"], flaws)
        if found is None:
            problems.append(
                f"candidate {index} major_flaw {candidate['major_flaw']!r} is not listed; use "
                "none or one of " + ", ".join(flaws)
            )
        candidate["major_flaw"] = found
    key = candidate["concern_key"]
    known = scan.get("concerns", {})
    if len(key) < 3:
        problems.append(f"candidate {index} needs concern_key: {CANDIDATE_FIELDS['concern_key']}")
    elif key not in known and key not in new_keys:
        label = candidate["concern_label"]
        if not label:
            problems.append(
                f"candidate {index} gives the new concern_key {key!r} without concern_label; "
                "if it is the same concern as one in concern_register, use that key instead"
            )
        elif len(label.split()) > MAX_LABEL_WORDS:
            problems.append(f"candidate {index} concern_label is over {MAX_LABEL_WORDS} words")
        else:
            new_keys[key] = label
    del candidate["concern_label"]
    return problems


def submit_task(scan_id: str, proposal_path: Path) -> dict[str, Any]:
    root = _scan_root(scan_id)
    proposal = read_json(proposal_path)
    with FileLock(str(root / ".lock")):
        scan = read_json(root / "scan.json")
        task = next((t for t in scan["tasks"] if t["status"] == "pending"), None)
        if task is None or proposal.get("task_id") != task["id"]:
            raise ReviewError("the proposal is not for the current scan task")
        raw = proposal.get("candidates")
        if not isinstance(raw, list):
            raise ReviewError("proposal candidates must be a list")
        sources = {s["source_id"]: s for s in _current_sources(scan)}
        accepted, problems = [], []
        new_keys: dict[str, str] = {}
        for index, item in enumerate(raw, start=1):
            candidate, issues = _validate_candidate(index, item, sources)
            problems.extend(issues)
            if candidate:
                problems.extend(_check_tags(index, candidate, scan, new_keys))
            if candidate and candidate["profile_area"]:
                try:
                    (candidate["profile_area"],) = _check_areas(
                        scan, [candidate["profile_area"]], f"candidate {index}"
                    )
                except ReviewError as exc:
                    problems.append(str(exc))
            if candidate:
                accepted.append(candidate)
        checks, check_problems = _number_checks(proposal.get("number_checks"), sources)
        problems.extend(check_problems)
        segment = _segment(scan, task["segment_id"])
        reported = _reported_numbers(segment_blocks(segment, sources[segment["source_id"]]))
        none_reason = str(proposal.get("no_number_checks_reason") or "").strip()
        if (
            task["pass"] == 1
            and reported >= MIN_NUMBERS_FOR_CHECKS
            and not checks
            and not check_problems
            and not none_reason
        ):
            problems.append(
                f"this segment reports {reported} numbers: add number_checks for its totals, "
                "differences, sums of parts, and percentages, or say in "
                "no_number_checks_reason why none of them depend on each other"
            )
        accepted.extend(_number_candidate(c) for c in checks if not c["matches"])
        summary = str(proposal.get("summary") or "").strip()
        if task["pass"] == 1 and not summary:
            problems.append("a first-pass proposal needs summary: " + SUMMARY_FIELD)
        if problems:
            raise ReviewError("proposal refused: " + "; ".join(problems))
        if task["pass"] == 1:
            scan.setdefault("summaries", {})[task["segment_id"]] = summary[:2000]
        for key, label in new_keys.items():
            scan.setdefault("concerns", {})[key] = {"label": label, "task_id": task["id"]}
        for candidate in accepted:
            scan["candidates"].append(
                {
                    "id": f"cand-{len(scan['candidates']) + 1:03d}",
                    "task_id": task["id"],
                    "segment_id": task["segment_id"],
                    **candidate,
                }
            )
        task.update(status="done", note=str(proposal.get("note") or "")[:1000], done_at=now_iso())
        if all(t["status"] == "done" for t in scan["tasks"]):
            scan["phase"] = "synthesis"
        scan["updated_at"] = now_iso()
        atomic_write_json(root / "scan.json", scan)
    result: dict[str, Any] = {
        "scan_id": scan_id,
        "task_id": task["id"],
        "state": scan["phase"],
        "next": _phase_next(scan),
    }
    if checks:
        result["number_checks"] = [
            {k: c[k] for k in ("expression", "stated", "computed", "matches")} for c in checks
        ]
    if scan["phase"] == "scanning":
        # Saves the agent a `scan next` call per pass; Hermes caps tool calls per turn.
        result["next_task"] = next_task(scan_id)
    return result


def _phase_next(scan: dict[str, Any]) -> str | None:
    scan_id = scan["scan_id"]
    return {
        "planning": (
            f"creview scan plan {scan_id} PLAN_PATH, then, once the reviewer has answered, the "
            "same with --confirmation"
        ),
        "summary": f"creview scan overview {scan_id} OVERVIEW_PATH",
        "scanning": f"creview scan next {scan_id}",
        "synthesis": f"creview scan synthesize {scan_id}",
        "sweep": f"creview scan synthesize {scan_id} (returns the sweep request)",
        "ready": f"creview scan candidate {scan_id}",
    }.get(scan["phase"])


def _numbers_in(text: str) -> set[float]:
    return {float(n) for n in re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))}


def _restates(candidate: dict[str, Any], check: dict[str, Any]) -> bool:
    """A model-written candidate that restates a computed mismatch: same block, and its text
    gives both the stated figure and the computed one."""
    blocks = {(e["source_id"], e["locator"]) for e in check["evidence"]}
    if not any((e["source_id"], e["locator"]) in blocks for e in candidate["evidence"]):
        return False
    numbers = _numbers_in(candidate["potential_issue"] + " " + candidate["why_it_matters"])
    detail = check["number_check"]
    return float(detail["stated"]) in numbers and round(float(detail["computed"]), 2) in {
        round(n, 2) for n in numbers
    }


def _members(scan: dict[str, Any], entry: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in scan["candidates"] if c["id"] in entry["member_ids"]]


def _blocks_of(scan: dict[str, Any], entry: dict[str, Any]) -> set[tuple[str, str]]:
    return {(e["source_id"], e["locator"]) for m in _members(scan, entry) for e in m["evidence"]}


def _computed(scan: dict[str, Any], entry: dict[str, Any]) -> bool:
    return any(m.get("source") == "number_check" for m in _members(scan, entry))


def _check_of(scan: dict[str, Any], entry: dict[str, Any]) -> tuple[str, str] | None:
    """The computed number check an entry holds, as (expression, stated), or None."""
    for member in _members(scan, entry):
        if member.get("number_check"):
            return member["number_check"]["expression"], member["number_check"]["stated"]
    return None


def _group(candidates: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Candidates that raise one concern. Passes tag each candidate with a concern key, reusing
    the key of a concern already raised; independent passes quote different sentences for one
    concern, so the key, not the quotes, decides. A computed check keeps its own group with its
    restatements: a key cannot fold it into a broader concern."""
    grouped: set[str] = set()
    groups: list[list[dict[str, Any]]] = []
    for check in (c for c in candidates if c.get("source") == "number_check"):
        if check["id"] in grouped:
            continue
        same = (check["number_check"]["expression"], check["number_check"]["stated"])
        group = [
            c
            for c in candidates
            if c["id"] not in grouped
            and (
                (
                    c.get("source") == "number_check"
                    and (c["number_check"]["expression"], c["number_check"]["stated"]) == same
                )
                or (c.get("source") != "number_check" and _restates(c, check))
            )
        ]
        grouped |= {c["id"] for c in group}
        groups.append(group)
    by_key: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        if candidate["id"] not in grouped:
            by_key.setdefault(candidate.get("concern_key") or candidate["id"], []).append(candidate)
    return groups + list(by_key.values())


def synthesize(scan_id: str) -> dict[str, Any]:
    """Group the candidates in code, then hand the whole pool to the sweep."""
    root = _scan_root(scan_id)
    with FileLock(str(root / ".lock")):
        scan = read_json(root / "scan.json")
        if scan["phase"] == "sweep":
            return _sweep_request(scan, root)
        if scan["phase"] != "synthesis":
            raise ReviewError(f"the scan is in {scan['phase']}; {_phase_next(scan)}")
        order = {s["id"]: n for n, s in enumerate(scan["plan"]["segments"])}
        concerns = scan.get("concerns", {})
        pool = []
        for members in sorted(
            _group(scan["candidates"]), key=lambda m: (order[m[0]["segment_id"]], m[0]["id"])
        ):
            key = members[0].get("concern_key")
            pool.append(
                {
                    "id": f"pool-{len(pool) + 1:03d}",
                    "member_ids": [m["id"] for m in members],
                    "segment_ids": sorted({m["segment_id"] for m in members}, key=order.get),
                    "concern_key": key,
                    "label": (concerns.get(key) or {}).get("label")
                    or members[0]["potential_issue"][:200],
                    "decision": None,
                    "surfaced_at": None,
                }
            )
        sources = {s["source_id"]: s for s in _current_sources(scan)}
        for entry in pool:
            # Before the sweep, from what the passes tagged and voted: the sweep must then say,
            # for every preliminary major, whether it is a concern of its own or a duplicate.
            entry["preliminary"], _, _ = _severity(scan, entry | {"swept_flaws": []}, sources)
            entry["main_conclusion"] = _main_conclusion_of(scan, entry)
        scan.update(pool=pool, phase="sweep" if pool else "ready", updated_at=now_iso())
        atomic_write_json(root / "scan.json", scan)
        if not pool:
            return {
                "scan_id": scan_id,
                "state": "ready",
                "next": f"creview scan candidate {scan_id}",
            }
        return _sweep_request(scan, root)


def _sweep_request(scan: dict[str, Any], root: Path) -> dict[str, Any]:
    """One step over the whole pool: what to drop, and, flaw by flaw, which entries show each
    listed major flaw. Tags made during the passes follow each candidate's own wording; looking
    up each flaw across every entry finds one a narrowly worded candidate missed."""
    scan_id = scan["scan_id"]
    sweep_path = root / "sweep.json"
    entries = []
    for entry in scan["pool"]:
        members = _members(scan, entry)
        lead = max(members, key=lambda c: len(c["why_it_matters"]))
        check = next((m["number_check"] for m in members if m.get("number_check")), None)
        entries.append(
            {
                "id": entry["id"],
                "concern": entry["label"],
                "potential_issue": lead["potential_issue"],
                "type": lead.get("type"),
                "segments": [_segment(scan, s)["title"] for s in entry["segment_ids"]],
                "tagged_flaws": sorted({m["major_flaw"] for m in members if m.get("major_flaw")}),
                **({"computed_check": check} if check else {}),
                "preliminary_severity": entry.get("preliminary"),
                "main_conclusion": entry.get("main_conclusion"),
                "evidence": [e["quote"] for m in members for e in m["evidence"]][:4],
            }
        )
    majors = sorted(
        (e for e in entries if e["preliminary_severity"] == "major"),
        key=lambda e: (e["main_conclusion"] is None, e["main_conclusion"] or 0, e["id"]),
    )
    return {
        "scan_id": scan_id,
        "state": "sweep",
        "entries": entries,
        "preliminary_majors": [
            {k: e[k] for k in ("id", "concern", "main_conclusion", "tagged_flaws")} for e in majors
        ],
        "main_conclusions": [m["quote"] for m in _main_conclusions(scan)],
        "major_flaws": _major_flaws(scan),
        "false_alarms": _false_alarms(scan),
        "sweep_path": str(sweep_path),
        "sweep_template": {
            "drops": [],
            "concerns": [{"ids": [e["id"]], "reason": ""} for e in majors],
            "merges": [],
            "flaws": [
                {
                    "flaw": f["id"],
                    "entries": [],
                    "quote": {"quote": "", "locator": ""},
                    "reason": "",
                }
                for f in _major_flaws(scan)
            ],
        },
        "sweep_fields": SWEEP_FIELDS,
        "instructions": (
            "Read every entry once, as a careful reviewer. In drops, list each entry to drop with "
            "a reason: it matches one of false_alarms, its own quotes do not support it, a "
            "careful reviewer would not put it in a report, or it is a computed check whose "
            "expression is not what the manuscript implies. In concerns, sort every preliminary "
            "major into the concern it raises: put entries that the reviewer would answer with "
            "one major comment in one item, with a reason, and leave an entry alone only when it "
            "is a concern of its own. preliminary_majors lists them by the main conclusion they "
            "bear on, so duplicates usually sit together. In merges, group any other entries that "
            "raise one concern under different keys. Then, for every flaw in "
            "major_flaws, list the entries whose evidence shows it, judged on the manuscript "
            "rather than on how the entry is worded, with a verbatim quote from those entries' "
            "evidence and one sentence on how it shows the flaw; leave entries empty when none "
            "does. An entry may show several flaws. creview sets each entry's severity in code. "
            f"Write sweep_template, filled in, as a new file at {sweep_path}, then run creview "
            f"scan sweep {scan_id} {sweep_path}. Do not show the pool to the reviewer."
        ),
    }


def sweep(scan_id: str, sweep_path: Path) -> dict[str, Any]:
    """Store the sweep, then set every kept entry's severity in code."""
    root = _scan_root(scan_id)
    answer = read_json(sweep_path)
    if not isinstance(answer, dict):
        raise ReviewError("the sweep file must be an object with drops and flaws")
    with FileLock(str(root / ".lock")):
        scan = read_json(root / "scan.json")
        if scan["phase"] != "sweep":
            raise ReviewError(f"the scan is in {scan['phase']}; {_phase_next(scan)}")
        by_id = {p["id"]: p for p in scan["pool"]}
        sources = {s["source_id"]: s for s in _current_sources(scan)}
        drops: dict[str, str] = {}
        for item in answer.get("drops") or []:
            if not isinstance(item, dict):
                raise ReviewError("each drop must be an object {id, reason}")
            pool_id = str(item.get("id") or "").strip()
            reason = str(item.get("reason") or "").strip()
            if pool_id not in by_id:
                raise ReviewError(f"drop names {pool_id!r}, which is not a pool entry")
            if not reason:
                raise ReviewError(f"{pool_id} is dropped without a reason")
            drops[pool_id] = reason[:500]
        majors = [p["id"] for p in scan["pool"] if p.get("preliminary") == "major"]
        clustered: list[str] = []
        merges = list(answer.get("merges") or [])
        for item in answer.get("concerns") or []:
            if not isinstance(item, dict):
                raise ReviewError("each concerns item must be an object {ids, reason}")
            ids = item.get("ids") or []
            ids = [
                str(i).strip() for i in ([ids] if isinstance(ids, str) else ids) if str(i).strip()
            ]
            if not ids:
                continue
            clustered += ids
            if len(ids) > 1:
                merges.append({"into": ids[0], "ids": ids[1:], "reason": item.get("reason")})
        repeated = sorted({i for i in clustered if clustered.count(i) > 1})
        if repeated:
            raise ReviewError(f"concerns lists {', '.join(repeated)} more than once")
        missing = [i for i in majors if i not in clustered and i not in drops]
        if missing:
            raise ReviewError(
                "concerns must place every preliminary major that is not dropped, alone or with "
                "the entries that raise the same concern: " + ", ".join(missing)
            )
        into: dict[str, str] = {}  # merged entry -> the entry that remains
        for item in merges:
            if not isinstance(item, dict):
                raise ReviewError("each merge must be an object {into, ids, reason}")
            target = str(item.get("into") or "").strip()
            ids = item.get("ids") or []
            ids = [ids] if isinstance(ids, str) else ids
            ids = [str(i).strip() for i in ids if str(i).strip() and str(i).strip() != target]
            if target not in by_id or any(i not in by_id for i in ids):
                raise ReviewError(f"merge into {target!r} names an entry that is not in the pool")
            if not ids:
                continue
            if not str(item.get("reason") or "").strip():
                raise ReviewError(f"the merge into {target} has no reason")
            if target in drops or any(i in drops for i in ids):
                raise ReviewError(f"the merge into {target} names a dropped entry")
            if target in into or any(i in into or i in into.values() for i in ids):
                raise ReviewError(
                    f"the merge into {target} overlaps another merge: give each concern one merge, "
                    "into an entry that is not itself merged"
                )
            checks = {_check_of(scan, by_id[i]) for i in [target, *ids]}
            if len(checks) > 1:
                raise ReviewError(
                    f"the merge into {target} joins a computed number check with something other "
                    "than the same check"
                )
            into.update({i: target for i in ids})
        flaws = [f["id"] for f in _major_flaws(scan)]
        given: dict[str, dict[str, Any]] = {}
        for item in answer.get("flaws") or []:
            if not isinstance(item, dict):
                raise ReviewError(
                    "each flaws item must be an object {flaw, entries, quote, reason}"
                )
            raw_flaw = str(item.get("flaw") or "").strip().lower()
            flaw = _flaw_id(raw_flaw, flaws)
            if flaw is None:
                raise ReviewError(
                    f"{raw_flaw!r} is not a listed major flaw; use {', '.join(flaws)}"
                )
            if flaw in given:
                raise ReviewError(f"{flaw} is answered twice")
            given[flaw] = item
        unanswered = [f for f in flaws if f not in given]
        if unanswered:
            raise ReviewError(
                "answer every listed major flaw, with entries empty when no entry shows it: "
                + ", ".join(unanswered)
            )
        found: dict[str, list[str]] = {}
        for flaw, item in given.items():
            entries = item.get("entries") or []
            if isinstance(entries, str):
                entries = [entries]
            entries = [str(e).strip() for e in entries if str(e).strip().lower() != "none"]
            # An entry merged in this sweep counts as the entry that remains.
            entries = list(dict.fromkeys(into.get(e, e) for e in entries))
            if not entries:
                continue
            unknown = [e for e in entries if e not in by_id or e in drops]
            if unknown:
                raise ReviewError(
                    f"{flaw} names {', '.join(unknown)}, which are not kept entries; name kept "
                    "entries only"
                )
            computed = [e for e in entries if _computed(scan, by_id[e])]
            if computed:
                raise ReviewError(
                    f"{flaw} names {', '.join(computed)}, which hold a computed number check: "
                    "creview sets their severity from how the manuscript uses the figure"
                )
            if not str(item.get("reason") or "").strip():
                raise ReviewError(f"{flaw} names entries without a reason")
            quote, problem = _check_quote(f"{flaw} quote", _as_quote(item.get("quote")), sources)
            if quote is None:
                raise ReviewError(f"{problem}: {SWEEP_FIELDS['flaws']}")
            merged = [m for e in entries for m in [e, *[i for i, t in into.items() if t == e]]]
            shown = set().union(*(_blocks_of(scan, by_id[m]) for m in merged))
            if (quote["source_id"], quote["locator"]) not in shown:
                raise ReviewError(
                    f"{flaw} quote is not from the evidence of {', '.join(entries)}; quote the "
                    "passage in those entries that shows the flaw"
                )
            found[flaw] = entries
        order = {s["id"]: n for n, s in enumerate(scan["plan"]["segments"])}
        for merged_id, target_id in into.items():
            target, merged = by_id[target_id], by_id[merged_id]
            target["member_ids"] += merged["member_ids"]
            target["segment_ids"] = sorted(
                {*target["segment_ids"], *merged["segment_ids"]}, key=order.get
            )
            merged.update(decision="merge", merged_into=target_id)
        for entry in scan["pool"]:
            if entry["id"] in into:
                continue
            if entry["id"] in drops:
                entry.update(decision="drop", reason=drops[entry["id"]])
                continue
            entry["decision"] = "keep"
            entry["swept_flaws"] = sorted(f for f, ids in found.items() if entry["id"] in ids)
            entry["severity"], entry["severity_basis"], entry["major_flaws"] = _severity(
                scan, entry, sources
            )
            entry["main_conclusion"] = _main_conclusion_of(scan, entry)
            entry["support"] = _support(scan, entry)
        scan.update(
            sweep={"drops": drops, "merges": into, "flaws": {f: found.get(f, []) for f in flaws}},
            phase="ready",
            updated_at=now_iso(),
        )
        atomic_write_json(root / "scan.json", scan)
    return {"scan_id": scan_id, "state": "ready", "next": f"creview scan candidate {scan_id}"}


def _support(scan: dict[str, Any], entry: dict[str, Any]) -> float:
    """How many independent passes raised the entry, relative to its segments' passes."""
    tasks = {t["id"]: t for t in scan["tasks"]}
    raised = {m["task_id"] for m in _members(scan, entry)}
    passes = max(tasks[t]["passes"] for t in raised) if raised else 1
    return round(len(raised) / passes, 3)


def _severity(
    scan: dict[str, Any], entry: dict[str, Any], sources: dict[str, dict[str, Any]]
) -> tuple[str, list[str], list[str]]:
    """Major when a pass or the sweep found a listed major flaw in it, or when at least half the
    passes over its segment rated it major. A computed number check takes its severity only from
    whether the mismatched figure is load-bearing: a tag or a vote cannot raise it."""
    members = _members(scan, entry)
    if any(m.get("source") == "number_check" for m in members):
        figure = _load_bearing(scan, entry, sources)
        basis = [f"mismatched figure {figure} recurs across the manuscript"] if figure else []
        return ("major" if basis else "minor"), basis, []
    flaws = sorted(
        {m["major_flaw"] for m in members if m.get("major_flaw")} | set(entry["swept_flaws"])
    )
    basis = [f"listed major flaw {flaw}" for flaw in flaws]
    # Votes count per segment: an entry merged across segments is major when at least half the
    # passes over one of its segments rated it major.
    tasks = {t["id"]: t for t in scan["tasks"]}
    votes: dict[str, set[str]] = {}
    for m in members:
        if m["severity"] == "major":
            votes.setdefault(m["segment_id"], set()).add(m["task_id"])
    for segment_id, voted in votes.items():
        passes = next(t["passes"] for t in tasks.values() if t["segment_id"] == segment_id)
        if 2 * len(voted) >= passes:
            title = _segment(scan, segment_id)["title"]
            basis.append(f"rated major in {len(voted)} of {passes} passes over {title}")
            break
    return ("major" if basis else "minor"), basis, flaws


def _as_quote(value: Any) -> Any:
    return {"quote": value} if isinstance(value, str) or value is None else value


def _main_conclusions(scan: dict[str, Any]) -> list[dict[str, str]]:
    return (scan.get("overview") or {}).get("main_conclusions") or []


def _main_conclusion_of(scan: dict[str, Any], entry: dict[str, Any]) -> int | None:
    """The first main conclusion from the initial summary that an entry's evidence quotes: one
    quote containing the other, or failing that the same paragraph."""
    evidence = [e for m in _members(scan, entry) for e in m["evidence"]]
    mains = _main_conclusions(scan)
    for index, main in enumerate(mains):
        other = _flat(main["quote"]).lower()
        for e in evidence:
            quote = _flat(e["quote"]).lower()
            if quote in other or other in quote:
                return index
    blocks = {(e["source_id"], e["locator"]) for e in evidence}
    for index, main in enumerate(mains):
        if (main["source_id"], main["locator"]) in blocks:
            return index
    return None


_REFERENCE_HEADING = re.compile(r"^heading:(references|bibliography|works cited|notes)\b", re.I)


def _load_bearing(
    scan: dict[str, Any], entry: dict[str, Any], sources: dict[str, dict[str, Any]]
) -> str | None:
    """A computed number check whose stated figure recurs in several paragraphs, tables, or the
    abstract: the stated figure is the one other results are built on."""
    members = [c for c in scan["candidates"] if c["id"] in entry["member_ids"]]
    for member in members:
        if member.get("source") != "number_check":
            continue
        stated = member["number_check"]["stated"]
        whole = f"{float(stated):,.0f}" if float(stated).is_integer() else stated
        forms = {stated, whole, whole.replace(",", "")}
        pattern = re.compile(
            r"(?<![\w.,])(?:" + "|".join(map(re.escape, forms)) + r")(?![\w]|[.,]\d)"
        )
        source = sources.get(member["evidence"][0]["source_id"])
        if source is None:
            continue
        blocks = [
            b
            for b in source["segments"]
            if not _REFERENCE_HEADING.match(b["locator"]) and pattern.search(b["text"])
        ]
        if len(blocks) >= LOAD_BEARING_BLOCKS:
            return stated
    return None


def _summaries(scan: dict[str, Any], segment_ids: list[str]) -> list[dict[str, str]]:
    stored = scan.get("summaries", {})
    return [
        {"id": s, "title": _segment(scan, s)["title"], "summary": stored[s]}
        for s in segment_ids
        if s in stored
    ]


def _overview_request(scan: dict[str, Any], root: Path) -> dict[str, Any]:
    overview_path = root / "overview.json"
    scan_id = scan["scan_id"]
    return {
        "overview_path": str(overview_path),
        "overview_template": {
            "summary": "",
            "analysis": "",
            "considerations": [{"kind": "", "consideration": "", "quote": ""}],
            "main_conclusions": [{"quote": "", "locator": ""}],
        },
        "overview_fields": OVERVIEW_FIELDS,
        "special_kinds": SPECIAL_KINDS,
        "overview_instructions": (
            "Before any pass, write the initial summary: a faithful account of the article as "
            "the authors present it, not a preliminary review. Describe; do not evaluate. "
            "Considerations are the article's own special considerations, the things the "
            "authors themselves single out (scope, acknowledged limitations, ethics, context, "
            "justified choices), each stated as the authors state it and quoted verbatim. "
            "main_conclusions quote what the article concludes, proposes, or recommends, in the "
            "authors' words. "
            f"Write overview_template, filled in, as a new file at {overview_path}, then run "
            f"creview scan overview {scan_id} {overview_path}."
        ),
    }


def set_overview(scan_id: str, overview_path: Path) -> dict[str, Any]:
    """Store the initial summary, written before the passes, that the conversation opens with."""
    root = _scan_root(scan_id)
    raw = read_json(overview_path)
    if not isinstance(raw, dict):
        raise ReviewError(
            "overview must be an object with summary, analysis, considerations, and "
            "main_conclusions"
        )
    summary = str(raw.get("summary") or "").strip()
    analysis = str(raw.get("analysis") or "").strip()
    considerations = raw.get("considerations") or []
    conclusions = raw.get("main_conclusions") or []
    problems = [
        f"overview needs {name}: {OVERVIEW_FIELDS[name]}"
        for name, value in (("summary", summary), ("analysis", analysis))
        if not value
    ]
    if not isinstance(considerations, list):
        problems.append("overview considerations must be a list")
        considerations = []
    if not isinstance(conclusions, list):
        problems.append("overview main_conclusions must be a list")
        conclusions = []
    with FileLock(str(root / ".lock")):
        scan = read_json(root / "scan.json")
        if scan["phase"] != "summary":
            raise ReviewError(
                "the initial summary is written once, after the plan and before the passes"
            )
        sources = {s["source_id"]: s for s in _current_sources(scan)}
        checked: list[dict[str, Any]] = []
        for number, item in enumerate(considerations, start=1):
            if not isinstance(item, dict):
                problems.append(f"consideration {number} must be an object")
                continue
            kind = str(item.get("kind") or "").strip().lower()
            text = str(item.get("consideration") or "").strip()
            if not text and not kind and not item.get("quote"):
                continue  # an untouched template entry
            if kind not in SPECIAL_KINDS:
                problems.append(
                    f"consideration {number} kind must be one of {', '.join(SPECIAL_KINDS)}"
                )
                continue
            if not text:
                problems.append(f"consideration {number} needs consideration")
                continue
            evidence, problem = _check_quote(f"consideration {number}", item, sources)
            if evidence is None:
                problems.append(f"{problem}; quote the authors' own words for it")
                continue
            checked.append({"kind": kind, "consideration": text[:500], "evidence": evidence})
        if len(checked) > MAX_CONSIDERATIONS:
            problems.append(f"overview has more than {MAX_CONSIDERATIONS} considerations")
        main: list[dict[str, str]] = []
        for number, item in enumerate(conclusions, start=1):
            if isinstance(item, str):
                item = {"quote": item}
            if isinstance(item, dict) and not str(item.get("quote") or "").strip():
                continue  # an untouched template entry
            evidence, problem = _check_quote(f"main conclusion {number}", item, sources)
            if evidence is None:
                problems.append(f"{problem}; quote the authors' own words for it")
                continue
            main.append(evidence)
        if not main and not any("main conclusion" in p for p in problems):
            problems.append(
                f"overview needs main_conclusions: {OVERVIEW_FIELDS['main_conclusions']}"
            )
        if len(main) > MAX_MAIN_CONCLUSIONS:
            problems.append(f"overview has more than {MAX_MAIN_CONCLUSIONS} main_conclusions")
        if problems:
            raise ReviewError("overview refused: " + "; ".join(problems))
        scan.update(
            overview={
                "summary": summary[:3000],
                "analysis": analysis[:3000],
                "considerations": checked,
                "main_conclusions": main,
            },
            phase="scanning",
            updated_at=now_iso(),
        )
        atomic_write_json(root / "scan.json", scan)
    return {"scan_id": scan_id, "state": "scanning", "next": f"creview scan next {scan_id}"}


def _entry_texts(scan: dict[str, Any], entry: dict[str, Any]) -> list[str]:
    """Everything written about a pool entry: every member's text, not only the lead's."""
    members = [c for c in scan["candidates"] if c["id"] in entry["member_ids"]]
    texts = [entry.get("label") or ""]
    for member in members:
        texts += [member["potential_issue"], member["why_it_matters"]]
        texts += member["solution_candidates"]
    return [text for text in texts if text]


def _literature(
    scan: dict[str, Any], entry: dict[str, Any], blocks: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """creview's labels for the works an entry cites, and pending lookups it prepared for them."""
    texts = _entry_texts(scan, entry)
    labelled = label_citations(texts, blocks)
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


def _presented(scan: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    members = _members(scan, entry)
    lead = max(members, key=lambda c: len(c["why_it_matters"]))
    evidence = list(
        {
            (e["source_id"], e["locator"], e["quote"]): e for m in members for e in m["evidence"]
        }.values()
    )
    solutions = list(dict.fromkeys(s for m in members for s in m["solution_candidates"]))
    mains = _main_conclusions(scan)
    main = entry.get("main_conclusion")
    check = next((m["number_check"] for m in members if m.get("number_check")), None)
    return {
        "pool_id": entry["id"],
        "concern": entry.get("label"),
        "potential_issue": lead["potential_issue"],
        "why_it_matters": lead["why_it_matters"],
        "severity": entry["severity"],
        "severity_basis": entry.get("severity_basis"),
        "major_flaws": entry.get("major_flaws") or [],
        "profile_area": lead["profile_area"],
        "segments": [{"id": s, "title": _segment(scan, s)["title"]} for s in entry["segment_ids"]],
        "evidence": evidence,
        "solution_candidates": solutions,
        "type": lead.get("type"),
        "verifiable": _verifiable(scan, entry),
        **({"computed_check": check} if check else {}),
        "main_conclusion": mains[main]["quote"] if main is not None else None,
        "context": _summaries(scan, entry["segment_ids"]),
    }


def _verifiable(scan: dict[str, Any], entry: dict[str, Any]) -> bool:
    """A computed number check, or an inconsistency quoting both statements (checked at submit):
    the manuscript itself shows it, so no ranking judgement may hide it."""
    return any(
        c.get("source") == "number_check" or c.get("type") == "inconsistency"
        for c in scan["candidates"]
        if c["id"] in entry["member_ids"]
    )


def _minor_order(scan: dict[str, Any]) -> list[dict[str, Any]]:
    """Kept minors: verifiable ones first, then by how many independent passes raised them,
    relative to their segments' passes."""
    minors = [p for p in scan["pool"] if p["decision"] == "keep" and p["severity"] == "minor"]
    return sorted(
        minors,
        key=lambda p: (not _verifiable(scan, p), -_support(scan, p), p["id"]),
    )


def _reserve_ids(scan: dict[str, Any]) -> set[str]:
    """Minors past the first MAX_ACTIVE_MINORS in order, surfaced only on request. A verifiable
    entry is never held back."""
    return {
        p["id"]
        for index, p in enumerate(_minor_order(scan))
        if index >= MAX_ACTIVE_MINORS and not _verifiable(scan, p)
    }


def next_candidate(scan_id: str, *, reserve: bool = False) -> dict[str, Any]:
    """The next kept candidates: one major at a time in plan order, then minors in order in
    batches of up to three. Each must have a recorded response before the next call. Minors
    beyond the first MAX_ACTIVE_MINORS are a reserve, surfaced only with `reserve`."""
    root = _scan_root(scan_id)
    with FileLock(str(root / ".lock")):
        scan = read_json(root / "scan.json")
        if scan["phase"] != "ready":
            raise ReviewError(f"the scan is in {scan['phase']}; {_phase_next(scan)}")
        first = not scan.get("overview_presented_at") and not any(
            p.get("surfaced_at") for p in scan["pool"]
        )
        held = _reserve_ids(scan)
        kept = [p for p in scan["pool"] if p["decision"] == "keep" and not p["surfaced_at"]]
        position = {p["id"]: n for n, p in enumerate(_minor_order(scan))}
        kept.sort(key=lambda p: (p["severity"] != "major", position.get(p["id"], 0), p["id"]))
        reserve_left = any(p["id"] in held for p in kept)
        if not reserve:
            kept = [p for p in kept if p["id"] not in held]
        waiting = [p for p in scan["pool"] if p.get("surfaced_at") and not p.get("disposition")]
        if waiting and kept:
            ids = ", ".join(p["id"] for p in waiting)
            raise ReviewError(
                f"record the reviewer's response to {ids} first: creview scan record {scan_id} "
                f"POOL_ID {'|'.join(DISPOSITIONS)}. If the reviewer has not answered, end the "
                "turn and wait"
            )
        opening = {}
        if first and scan.get("overview"):
            scan["overview_presented_at"] = now_iso()
            opening = {
                "overview": scan["overview"],
                "overview_instructions": (
                    "Before anything else, present this initial summary to the reviewer as "
                    "stored: the summary, the analysis (methods, models, and frameworks), and "
                    "the article's own special considerations with their quotes. It was written "
                    "before the scan; do not add findings or evaluation to it. Tell the "
                    "reviewer once that you can propose literature lookups (Crossref or OpenAlex, "
                    "each exact query run only with their approval) where a point depends on "
                    "literature, and that they can ask for one at any time. Then continue."
                ),
            }
        if not kept:
            atomic_write_json(root / "scan.json", scan)
            return {
                "scan_id": scan_id,
                **opening,
                "candidates": [],
                "more_available": False,
                "next_severity": None,
                "reserve_available": reserve_left,
            }
        if kept[0]["severity"] == "major":
            # Majors on the same main conclusion come together, so the reviewer can answer them
            # as one point or tell them apart.
            lead = kept[0]
            batch = [lead] + [
                p
                for p in kept[1:]
                if p["severity"] == "major"
                and lead.get("main_conclusion") is not None
                and p.get("main_conclusion") == lead["main_conclusion"]
            ][: MAX_MINOR_BATCH - 1]
        else:
            batch = [p for p in kept if p["severity"] == "minor"][:MAX_MINOR_BATCH]
        # Build everything first: a failure here must not leave an entry marked as shown.
        blocks = next(s for s in _current_sources(scan) if s["source_id"] == "manuscript")[
            "segments"
        ]
        presented = []
        for entry in batch:
            record = _presented(scan, entry)
            record["literature"], record["lookups"] = _literature(scan, entry, blocks)
            presented.append(record)
        for entry in batch:
            entry["surfaced_at"] = now_iso()
        atomic_write_json(root / "scan.json", scan)
    if batch[0]["severity"] == "minor":
        shape = "Present these minor candidates together as one batch of issue records"
    elif len(batch) == 1:
        shape = "Present this major candidate as the current issue record"
    else:
        shape = (
            "Present these major candidates together: they challenge the same main conclusion. "
            "Say which conclusion, present each as an issue record, and ask whether the "
            "reviewer sees them as one point or several"
        )
    ids = " ".join(entry["id"] for entry in batch)
    return {
        "scan_id": scan_id,
        **opening,
        "candidates": presented,
        "more_available": len(kept) > len(batch),
        "reserve_available": reserve_left and len(kept) == len(batch),
        # Lets the agent ask whether to go on to minors before surfacing any.
        "next_severity": kept[len(batch)]["severity"] if len(kept) > len(batch) else None,
        "instructions": (
            f"{shape}, following the development contract, and present only what is returned "
            "here, never other pool entries from memory. Open each with its context: in one or "
            "two sentences, what the authors do in the cited segments, drawn from its context "
            "summaries. In why it matters, give the strongest reply the authors could make from "
            "their own manuscript, citing where it says so, and why the concern survives it, so "
            "the reviewer can judge it quickly; if the reply answers the concern, say so plainly. "
            "For a computed_check, show the expression and the stated figure, and ask the "
            "reviewer to confirm the expression is what the manuscript implies. literature gives "
            "creview's label for each work the record cites; use exactly those labels, and "
            "label any content_claim (what a work argues or requires) model_lead, since only the "
            "source itself can confirm it. lookups "
            "are prepared Crossref requests, not yet run: show each one's exact query and URL in "
            "the literature context and ask whether to run it; run one only after the reviewer "
            "approves it, with creview lookup run REQUEST_ID --approval-statement and their "
            "words. Anything else you say about what a named source argues is model_lead. Do not "
            "mention how many candidates remain or "
            "what they concern, and never refer to one not yet surfaced, not even to suggest "
            "combining it with this one. Then ask for the reviewer's view and end your turn. "
            f"When the reviewer responds, record each of {ids} with creview scan record "
            f"{scan_id} POOL_ID DISPOSITION ({', '.join(DISPOSITIONS)}); scan candidate refuses "
            "more candidates until every one shown has a recorded response."
        ),
    }


def record_response(scan_id: str, pool_id: str, disposition: str, words: str) -> dict[str, Any]:
    """Record the reviewer's disposition of a surfaced candidate; it can be revised later.

    `words` must quote the reviewer's reply, sent after the candidate was shown."""
    disposition = disposition.strip().lower()
    if disposition not in DISPOSITIONS:
        raise ReviewError(f"disposition must be one of {', '.join(DISPOSITIONS)}")
    root = _scan_root(scan_id)
    with FileLock(str(root / ".lock")):
        scan = read_json(root / "scan.json")
        entry = next((p for p in scan["pool"] if p["id"] == pool_id), None)
        if entry is None or not entry.get("surfaced_at"):
            raise ReviewError(f"{pool_id} has not been surfaced to the reviewer")
        reply = reviewer_words(
            words,
            hermes_session=scan.get("session_source") == "hermes_session",
            what=f"the response to {pool_id}",
            since=entry["surfaced_at"],
        )
        entry.update(disposition=disposition, responded_at=now_iso(), response=reply)
        scan["updated_at"] = now_iso()
        atomic_write_json(root / "scan.json", scan)
    return {
        "scan_id": scan_id,
        "pool_id": pool_id,
        "disposition": disposition,
        "records": _record_counts(scan),
    }


def _record_counts(scan: dict[str, Any]) -> dict[str, int]:
    """Status counts over surfaced candidates only; unanswered ones count as `candidate`."""
    surfaced = [p for p in scan["pool"] if p.get("surfaced_at")]
    counts = {name: 0 for name in ("accepted", "developing", "candidate", "deferred", "dismissed")}
    for entry in surfaced:
        counts[entry.get("disposition") or "candidate"] += 1
    return counts


def scan_status(scan_id: str) -> dict[str, Any]:
    """Coverage progress the reviewer may see; never the size of the unsurfaced pool."""
    root = _scan_root(scan_id)
    scan = read_json(root / "scan.json")
    segments = []
    for segment in (scan["plan"] or {}).get("segments", []):
        tasks = [t for t in scan["tasks"] if t["segment_id"] == segment["id"]]
        segments.append(
            {
                "id": segment["id"],
                "title": segment["title"],
                "tier": segment["tier"],
                "passes_done": sum(t["status"] == "done" for t in tasks),
                "passes": len(tasks),
            }
        )
    return {
        "scan_id": scan_id,
        "phase": scan["phase"],
        "segments": segments,
        "surfaced": sum(1 for p in scan["pool"] if p.get("surfaced_at")),
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
