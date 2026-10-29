from __future__ import annotations

import json
import re
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from filelock import FileLock

from .errors import ReviewError
from .io import (
    atomic_write_json,
    data_home,
    ensure_private_dir,
    now_iso,
    read_json,
    read_statement,
    sha256_bytes,
    sha256_file,
)
from .parsers import parse_document

REFERENCE_HEADING = re.compile(r"\b(?:references|bibliography|literature cited)\b", re.I)
DOI = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
YEAR = re.compile(r"(?:19|20)\d{2}[a-z]?")
SURNAME = r"[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'’\-]+"
NARRATIVE_CITATION = re.compile(rf"\b({SURNAME})(?:\s+et\s+al\.)?\s*\(({YEAR.pattern})\)")
AUTHOR_YEAR_REFERENCE = re.compile(
    rf"({SURNAME}),\s+(?:[A-Z]\.\s*)+.{{0,500}}?\(({YEAR.pattern})\)\.", re.S
)
CORPORATE_AUTHOR_YEAR_REFERENCE = re.compile(
    rf"(?<![\w,])"
    rf"((?:[A-Z][A-Za-zÀ-ÖØ-öø-ÿ&'’\-]*\s+){{1,7}}"
    rf"(?:Society|Association|Organization|Organisation|Committee|Agency|Institute|"
    rf"Ministry|Department|Council|Office|Group))\.?\s*\(({YEAR.pattern})\)\."
)
NUMBERED_REFERENCE = re.compile(r"(?:^|\s)(?:\[(\d{1,4})\]|(\d{1,4})[.)])\s+")
NUMBERED_CITATION = re.compile(r"\[([0-9,;\-–—\s]+)\]")


def _normalized(value: str) -> str:
    return re.sub(r"\W+", " ", value.casefold()).strip()


def _without_dense_line_numbers(value: str) -> tuple[str, bool]:
    pattern = re.compile(r"(?<![\w./-])(?:[1-9]|[1-9]\d)(?![\w./-])")
    matches = list(pattern.finditer(value))
    if len(matches) < 20:
        return value, False
    return pattern.sub(" ", value), True


def _repair_split_authors(value: str, entries: list[dict[str, Any]]) -> tuple[str, int]:
    repaired = value
    repair_count = 0
    authors = sorted(
        {str(entry.get("author", "")).strip() for entry in entries if entry.get("author")},
        key=len,
        reverse=True,
    )
    for author in authors:
        words = author.split()
        word_patterns = [r"\s*".join(re.escape(char) for char in word) for word in words]
        pattern = re.compile(r"(?<!\w)" + r"\s+".join(word_patterns) + r"(?!\w)", re.I)

        def replace(match: re.Match[str], canonical: str = author) -> str:
            nonlocal repair_count
            if match.group(0).casefold() != canonical.casefold():
                repair_count += 1
            return canonical

        repaired = pattern.sub(replace, repaired)
    return repaired, repair_count


def _repair_doi_spacing(value: str) -> tuple[str, int]:
    repaired = value
    repair_count = 0

    def compact_start(match: re.Match[str]) -> str:
        nonlocal repair_count
        compact = re.sub(r"\s+", "", match.group(0))
        if compact != match.group(0):
            repair_count += 1
        return compact

    repaired = re.sub(r"\b10\.\d{4,9}\s*/\s*", compact_start, repaired, flags=re.I)
    continuation_patterns = (
        re.compile(r"(\b10\.\d{4,9}/\S{1,200}-)\s+(?=[A-Za-z0-9])", re.I),
        re.compile(r"(\b10\.\d{4,9}/\S{1,200})\s+(?=-\d)", re.I),
    )
    changed = True
    while changed:
        changed = False
        for pattern in continuation_patterns:
            repaired, count = pattern.subn(r"\1", repaired)
            if count:
                repair_count += count
                changed = True
    return repaired, repair_count


