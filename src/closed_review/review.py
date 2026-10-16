from __future__ import annotations

import os
import re
import secrets
from collections import defaultdict
from pathlib import Path
from typing import Any

from filelock import FileLock

from .cases import append_event, load_source, now_iso
from .errors import ReviewError
from .hermes import inspect_profile, require_ready_profile, selected_profile
from .io import (
    atomic_write_json,
    atomic_write_text,
    case_root,
    ensure_private_dir,
    load_case,
    permission_problem,
    read_json,
    secure_file,
    sha256_file,
)
from .receipts import RECEIPT_NAME, write_receipt
from .segments import draft_plan, outline, validate_plan

DEFAULT_BATCH_ITEMS = 3
MAX_BATCH_ITEMS = 5
FINDING_CATEGORIES = {
    "contribution_scope",
    "literature_theory",
    "design_methods",
    "analysis_statistics",
    "results",
    "interpretation_conclusions",
    "ethics_transparency",
    "references_reporting",
    "organization_clarity",
    "presentation_mechanics",
}
SEVERITIES = {"major", "minor"}
AUDIENCES = {"authors", "editor", "both"}
CONFIDENCE = {"low", "medium", "high"}
VERIFICATION = {"verified", "inference", "unresolved"}
RECOMMENDATIONS = {"accept", "minor_revision", "major_revision", "reject"}
FINDING_STATUSES = {"candidate", "developing", "accepted", "deferred", "dismissed"}
LITERATURE_TIERS = {
    "supplied_source",
    "manuscript_reported",
    "user_lead",
    "model_lead",
    "metadata_verified",
}

RUBRIC = [
    (
        "rubric-contribution",
        "Contribution and scope",
        "Assess the question, contribution, originality claims, and fit.",
    ),
    (
        "rubric-literature",
        "Literature and theory",
        "Assess framing, relevant alternatives, and whether claims follow from cited work.",
    ),
    (
        "rubric-methods",
        "Design and methods",
        "Assess design fitness, sampling, measurement, procedures, and reproducibility.",
    ),
    (
        "rubric-analysis",
        "Analysis and statistics",
        "Check analysis choices and recompute only claims supported by supplied numbers.",
    ),
    (
        "rubric-results",
        "Results",
        "Check completeness, internal consistency, tables, figures, and separation "
        "from interpretation.",
    ),
    (
        "rubric-interpretation",
        "Interpretation and conclusions",
        "Assess whether conclusions match results and limitations.",
    ),
    (
        "rubric-ethics",
        "Ethics and transparency",
        "Check ethics, consent, conflicts, funding, data/code access, and disclosures "
        "when applicable.",
    ),
    (
        "rubric-reporting",
        "References and reporting",
        "Check reference support, reporting completeness, and supplied journal requirements.",
    ),
    (
        "rubric-clarity",
        "Organization and clarity",
        "Identify structural or clarity problems that affect evaluation.",
    ),
    (
        "rubric-supplements",
        "Supplements and cross-document consistency",
        "Check consistency across the manuscript, supplements, guidance, and review form.",
    ),
]


def _sentence_candidates(source: dict[str, Any]) -> list[dict[str, Any]]:
    seen: dict[str, tuple[str, str]] = {}
    candidates: list[dict[str, Any]] = []
    for segment in source["segments"]:
        sentences = re.split(r"(?<=[.!?])\s+", segment["text"])
        for sentence in sentences:
            normalized = re.sub(r"\W+", " ", sentence.lower()).strip()
            if len(normalized) < 60:
                continue
            if normalized in seen:
                first_locator, first_text = seen[normalized]
                candidates.append(
                    {
                        "kind": "duplicate_sentence",
                        "source_id": source["source_id"],
                        "locator": segment["locator"],
                        "quote": sentence.strip(),
                        "message": f"Possible duplicate of {first_locator}: {first_text[:160]}",
                    }
                )
            else:
                seen[normalized] = (segment["locator"], sentence.strip())
    return candidates


def _numbering_candidates(source: dict[str, Any]) -> list[dict[str, Any]]:
    collected: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    for segment in source["segments"]:
        for match in re.finditer(r"\b(Figure|Fig\.?|Table)\s+(\d+)\b", segment["text"], re.I):
            label = "table" if match.group(1).lower().startswith("table") else "figure"
            collected[label].append((int(match.group(2)), segment["locator"], match.group(0)))
    candidates: list[dict[str, Any]] = []
    for label, values in collected.items():
        numbers = sorted({value[0] for value in values})
        if len(numbers) < 2:
            continue
        missing = sorted(set(range(numbers[0], numbers[-1] + 1)) - set(numbers))
        if missing:
            _, locator, quote = values[0]
            candidates.append(
                {
                    "kind": "numbering_gap",
                    "source_id": source["source_id"],
                    "locator": locator,
                    "quote": quote,
                    "message": f"Possible {label} numbering gap: missing {missing}",
                }
            )
    return candidates


def _citation_candidates(source: dict[str, Any]) -> list[dict[str, Any]]:
    citations: set[int] = set()
    references: set[int] = set()
    first: dict[int, tuple[str, str]] = {}
    for segment in source["segments"]:
        for match in re.finditer(r"\[(\d{1,4})\]", segment["text"]):
            number = int(match.group(1))
            citations.add(number)
            first.setdefault(number, (segment["locator"], match.group(0)))
        match = re.match(r"^\s*(?:\[(\d{1,4})\]|(\d{1,4})[.)])\s+", segment["text"])
        if match:
            references.add(int(match.group(1) or match.group(2)))
    if not citations or not references:
        return []
    candidates: list[dict[str, Any]] = []
    for number in sorted(citations - references):
        locator, quote = first[number]
        candidates.append(
            {
                "kind": "citation_without_reference",
                "source_id": source["source_id"],
                "locator": locator,
                "quote": quote,
                "message": f"Citation [{number}] has no detected numbered reference entry.",
            }
        )
    return candidates


