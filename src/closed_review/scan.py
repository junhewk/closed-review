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

import re
import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from filelock import FileLock

from .cases import now_iso
from .errors import ReviewError
from .hermes import inspect_profile
from .io import atomic_write_json, data_home, ensure_private_dir, read_json, sha256_file
from .parsers import parse_document
from .segments import TIER_PASSES, draft_plan, outline, segment_blocks, validate_plan
from .session import preflight_summary, session_key

SCAN_ID_RE = re.compile(r"^scan-\d{8}T\d{6}Z-[0-9a-f]{8}$")
SEVERITIES = ("major", "minor")
CANDIDATE_FIELDS = {
    "potential_issue": "a falsifiable, proportionate concern, not a verdict",
    "why_it_matters": "the consequence for validity, interpretation, ethics, or use",
    "severity": "major or minor",
    "profile_area": "the design profile area this falls under, if any",
    "evidence": "one or more {source_id, locator, quote} with the quote copied verbatim",
    "solution_candidates": "proportionate ways the authors could resolve it",
}
SUMMARY_FIELD = (
    "two or three neutral sentences on what this segment says and does: its claims, data or "
    "sources, and the methods, models, or frameworks it uses; no evaluation"
)
OVERVIEW_FIELDS = {
    "summary": "what the article asks, what it does, and what it concludes, in a short paragraph",
    "analysis": (
        "the design, the data or sources, the analytic methods, and the theoretical models or "
        "frameworks the analysis uses, as the authors describe them"
    ),
    "considerations": (
        "up to five open questions about the article as a whole for the reviewer to weigh, such "
        "as its contribution and place in the field, the scope of its conclusions, frameworks or "
        "guidance it could engage, and context such as ethics or applicability"
    ),
}
MAX_CONSIDERATIONS = 5


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
    manuscript: Path, supplements: list[Path] | None = None, session: str | None = None
) -> dict[str, Any]:
    key, source = session_key(session)
    preflight = preflight_summary(key, source)
    if preflight["status"] != "passed":
        raise ReviewError("run `creview session start` in this Hermes session before a deep scan")
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
        "plan": None,
        "tasks": [],
        "candidates": [],
        "pool": [],
    }
    atomic_write_json(root / "scan.json", scan)
    draft_path = root / "plan-draft.json"
    atomic_write_json(draft_path, draft_plan(sources))
    return {
        "scan_id": scan_id,
        "plan_draft_path": str(draft_path),
        "sources": scan["sources"],
        "next": f"refine the draft plan, then run creview scan plan {scan_id} PLAN_PATH",
    }


def set_plan(scan_id: str, plan_path: Path) -> dict[str, Any]:
    root = _scan_root(scan_id)
    with FileLock(str(root / ".lock")):
        scan = read_json(root / "scan.json")
        if any(task["status"] == "done" for task in scan["tasks"]):
            raise ReviewError("the scan has started; start a new scan to change the plan")
        plan = validate_plan(read_json(plan_path), _current_sources(scan))
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
        scan.update(plan=plan, tasks=tasks, phase="scanning", updated_at=now_iso())
        atomic_write_json(root / "scan.json", scan)
    return {
        "scan_id": scan_id,
        "segments": outline(plan),
        "passes": len(tasks),
        "warnings": plan["warnings"],
        "next": f"creview scan next {scan_id}",
    }


def _segment(scan: dict[str, Any], segment_id: str) -> dict[str, Any]:
    return next(s for s in scan["plan"]["segments"] if s["id"] == segment_id)


