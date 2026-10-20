"""creview as a library for a host app that drives the review itself.

`python -m closed_review.sidecar` reads one JSON request per line on stdin, {"id", "method",
"params"}, and writes one JSON reply per line on stdout, {"id", "result"} or {"id", "error"}. The
host keeps the review state; creview checks quotes and arithmetic, applies the severity and order
rules (findings.py), runs lookups the host has had the reviewer approve, and writes exports with a
receipt. Parsed documents stay in memory for the life of the process.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from . import __version__, designs, findings, pipeline
from .cases import assert_private_store, now_iso
from .errors import ReviewError
from .hermes import _models_url
from .io import atomic_write_json, atomic_write_text, data_home, ensure_private_dir
from .lookups import PROVIDERS, _crossref_items, _openalex_items, _request_url
from .receipts import RECEIPT_NAME, write_receipt
from .segments import draft_plan
from .settings import trusted_gateway

SESSION_CHARS = set("0123456789abcdef")
PROTOCOL = 2
"""The sidecar protocol a host checks at start: 2 adds the deep analysis (pipeline.py)."""
ROLES = {
    "authors": "comments-to-authors.md",
    "editor": "comments-to-editor.md",
    "development": "review-development.md",
}


class Sidecar:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}

    def _document(self, doc_id: str) -> dict[str, Any]:
        try:
            return self.documents[doc_id]
        except KeyError:
            raise ReviewError(f"no open document {doc_id}; open it first") from None

    @staticmethod
    def _session_dir(kind: str, session: str) -> Path:
        if len(session) != 32 or not set(session) <= SESSION_CHARS:
            raise ReviewError("session must be 32 lowercase hex characters")
        return ensure_private_dir(
            ensure_private_dir(ensure_private_dir(data_home()) / kind) / session
        )

    def preflight(self, live: bool = True) -> dict[str, Any]:
        """The trusted gateway, the models it serves, and whether the private store is private."""
        settings = trusted_gateway()
        problems = list(assert_private_store())
        if not (settings["url"] and settings["model"]):
            problems.append("no trusted model gateway is configured")
        models: list[dict[str, Any]] = []
        if live and settings["url"]:
            try:
                key = os.environ.get("CREVIEW_MODEL_API_KEY")
                headers = {"Authorization": f"Bearer {key}"} if key else {}
                reply = httpx.get(_models_url(settings["url"]), headers=headers, timeout=5.0)
                reply.raise_for_status()
                models = [m for m in reply.json().get("data", []) if isinstance(m, dict)]
            except Exception as exc:
                problems.append(f"trusted gateway health check failed: {exc}")
        return {
            "creview_version": __version__,
            "protocol": PROTOCOL,
            "gateway": settings["url"],
            "model": settings["model"],
            "trusted_models": settings["trusted_models"],
            "served": models,
            "problems": problems,
            "ready": not problems,
        }

    def knowledge(self, profiles: list[str] | None = None) -> dict[str, Any]:
        """closed-review's review knowledge, read from the installed package: the profiles on
        offer, the review contract and rubric by section, the major flaws in any design, and the
        chosen profiles' monitoring areas, false alarms, major flaws, and full text."""

        def sections(name: str) -> dict[str, str]:
            text = designs._references().joinpath(name).read_text(encoding="utf-8")
            parts = re.split(r"^## +(.+)$", text, flags=re.M)
            return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts), 2)}

        index = designs._designs().joinpath("index.md").read_text(encoding="utf-8")
        row = re.compile(r"^\| \[([a-z-]+)\]\([a-z-]+\.md\) \| (.+?) \|$", re.M)
        available = [{"id": m.group(1), "use_for": m.group(2).strip()} for m in row.finditer(index)]
        chosen = designs.load_profiles(profiles or [])
        for profile in chosen:
            profile["text"] = (
                designs._designs().joinpath(f"{profile['id']}.md").read_text(encoding="utf-8")
            )
        return {
            "available": available,
            "choosing": sections("designs/index.md"),
            "contract": sections("development.md"),
            "rubric": sections("review-rubric.md"),
            "general_major_flaws": designs.general_major_flaws(),
            "profiles": chosen,
        }

    def open(self, path: str) -> dict[str, Any]:
        document = findings.open_document(Path(path))
        doc_id = document["sha256"][:16]
        self.documents[doc_id] = document
        return {
            "doc_id": doc_id,
            "sha256": document["sha256"],
            "format": document["format"],
            "page_count": document["page_count"],
            "warnings": document["warnings"],
            "blocks": [
                {
                    "block_id": b["segment_id"],
                    "locator": b["locator"],
                    "kind": b["kind"],
                    "text": b["text"],
                }
                for b in document["segments"]
            ],
        }

    def plan(self, doc_id: str) -> dict[str, Any]:
        """Draft logical segments from the manuscript's headings: each with its title and blocks."""
        document = self._document(doc_id)
        drafted = draft_plan([{"source_id": "manuscript", "segments": document["segments"]}])
        return {
            "segments": [
                {"id": s["id"], "title": s["title"], "block_ids": s["block_ids"]}
                for s in drafted["segments"]
            ]
        }

    def reading_plan(self, doc_id: str) -> dict[str, Any]:
        """The plan to read by: heading-only fragments joined to the next segment, with each
        segment's words."""
        document = self._document(doc_id)
        blocks = pipeline.blocks_of(document)
        segments = pipeline.merge_short(blocks, self.plan(doc_id)["segments"])
        return {"segments": segments, "words": pipeline.segment_words(blocks, segments)}

    def flaws(self, profiles: list[str]) -> list[dict[str, str]]:
        """The listed major flaws for the confirmed profiles, in the order the profiles are
        offered."""
        offered = [p["id"] for p in self.knowledge()["available"]]
        chosen = [p for p in offered if p in profiles]
        knowledge = {
            "general_major_flaws": designs.general_major_flaws(),
            "profiles": designs.load_profiles(chosen),
        }
        return pipeline.listed_flaws(knowledge, chosen)

    def false_alarms(self, profiles: list[str]) -> dict[str, str]:
        offered = [p["id"] for p in self.knowledge()["available"]]
        chosen = [p for p in offered if p in profiles]
        return pipeline.false_alarms({"profiles": designs.load_profiles(chosen)}, chosen)

    def check_quotes(self, doc_id: str, quotes: list[Any]) -> dict[str, Any]:
        return findings.check_quotes(self._document(doc_id), quotes)

    def number_checks(self, doc_id: str, checks: list[Any]) -> dict[str, Any]:
        return findings.number_checks(self._document(doc_id), checks)

    def severity(self, finding: dict[str, Any]) -> dict[str, Any]:
        return findings.severity(finding)

    def merge_number_checks(self, findings_: list[dict[str, Any]]) -> list[list[str]]:
        return findings.merge_number_checks(findings_)

    def order(self, findings_: list[dict[str, Any]], segment_order: list[str]) -> dict[str, Any]:
        return findings.order(findings_, segment_order)

    def lookup_url(self, provider: str, query: str) -> dict[str, str]:
        """The exact URL a lookup would request, for the reviewer to approve before it runs."""
        provider = provider.lower().strip()
        if provider not in PROVIDERS:
            raise ReviewError("lookup provider must be crossref or openalex")
        return {
            "provider": provider,
            "query": query.strip(),
            "url": _request_url(provider, query.strip()),
        }

    def lookup(self, session: str, provider: str, query: str, approved_at: str) -> dict[str, Any]:
        """Run one Crossref or OpenAlex query the reviewer approved in the host, and keep a record:
        the exact URL, when it was approved, and what came back (bibliographic records only)."""
        provider = provider.lower().strip()
        query = query.strip()
        if provider not in PROVIDERS:
            raise ReviewError("lookup provider must be crossref or openalex")
        if not query or len(query) > 500:
            raise ReviewError("lookup query must contain 1 to 500 characters")
        if not approved_at:
            raise ReviewError("a lookup runs only with the reviewer's approval")
        url = _request_url(provider, query)
        record: dict[str, Any] = {
            "request_id": f"lookup-{secrets.token_hex(5)}",
            "provider": provider,
            "query": query,
            "url": url,
            "approved_at": approved_at,
            "executed_at": None,
            "result": None,
        }
        path = self._session_dir("pi-lookups", session) / f"{record['request_id']}.json"
        atomic_write_json(path, record)
        headers = {
            "Accept": "application/json",
            "User-Agent": f"closed-review/{__version__} (local confidential review; approved)",
        }
        try:
            reply = httpx.get(url, headers=headers, timeout=15.0, follow_redirects=False)
            reply.raise_for_status()
            payload = reply.json()
            items = _crossref_items(payload) if provider == "crossref" else _openalex_items(payload)
        except Exception as exc:
            record.update(executed_at=now_iso(), error=str(exc))
            atomic_write_json(path, record)
            raise ReviewError(f"approved lookup failed: {exc}") from exc
        record.update(executed_at=now_iso(), result=items)
        atomic_write_json(path, record)
        return record

    def export(
        self, session: str, files: dict[str, str], models: list[str], gateway: str
    ) -> dict[str, Any]:
        """Write the author and editor drafts and the private development record, with a receipt
        naming the host and every model that saw the manuscript."""
        unknown = sorted(set(files) - set(ROLES))
        if unknown or "authors" not in files:
            raise ReviewError("export needs authors (and may have editor, development) only")
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        directory = ensure_private_dir(
            self._session_dir("pi-exports", session) / f"{stamp}-{secrets.token_hex(4)}"
        )
        for role, text in files.items():
            atomic_write_text(directory / ROLES[role], text.rstrip() + "\n")
        checked_at = now_iso()
        doctor = {
            "host": "pi",
            "model": ", ".join(models),
            "base_url": gateway,
            "ready": True,
            "skill_privacy_block": None,
        }
        receipt = write_receipt(
            directory,
            doctor,
            checked_at,
            {"status": "host", "session_source": "pi", "checked_at": checked_at},
        )
        return {
            "directory": str(directory),
            "files": {role: str(directory / ROLES[role]) for role in files},
            "receipt_path": str(directory / RECEIPT_NAME),
            "receipt_id": receipt["receipt_id"],
        }


