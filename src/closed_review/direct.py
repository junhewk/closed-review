from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime
from typing import Any

from .cases import now_iso
from .errors import ReviewError
from .hermes import inspect_profile
from .io import atomic_write_json, data_home, ensure_private_dir, read_json
from .receipts import RECEIPT_NAME, SUBJECT_ROLES, write_receipt
from .session import preflight_summary, profiles_confirmed, session_key

EXPORT_ID_RE = re.compile(r"^direct-\d{8}T\d{6}Z-[0-9a-f]{8}$")
EXPORT_META = "export.json"


def prepare_direct_export(session: str | None = None) -> dict[str, Any]:
    """Create a private directory for one direct-review Markdown export."""
    key, source = session_key(session)
    if preflight_summary(key, source)["status"] == "passed" and not profiles_confirmed(key):
        raise ReviewError(
            "the reviewer never confirmed the design profiles in this session: propose them, wait "
            "for the reviewer's reply, and record it with creview segments propose MANUSCRIPT "
            '--profile NAME --confirmation "THEIR WORDS" (or --no-profile)'
        )
    exports = ensure_private_dir(ensure_private_dir(data_home()) / "exports")
    export_id = f"direct-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"
    directory = ensure_private_dir(exports / export_id)
    atomic_write_json(
        directory / EXPORT_META,
        {"prepared_at": now_iso(), "session_id": key, "session_source": source},
    )
    output_path = directory / "journal-review.md"
    return {
        "export_id": export_id,
        "directory": str(directory),
        "directory_mode": "0o700",
        "output_path": str(output_path),
        "output_paths": {
            "development": str(directory / "review-development.md"),
            "authors": str(directory / "comments-to-authors.md"),
            "editor": str(directory / "comments-to-editor.md"),
        },
        "receipt_path": str(directory / RECEIPT_NAME),
        "finalize_command": f"creview direct finalize {export_id}",
    }


def finalize_direct_export(export_id: str, profile: str | None = None) -> dict[str, Any]:
    """Record a receipt for the files the agent wrote into a prepared direct export."""
    if not EXPORT_ID_RE.fullmatch(export_id):
        raise ReviewError("invalid direct export id")
    directory = data_home() / "exports" / export_id
    if not directory.is_dir():
        raise ReviewError(f"direct export does not exist: {export_id}")
    if not any((directory / name).is_file() for name in SUBJECT_ROLES):
        raise ReviewError("write the export files before finalizing")
    meta_path = directory / EXPORT_META
    meta = read_json(meta_path) if meta_path.is_file() else {}
    key, source = meta.get("session_id"), meta.get("session_source")
    if key is None:
        key, source = session_key()
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
    }
