"""Offline, hash-bound evaluation provenance. No model calls or human judgments."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from ..errors import ReviewError
from ..io import read_json, sha256_file
from ..receipts import endpoint_class
from ..routes import normalized_endpoint
from . import PROTOCOL
from .evaluation import BASELINE_CHECKS, SHA256, load_manifest


def verified_file(meta: dict, name: str, directory: Path) -> Path | None:
    value, digest = meta.get(name), meta.get(name + "_sha256")
    if (
        not isinstance(value, str)
        or not value
        or not isinstance(digest, str)
        or not SHA256.fullmatch(digest)
    ):
        return None
    target = Path(value)
    if not target.is_absolute():
        target = directory / target
    try:
        if not target.is_file() or target.is_symlink() or sha256_file(target) != digest:
            return None
    except (OSError, ValueError):
        return None
    return target


def corpus_provenance(audit: dict, directory: Path) -> tuple[bool, dict]:
    meta = audit.get("corpus", {})
    if not isinstance(meta, dict):
        return False, {}
    manifest = verified_file(meta, "manifest", directory)
    if manifest is None:
        return False, {}
    try:
        value, rows = load_manifest(manifest)
    except (OSError, ValueError, ReviewError):
        return False, {}
    approved = (
        value["synthetic_only"] is True
        and meta.get("source_only_validated") is True
        and meta.get("representative_medical_cases") is True
        and isinstance(meta.get("validation_reviewer"), str)
        and bool(meta["validation_reviewer"].strip())
    )
    return approved, {(row["module"], row["case_id"]): row["sha256"] for row in rows}


def evaluation_provenance(audit: dict, directory: Path, cases: dict) -> tuple:
    meta = audit.get("evaluation", {})
    batch_file = verified_file(meta, "batch", directory) if isinstance(meta, dict) else None
    if batch_file is None:
        return False, False, {}, {}, {}
    try:
        batch = read_json(batch_file)
        manifest_file = verified_file(audit.get("corpus", {}), "manifest", directory)
        if manifest_file is None:
            return False, False, {}, {}, {}
        manifest, _ = load_manifest(manifest_file)
        settings = batch.get("model_settings", {})
        indexes = []
        expected = {
            (module, case, repetition) for module, case in cases for repetition in (1, 2, 3)
        }
        for name in ("runs", "baselines"):
            rows = batch.get(name, [])
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                return False, False, {}, {}, {}
            indexed = {
                (row.get("module"), row.get("case_id"), row.get("repetition")): row for row in rows
            }
            if len(indexed) != len(rows) or set(indexed) != expected:
                return False, False, {}, {}, {}
            indexes.append(indexed)
        okay = (
            bool(cases)
            and batch.get("protocol") == PROTOCOL
            and batch.get("synthetic_only") is True
            and manifest["synthetic_only"] is True
            and batch.get("corpus_independently_reviewed") is manifest["independently_reviewed"]
            and bool(batch.get("finished_at"))
            and batch.get("requested_repetitions") == 3
            and batch.get("identity", {}).get("sums_sha256") == audit["identity"]["runner"]
            and batch.get("manifest_sha256") == audit.get("corpus", {}).get("manifest_sha256")
            and isinstance(settings, dict)
        )
        return (
            okay,
            batch.get("corpus_independently_reviewed") is True,
            indexes[0],
            indexes[1],
            settings,
        )
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        return False, False, {}, {}, {}


def baseline_provenance(
    entry: dict,
    run: dict,
    directory: Path,
    seen: set[str],
    expected: dict | None,
) -> bool:
    artifact = verified_file(entry, "baseline_artifact", directory)
    record_path = verified_file(entry, "baseline_record", directory)
    if artifact is None or record_path is None:
        return False
    try:
        record = read_json(record_path)
        if not isinstance(record, dict) or expected is None or record != expected:
            return False
        route = run.get("route", {})
        runtime, source_runtime = record.get("runtime", {}), route.get("runtime", {})
        context = route.get("configured_context_length")
        endpoint = route.get("base_url")
        parsed = urlsplit(endpoint or "")
        local = (
            parsed.scheme in {"http", "https"}
            and not (parsed.username or parsed.password or parsed.query or parsed.fragment)
            and endpoint_class(endpoint) in {"loopback", "private-network"}
        )
        session = record.get("session")
        okay = (
            record.get("protocol") == PROTOCOL
            and record.get("kind") == "ordinary_hermes_baseline"
            and record.get("engineering_passed") is True
            and record.get("case_id") == entry["case_id"]
            and record.get("module") == entry["module"]
            and record.get("repetition", 1) == entry["repetition"]
            and record.get("identity") == run.get("identity", {}).get("runner")
            and record.get("manuscript_sha256") == run.get("source", {}).get("sha256")
            and record.get("artifact_sha256") == entry["baseline_artifact_sha256"]
            and record.get("model") == entry.get("baseline_model") == route.get("model")
            and type(context) is int
            and context >= 65536
            and record.get("configured_context_length") == context
            and local
            and all(
                lane.get("status") == "verified"
                and lane.get("provider") == "custom"
                and lane.get("model") == route.get("model")
                and normalized_endpoint(lane.get("base_url")) == normalized_endpoint(endpoint)
                for lane in (runtime, source_runtime)
            )
            and isinstance(session, str)
            and bool(session)
            and session not in seen
            and isinstance(record.get("checks"), dict)
            and all(record["checks"].get(check) is True for check in BASELINE_CHECKS)
            and entry.get("baseline_reviewed") is True
            and isinstance(entry.get("baseline_review_notes"), str)
            and bool(entry["baseline_review_notes"].strip())
        )
        if okay:
            seen.add(session)
        return okay
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        return False