def _segments_from_input(manuscript: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = manuscript.expanduser().resolve()
    if not path.is_file():
        raise ReviewError(f"input is not a file: {path}")
    parsed = parse_document(path)
    return parsed.segments, {
        "source_id": "manuscript",
        "source_path": str(path),
        "source_sha256": sha256_file(path),
    }


def _partition_segments(
    segments: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[str]]:
    body: list[dict[str, str]] = []
    references: list[dict[str, str]] = []
    warnings: list[str] = []
    found = False
    for segment in segments:
        text = segment["text"]
        if not found:
            match = REFERENCE_HEADING.search(text)
            if text.strip().strip(":： ").casefold() in ("참고문헌", "참고 문헌"):
                found = True
                continue
            if match:
                found = True
                before = text[: match.start()].strip()
                after = text[match.end() :].strip(" :\n\t")
                if before:
                    body.append({"locator": segment["locator"], "text": before})
                if after:
                    references.append({"locator": segment["locator"], "text": after})
                continue
            body.append({"locator": segment["locator"], "text": text})
        else:
            references.append({"locator": segment["locator"], "text": text})
    if not found:
        warnings.append("No bibliography heading was detected; reference matching is unresolved.")
    if found and not references:
        warnings.append("The bibliography heading was detected but no reference text followed it.")
    return body, references, warnings


def _citation_numbers(text: str) -> set[int]:
    found: set[int] = set()
    for match in NUMBERED_CITATION.finditer(text):
        for part in re.split(r"[,;]\s*", match.group(1)):
            part = part.strip()
            range_match = re.fullmatch(r"(\d{1,4})\s*[-–—]\s*(\d{1,4})", part)
            if range_match:
                start, end = map(int, range_match.groups())
                if 0 < start <= end <= 500 and end - start <= 100:
                    found.update(range(start, end + 1))
            elif part.isdigit() and 0 < int(part) <= 500:
                found.add(int(part))
    return found


def _author_year_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for match in NARRATIVE_CITATION.finditer(text):
        keys.add(f"{match.group(1).casefold()}:{match.group(2).casefold()}")
    for group in re.findall(r"\(([^()]{0,300}(?:19|20)\d{2}[a-z]?[^()]*)\)", text):
        for item in group.split(";"):
            surname = re.search(SURNAME, item)
            if not surname:
                continue
            for year in YEAR.findall(item):
                keys.add(f"{surname.group(0).casefold()}:{year.casefold()}")
    return keys


def _reference_entries(
    reference_segments: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], str, bool, int]:
    raw = "\n".join(item["text"] for item in reference_segments)
    raw, doi_repairs = _repair_doi_spacing(raw)
    joined, normalized_line_numbers = _without_dense_line_numbers(raw)
    if not joined.strip():
        return [], "unknown", normalized_line_numbers, doi_repairs
    numbered = list(NUMBERED_REFERENCE.finditer(joined))
    bracketed = sum(bool(match.group(1)) for match in numbered)
    numbers = [int(match.group(1) or match.group(2)) for match in numbered]
    sequential = (
        len(numbers) >= 2
        and numbers[0] <= 5
        and sum(right == left + 1 for left, right in zip(numbers, numbers[1:], strict=False))
        >= max(1, len(numbers) - 2)
    )
    if len(numbered) >= 2 and (bracketed >= 2 or sequential):
        entries: list[dict[str, Any]] = []
        for index, match in enumerate(numbered):
            end = numbered[index + 1].start() if index + 1 < len(numbered) else len(joined)
            value = joined[match.end() : end].strip()
            if value:
                entries.append(
                    {
                        "reference_id": f"ref-{len(entries) + 1:04d}",
                        "number": int(match.group(1) or match.group(2)),
                        "key": str(int(match.group(1) or match.group(2))),
                        "text": value,
                    }
                )
        if len(entries) >= 2:
            return entries, "numbered", normalized_line_numbers, doi_repairs

    matches = [
        (match.start(), match.group(1), match.group(2))
        for match in AUTHOR_YEAR_REFERENCE.finditer(joined)
    ]
    matches.extend(
        (match.start(), match.group(1), match.group(2))
        for match in CORPORATE_AUTHOR_YEAR_REFERENCE.finditer(joined)
    )
    matches.sort(key=lambda item: item[0])
    entries = []
    for index, (start, author, year) in enumerate(matches):
        end = matches[index + 1][0] if index + 1 < len(matches) else len(joined)
        value = joined[start:end].strip()
        key_author = author.split()[0]
        entries.append(
            {
                "reference_id": f"ref-{index + 1:04d}",
                "key": f"{key_author.casefold()}:{year.casefold()}",
                "author": author,
                "year": year,
                "text": value,
            }
        )
    return (
        entries,
        "author_year" if entries else "unknown",
        normalized_line_numbers,
        doi_repairs,
    )