# The deep analysis, as pure rules over the review state the host sends (pipeline.py). A doc_id
# in the request is replaced by the open document.
PIPELINE = {
    name: getattr(pipeline, name)
    for name in (
        "orient_task",
        "orient_answer",
        "all_parts",
        "register",
        "read_task",
        "read_answer",
        "check_task",
        "check_answer",
        "attach_checks",
        "merge_number_findings",
        "sweep_task",
        "sweep_answer",
        "unswept",
        "to_confirm",
        "confirm_task",
        "confirm_answer",
        "apply_confirmations",
        "screen_acknowledged",
        "screen_task",
        "screen_answer",
        "apply_screening",
    )
}

METHODS = {
    "reading_plan",
    "flaws",
    "false_alarms",
    "preflight",
    "knowledge",
    "open",
    "plan",
    "check_quotes",
    "number_checks",
    "severity",
    "merge_number_checks",
    "order",
    "lookup_url",
    "lookup",
    "export",
}


def handle(sidecar: Sidecar, line: str) -> dict[str, Any]:
    request_id: Any = None
    try:
        request = json.loads(line)
        request_id = request.get("id")
        method = request.get("method")
        if method not in METHODS and method not in PIPELINE:
            raise ReviewError(f"unknown method {method!r}")
        params = request.get("params") or {}
        if not isinstance(params, dict):
            raise ReviewError("params must be an object")
        if method in PIPELINE:
            if "doc_id" in params:
                document = sidecar._document(params.pop("doc_id"))
                params = {**params, "document": document}
            return {"id": request_id, "result": PIPELINE[method](**params)}
        if method in {"merge_number_checks", "order"} and "findings" in params:
            params = {"findings_": params.pop("findings"), **params}
        return {"id": request_id, "result": getattr(sidecar, method)(**params)}
    except ReviewError as exc:
        return {"id": request_id, "error": str(exc)}
    except (json.JSONDecodeError, TypeError) as exc:
        return {"id": request_id, "error": f"bad request: {exc}"}


def main() -> int:
    sidecar = Sidecar()
    for line in sys.stdin:
        if not line.strip():
            continue
        sys.stdout.write(json.dumps(handle(sidecar, line), ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
