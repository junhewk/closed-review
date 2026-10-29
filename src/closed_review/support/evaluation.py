"""Key-free corpus contracts for diagnostic runs and offline synthetic qualification."""

from __future__ import annotations

import re
from pathlib import Path

from ..errors import ReviewError
from ..io import read_json, sha256_file
from . import PROTOCOL
from .methods import MODULES
from .sources import FORMATS

SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,59}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
BASELINE_CHECKS = {
    "strict_local_runtime",
    "strict_preflight_recorded",
    "source_unchanged",
    "baseline_file_exists",
    "no_support_workflow",
    "no_legacy_scan",
    "tool_trace_available",
    "ordinary_tools_only",
    "no_auto_loaded_support_skill",
    "requested_model_endpoint_context",
}


def load_manifest(path: Path, corpus: Path | None = None) -> tuple[dict, list[dict]]:
    value = read_json(path)
    if not isinstance(value, dict) or set(value) != {
        "protocol",
        "corpus_id",
        "synthetic_only",
        "independently_reviewed",
        "cases",
    }:
        raise ReviewError("use only the key-free corpus manifest fields, never private answer keys")
    if (
        value["protocol"] != PROTOCOL
        or type(value["synthetic_only"]) is not bool
        or type(value["independently_reviewed"]) is not bool
        or not isinstance(value["corpus_id"], str)
        or not value["corpus_id"].strip()
        or not isinstance(value["cases"], list)
        or not value["cases"]
    ):
        raise ReviewError("expected a medical-support corpus manifest with explicit source kind")
    seen, cases = set(), []
    for row in value["cases"]:
        if not isinstance(row, dict) or set(row) != {"case_id", "module", "file", "sha256"}:
            raise ReviewError(
                "case fields must be case_id/module/file/sha256 only, never expected issues"
            )
        case = row["case_id"]
        if (
            not isinstance(case, str)
            or not SAFE_ID.fullmatch(case)
            or case in seen
            or not isinstance(row["module"], str)
            or row["module"] not in MODULES
        ):
            raise ReviewError("cases need distinct safe IDs and one known module each")
        if not isinstance(row["file"], str):
            raise ReviewError("case file must name a corpus-relative manuscript")
        relative = Path(row["file"])
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.suffix.lower() not in FORMATS
            or not isinstance(row["sha256"], str)
            or not SHA256.fullmatch(row["sha256"])
        ):
            raise ReviewError("missing, changed, out-of-corpus or unsupported case file")
        entry = dict(row)
        if corpus is not None:
            paper = corpus / relative
            if (
                not paper.is_file()
                or paper.is_symlink()
                or not paper.resolve().is_relative_to(corpus.resolve())
                or sha256_file(paper) != row["sha256"]
            ):
                raise ReviewError("missing, changed, out-of-corpus or unsupported case file")
            entry["path"] = paper.resolve()
        seen.add(case)
        cases.append(entry)
    return value, cases