def _issue(kind: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"kind": kind, "message": message, **extra}


def _local_report(segments: list[dict[str, Any]]) -> dict[str, Any]:
    body, reference_segments, warnings = _partition_segments(segments)
    body_text, body_line_numbers = _without_dense_line_numbers(
        "\n".join(item["text"] for item in body)
    )
    entries, style, reference_line_numbers, preparse_doi_repairs = _reference_entries(
        reference_segments
    )
    body_text, author_repairs = _repair_split_authors(body_text, entries)
    normalizations: list[dict[str, Any]] = []
    if body_line_numbers or reference_line_numbers:
        normalizations.append(
            {
                "kind": "dense_line_numbers_removed",
                "message": "Dense standalone line-number artifacts were removed before matching.",
            }
        )
    if author_repairs:
        normalizations.append(
            {
                "kind": "split_author_tokens_repaired",
                "count": author_repairs,
                "message": (
                    "Author names split by extraction whitespace were repaired before matching."
                ),
            }
        )
    issues: list[dict[str, Any]] = []

    if style == "numbered":
        citations = _citation_numbers(body_text)
        numbers = [int(item["number"]) for item in entries]
        reference_numbers = set(numbers)
        for number in sorted(citations - reference_numbers):
            issues.append(
                _issue(
                    "citation_without_reference",
                    f"In-text citation [{number}] has no detected bibliography entry.",
                    citation_key=str(number),
                )
            )
        for number in sorted(reference_numbers - citations):
            issues.append(
                _issue(
                    "uncited_reference",
                    f"Bibliography entry {number} was not detected in the manuscript body.",
                    reference_key=str(number),
                )
            )
        duplicates = sorted({number for number in numbers if numbers.count(number) > 1})
        for number in duplicates:
            issues.append(
                _issue("duplicate_reference_number", f"Reference number {number} is duplicated.")
            )
        if reference_numbers:
            missing = sorted(
                set(range(min(reference_numbers), max(reference_numbers) + 1)) - reference_numbers
            )
            if missing:
                issues.append(
                    _issue("reference_numbering_gap", f"Reference numbering skips {missing}.")
                )
        citation_count = len(citations)
    else:
        citations = _author_year_keys(body_text)
        reference_keys = {item["key"] for item in entries}
        for key in sorted(citations - reference_keys):
            issues.append(
                _issue(
                    "citation_without_reference",
                    f"In-text author–year citation {key} has no detected bibliography entry.",
                    citation_key=key,
                )
            )
        for key in sorted(reference_keys - citations):
            issues.append(
                _issue(
                    "uncited_reference",
                    f"Bibliography entry {key} was not detected in the manuscript body.",
                    reference_key=key,
                )
            )
        duplicate_keys = sorted(
            {key for key in reference_keys if sum(item["key"] == key for item in entries) > 1}
        )
        for key in duplicate_keys:
            issues.append(
                _issue("duplicate_author_year_key", f"Reference key {key} is duplicated.")
            )
        citation_count = len(citations)

    normalized_entries: dict[str, list[str]] = {}
    doi_entries: dict[str, list[str]] = {}
    doi_repairs = preparse_doi_repairs
    for entry in entries:
        normalized_entries.setdefault(_normalized(entry["text"]), []).append(entry["reference_id"])
        doi_text, repairs = _repair_doi_spacing(entry["text"])
        doi_repairs += repairs
        dois = [value.rstrip(".,;") for value in DOI.findall(doi_text)]
        entry["dois"] = [value.lower() for value in dois]
        for doi in entry["dois"]:
            doi_entries.setdefault(doi, []).append(entry["reference_id"])
        suspicious = re.findall(r"\b10\.\S+", doi_text, re.I)
        for token in suspicious:
            cleaned = token.rstrip(".,;")
            if not DOI.fullmatch(cleaned):
                issues.append(
                    _issue(
                        "malformed_doi",
                        f"{entry['reference_id']} contains a DOI-like token with invalid syntax.",
                        reference_id=entry["reference_id"],
                        token=cleaned,
                    )
                )
    for ids in normalized_entries.values():
        if len(ids) > 1:
            issues.append(_issue("duplicate_reference", f"Duplicate entries detected: {ids}."))
    for doi, ids in doi_entries.items():
        if len(ids) > 1:
            issues.append(_issue("duplicate_doi", f"DOI {doi} appears in entries {ids}.", doi=doi))

    if doi_repairs:
        normalizations.append(
            {
                "kind": "doi_spacing_repaired",
                "count": doi_repairs,
                "message": (
                    "DOI spacing introduced by extraction wrapping was repaired before validation."
                ),
            }
        )

    if style == "unknown":
        warnings.append(
            "Citation style or bibliography entries could not be parsed reliably; no clean bill "
            "of reference consistency can be given."
        )
    if entries and not warnings and not normalizations:
        confidence = "high"
    else:
        confidence = "medium" if entries else "low"
    anchor = (reference_segments or body or [{"locator": "unknown", "text": "unresolved"}])[0]
    return {
        "citation_style": style,
        "parse_confidence": confidence,
        "citation_count": citation_count,
        "reference_count": len(entries),
        "entries": entries,
        "issues": issues,
        "warnings": warnings,
        "normalizations": normalizations,
        "default_evidence": {
            "locator": anchor["locator"],
            "quote": anchor["text"][:240],
        },
    }


