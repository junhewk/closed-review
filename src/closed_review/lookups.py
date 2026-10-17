"""Individually approved scholarly lookups (Crossref, OpenAlex).

A request records the exact query and URL before anything leaves the machine; `run` executes only
that URL, after the reviewer's approval is recorded. Requests belong to an audited case, or, in a
direct or deep review, to the Hermes session that passed `creview session start`.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from filelock import FileLock

from . import __version__
from .cases import append_event, now_iso, read_statement
from .errors import ReviewError
from .io import atomic_write_json, data_home, ensure_private_dir, load_case, read_json
from .session import preflight_summary, session_key
from .transcript import reviewer_words


def session_source(session: str | None) -> str | None:
    return session_key(session)[1]


PROVIDERS = {"crossref", "openalex"}


def _request_url(provider: str, query: str) -> str:
    if provider == "crossref":
        params = urlencode(
            {
                "query.bibliographic": query,
                "rows": 5,
                "select": "DOI,title,author,published,URL,type,container-title",
            }
        )
        return f"https://api.crossref.org/works?{params}"
    params = urlencode({"search": query, "per-page": 5})
    return f"https://api.openalex.org/works?{params}"


def _store(case_id: str | None, session: str | None) -> tuple[Path, dict[str, str], Path | None]:
    """The lookups directory, the owner recorded on each request, and the case root for events."""
    if case_id:
        root, _ = load_case(case_id)
        return root / "lookups", {"case_id": case_id}, root
    key, source = session_key(session)
    if preflight_summary(key, source)["status"] != "passed":
        raise ReviewError(
            "run `creview session start` in this Hermes session first, or pass an audited CASE"
        )
    directory = ensure_private_dir(ensure_private_dir(data_home() / "lookups") / str(key))
    return directory, {"session_id": str(key)}, None


def _request_path(directory: Path, request_id: str) -> Path:
    if not request_id.startswith("lookup-") or "/" in request_id or "\\" in request_id:
        raise ReviewError("invalid lookup request id")
    path = directory / f"{request_id}.json"
    if not path.is_file():
        raise ReviewError(f"lookup request does not exist: {request_id}")
    return path


def create_lookup(
    case_id: str | None,
    provider: str,
    query: str,
    *,
    session: str | None = None,
    scan_id: str | None = None,
) -> dict[str, Any]:
    provider = provider.lower().strip()
    query = query.strip()
    if provider not in PROVIDERS:
        raise ReviewError("lookup provider must be crossref or openalex")
    if not query or len(query) > 500:
        raise ReviewError("lookup query must contain 1 to 500 characters")
    directory, owner, case_root = _store(case_id, session)
    request = {
        "schema_version": "1",
        "request_id": f"lookup-{secrets.token_hex(5)}",
        **owner,
        **({"scan_id": scan_id} if scan_id else {}),
        "provider": provider,
        "query": query,
        "url": _request_url(provider, query),
        "status": "pending_approval",
        "created_at": now_iso(),
        "approval": None,
        "executed_at": None,
        "result": None,
    }
    atomic_write_json(directory / f"{request['request_id']}.json", request)
    if case_root:
        append_event(
            case_root,
            "lookup_requested",
            {"request_id": request["request_id"], "provider": provider, "query": query},
        )
    return request


def _crossref_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = ((payload.get("message") or {}).get("items") or [])[:5]
    return [
        {
            "doi": item.get("DOI"),
            "title": (item.get("title") or [None])[0],
            "authors": [
                " ".join(part for part in (author.get("given"), author.get("family")) if part)
                for author in (item.get("author") or [])[:12]
            ],
            "published": item.get("published"),
            "url": item.get("URL"),
            "type": item.get("type"),
            "container_title": (item.get("container-title") or [None])[0],
        }
        for item in items
        if isinstance(item, dict)
    ]


def _openalex_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = (payload.get("results") or [])[:5]
    return [
        {
            "openalex_id": item.get("id"),
            "doi": item.get("doi"),
            "title": item.get("display_name"),
            "authors": [
                ((authorship.get("author") or {}).get("display_name"))
                for authorship in (item.get("authorships") or [])[:12]
                if isinstance(authorship, dict)
            ],
            "published": item.get("publication_date"),
            "url": ((item.get("primary_location") or {}).get("landing_page_url")),
            "type": item.get("type"),
            "cited_by_count": item.get("cited_by_count"),
        }
        for item in items
        if isinstance(item, dict)
    ]


def run_lookup(
    case_id: str | None,
    request_id: str,
    *,
    approval_statement: str | None = None,
    approval_file: Path | None = None,
    session: str | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    directory, owner, case_root = _store(case_id, session)
    path = _request_path(directory, request_id)
    lock = FileLock(str((case_root or directory) / ".lock"))
    with lock:
        request = read_json(path)
        if any(request.get(name) != value for name, value in owner.items()):
            raise ReviewError("lookup request belongs to another case or session")
        if request.get("status") != "pending_approval":
            raise ReviewError("lookup request is not waiting for approval")
        expected_url = _request_url(request.get("provider", ""), request.get("query", ""))
        if request.get("url") != expected_url:
            raise ReviewError("lookup request URL does not match its approved provider and query")
        statement = read_statement(approval_statement, approval_file).strip()
        if len(statement) < 8:
            raise ReviewError("record the user's explicit approval of this exact query")
        approval = reviewer_words(
            statement,
            hermes_session="session_id" in owner and session_source(session) == "hermes_session",
            what="the lookup approval",
            since=request.get("created_at"),
        )
        request["approval"] = approval | {"statement": statement, "recorded_at": now_iso()}
        request["status"] = "approved"
        atomic_write_json(path, request)

    headers = {
        "Accept": "application/json",
        "User-Agent": f"closed-review/{__version__} (local confidential review; approved query)",
    }
    try:
        response = httpx.get(
            request["url"], headers=headers, timeout=timeout, follow_redirects=False
        )
        response.raise_for_status()
        payload = response.json()
        result = (
            _crossref_items(payload)
            if request["provider"] == "crossref"
            else _openalex_items(payload)
        )
    except Exception as exc:
        with lock:
            request = read_json(path)
            request["status"] = "failed"
            request["executed_at"] = now_iso()
            request["error"] = str(exc)
            atomic_write_json(path, request)
            if case_root:
                append_event(
                    case_root, "lookup_failed", {"request_id": request_id, "error": str(exc)}
                )
        raise ReviewError(f"approved lookup failed: {exc}") from exc

    with lock:
        request = read_json(path)
        request["status"] = "executed"
        request["executed_at"] = now_iso()
        request["result"] = result
        atomic_write_json(path, request)
        if case_root:
            append_event(
                case_root,
                "lookup_executed",
                {"request_id": request_id, "result_count": len(result)},
            )
    return request


def show_lookup(
    case_id: str | None, request_id: str, *, session: str | None = None
) -> dict[str, Any]:
    directory, _, _ = _store(case_id, session)
    return read_json(_request_path(directory, request_id))


def purge_scan_lookups(session: str, scan_id: str) -> int:
    """Delete the lookup requests a deep scan prepared; `scan purge` calls this."""
    directory = data_home() / "lookups" / session
    removed = 0
    for path in sorted(directory.glob("lookup-*.json")) if directory.is_dir() else []:
        if read_json(path).get("scan_id") == scan_id:
            path.unlink()
            removed += 1
    return removed
