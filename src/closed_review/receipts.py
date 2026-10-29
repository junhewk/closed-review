"""Self-reported export receipts.

A receipt records which creview build and model settings produced an export, plus hashes of the
exported text. It is written by creview itself, but it is not signed: it shows integrity against
accidental change, not proof against deliberate forgery.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from filelock import FileLock

from . import __version__
from .errors import ReviewError
from .io import (
    atomic_write_json,
    data_home,
    ensure_private_dir,
    now_iso,
    read_json,
    secure_file,
    sha256_file,
)

RECEIPT_VERSION = 2
RECEIPT_NAME = "receipt.json"
TEXT_NORMALIZATION = "nfkc-collapse-whitespace-v1"
SHARED_ADDRESS_SPACE = ipaddress.ip_network("100.64.0.0/10")
SUBJECT_ROLES = {
    "comments-to-authors.md": "authors",
    "comments-to-editor.md": "editor",
    "review-development.md": "development",
}


def normalize_text(value: str) -> str:
    """Fold formatting that journal web forms change, while keeping every word."""
    return " ".join(unicodedata.normalize("NFKC", value).split())


def text_sha256(value: str) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def receipt_id(receipt: dict[str, Any]) -> str:
    body = {key: value for key, value in receipt.items() if key != "receipt_id"}
    return hashlib.sha256(canonical_json(body)).hexdigest()


def installed_sums() -> str:
    """List installed package files in `sha256sum` format, excluding interpreter caches."""
    package = Path(__file__).resolve().parent
    lines = [
        f"{sha256_file(path)}  {path.relative_to(package).as_posix()}"
        for path in package.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ]
    return "".join(f"{line}\n" for line in sorted(lines, key=lambda line: line[66:]))


def endpoint_class(url: str | None) -> str:
    """Classify the model endpoint without recording an address that could identify a reviewer."""
    if not url:
        return "unknown"
    host = (urlsplit(url).hostname or "").lower()
    if host == "localhost":
        return "loopback"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return "private-network" if host.endswith(".ts.net") else "hostname"
    if address.is_loopback:
        return "loopback"
    if address.is_private or address in SHARED_ADDRESS_SPACE:
        return "private-network"
    return "public"


def build_receipt(
    directory: Path, doctor: dict[str, Any], checked_at: str, preflight: dict[str, Any]
) -> dict[str, Any]:
    subjects = []
    for name, role in SUBJECT_ROLES.items():
        path = directory / name
        if path.is_file():
            subjects.append(
                {
                    "role": role,
                    "file": name,
                    "sha256": sha256_file(path),
                    "text_sha256": text_sha256(path.read_text(encoding="utf-8")),
                }
            )
    sums = installed_sums()
    receipt: dict[str, Any] = {
        "receipt_version": RECEIPT_VERSION,
        "tool": {
            "name": "closed-review",
            "version": __version__,
            "sums_sha256": hashlib.sha256(sums.encode("utf-8")).hexdigest(),
        },
        "environment": {
            "host": doctor.get("host", "hermes"),
            "model": doctor.get("model"),
            "endpoint_class": endpoint_class(doctor.get("base_url")),
            "doctor": "pass" if doctor.get("ready") else "fail",
            "doctor_checked_at": checked_at,
            "skill_privacy_block": doctor.get("skill_privacy_block"),
        },
        "preflight": preflight,
        "exported_at": now_iso(),
        "text_normalization": TEXT_NORMALIZATION,
        "subjects": subjects,
        "attestations": [{"type": "self"}],
    }
    return {"receipt_id": receipt_id(receipt), **receipt}


def write_receipt(
    directory: Path, doctor: dict[str, Any], checked_at: str, preflight: dict[str, Any]
) -> dict[str, Any]:
    """Write the receipt beside the export and append it to the private local log."""
    receipt = build_receipt(directory, doctor, checked_at, preflight)
    atomic_write_json(directory / RECEIPT_NAME, receipt)
    root = ensure_private_dir(data_home())
    log = root / "receipts.jsonl"
    with FileLock(str(root / ".receipts.lock")):
        fd = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "ab") as handle:
            handle.write(canonical_json(receipt) + b"\n")
    secure_file(log)
    return receipt


def installed_identity() -> dict[str, str]:
    sums = installed_sums()
    return {
        "version": __version__,
        "sums_sha256": hashlib.sha256(sums.encode("utf-8")).hexdigest(),
        "sums": sums,
    }


def verify_receipt(path: Path, sums_file: Path | None = None) -> dict[str, Any]:
    """Check a receipt against its exported files and a reference build of creview.

    The tool check is meaningful only when this verifier is not the copy being audited: run it
    from a fresh install of the release named in the receipt, or pass that release's sums file.
    """
    receipt = read_json(path)
    if not isinstance(receipt, dict) or not isinstance(receipt.get("tool"), dict):
        raise ReviewError(f"not a closed-review receipt: {path}")
    subjects = []
    for subject in receipt.get("subjects", []):
        exported = path.parent / subject["file"]
        if not exported.is_file():
            status = "missing"
        elif sha256_file(exported) == subject["sha256"]:
            status = "match"
        elif text_sha256(exported.read_text(encoding="utf-8")) == subject["text_sha256"]:
            status = "text_match"
        else:
            status = "changed"
        subjects.append({"file": subject["file"], "status": status})
    tool = receipt["tool"]
    identity = installed_identity()
    if sums_file is not None:
        reference = hashlib.sha256(sums_file.read_bytes()).hexdigest()
        reference_source = "sums_file"
    elif tool.get("version") == __version__:
        reference = identity["sums_sha256"]
        reference_source = "this_creview"
    else:
        reference = None
        reference_source = None
    tool_status = (
        "not_checked"
        if reference is None
        else "match"
        if reference == tool.get("sums_sha256")
        else "mismatch"
    )
    receipt_id_valid = receipt.get("receipt_id") == receipt_id(receipt)
    return {
        "verified": receipt_id_valid
        and tool_status == "match"
        and all(item["status"] in {"match", "text_match"} for item in subjects),
        "receipt_id_valid": receipt_id_valid,
        "subjects": subjects,
        "tool": {
            "receipt_version": tool.get("version"),
            "status": tool_status,
            "reference": reference_source,
        },
        "preflight": receipt.get("preflight", {"status": "not_recorded"}),
        "verifier": {
            "version": identity["version"],
            "sums_sha256": identity["sums_sha256"],
            "note": (
                "A copy of creview on the reviewed machine cannot vouch for itself. Run this "
                "from a fresh install of the receipt's release, e.g. `uvx --from "
                "git+https://github.com/junhewk/closed-review.git@vVERSION creview receipts "
                "verify RECEIPT`."
            ),
        },
    }