def check_references(manuscript: Path) -> dict[str, Any]:
    segments, source = _segments_from_input(manuscript)
    report = {
        "schema_version": "2",
        "check_id": f"refcheck-{secrets.token_hex(5)}",
        "created_at": now_iso(),
        **source,
        **_local_report(segments),
        "metadata_requests": [],
    }
    root = ensure_private_dir(data_home() / "reference-checks")
    atomic_write_json(root / f"{report['check_id']}.json", report)
    return report


def _find_check(check_id: str) -> Path:
    if not re.fullmatch(r"refcheck-[a-f0-9]{10}", check_id):
        raise ReviewError("invalid reference check id")
    path = data_home() / "reference-checks" / f"{check_id}.json"
    if not path.is_file():
        raise ReviewError(f"unknown reference check id: {check_id}")
    return path


def show_reference_check(check_id: str) -> dict[str, Any]:
    return read_json(_find_check(check_id))


def _metadata_url(provider: str, entry: dict[str, Any]) -> tuple[str, str]:
    doi = (entry.get("dois") or [None])[0]
    if provider == "crossref" and doi:
        return doi, f"https://api.crossref.org/works/{quote(doi, safe='')}"
    query = doi or entry["text"][:500]
    if provider == "crossref":
        return query, "https://api.crossref.org/works?" + urlencode(
            {"query.bibliographic": query, "rows": 3}
        )
    return query, "https://api.openalex.org/works?" + urlencode({"search": query, "per-page": 3})


def request_reference_metadata(check_id: str, provider: str) -> dict[str, Any]:
    provider = provider.strip().lower()
    if provider not in {"crossref", "openalex"}:
        raise ReviewError("metadata provider must be crossref or openalex")
    path = _find_check(check_id)
    report = read_json(path)
    if not report.get("entries"):
        raise ReviewError("reference check contains no parsed entries")
    queries = []
    for entry in report["entries"]:
        query, url = _metadata_url(provider, entry)
        queries.append({"reference_id": entry["reference_id"], "query": query, "url": url})
    digest = sha256_bytes(json.dumps(queries, sort_keys=True).encode())
    request = {
        "schema_version": "1",
        "request_id": f"refmeta-{secrets.token_hex(5)}",
        "check_id": check_id,
        "provider": provider,
        "status": "pending_approval",
        "created_at": now_iso(),
        "query_manifest_sha256": digest,
        "queries": queries,
        "approval": None,
        "results": [],
    }
    request_path = path.parent / f"{request['request_id']}.json"
    atomic_write_json(request_path, request)
    report["metadata_requests"].append(request["request_id"])
    atomic_write_json(path, report)
    return request