def _arithmetic_candidates(source: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for segment in source["segments"]:
        for match in re.finditer(r"\b(\d+)\s*\+\s*(\d+)\s*=\s*(\d+)\b", segment["text"]):
            left, right, stated = (int(match.group(index)) for index in range(1, 4))
            if left + right != stated:
                candidates.append(
                    {
                        "kind": "arithmetic_mismatch",
                        "source_id": source["source_id"],
                        "locator": segment["locator"],
                        "quote": match.group(0),
                        "message": (
                            f"Explicit arithmetic does not reconcile: {left} + {right} = "
                            f"{left + right}, not {stated}."
                        ),
                    }
                )
    return candidates


def deterministic_candidates(source: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        *_sentence_candidates(source),
        *_numbering_candidates(source),
        *_citation_candidates(source),
        *_arithmetic_candidates(source),
    ]
    for index, candidate in enumerate(candidates, start=1):
        candidate["id"] = f"check-{source['source_id']}-{index:04d}"
    return candidates


def _planned_sources(case_id: str, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        load_source(case_id, item["source_id"])
        for item in manifest["sources"]
        if item["role"] in {"manuscript", "supplement"}
    ]


def propose_case_plan(case_id: str) -> dict[str, Any]:
    """Draft logical segments for an audited case; the agent refines and stores them."""
    root, manifest = load_case(case_id)
    draft = draft_plan(_planned_sources(case_id, manifest))
    path = root / "scratch" / "segment-plan-draft.json"
    atomic_write_json(path, draft)
    return {
        "case_id": case_id,
        "plan_draft_path": str(path),
        "segments": len(draft["segments"]),
        "next": f"refine the draft, then run creview segments set --case {case_id} PLAN_PATH",
    }


def set_case_plan(case_id: str, plan_path: Path) -> dict[str, Any]:
    root, manifest = load_case(case_id)
    if (root / "review-state.json").exists():
        raise ReviewError("review has already started; the segment plan can no longer change")
    plan = validate_plan(read_json(plan_path), _planned_sources(case_id, manifest))
    atomic_write_json(root / "segment-plan.json", plan)
    append_event(root, "segment_plan_set", {"segments": [s["id"] for s in plan["segments"]]})
    return {
        "case_id": case_id,
        "segments": outline(plan),
        "warnings": plan["warnings"],
        "next": f"creview review start {case_id}",
    }


def _segment_units(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": f"coverage-{segment['id']}",
            "kind": "segment",
            "source_id": segment["source_id"],
            "segment_ids": segment["block_ids"],
            "locators": segment["locators"],
            "character_count": segment["character_count"],
            "title": segment["title"],
            "theme": segment["theme"],
            "profile_areas": segment["profile_areas"],
            "tier": segment["tier"],
            "status": "pending",
            "note": None,
        }
        for segment in plan["segments"]
    ]


def start_review(case_id: str, profile: str | None, *, live_doctor: bool = True) -> dict[str, Any]:
    root, manifest = load_case(case_id)
    if not manifest.get("policy_attestation"):
        raise ReviewError("record the user's journal-policy attestation before starting review")
    if not (root / "segment-plan.json").is_file():
        raise ReviewError(
            f"set a segment plan first: creview segments propose --case {case_id}, refine it, "
            f"then creview segments set --case {case_id} PLAN_PATH"
        )
    plan = read_json(root / "segment-plan.json")
    profile_name = selected_profile(profile)
    doctor = require_ready_profile(profile_name, live=live_doctor)
    with FileLock(str(root / ".lock")):
        if (root / "review-state.json").exists():
            raise ReviewError("review has already started for this case")
        coverage = _segment_units(plan)
        checks: list[dict[str, Any]] = []
        for source in _planned_sources(case_id, manifest):
            checks.extend(deterministic_candidates(source))
        rubric = [
            {
                "id": item_id,
                "kind": "rubric",
                "title": title,
                "instruction": instruction,
                "status": "pending",
                "note": None,
            }
            for item_id, title, instruction in RUBRIC
        ]
        for source_meta in manifest["sources"]:
            for index, warning in enumerate(source_meta.get("warnings") or [], start=1):
                rubric.append(
                    {
                        "id": f"rubric-manual-{source_meta['source_id']}-{index:03d}",
                        "kind": "rubric",
                        "title": f"Human inspection: {source_meta['source_id']}",
                        "instruction": (
                            f"Parser warning: {warning}. Mark unresolved unless the user reports "
                            "that the affected material was inspected by a human."
                        ),
                        "status": "pending",
                        "note": None,
                    }
                )
        state = {
            "schema_version": "3",
            "case_id": case_id,
            "status": "in_progress",
            "started_at": now_iso(),
            "updated_at": now_iso(),
            "profile": profile_name,
            "privacy_check": doctor,
            "coverage": coverage,
            "rubric": rubric,
            "deterministic_candidates": checks,
            "current_item": None,
            "finding_ids": [],
            "reference_check_ids": [],
            "draft_id": None,
            "active_batch": None,
            "last_batch": None,
            "intake_session_id": os.environ.get("HERMES_SESSION_ID"),
        }
        atomic_write_json(root / "review-state.json", state)
        manifest["status"] = "reviewing"
        manifest["updated_at"] = now_iso()
        atomic_write_json(root / "manifest.json", manifest)
        append_event(
            root, "review_started", {"profile": profile_name, "coverage_units": len(coverage)}
        )
    return review_status(case_id)


def _state(case_id: str) -> tuple[Path, dict[str, Any]]:
    root, _ = load_case(case_id)
    path = root / "review-state.json"
    if not path.exists():
        raise ReviewError("review has not started")
    state = read_json(path)
    if state.get("schema_version") != "3":
        with FileLock(str(root / ".lock")):
            state = read_json(path)
            state = _migrate_review_state(root, state)
    return root, state


