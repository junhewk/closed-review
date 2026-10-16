from __future__ import annotations

import secrets
import shutil
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from filelock import FileLock

from . import __version__
from .errors import ReviewError
from .io import (
    atomic_write_json,
    case_root,
    data_home,
    ensure_private_dir,
    load_case,
    permission_problem,
    read_json,
    safe_name,
    secure_file,
    sha256_file,
)
from .parsers import parse_document


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_case_id() -> str:
    return f"review-{datetime.now(UTC).strftime('%Y%m%d')}-{secrets.token_hex(4)}"


def _copy_and_parse(
    root: Path, source: Path, role: str, ordinal: int, source_id: str
) -> dict[str, Any]:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise ReviewError(f"input is not a file: {source}")
    destination = root / "originals" / f"{role}-{ordinal}-{safe_name(source.name)}"
    shutil.copyfile(source, destination)
    secure_file(destination)
    parsed = parse_document(destination)
    source_record = {
        "schema_version": "1",
        "source_id": source_id,
        "role": role,
        "original_name": source.name,
        "snapshot_name": destination.name,
        "sha256": sha256_file(destination),
        "format": parsed.format,
        "page_count": parsed.page_count,
        "warnings": parsed.warnings,
        "segments": parsed.segments,
    }
    atomic_write_json(root / "sources" / f"{source_id}.json", source_record)
    return {
        key: source_record[key]
        for key in (
            "source_id",
            "role",
            "original_name",
            "snapshot_name",
            "sha256",
            "format",
            "page_count",
            "warnings",
        )
    } | {
        "segment_count": len(parsed.segments),
        "character_count": sum(len(item["text"]) for item in parsed.segments),
    }


def create_case(
    manuscript: Path,
    *,
    journal: str,
    title: str | None = None,
    language: str = "English",
    supplements: Iterable[Path] = (),
    guidelines: Iterable[Path] = (),
    review_forms: Iterable[Path] = (),
) -> dict[str, Any]:
    if not journal.strip():
        raise ReviewError("journal is required")
    ensure_private_dir(data_home())
    ensure_private_dir(data_home() / "cases")
    root = case_root(_new_case_id())
    if root.exists():
        raise ReviewError("generated case id already exists")
    ensure_private_dir(root)
    for directory in (
        "originals",
        "sources",
        "findings",
        "proposals",
        "lookups",
        "drafts",
        "scratch",
    ):
        ensure_private_dir(root / directory)

    try:
        sources: list[dict[str, Any]] = []
        sources.append(_copy_and_parse(root, manuscript, "manuscript", 1, "manuscript"))
        groups = (
            ("supplement", list(supplements)),
            ("guideline", list(guidelines)),
            ("review-form", list(review_forms)),
        )
        for role, paths in groups:
            for index, path in enumerate(paths, start=1):
                sources.append(_copy_and_parse(root, path, role, index, f"{role}-{index}"))
        created = now_iso()
        manifest = {
            "schema_version": "1",
            "runner_version": __version__,
            "case_id": root.name,
            "journal": journal.strip(),
            "title": title.strip() if title else None,
            "language": language.strip() or "English",
            "created_at": created,
            "updated_at": created,
            "status": "intake",
            "policy_attestation": None,
            "sources": sources,
        }
        atomic_write_json(root / "manifest.json", manifest)
        atomic_write_json(root / "events.json", [])
        append_event(root, "case_created", {"source_ids": [item["source_id"] for item in sources]})
        return manifest
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


def append_event(root: Path, event: str, detail: dict[str, Any]) -> None:
    path = root / "events.json"
    events = read_json(path) if path.exists() else []
    events.append({"at": now_iso(), "event": event, "detail": detail})
    atomic_write_json(path, events)


def attest_case(case_id: str, statement: str) -> dict[str, Any]:
    statement = statement.strip()
    if len(statement) < 10:
        raise ReviewError("attestation must contain the user's explicit confirmation")
    root, manifest = load_case(case_id)
    with FileLock(str(root / ".lock")):
        manifest = read_json(root / "manifest.json")
        manifest["policy_attestation"] = {
            "statement": statement,
            "recorded_at": now_iso(),
            "kind": "user_attestation",
        }
        manifest["updated_at"] = now_iso()
        atomic_write_json(root / "manifest.json", manifest)
        append_event(root, "policy_attested", {"statement": statement})
    return manifest["policy_attestation"]


def list_sources(case_id: str) -> list[dict[str, Any]]:
    _, manifest = load_case(case_id)
    return manifest["sources"]


def load_source(case_id: str, source_id: str) -> dict[str, Any]:
    root, manifest = load_case(case_id)
    allowed = {item["source_id"] for item in manifest["sources"]}
    if source_id not in allowed:
        raise ReviewError(f"unknown source id: {source_id}")
    return read_json(root / "sources" / f"{source_id}.json")


def read_locator(case_id: str, source_id: str, locator: str) -> dict[str, Any]:
    source = load_source(case_id, source_id)
    for segment in source["segments"]:
        if segment["locator"] == locator:
            return {
                "source_id": source_id,
                "locator": locator,
                "kind": segment["kind"],
                "text": segment["text"],
            }
    raise ReviewError(f"unknown locator for {source_id}: {locator}")


def find_source(
    case_id: str, words: str, *, source_id: str | None = None, limit: int = 10
) -> list[dict[str, Any]]:
    tokens = {token.lower() for token in words.split() if token.strip()}
    if not tokens:
        raise ReviewError("search words are required")
    sources = (
        [load_source(case_id, source_id)]
        if source_id
        else [load_source(case_id, item["source_id"]) for item in list_sources(case_id)]
    )
    matches: list[tuple[int, dict[str, Any]]] = []
    for source in sources:
        for segment in source["segments"]:
            lowered = segment["text"].lower()
            score = sum(lowered.count(token) for token in tokens)
            if score:
                snippet = segment["text"][:500]
                matches.append(
                    (
                        score,
                        {
                            "source_id": source["source_id"],
                            "locator": segment["locator"],
                            "kind": segment["kind"],
                            "score": score,
                            "snippet": snippet,
                        },
                    )
                )
    matches.sort(key=lambda item: (-item[0], item[1]["source_id"], item[1]["locator"]))
    return [item for _, item in matches[: max(1, min(limit, 50))]]


def case_status(case_id: str) -> dict[str, Any]:
    root, manifest = load_case(case_id)
    state_path = root / "review-state.json"
    state = read_json(state_path) if state_path.exists() else None
    return {
        "case_id": case_id,
        "journal": manifest["journal"],
        "title": manifest.get("title"),
        "status": manifest["status"],
        "policy_attested": bool(manifest.get("policy_attestation")),
        "sources": manifest["sources"],
        "review": state,
    }


def purge_case(case_id: str, confirmation: str) -> dict[str, Any]:
    if confirmation != case_id:
        raise ReviewError("confirmation must exactly match the case id")
    root, _ = load_case(case_id)
    resolved_root = data_home().resolve()
    resolved_case = root.resolve()
    if resolved_case.parent != resolved_root / "cases":
        raise ReviewError("refusing to purge a path outside the case store")
    shutil.rmtree(resolved_case)
    return {"case_id": case_id, "purged": True}


def read_statement(statement: str | None, statement_file: Path | None) -> str:
    if statement_file:
        try:
            return statement_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise ReviewError(f"cannot read statement file: {exc}") from exc
    return statement or ""


def assert_private_store() -> list[str]:
    problems: list[str] = []
    root = data_home()
    problem = permission_problem(root) if root.exists() else None
    if problem:
        problems.append(f"data store is not private: {problem}")
    return problems