def next_task(scan_id: str) -> dict[str, Any]:
    _require_profile()
    root = _scan_root(scan_id)
    scan = read_json(root / "scan.json")
    if scan["phase"] == "planning":
        raise ReviewError(f"set the segment plan first: creview scan plan {scan_id} PLAN_PATH")
    task = next((t for t in scan["tasks"] if t["status"] == "pending"), None)
    if task is None:
        return {"scan_id": scan_id, "state": scan["phase"], "next": _phase_next(scan)}
    sources = {s["source_id"]: s for s in _current_sources(scan)}
    segment = _segment(scan, task["segment_id"])
    proposal_path = root / "proposals" / f"{task['id']}.json"
    if not proposal_path.exists():
        template: dict[str, Any] = {"task_id": task["id"], "note": "", "candidates": []}
        if task["pass"] == 1:
            template["summary"] = ""
        atomic_write_json(proposal_path, template)
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
        "candidate_fields": CANDIDATE_FIELDS,
        **({"summary_field": SUMMARY_FIELD} if task["pass"] == 1 else {}),
        "instructions": (
            f"{angle} The whole manuscript is available through the outline and the attached "
            "file; focus on this segment. Check each concern against the confirmed profiles' "
            "false alarms before adding it. Write candidates to the proposal file, then run "
            f"creview scan submit {scan_id} PROPOSAL_PATH. Do not tell the reviewer about "
            "candidates, their number, or their content during the scan."
        ),
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
    evidence = raw.get("evidence")
    checked: list[dict[str, str]] = []
    if not isinstance(evidence, list) or not evidence:
        problems.append(f"candidate {index} needs at least one evidence quote")
        evidence = []
    for number, item in enumerate(evidence, start=1):
        label = f"candidate {index} evidence {number}"
        if not isinstance(item, dict):
            problems.append(f"{label} must be an object")
            continue
        source = sources.get(str(item.get("source_id") or ""))
        locator = str(item.get("locator") or "")
        quote = str(item.get("quote") or "").strip()
        block = next(
            (b for b in (source or {}).get("segments", []) if b["locator"] == locator), None
        )
        if source is None or block is None:
            problems.append(f"{label} cites an unknown source or locator")
        elif not quote or _flat(quote) not in _flat(block["text"]):
            problems.append(f"{label} quote is not verbatim at {locator}")
        else:
            checked.append({"source_id": source["source_id"], "locator": locator, "quote": quote})
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
        "profile_area": str(raw.get("profile_area") or "").strip() or None,
        "evidence": checked,
        "solution_candidates": [str(s).strip() for s in solutions if str(s).strip()],
    }, []


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
        for index, item in enumerate(raw, start=1):
            candidate, issues = _validate_candidate(index, item, sources)
            problems.extend(issues)
            if candidate:
                accepted.append(candidate)
        summary = str(proposal.get("summary") or "").strip()
        if task["pass"] == 1 and not summary:
            problems.append("a first-pass proposal needs summary: " + SUMMARY_FIELD)
        if problems:
            raise ReviewError("proposal refused: " + "; ".join(problems))
        if task["pass"] == 1:
            scan.setdefault("summaries", {})[task["segment_id"]] = summary[:2000]
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
    return {
        "scan_id": scan_id,
        "task_id": task["id"],
        "state": scan["phase"],
        "next": _phase_next(scan),
    }


def _phase_next(scan: dict[str, Any]) -> str | None:
    scan_id = scan["scan_id"]
    return {
        "planning": f"creview scan plan {scan_id} PLAN_PATH",
        "scanning": f"creview scan next {scan_id}",
        "synthesis": f"creview scan synthesize {scan_id}",
        "screening": f"creview scan screen {scan_id} SCREENING_PATH",
        "overview": f"creview scan overview {scan_id} OVERVIEW_PATH",
        "ready": f"creview scan candidate {scan_id}",
    }.get(scan["phase"])


def _overlap(a: dict[str, Any], b: dict[str, Any]) -> bool:
    for x in a["evidence"]:
        for y in b["evidence"]:
            if (x["source_id"], x["locator"]) != (y["source_id"], y["locator"]):
                continue
            qx, qy = _flat(x["quote"]).lower(), _flat(y["quote"]).lower()
            if qx in qy or qy in qx:
                return True
    return False