def _migrate_review_state(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    """Upgrade legacy cases without discarding coverage, findings, or submitted drafts."""
    if state.get("schema_version") == "3":
        return state
    for finding_id in state.get("finding_ids") or []:
        path = root / "findings" / f"{finding_id}.json"
        if not path.is_file():
            continue
        finding = read_json(path)
        status = finding.get("status", "active")
        if status != "dismissed":
            finding["status"] = "accepted"
        finding.setdefault("schema_version", "2")
        finding.setdefault("origin", "legacy")
        finding.setdefault(
            "solution_candidates",
            [finding["requested_action"]] if finding.get("requested_action") else [],
        )
        finding.setdefault("literature_evidence", [])
        finding.setdefault(
            "discussion_history",
            [
                {
                    "recorded_at": now_iso(),
                    "disposition": "accepted" if finding["status"] == "accepted" else "dismissed",
                    "reviewer_reasoning": None,
                    "agent_synthesis": (
                        "Imported from the legacy workflow; historical reviewer reasoning was "
                        "not captured and has not been invented."
                    ),
                    "source": "legacy_migration",
                }
            ],
        )
        atomic_write_json(path, finding)
    state["schema_version"] = "3"
    state.setdefault("reference_check_ids", [])
    state["updated_at"] = now_iso()
    atomic_write_json(root / "review-state.json", state)
    append_event(root, "review_state_migrated", {"schema_version": "3"})
    return state


def require_review_access(case_id: str) -> dict[str, Any]:
    """Recheck the configured profile before returning confidential source text."""
    root, state = _state(case_id)
    problem = permission_problem(root)
    if problem:
        raise ReviewError(f"case directory is not private: {problem}")
    exposed = [
        problem
        for directory in (
            root / "originals",
            root / "sources",
            root / "findings",
            root / "reference-checks",
        )
        for path in directory.glob("*")
        if path.is_file() and (problem := permission_problem(path))
    ]
    if exposed:
        raise ReviewError(f"confidential case file is not private: {exposed[0]}")
    active_profile = os.environ.get("HERMES_SESSION_PROFILE")
    if active_profile and active_profile != state["profile"]:
        raise ReviewError(
            f"case belongs to Hermes profile {state['profile']!r}, not {active_profile!r}"
        )
    report = inspect_profile(state["profile"], live=False)
    if not report["ready"]:
        raise ReviewError(
            "current Hermes profile no longer satisfies the privacy gate: "
            + "; ".join(report["problems"])
        )
    return report


def _all_items(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [*state["coverage"], *state["rubric"]]


def _status_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[item["status"]] += 1
    return dict(counts)


def _pending_phase(state: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    root = case_root(state["case_id"])
    developing = [
        item
        for item in _load_all_findings(root, state)
        if item.get("status", "accepted") in {"candidate", "developing"}
    ]
    if developing:
        return "issue_development", developing
    coverage = [item for item in state["coverage"] if item["status"] == "pending"]
    if coverage:
        return "evidence_coverage", coverage
    rubric = [item for item in state["rubric"] if item["status"] == "pending"]
    if rubric:
        return "cross_cutting_appraisal", rubric
    return ("complete" if state.get("status") == "ready" else "finalization"), []


def _batch_summary(state: dict[str, Any]) -> dict[str, Any] | None:
    batch = state.get("active_batch")
    if not isinstance(batch, dict):
        return None
    by_id = {item["id"]: item for item in _all_items(state)}
    task_ids = [task_id for task_id in batch.get("task_ids", []) if task_id in by_id]
    remaining = [task_id for task_id in task_ids if by_id[task_id]["status"] == "pending"]
    return {
        "batch_id": batch["batch_id"],
        "phase": batch["phase"],
        "limit": batch["limit"],
        "task_ids": task_ids,
        "completed": len(task_ids) - len(remaining),
        "remaining": len(remaining),
        "remaining_task_ids": remaining,
        "session_id": batch.get("session_id"),
    }


def review_status(case_id: str) -> dict[str, Any]:
    root, state = _state(case_id)
    phase, pending = _pending_phase(state)
    batch = _batch_summary(state)
    findings = _load_all_findings(root, state)
    finding_status_counts = {status: 0 for status in sorted(FINDING_STATUSES)}
    finding_status_counts.update(_status_counts(findings))
    return {
        "case_id": case_id,
        "status": state["status"],
        "profile": state["profile"],
        "phase": phase,
        "coverage_total": len(state["coverage"]),
        "rubric_total": len(state["rubric"]),
        "coverage_status_counts": _status_counts(state["coverage"]),
        "rubric_status_counts": _status_counts(state["rubric"]),
        "item_status_counts": _status_counts(_all_items(state)),
        "remaining_in_phase": len(pending),
        "finding_count": len(findings),
        "finding_status_counts": finding_status_counts,
        "accepted_finding_count": finding_status_counts.get("accepted", 0),
        "current_item": state["current_item"],
        "active_batch": batch,
        "last_batch": state.get("last_batch"),
        "next_action": (
            "complete"
            if phase == "complete"
            else "finding_next"
            if phase == "issue_development"
            else "draft_prepare"
            if phase == "finalization"
            else "review_next"
            if batch
            else "review_batch_start"
        ),
    }


def start_batch(case_id: str, limit: int = DEFAULT_BATCH_ITEMS) -> dict[str, Any]:
    require_review_access(case_id)
    if not 1 <= limit <= MAX_BATCH_ITEMS:
        raise ReviewError(f"batch limit must be between 1 and {MAX_BATCH_ITEMS}")
    root, _ = _state(case_id)
    with FileLock(str(root / ".lock")):
        state = read_json(root / "review-state.json")
        existing = _batch_summary(state)
        if existing:
            return {"case_id": case_id, "state": "batch_resumed", "batch": existing}
        phase, pending = _pending_phase(state)
        if phase == "issue_development":
            return {
                "case_id": case_id,
                "state": phase,
                "remaining_candidates": len(pending),
                "next": f"creview finding next {case_id}",
            }
        if not pending:
            return {
                "case_id": case_id,
                "state": phase,
                "next": "creview draft prepare" if phase == "finalization" else None,
            }
        session_id = os.environ.get("HERMES_SESSION_ID")
        last_batch = state.get("last_batch") or {}
        if session_id and (
            state.get("intake_session_id") == session_id
            or last_batch.get("session_id") == session_id
        ):
            return {
                "case_id": case_id,
                "state": "session_checkpoint_required",
                "phase": phase,
                "remaining_in_phase": len(pending),
                "next": (
                    "Start a new Hermes session, then run "
                    f"/journal-article-review continue {case_id}"
                ),
            }
        current_id = state.get("current_item")
        ordered = sorted(pending, key=lambda item: item["id"] != current_id)
        task_ids = [item["id"] for item in ordered[:limit]]
        batch = {
            "batch_id": f"batch-{secrets.token_hex(4)}",
            "phase": phase,
            "limit": limit,
            "task_ids": task_ids,
            "started_at": now_iso(),
            "session_id": session_id,
        }
        state["active_batch"] = batch
        state["updated_at"] = now_iso()
        atomic_write_json(root / "review-state.json", state)
        append_event(
            root,
            "review_batch_started",
            {"batch_id": batch["batch_id"], "phase": phase, "task_ids": task_ids},
        )
        return {
            "case_id": case_id,
            "state": "batch_started",
            "batch": _batch_summary(state),
            "next": "creview review next",
        }


def _unit_content(case_id: str, item: dict[str, Any]) -> list[dict[str, Any]]:
    source = load_source(case_id, item["source_id"])
    selected = set(item["segment_ids"])
    return [
        {
            "segment_id": segment["segment_id"],
            "locator": segment["locator"],
            "kind": segment["kind"],
            "text": segment["text"],
        }
        for segment in source["segments"]
        if segment["segment_id"] in selected
    ]


def next_item(case_id: str) -> dict[str, Any]:
    require_review_access(case_id)
    root, state = _state(case_id)
    with FileLock(str(root / ".lock")):
        state = read_json(root / "review-state.json")
        batch = _batch_summary(state)
        phase, pending = _pending_phase(state)
        if phase == "issue_development":
            return {
                "case_id": case_id,
                "state": phase,
                "remaining_candidates": len(pending),
                "next": f"creview finding next {case_id}",
            }
        if not pending:
            return {
                "case_id": case_id,
                "state": phase,
                "next": "creview draft prepare" if phase == "finalization" else None,
            }
        if batch is None:
            return {
                "case_id": case_id,
                "state": "batch_required",
                "phase": phase,
                "remaining_in_phase": len(pending),
                "next": f"creview review batch-start {case_id}",
            }
        current_id = state.get("current_item")
        allowed_ids = set(batch["remaining_task_ids"])
        item = next(
            (
                entry
                for entry in _all_items(state)
                if entry["id"] == current_id and entry["id"] in allowed_ids
            ),
            None,
        )
        if item is None:
            item = next((entry for entry in _all_items(state) if entry["id"] in allowed_ids), None)
            if item is None:
                return {
                    "case_id": case_id,
                    "state": "batch_complete",
                    "batch": batch,
                    "next": f"creview review status {case_id}",
                }
            state["current_item"] = item["id"]
            state["updated_at"] = now_iso()
            atomic_write_json(root / "review-state.json", state)

        proposal = {
            "schema_version": "1",
            "case_id": case_id,
            "task_id": item["id"],
            "task_status": "",
            "note": "",
            "checklist_updates": [],
            "findings": [],
        }
        proposal_path = root / "proposals" / f"{item['id']}.json"
        if not proposal_path.exists():
            atomic_write_json(proposal_path, proposal)

        if item["kind"] in {"source", "segment"}:
            content = _unit_content(case_id, item)
            locators = set(item["locators"])
            checks = [
                candidate
                for candidate in state["deterministic_candidates"]
                if candidate["source_id"] == item["source_id"] and candidate["locator"] in locators
            ]
            task = {**item, "content": content, "deterministic_candidates": checks}
            plan_path = root / "segment-plan.json"
            if item["kind"] == "segment" and plan_path.is_file():
                task["outline"] = outline(read_json(plan_path))
        else:
            task = item
        return {
            "case_id": case_id,
            "batch": batch,
            "task": task,
            "proposal_path": str(proposal_path),
            "instructions": (
                "Review this item, edit only the proposal fields, then run "
                "creview finding submit CASE PROPOSAL_PATH. When the returned active_batch is "
                "null, stop this invocation and report the checkpoint."
            ),
        }


def _evidence_text(case_id: str, evidence: dict[str, Any]) -> str:
    if not isinstance(evidence, dict):
        raise ReviewError("each source_evidence entry must be an object")
    source_id = str(evidence.get("source_id") or "")
    locator = str(evidence.get("locator") or "")
    quote = str(evidence.get("quote") or "").strip()
    if not source_id or not locator or not quote:
        raise ReviewError("source evidence requires source_id, locator, and quote")
    source = load_source(case_id, source_id)
    segment = next((item for item in source["segments"] if item["locator"] == locator), None)
    if segment is None:
        raise ReviewError(f"evidence locator does not exist: {source_id} {locator}")
    if quote not in segment["text"]:
        raise ReviewError(f"evidence quote is not verbatim at {source_id} {locator}")
    return quote


def _lookup_ids(root: Path) -> set[str]:
    found: set[str] = set()
    for path in (root / "lookups").glob("*.json"):
        value = read_json(path)
        if value.get("status") == "executed":
            found.add(value["request_id"])
    return found


def _validate_literature_evidence(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ReviewError("literature_evidence must be an array")
    result: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict) or entry.get("tier") not in LITERATURE_TIERS:
            raise ReviewError("literature evidence has an invalid tier")
        citation = str(entry.get("citation") or "").strip()
        relevance = str(entry.get("relevance") or "").strip()
        if not citation or not relevance:
            raise ReviewError("literature evidence requires citation and relevance")
        verification = str(entry.get("verification_state") or "").strip()
        if entry["tier"] in {"model_lead", "user_lead", "manuscript_reported"}:
            if verification not in {"unverified", "manuscript_only"}:
                raise ReviewError(f"{entry['tier']} literature must remain explicitly unverified")
        elif not verification:
            raise ReviewError("literature evidence requires verification_state")
        result.append(
            {
                "tier": entry["tier"],
                "citation": citation,
                "relevance": relevance,
                "verification_state": verification,
                "source_id": entry.get("source_id"),
                "locator": entry.get("locator"),
                "lookup_id": entry.get("lookup_id"),
            }
        )
    return result


def _validate_finding(
    case_id: str, root: Path, raw: Any, *, status: str = "candidate"
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ReviewError("each finding must be an object")
    category = raw.get("category")
    severity = raw.get("severity")
    audience = raw.get("audience")
    confidence = raw.get("confidence")
    verification = raw.get("verification_state")
    if category not in FINDING_CATEGORIES:
        raise ReviewError(f"invalid finding category: {category!r}")
    if severity not in SEVERITIES:
        raise ReviewError(f"invalid finding severity: {severity!r}")
    if audience not in AUDIENCES:
        raise ReviewError(f"invalid finding audience: {audience!r}")
    if confidence not in CONFIDENCE:
        raise ReviewError(f"invalid finding confidence: {confidence!r}")
    if verification not in VERIFICATION:
        raise ReviewError(f"invalid verification_state: {verification!r}")
    evidence = raw.get("source_evidence") or []
    if not isinstance(evidence, list) or not evidence:
        raise ReviewError("every finding requires at least one source_evidence entry")
    for entry in evidence:
        _evidence_text(case_id, entry)
    for field in ("critique", "why_it_matters"):
        if not isinstance(raw.get(field), str) or not raw[field].strip():
            raise ReviewError(f"finding requires nonempty {field}")
    requested = raw.get("requested_action")
    if audience in {"authors", "both"} and (
        not isinstance(requested, str) or not requested.strip()
    ):
        raise ReviewError("author-facing findings require requested_action")
    external_ids = raw.get("external_lookup_ids") or []
    if not isinstance(external_ids, list) or not all(
        isinstance(item, str) for item in external_ids
    ):
        raise ReviewError("external_lookup_ids must be a string array")
    unknown = set(external_ids) - _lookup_ids(root)
    if unknown:
        raise ReviewError("finding cites unexecuted lookup requests: " + ", ".join(sorted(unknown)))
    solutions = raw.get("solution_candidates")
    if solutions is None:
        solutions = [requested.strip()] if isinstance(requested, str) and requested.strip() else []
    if not isinstance(solutions, list) or not all(
        isinstance(item, str) and item.strip() for item in solutions
    ):
        raise ReviewError("solution_candidates must be a nonempty-string array")
    return {
        "schema_version": "2",
        "finding_id": f"finding-{secrets.token_hex(5)}",
        "status": status,
        "origin": str(raw.get("origin") or "agent"),
        "category": category,
        "severity": severity,
        "audience": audience,
        "source_evidence": evidence,
        "critique": raw["critique"].strip(),
        "why_it_matters": raw["why_it_matters"].strip(),
        "requested_action": requested.strip()
        if isinstance(requested, str) and requested.strip()
        else None,
        "confidence": confidence,
        "verification_state": verification,
        "external_lookup_ids": external_ids,
        "literature_evidence": _validate_literature_evidence(raw.get("literature_evidence")),
        "solution_candidates": [item.strip() for item in solutions],
        "discussion_history": [],
        "origin_task_id": raw.get("origin_task_id"),
        "reference_check_id": raw.get("reference_check_id"),
        "created_at": now_iso(),
    }


def _validate_checklist_updates(state: dict[str, Any], raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        raise ReviewError("checklist_updates must be an array")
    allowed_ids = {item["id"] for item in state["rubric"]}
    updates: list[dict[str, str]] = []
    for entry in raw:
        if not isinstance(entry, dict) or entry.get("id") not in allowed_ids:
            raise ReviewError("checklist update has an unknown id")
        status = entry.get("status")
        if status not in {"reviewed", "not_applicable", "unresolved"}:
            raise ReviewError("checklist status must be reviewed, not_applicable, or unresolved")
        note = str(entry.get("note") or "").strip()
        if not note:
            raise ReviewError("checklist updates require a note")
        updates.append({"id": entry["id"], "status": status, "note": note})
    return updates


def submit_findings(case_id: str, proposal_path: Path) -> dict[str, Any]:
    root, state = _state(case_id)
    try:
        proposal = read_json(proposal_path.resolve())
    except OSError as exc:
        raise ReviewError(f"cannot read proposal: {exc}") from exc
    with FileLock(str(root / ".lock")):
        state = read_json(root / "review-state.json")
        current_id = state.get("current_item")
        if (
            not current_id
            or proposal.get("task_id") != current_id
            or proposal.get("case_id") != case_id
        ):
            raise ReviewError("proposal does not belong to the current review item")
        current = next(item for item in _all_items(state) if item["id"] == current_id)
        status = proposal.get("task_status")
        allowed = (
            {"reviewed", "not_reviewable"}
            if current["kind"] == "source"
            else {"reviewed", "not_applicable", "unresolved"}
        )
        if status not in allowed:
            raise ReviewError("proposal task_status is not allowed for this task")
        note = str(proposal.get("note") or "").strip()
        if status != "reviewed" and not note:
            raise ReviewError("non-reviewed task status requires a note")
        updates = _validate_checklist_updates(state, proposal.get("checklist_updates") or [])
        raw_findings = proposal.get("findings") or []
        if not isinstance(raw_findings, list):
            raise ReviewError("findings must be an array")
        findings = []
        for item in raw_findings:
            if isinstance(item, dict):
                item = {**item, "origin_task_id": current_id}
            findings.append(_validate_finding(case_id, root, item, status="candidate"))
        for finding in findings:
            atomic_write_json(root / "findings" / f"{finding['finding_id']}.json", finding)
            state["finding_ids"].append(finding["finding_id"])
        current["status"] = status
        current["note"] = note or None
        for update in updates:
            item = next(entry for entry in state["rubric"] if entry["id"] == update["id"])
            item["status"] = update["status"]
            item["note"] = update["note"]
        state["current_item"] = None
        completed_batch: dict[str, Any] | None = None
        batch = _batch_summary(state)
        if batch and batch["remaining"] == 0:
            completed_batch = {
                **batch,
                "completed_at": now_iso(),
            }
            state["last_batch"] = completed_batch
            state["active_batch"] = None
        state["updated_at"] = now_iso()
        atomic_write_json(root / "review-state.json", state)
        append_event(
            root,
            "review_item_submitted",
            {
                "task_id": current_id,
                "status": status,
                "finding_ids": [item["finding_id"] for item in findings],
                "batch_id": completed_batch["batch_id"] if completed_batch else None,
            },
        )
        if completed_batch:
            append_event(
                root,
                "review_batch_completed",
                {
                    "batch_id": completed_batch["batch_id"],
                    "phase": completed_batch["phase"],
                    "task_ids": completed_batch["task_ids"],
                },
            )
    return {
        "case_id": case_id,
        "task_id": current_id,
        "status": status,
        "candidate_findings": findings,
        "review": review_status(case_id),
    }


def _load_all_findings(root: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    findings = [
        read_json(root / "findings" / f"{finding_id}.json") for finding_id in state["finding_ids"]
    ]
    return findings


def _load_findings(root: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _load_all_findings(root, state) if item.get("status") == "accepted"]


def list_findings(
    case_id: str, *, include_dismissed: bool = False, status: str | None = None
) -> list[dict[str, Any]]:
    root, state = _state(case_id)
    findings = _load_all_findings(root, state)
    if status:
        if status not in FINDING_STATUSES:
            raise ReviewError(f"invalid finding status: {status}")
        return [item for item in findings if item.get("status") == status]
    if include_dismissed:
        return findings
    return [item for item in findings if item.get("status") != "dismissed"]


def _finding_path(root: Path, state: dict[str, Any], finding_id: str) -> Path:
    if finding_id not in state["finding_ids"]:
        raise ReviewError(f"unknown finding id: {finding_id}")
    return root / "findings" / f"{finding_id}.json"


def _response_proposal(case_id: str, finding: dict[str, Any]) -> dict[str, Any]:
    editable = {
        key: finding.get(key)
        for key in (
            "origin",
            "category",
            "severity",
            "audience",
            "source_evidence",
            "critique",
            "why_it_matters",
            "requested_action",
            "confidence",
            "verification_state",
            "external_lookup_ids",
            "literature_evidence",
            "solution_candidates",
            "origin_task_id",
            "reference_check_id",
        )
    }
    return {
        "schema_version": "2",
        "case_id": case_id,
        "finding_id": finding["finding_id"],
        "disposition": "",
        "reviewer_reasoning": "",
        "agent_synthesis": "",
        **editable,
    }


def prepare_finding_response(case_id: str, finding_id: str) -> dict[str, Any]:
    root, state = _state(case_id)
    finding = read_json(_finding_path(root, state, finding_id))
    if finding.get("status") == "dismissed":
        raise ReviewError("cannot respond to a dismissed finding")
    path = root / "proposals" / f"respond-{finding_id}.json"
    atomic_write_json(path, _response_proposal(case_id, finding))
    return {"case_id": case_id, "finding_id": finding_id, "proposal_path": str(path)}


def next_finding(case_id: str) -> dict[str, Any]:
    root, state = _state(case_id)
    pending = [
        item
        for item in _load_all_findings(root, state)
        if item.get("status") in {"candidate", "developing"}
    ]
    if not pending:
        return {"case_id": case_id, "state": "none_pending", "review": review_status(case_id)}
    pending.sort(
        key=lambda item: (
            item.get("severity") != "major",
            item.get("created_at", ""),
            item["finding_id"],
        )
    )
    first = pending[0]
    selected = [first]
    if first.get("severity") == "minor":
        selected.extend(
            item
            for item in pending[1:]
            if item.get("severity") == "minor"
            and item.get("category") == first.get("category")
            and item.get("origin_task_id") == first.get("origin_task_id")
        )
        selected = selected[:3]
    items = []
    for finding in selected:
        prepared = prepare_finding_response(case_id, finding["finding_id"])
        items.append({"finding": finding, "proposal_path": prepared["proposal_path"]})
    return {
        "case_id": case_id,
        "state": "development_required",
        "items": items,
        "progress": review_status(case_id)["finding_status_counts"],
        "instructions": (
            "Discuss these candidates with the reviewer. Record their full substantive reasoning "
            "and the resulting disposition in each proposal, then run creview finding respond."
        ),
    }


def respond_finding(case_id: str, finding_id: str, proposal_path: Path) -> dict[str, Any]:
    root, state = _state(case_id)
    proposal = read_json(proposal_path.resolve())
    if proposal.get("case_id") != case_id or proposal.get("finding_id") != finding_id:
        raise ReviewError("response proposal belongs to another finding")
    disposition = proposal.get("disposition")
    if disposition not in {"developing", "accepted", "deferred", "dismissed"}:
        raise ReviewError("disposition must be developing, accepted, deferred, or dismissed")
    reviewer_reasoning = str(proposal.get("reviewer_reasoning") or "").strip()
    agent_synthesis = str(proposal.get("agent_synthesis") or "").strip()
    if not reviewer_reasoning or not agent_synthesis:
        raise ReviewError("finding responses require reviewer_reasoning and agent_synthesis")
    validated = _validate_finding(case_id, root, proposal, status=disposition)
    with FileLock(str(root / ".lock")):
        state = read_json(root / "review-state.json")
        path = _finding_path(root, state, finding_id)
        previous = read_json(path)
        if previous.get("status") == "dismissed":
            raise ReviewError("cannot respond to a dismissed finding")
        history = list(previous.get("discussion_history") or [])
        history.append(
            {
                "recorded_at": now_iso(),
                "disposition": disposition,
                "reviewer_reasoning": reviewer_reasoning,
                "agent_synthesis": agent_synthesis,
                "source": "reviewer_dialogue",
            }
        )
        validated["finding_id"] = finding_id
        validated["created_at"] = previous["created_at"]
        validated["updated_at"] = now_iso()
        validated["discussion_history"] = history
        validated["revision_history"] = previous.get("revision_history") or []
        atomic_write_json(path, validated)
        _invalidate_draft(root, state)
        state["updated_at"] = now_iso()
        atomic_write_json(root / "review-state.json", state)
        append_event(
            root,
            "finding_response_recorded",
            {"finding_id": finding_id, "disposition": disposition},
        )
    return {**validated, "progress": review_status(case_id)["finding_status_counts"]}


def import_reference_issues(case_id: str, report: dict[str, Any]) -> list[dict[str, Any]]:
    root, state = _state(case_id)
    if report.get("case_id") != case_id:
        raise ReviewError("reference check belongs to another case")
    check_id = str(report.get("check_id") or "")
    if check_id in state.get("reference_check_ids", []):
        return [
            item
            for item in _load_all_findings(root, state)
            if item.get("reference_check_id") == check_id
        ]
    anchor = report.get("default_evidence") or {}
    quote = str(anchor.get("quote") or "").strip()
    locator = str(anchor.get("locator") or "").strip()
    if report.get("issues") and (not quote or not locator):
        raise ReviewError("reference report has no stable evidence anchor")
    imported: list[dict[str, Any]] = []
    for issue in report.get("issues") or []:
        message = str(issue.get("message") or "").strip()
        raw = {
            "origin": "mechanical_reference_check",
            "category": "references_reporting",
            "severity": "minor",
            "audience": "authors",
            "source_evidence": [
                {
                    "source_id": report.get("source_id", "manuscript"),
                    "locator": locator,
                    "quote": quote,
                }
            ],
            "critique": message,
            "why_it_matters": (
                "A mechanically detected reference inconsistency can prevent readers from "
                "identifying or evaluating the cited source; it requires reviewer confirmation."
            ),
            "requested_action": "Verify and correct the citation and bibliography record.",
            "confidence": "medium",
            "verification_state": "unresolved",
            "external_lookup_ids": [],
            "literature_evidence": [],
            "solution_candidates": [
                "Correct the in-text citation or bibliography entry after checking the source.",
                (
                    "Dismiss this warning if extraction or citation style explains the apparent "
                    "mismatch."
                ),
            ],
            "reference_check_id": check_id,
        }
        imported.append(_validate_finding(case_id, root, raw, status="candidate"))
    with FileLock(str(root / ".lock")):
        state = read_json(root / "review-state.json")
        for finding in imported:
            atomic_write_json(root / "findings" / f"{finding['finding_id']}.json", finding)
            state["finding_ids"].append(finding["finding_id"])
        state.setdefault("reference_check_ids", []).append(check_id)
        state["updated_at"] = now_iso()
        atomic_write_json(root / "review-state.json", state)
        append_event(
            root,
            "reference_issues_imported",
            {"check_id": check_id, "finding_ids": [item["finding_id"] for item in imported]},
        )
    return imported


def prepare_finding_revision(case_id: str, finding_id: str) -> dict[str, Any]:
    root, state = _state(case_id)
    finding = read_json(_finding_path(root, state, finding_id))
    if finding.get("status") == "dismissed":
        raise ReviewError("cannot revise a dismissed finding")
    editable = {
        key: finding.get(key)
        for key in (
            "origin",
            "category",
            "severity",
            "audience",
            "source_evidence",
            "critique",
            "why_it_matters",
            "requested_action",
            "confidence",
            "verification_state",
            "external_lookup_ids",
            "literature_evidence",
            "solution_candidates",
            "origin_task_id",
            "reference_check_id",
        )
    }
    proposal = {
        "schema_version": "1",
        "case_id": case_id,
        "finding_id": finding_id,
        **editable,
    }
    path = root / "proposals" / f"revise-{finding_id}.json"
    atomic_write_json(path, proposal)
    return {"case_id": case_id, "finding_id": finding_id, "proposal_path": str(path)}


def _invalidate_draft(root: Path, state: dict[str, Any]) -> None:
    if state.get("draft_id"):
        state["draft_id"] = None
        state["status"] = "in_progress"
        _, manifest = load_case(state["case_id"])
        manifest["status"] = "reviewing"
        manifest["updated_at"] = now_iso()
        atomic_write_json(root / "manifest.json", manifest)


def revise_finding(case_id: str, finding_id: str, proposal_path: Path) -> dict[str, Any]:
    root, state = _state(case_id)
    proposal = read_json(proposal_path.resolve())
    if proposal.get("case_id") != case_id or proposal.get("finding_id") != finding_id:
        raise ReviewError("revision proposal belongs to another finding")
    revised = _validate_finding(case_id, root, proposal, status="accepted")
    with FileLock(str(root / ".lock")):
        state = read_json(root / "review-state.json")
        path = _finding_path(root, state, finding_id)
        previous = read_json(path)
        if previous.get("status") == "dismissed":
            raise ReviewError("cannot revise a dismissed finding")
        history = previous.get("revision_history") or []
        prior_version = {key: value for key, value in previous.items() if key != "revision_history"}
        history.append({"revised_at": now_iso(), "previous": prior_version})
        revised["finding_id"] = finding_id
        revised["created_at"] = previous["created_at"]
        revised["updated_at"] = now_iso()
        revised["revision_history"] = history
        revised["discussion_history"] = previous.get("discussion_history") or []
        atomic_write_json(path, revised)
        _invalidate_draft(root, state)
        state["updated_at"] = now_iso()
        atomic_write_json(root / "review-state.json", state)
        append_event(root, "finding_revised", {"finding_id": finding_id})
    return revised


def dismiss_finding(case_id: str, finding_id: str, reason: str) -> dict[str, Any]:
    reason = reason.strip()
    if not reason:
        raise ReviewError("dismissing a finding requires a reason")
    root, state = _state(case_id)
    with FileLock(str(root / ".lock")):
        state = read_json(root / "review-state.json")
        path = _finding_path(root, state, finding_id)
        finding = read_json(path)
        if finding.get("status") == "dismissed":
            raise ReviewError("finding is already dismissed")
        finding["status"] = "dismissed"
        finding["dismissed_at"] = now_iso()
        finding["dismissal_reason"] = reason
        atomic_write_json(path, finding)
        _invalidate_draft(root, state)
        state["updated_at"] = now_iso()
        atomic_write_json(root / "review-state.json", state)
        append_event(root, "finding_dismissed", {"finding_id": finding_id, "reason": reason})
    return finding


def _require_coverage_complete(state: dict[str, Any]) -> None:
    pending = [item["id"] for item in _all_items(state) if item["status"] == "pending"]
    if pending:
        raise ReviewError("review coverage is incomplete: " + ", ".join(pending[:10]))


def _require_development_complete(root: Path, state: dict[str, Any]) -> None:
    pending = [
        item["finding_id"]
        for item in _load_all_findings(root, state)
        if item.get("status") in {"candidate", "developing"}
    ]
    if pending:
        raise ReviewError("issue development is incomplete: " + ", ".join(pending[:10]))


def prepare_draft(case_id: str) -> dict[str, Any]:
    root, state = _state(case_id)
    _require_coverage_complete(state)
    _require_development_complete(root, state)
    session_id = os.environ.get("HERMES_SESSION_ID")
    last_batch = state.get("last_batch") or {}
    if session_id and last_batch.get("session_id") == session_id:
        raise ReviewError(
            "finalization requires a new Hermes session after the last appraisal batch"
        )
    findings = _load_findings(root, state)
    proposal = {
        "schema_version": "2",
        "case_id": case_id,
        "author_summary": "",
        "author_overall_assessment": "",
        "editor_confidential_comments": "",
        "recommendation": None,
        "recommendation_rationale": "",
        "recommendation_user_reasoning": "",
        "unresolved_items": [
            item["note"]
            for item in _all_items(state)
            if item["status"] in {"unresolved", "not_reviewable"} and item.get("note")
        ],
        "finding_order": [item["finding_id"] for item in findings],
        "finding_digests": {
            item["finding_id"]: sha256_file(root / "findings" / f"{item['finding_id']}.json")
            for item in findings
        },
        "disclosure_purpose": "supporting manuscript analysis and structuring this review report",
    }
    path = root / "proposals" / "draft.json"
    atomic_write_json(path, proposal)
    return {"case_id": case_id, "proposal_path": str(path), "finding_count": len(findings)}


def submit_draft(case_id: str, proposal_path: Path) -> dict[str, Any]:
    root, state = _state(case_id)
    _require_coverage_complete(state)
    _require_development_complete(root, state)
    proposal = read_json(proposal_path.resolve())
    if proposal.get("case_id") != case_id:
        raise ReviewError("draft proposal belongs to another case")
    for field in (
        "author_summary",
        "author_overall_assessment",
        "disclosure_purpose",
    ):
        if not isinstance(proposal.get(field), str) or not proposal[field].strip():
            raise ReviewError(f"draft requires nonempty {field}")
    recommendation = proposal.get("recommendation")
    rationale = str(proposal.get("recommendation_rationale") or "").strip()
    user_reasoning = str(proposal.get("recommendation_user_reasoning") or "").strip()
    if recommendation is not None and recommendation not in RECOMMENDATIONS:
        raise ReviewError("invalid user-owned recommendation")
    if recommendation is not None and (not rationale or not user_reasoning):
        raise ReviewError(
            "a recommendation requires the user's selected rationale and recorded reasoning"
        )
    if recommendation is None and (rationale or user_reasoning):
        raise ReviewError("recommendation rationale must be empty when recommendation is omitted")
    unresolved = proposal.get("unresolved_items")
    if not isinstance(unresolved, list) or not all(
        isinstance(item, str) and item.strip() for item in unresolved
    ):
        raise ReviewError("unresolved_items must be a string array")
    order = proposal.get("finding_order")
    active_ids = {item["finding_id"] for item in _load_findings(root, state)}
    if not isinstance(order, list) or len(order) != len(set(order)) or set(order) != active_ids:
        raise ReviewError("finding_order must contain every accepted finding exactly once")
    expected_digests = {
        finding_id: sha256_file(root / "findings" / f"{finding_id}.json")
        for finding_id in active_ids
    }
    if proposal.get("finding_digests") != expected_digests:
        raise ReviewError("findings changed after draft preparation; prepare the draft again")
    editor_comments = proposal.get("editor_confidential_comments")
    if not isinstance(editor_comments, str):
        raise ReviewError("editor_confidential_comments must be a string")
    draft = {
        "schema_version": "2",
        "draft_id": f"draft-{secrets.token_hex(5)}",
        "case_id": case_id,
        "author_summary": proposal["author_summary"].strip(),
        "author_overall_assessment": proposal["author_overall_assessment"].strip(),
        "editor_confidential_comments": editor_comments.strip(),
        "recommendation": recommendation,
        "recommendation_rationale": rationale,
        "recommendation_user_reasoning": user_reasoning,
        "recommendation_owner": "user" if recommendation is not None else None,
        "unresolved_items": [item.strip() for item in unresolved],
        "finding_order": order,
        "disclosure_purpose": proposal["disclosure_purpose"].strip(),
        "created_at": now_iso(),
    }
    with FileLock(str(root / ".lock")):
        atomic_write_json(root / "drafts" / f"{draft['draft_id']}.json", draft)
        state = read_json(root / "review-state.json")
        state["draft_id"] = draft["draft_id"]
        state["status"] = "ready"
        state["updated_at"] = now_iso()
        atomic_write_json(root / "review-state.json", state)
        _, manifest = load_case(case_id)
        manifest["status"] = "ready"
        manifest["updated_at"] = now_iso()
        atomic_write_json(root / "manifest.json", manifest)
        append_event(root, "draft_submitted", {"draft_id": draft["draft_id"]})
    return draft


def _finding_markdown(finding: dict[str, Any], number: int) -> str:
    evidence = "; ".join(
        f"{item['source_id']} — {item['locator']}" for item in finding["source_evidence"]
    )
    parts = [
        f"{number}. **{finding['critique']}**",
        f"   - Why this matters: {finding['why_it_matters']}",
        f"   - Location: {evidence}",
    ]
    if finding.get("requested_action"):
        parts.append(f"   - Requested action: {finding['requested_action']}")
    if finding["verification_state"] != "verified" or finding["confidence"] != "high":
        parts.append(
            f"   - Review status: {finding['verification_state']}; "
            f"confidence {finding['confidence']}"
        )
    return "\n".join(parts)


def _development_markdown(findings: list[dict[str, Any]]) -> str:
    counts = _status_counts(findings)
    lines = [
        "# Review Development Record",
        "",
        "This private record preserves how candidate issues were examined with the reviewer. ",
        "It is not a journal-facing report.",
        "",
        "## Progress",
        "",
        " | ".join(
            f"{status}: {counts.get(status, 0)}"
            for status in ("accepted", "developing", "candidate", "deferred", "dismissed")
        ),
    ]
    for index, finding in enumerate(findings, start=1):
        lines += [
            "",
            f"## Issue {index}: {finding['status']}",
            "",
            f"**Potential issue:** {finding['critique']}",
            "",
            f"**Why it matters:** {finding['why_it_matters']}",
        ]
        if finding.get("solution_candidates"):
            lines += ["", "**Solution candidates:**"]
            lines += [f"- {item}" for item in finding["solution_candidates"]]
        if finding.get("literature_evidence"):
            lines += ["", "**Literature context:**"]
            lines += [
                (
                    f"- [{item['tier']}; {item['verification_state']}] "
                    f"{item['citation']}: {item['relevance']}"
                )
                for item in finding["literature_evidence"]
            ]
        if finding.get("discussion_history"):
            lines += ["", "**Reviewer discussion:**"]
            for turn in finding["discussion_history"]:
                reasoning = turn.get("reviewer_reasoning") or "Not captured by the legacy workflow."
                lines += [
                    f"- {turn['recorded_at']} — {turn['disposition']}: {reasoning}",
                    f"  - Synthesis: {turn['agent_synthesis']}",
                ]
    return "\n".join(lines).rstrip() + "\n"


def export_review(case_id: str, output: Path) -> dict[str, Any]:
    root, state = _state(case_id)
    if state.get("status") != "ready" or not state.get("draft_id"):
        raise ReviewError("submit a complete draft before export")
    _, manifest = load_case(case_id)
    draft = read_json(root / "drafts" / f"{state['draft_id']}.json")
    by_id = {item["finding_id"]: item for item in _load_findings(root, state)}
    ordered = [by_id[finding_id] for finding_id in draft["finding_order"]]
    author_findings = [item for item in ordered if item["audience"] in {"authors", "both"}]
    editor_findings = [item for item in ordered if item["audience"] in {"editor", "both"}]

    author_lines = [
        "# Comments to Authors",
        "",
        draft["author_summary"],
        "",
        "## Overall assessment",
        "",
        draft["author_overall_assessment"],
    ]
    for severity, heading in (("major", "Major comments"), ("minor", "Minor comments")):
        selected = [item for item in author_findings if item["severity"] == severity]
        if selected:
            author_lines += ["", f"## {heading}", ""]
            author_lines += [
                _finding_markdown(item, index) for index, item in enumerate(selected, start=1)
            ]

    editor_lines = ["# Confidential Comments to the Editor"]
    if draft.get("recommendation"):
        heading = (
            "User-selected recommendation"
            if draft.get("recommendation_owner") == "user"
            else "Provisional recommendation"
        )
        editor_lines += [
            "",
            f"## {heading}",
            "",
            f"**{draft['recommendation'].replace('_', ' ').title()}**",
            "",
            draft["recommendation_rationale"],
        ]
    if draft["editor_confidential_comments"]:
        editor_lines += [
            "",
            "## Confidential assessment",
            "",
            draft["editor_confidential_comments"],
        ]
    if editor_findings:
        editor_lines += ["", "## Findings for editorial attention", ""]
        editor_lines += [
            _finding_markdown(item, index) for index, item in enumerate(editor_findings, start=1)
        ]
    if draft["unresolved_items"]:
        editor_lines += ["", "## Unresolved items", ""]
        editor_lines += [f"- {item}" for item in draft["unresolved_items"]]

    lookup_records = [read_json(path) for path in sorted((root / "lookups").glob("*.json"))]
    all_findings = _load_all_findings(root, state)
    review_json = {
        "schema_version": "2",
        "case_id": case_id,
        "journal": manifest["journal"],
        "title": manifest.get("title"),
        "draft": draft,
        "findings": all_findings,
        "coverage": state["coverage"],
        "rubric": state["rubric"],
    }
    provenance = {
        "schema_version": "1",
        "case_id": case_id,
        "exported_at": now_iso(),
        "inputs": [
            {
                key: item.get(key)
                for key in ("source_id", "role", "original_name", "sha256", "format")
            }
            for item in manifest["sources"]
        ],
        "policy_attestation": manifest["policy_attestation"],
        "profile": state["profile"],
        "model": state["privacy_check"]["model"],
        "base_url": state["privacy_check"]["base_url"],
        "privacy_boundary": state["privacy_check"]["privacy_boundary"],
        "lookups": lookup_records,
    }
    disclosure = (
        f"During preparation of this review report, I used the self-hosted model "
        f"{state['privacy_check']['model']} for {draft['disclosure_purpose']}. "
        "I reviewed and edited the output and take full responsibility for the critical assessment "
        "and feedback in the report.\n"
    )

    output = output.expanduser().resolve()
    ensure_private_dir(output)
    files = {
        "comments-to-authors.md": "\n".join(author_lines).rstrip() + "\n",
        "comments-to-editor.md": "\n".join(editor_lines).rstrip() + "\n",
        "review-development.md": _development_markdown(all_findings),
        "ai-use-disclosure.txt": disclosure,
    }
    for name, content in files.items():
        atomic_write_text(output / name, content)
    atomic_write_json(output / "review.json", review_json)
    atomic_write_json(output / "provenance.json", provenance)
    # `review start` refuses to run unless the doctor passes, so the audited preflight is enforced.
    preflight = {
        "status": "passed",
        "session_source": "audited_case",
        "checked_at": state["started_at"],
    }
    receipt = write_receipt(output, state["privacy_check"], state["started_at"], preflight)
    for path in output.iterdir():
        if path.is_file():
            secure_file(path)
    append_event(
        root, "review_exported", {"output": str(output), "receipt_id": receipt["receipt_id"]}
    )
    return {
        "case_id": case_id,
        "output": str(output),
        "files": sorted([*files, "review.json", "provenance.json", RECEIPT_NAME]),
        "receipt_id": receipt["receipt_id"],
    }
