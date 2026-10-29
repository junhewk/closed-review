from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from filelock import FileLock

from .errors import ReviewError
from .hermes import inspect_profile
from .io import atomic_write_json, data_home, ensure_private_dir, now_iso, read_json
from .receipts import RECEIPT_NAME, SUBJECT_ROLES, write_receipt
from .session import preflight_summary, session_key

EXPORT_ID_RE = re.compile(r"^direct-\d{8}T\d{6}Z-[0-9a-f]{8}$")
EXPORT_META = "export.json"
_SEVERITY_PHRASE = re.compile(
    r"\b(major|minor)\s+(?:(?:methodological|reporting|statistical)\s+){0,2}"
    r"(?:issues?|concerns?|findings?|inconsistenc(?:y|ies)|flaws?|problems?)\b",
    re.IGNORECASE,
)
_SEVERITY_HEADING = re.compile(
    r"^\s*#{1,6}\s*(major|minor)(?:\s+(?:issues?|concerns?|findings?|problems?))?\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_NEGATION = re.compile(r"\b(?:not|no|never|neither|without)(?:\s+\w+){0,4}\s*$", re.IGNORECASE)
_UNSURFACED_MENTIONS = (
    re.compile(
        r"\b(?:unsurfaced|unseen|unshown|unreviewed|unpresented)\s+"
        r"(?:issues?|findings?|candidates?|concerns?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:major|minor)(?:[-\s]+severity)?\s+"
        r"(?:issues?|findings?|candidates?|concerns?)\b[^.!?\n]{0,70}"
        r"\b(?:not|never)\s+(?:yet\s+)?(?:surfaced|shown|presented|reviewed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:further|other|additional|more)\s+"
        r"(?:issues?|findings?|candidates?|concerns?)\b[^.!?\n]{0,40}"
        r"\b(?:available|remain|unseen|unsurfaced)\b",
        re.IGNORECASE,
    ),
)


def _accepted_scan_records(scan_id: str, key: str | None) -> list[dict[str, Any]]:
    """Read only accepted, surfaced records from the same session as the export."""
    from .findings import severity
    from .scan import _read, _scan_root

    root = _scan_root(scan_id)
    with FileLock(str(root / ".lock")):
        scan = _read(root)
    if not key or scan.get("session_id") != key:
        raise ReviewError("the export and scan must belong to the same review session")
    if scan.get("phase") != "ready":
        raise ReviewError("the scan must finish before preparing an export")
    findings = {f["id"]: f for f in scan.get("review", {}).get("findings", [])}
    accepted = []
    for finding_id, response in scan.get("surfaced", {}).items():
        if response.get("disposition") != "accepted":
            continue
        if finding_id not in findings:
            raise ReviewError(f"accepted finding {finding_id} is missing from the scan")
        accepted.append(
            {
                "id": finding_id,
                "rating": severity(findings[finding_id]),
                "reviewer_words": response.get("response", {}).get("words", ""),
            }
        )
    return accepted


def _severity_labels(text: str) -> set[str]:
    """Find explicit severity categories; this is not a semantic assessment of the draft."""
    labels = {match.group(1).lower() for match in _SEVERITY_HEADING.finditer(text)}
    for match in _SEVERITY_PHRASE.finditer(text):
        prefix = re.split(r"[.!?;\n]", text[: match.start()])[-1]
        if not _NEGATION.search(prefix):
            labels.add(match.group(1).lower())
    return labels


def check_export_severity(directory: Path, accepted: list[dict[str, Any]]) -> dict[str, Any]:
    """Check unambiguous severity categories in author/editor drafts against accepted records.

    A reviewer's own severity words, or mixed accepted ratings, need human interpretation. We do
    not turn the model's rating into the reviewer's judgment or pretend to understand all prose.
    """
    if not accepted:
        return {"status": "not_applicable", "reason": "no accepted scan findings"}
    ratings = {record["rating"]["severity"] for record in accepted}
    if len(ratings) != 1 or any(
        re.search(r"\b(?:major|minor)\b", record["reviewer_words"], re.IGNORECASE)
        for record in accepted
    ):
        return {
            "status": "manual_review_required",
            "reason": "mixed ratings or reviewer severity words require interpretation",
        }
    expected = next(iter(ratings))
    conflicts = []
    for name in ("comments-to-authors.md", "comments-to-editor.md"):
        path = directory / name
        if path.is_file():
            for label in sorted(_severity_labels(path.read_text(encoding="utf-8")) - {expected}):
                conflicts.append({"file": name, "draft_rating": label, "scan_rating": expected})
    return {
        "status": "conflict" if conflicts else "no_explicit_conflict_found",
        "conflicts": conflicts,
        "limitation": "checks explicit severity categories only; review wording and attribution",
    }


def check_export_scope(directory: Path) -> dict[str, Any]:
    """Catch explicit mentions of unseen findings; this does not assess all draft meaning."""
    conflicts = []
    for name in SUBJECT_ROLES:
        path = directory / name
        if path.is_file():
            draft = path.read_text(encoding="utf-8")
            if any(pattern.search(draft) for pattern in _UNSURFACED_MENTIONS):
                conflicts.append(name)
    return {
        "status": "conflict" if conflicts else "no_explicit_conflict_found",
        "files": conflicts,
        "limitation": "detects a few explicit phrases only; review drafts for unseen findings",
    }


def prepare_direct_export(session: str | None = None, scan_id: str | None = None) -> dict[str, Any]:
    """Create a private directory for one direct-review Markdown export."""
    key, source = session_key(session)
    accepted = _accepted_scan_records(scan_id, key) if scan_id else None
    exports = ensure_private_dir(ensure_private_dir(data_home()) / "exports")
    export_id = f"direct-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"
    directory = ensure_private_dir(exports / export_id)
    atomic_write_json(
        directory / EXPORT_META,
        {"prepared_at": now_iso(), "session_id": key, "session_source": source, "scan_id": scan_id},
    )
    return {
        "export_id": export_id,
        "directory": str(directory),
        "directory_mode": "0o700",
        "output_paths": {
            "development": str(directory / "review-development.md"),
            "authors": str(directory / "comments-to-authors.md"),
            "editor": str(directory / "comments-to-editor.md"),
        },
        "receipt_path": str(directory / RECEIPT_NAME),
        "finalize_command": f"creview direct finalize {export_id}",
        "accepted_scan_records": accepted,
    }


def finalize_direct_export(export_id: str, profile: str | None = None) -> dict[str, Any]:
    """Record a receipt for the files the agent wrote into a prepared direct export."""
    from .deployment import PROFILE_MANIFEST
    from .hermes import profile_root

    if not EXPORT_ID_RE.fullmatch(export_id):
        raise ReviewError("invalid direct export id")
    directory = data_home() / "exports" / export_id
    if not directory.is_dir():
        raise ReviewError(f"direct export does not exist: {export_id}")
    if (profile_root(profile) / PROFILE_MANIFEST).is_file():
        missing = [
            name
            for name in SUBJECT_ROLES
            if not (directory / name).is_file()
            or not (directory / name).read_text(encoding="utf-8").strip()
        ]
        if missing:
            raise ReviewError(
                "managed review export is incomplete; write these drafts before finalizing: "
                + ", ".join(missing)
            )
    if not any((directory / name).is_file() for name in SUBJECT_ROLES):
        raise ReviewError("write the export files before finalizing")
    meta_path = directory / EXPORT_META
    meta = read_json(meta_path) if meta_path.is_file() else {}
    key, source = meta.get("session_id"), meta.get("session_source")
    if key is None:
        key, source = session_key()
    severity_check = None
    scope_check = None
    if meta.get("scan_id"):
        accepted = _accepted_scan_records(meta["scan_id"], key)
        severity_check = check_export_severity(directory, accepted)
        if severity_check["status"] == "conflict":
            conflict = severity_check["conflicts"][0]
            raise ReviewError(
                f"{conflict['file']} calls the accepted concern {conflict['draft_rating']}, "
                f"but the scan rates it {conflict['scan_rating']}; correct the draft or ask "
                "the reviewer for their own severity judgment"
            )
        scope_check = check_export_scope(directory)
        if scope_check["status"] == "conflict":
            raise ReviewError(
                f"{scope_check['files'][0]} mentions findings not shown to the reviewer; "
                "remove that material before finalizing"
            )
    checked_at = now_iso()
    doctor = inspect_profile(profile, live=False)
    receipt = write_receipt(directory, doctor, checked_at, preflight_summary(key, source))
    return {
        "export_id": export_id,
        "receipt_path": str(directory / RECEIPT_NAME),
        "receipt_id": receipt["receipt_id"],
        "subjects": [subject["role"] for subject in receipt["subjects"]],
        "doctor": receipt["environment"]["doctor"],
        "preflight": receipt["preflight"]["status"],
        "severity_check": severity_check,
        "scope_check": scope_check,
    }