def _metadata_items(provider: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    if provider == "crossref":
        message = payload.get("message") or {}
        items = (
            [message]
            if isinstance(message, dict) and message.get("DOI")
            else message.get("items") or []
        )
        return [
            {
                "doi": item.get("DOI"),
                "title": (item.get("title") or [None])[0],
                "published": item.get("published"),
                "container_title": (item.get("container-title") or [None])[0],
            }
            for item in items[:3]
            if isinstance(item, dict)
        ]
    return [
        {
            "doi": item.get("doi"),
            "title": item.get("display_name"),
            "published": item.get("publication_date"),
            "container_title": ((item.get("primary_location") or {}).get("source") or {}).get(
                "display_name"
            ),
        }
        for item in (payload.get("results") or [])[:3]
        if isinstance(item, dict)
    ]


def run_reference_metadata(
    check_id: str,
    request_id: str,
    *,
    approval_statement: str | None = None,
    approval_file: Path | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    path = _find_check(check_id)
    request_path = path.parent / f"{request_id}.json"
    with FileLock(str(path.parent / ".lock")):
        request = read_json(request_path)
        if request.get("check_id") != check_id or request.get("status") != "pending_approval":
            raise ReviewError("metadata request is not pending for this reference check")
        digest = sha256_bytes(json.dumps(request.get("queries"), sort_keys=True).encode())
        if digest != request.get("query_manifest_sha256"):
            raise ReviewError("metadata query manifest changed after it was prepared")
        statement = read_statement(approval_statement, approval_file).strip()
        if len(statement) < 8:
            raise ReviewError("record explicit approval of the displayed metadata query manifest")
        request["approval"] = {"statement": statement, "recorded_at": now_iso()}
        request["status"] = "approved"
        atomic_write_json(request_path, request)

    headers = {"Accept": "application/json", "User-Agent": "closed-review/0.5"}
    results: list[dict[str, Any]] = []
    report = read_json(path)
    entries = {item["reference_id"]: item for item in report.get("entries") or []}
    for item in request["queries"]:
        try:
            response = httpx.get(
                item["url"], headers=headers, timeout=timeout, follow_redirects=False
            )
            response.raise_for_status()
            matches = _metadata_items(request["provider"], response.json())
            expected_doi = (entries.get(item["reference_id"], {}).get("dois") or [None])[0]
            returned_dois = {
                str(match.get("doi") or "").removeprefix("https://doi.org/").lower()
                for match in matches
            }
            identity_status = (
                "doi_match"
                if expected_doi and expected_doi.lower() in returned_dois
                else "doi_mismatch"
                if expected_doi and matches
                else "metadata_candidate"
                if matches
                else "no_match"
            )
            results.append(
                {
                    **item,
                    "status": "matched" if matches else "no_match",
                    "identity_status": identity_status,
                    "matches": matches,
                }
            )
        except Exception as exc:
            results.append({**item, "status": "failed", "error": str(exc), "matches": []})

    with FileLock(str(path.parent / ".lock")):
        request = read_json(request_path)
        request["status"] = "executed"
        request["executed_at"] = now_iso()
        request["results"] = results
        atomic_write_json(request_path, request)
        report = read_json(path)
        report["metadata_summary"] = {
            "request_id": request_id,
            "provider": request["provider"],
            "counts": {
                status: sum(item.get("identity_status") == status for item in results)
                for status in ("doi_match", "doi_mismatch", "metadata_candidate", "no_match")
            },
            "note": (
                "Metadata matching verifies bibliographic identity only; it does not verify that "
                "a cited work supports the manuscript's substantive claim."
            ),
        }
        atomic_write_json(path, report)
    return request