def synthesize(scan_id: str) -> dict[str, Any]:
    """Merge candidates that quote the same passage, then hand the pool to the agent to screen."""
    root = _scan_root(scan_id)
    with FileLock(str(root / ".lock")):
        scan = read_json(root / "scan.json")
        if scan["phase"] not in {"synthesis", "screening"}:
            raise ReviewError(f"the scan is in {scan['phase']}; finish the passes first")
        candidates = scan["candidates"]
        parent = list(range(len(candidates)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                if _overlap(candidates[i], candidates[j]):
                    parent[find(j)] = find(i)
        groups: dict[int, list[dict[str, Any]]] = {}
        for index, candidate in enumerate(candidates):
            groups.setdefault(find(index), []).append(candidate)
        order = {s["id"]: n for n, s in enumerate(scan["plan"]["segments"])}
        pool = []
        for members in sorted(
            groups.values(), key=lambda m: (order[m[0]["segment_id"]], m[0]["id"])
        ):
            pool.append(
                {
                    "id": f"pool-{len(pool) + 1:03d}",
                    "member_ids": [m["id"] for m in members],
                    "segment_ids": sorted({m["segment_id"] for m in members}, key=order.get),
                    "severity": "major"
                    if any(m["severity"] == "major" for m in members)
                    else "minor",
                    "decision": None,
                    "surfaced_at": None,
                }
            )
        scan.update(pool=pool, phase="screening", updated_at=now_iso())
        atomic_write_json(root / "scan.json", scan)
        by_id = {c["id"]: c for c in candidates}
        screening_path = root / "screening.json"
        atomic_write_json(
            screening_path,
            [
                {
                    "id": p["id"],
                    "decision": "",
                    "severity": p["severity"],
                    "reason": "",
                    "potential_issue": "",
                }
                for p in pool
            ],
        )
    return {
        "scan_id": scan_id,
        "pool": [p | {"members": [by_id[m] for m in p["member_ids"]]} for p in pool],
        "screening_path": str(screening_path),
        "instructions": (
            "For each entry decide keep, merge, or drop. Entries were merged only when they quote "
            "the same passage, so the same concern raised in different segments or with different "
            "quotes still appears more than once: keep the clearest one and set the others to "
            "merge with into set to its id. Drop an entry, with a reason, when it matches a "
            "confirmed profile's false alarms or is not supported by its quotes. For a kept entry "
            "set severity (major only when it could change the paper's validity, interpretation, "
            "or contribution), and optionally potential_issue to one wording that covers its "
            "members. Then run "
            f"creview scan screen {scan_id} SCREENING_PATH. Do not show this pool to the reviewer."
        ),
    }


def screen(scan_id: str, screening_path: Path) -> dict[str, Any]:
    root = _scan_root(scan_id)
    decisions = read_json(screening_path)
    if not isinstance(decisions, list):
        raise ReviewError("screening file must be a list")
    with FileLock(str(root / ".lock")):
        scan = read_json(root / "scan.json")
        if scan["phase"] != "screening":
            raise ReviewError(f"the scan is in {scan['phase']}, not screening")
        by_id = {p["id"]: p for p in scan["pool"]}
        given = {str(d.get("id")): d for d in decisions if isinstance(d, dict)}
        missing = sorted(set(by_id) - set(given))
        if missing:
            raise ReviewError(f"screening has no decision for {', '.join(missing[:5])}")
        merges: list[tuple[str, str]] = []
        for pool_id, entry in by_id.items():
            decision = str(given[pool_id].get("decision") or "").strip().lower()
            reason = str(given[pool_id].get("reason") or "").strip()
            if decision not in {"keep", "drop", "merge"}:
                raise ReviewError(f"{pool_id} decision must be keep, drop, or merge")
            if decision == "drop" and not reason:
                raise ReviewError(f"{pool_id} is dropped without a reason")
            if decision == "merge":
                target = str(given[pool_id].get("into") or "").strip()
                if target == pool_id or target not in by_id:
                    raise ReviewError(f"{pool_id} must merge into another pool entry")
                merges.append((pool_id, target))
            severity = str(given[pool_id].get("severity") or entry["severity"]).lower()
            if severity not in SEVERITIES:
                raise ReviewError(f"{pool_id} severity must be major or minor")
            entry.update(
                decision=decision,
                reason=reason or None,
                severity=severity,
                wording=str(given[pool_id].get("potential_issue") or "").strip() or None,
            )
        order = {s["id"]: n for n, s in enumerate(scan["plan"]["segments"])}
        for source_id, target_id in merges:
            target = by_id[target_id]
            if target["decision"] != "keep":
                raise ReviewError(f"{source_id} merges into {target_id}, which is not kept")
            source = by_id[source_id]
            target["member_ids"] += source["member_ids"]
            target["segment_ids"] = sorted(
                {*target["segment_ids"], *source["segment_ids"]}, key=order.get
            )
            if source["severity"] == "major":
                target["severity"] = "major"
            source["merged_into"] = target_id
        scan.update(phase="overview", updated_at=now_iso())
        atomic_write_json(root / "scan.json", scan)
        overview_path = root / "overview.json"
        atomic_write_json(overview_path, {"summary": "", "analysis": "", "considerations": []})
    return {
        "scan_id": scan_id,
        "state": "overview",
        "segment_summaries": _summaries(scan, [s["id"] for s in scan["plan"]["segments"]]),
        "overview_path": str(overview_path),
        "overview_fields": OVERVIEW_FIELDS,
        "instructions": (
            "Write the article overview from the segment summaries, reading the manuscript again "
            "where they leave something unclear. Considerations are questions for the reviewer, "
            "not candidates: give them no severity or evidence, and do not restate or preview a "
            "kept candidate. Then run "
            f"creview scan overview {scan_id} OVERVIEW_PATH."
        ),
        "next": f"creview scan overview {scan_id} OVERVIEW_PATH",
    }


def _summaries(scan: dict[str, Any], segment_ids: list[str]) -> list[dict[str, str]]:
    stored = scan.get("summaries", {})
    return [
        {"id": s, "title": _segment(scan, s)["title"], "summary": stored[s]}
        for s in segment_ids
        if s in stored
    ]


def set_overview(scan_id: str, overview_path: Path) -> dict[str, Any]:
    """Store the article overview the conversation opens with, before the first candidate."""
    root = _scan_root(scan_id)
    raw = read_json(overview_path)
    if not isinstance(raw, dict):
        raise ReviewError("overview must be an object with summary, analysis, and considerations")
    summary = str(raw.get("summary") or "").strip()
    analysis = str(raw.get("analysis") or "").strip()
    considerations = raw.get("considerations") or []
    problems = [
        f"overview needs {name}: {OVERVIEW_FIELDS[name]}"
        for name, value in (("summary", summary), ("analysis", analysis))
        if not value
    ]
    if not isinstance(considerations, list):
        problems.append("overview considerations must be a list")
        considerations = []
    considerations = [str(c).strip() for c in considerations if str(c).strip()]
    if len(considerations) > MAX_CONSIDERATIONS:
        problems.append(f"overview has more than {MAX_CONSIDERATIONS} considerations")
    if problems:
        raise ReviewError("overview refused: " + "; ".join(problems))
    with FileLock(str(root / ".lock")):
        scan = read_json(root / "scan.json")
        if scan["phase"] not in {"overview", "ready"}:
            raise ReviewError(f"the scan is in {scan['phase']}; {_phase_next(scan)}")
        if scan.get("overview_presented_at"):
            raise ReviewError("the overview was already presented to the reviewer")
        scan.update(
            overview={
                "summary": summary[:3000],
                "analysis": analysis[:3000],
                "considerations": [c[:500] for c in considerations],
            },
            phase="ready",
            updated_at=now_iso(),
        )
        atomic_write_json(root / "scan.json", scan)
    return {"scan_id": scan_id, "state": "ready", "next": f"creview scan candidate {scan_id}"}


def next_candidate(scan_id: str) -> dict[str, Any]:
    """One kept, not yet surfaced candidate: majors first, each in plan order."""
    root = _scan_root(scan_id)
    with FileLock(str(root / ".lock")):
        scan = read_json(root / "scan.json")
        if scan["phase"] != "ready":
            raise ReviewError(f"the scan is in {scan['phase']}; {_phase_next(scan)}")
        first = not scan.get("overview_presented_at") and not any(
            p.get("surfaced_at") for p in scan["pool"]
        )
        kept = [p for p in scan["pool"] if p["decision"] == "keep" and not p["surfaced_at"]]
        kept.sort(key=lambda p: (p["severity"] != "major", p["id"]))
        opening = {}
        if first and scan.get("overview"):
            scan["overview_presented_at"] = now_iso()
            opening = {
                "overview": scan["overview"],
                "overview_instructions": (
                    "Before anything else, present this overview to the reviewer: the summary, "
                    "the analysis (methods, models, and frameworks), and the considerations as "
                    "open questions. Then continue."
                ),
            }
        if not kept:
            atomic_write_json(root / "scan.json", scan)
            return {"scan_id": scan_id, **opening, "candidate": None, "more_available": False}
        entry = kept[0]
        entry["surfaced_at"] = now_iso()
        atomic_write_json(root / "scan.json", scan)
    members = [c for c in scan["candidates"] if c["id"] in entry["member_ids"]]
    lead = max(members, key=lambda c: len(c["why_it_matters"]))
    evidence = list(
        {
            (e["source_id"], e["locator"], e["quote"]): e for m in members for e in m["evidence"]
        }.values()
    )
    solutions = list(dict.fromkeys(s for m in members for s in m["solution_candidates"]))
    return {
        "scan_id": scan_id,
        **opening,
        "candidate": {
            "pool_id": entry["id"],
            "potential_issue": entry["wording"] or lead["potential_issue"],
            "why_it_matters": lead["why_it_matters"],
            "severity": entry["severity"],
            "profile_area": lead["profile_area"],
            "segments": [
                {"id": s, "title": _segment(scan, s)["title"]} for s in entry["segment_ids"]
            ],
            "evidence": evidence,
            "solution_candidates": solutions,
        },
        "context": _summaries(scan, entry["segment_ids"]),
        "more_available": len(kept) > 1,
        "instructions": (
            "Present this as the current candidate record, following the development contract. "
            "Open it with its context: in one or two sentences, what the authors do in the cited "
            "segments, drawn from the context summaries. Do not mention how many candidates remain."
        ),
    }


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
        "next": _phase_next(scan),
    }


def purge_scan(scan_id: str, confirmation: str) -> dict[str, Any]:
    root = _scan_root(scan_id)
    if confirmation != scan_id:
        raise ReviewError("confirm by repeating the scan id")
    shutil.rmtree(root)
    return {"scan_id": scan_id, "purged": True}
