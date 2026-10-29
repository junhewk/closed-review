"""Review rules for the deep scan (pipeline.py), over plain data.

creview enforces what it can: quotes must be verbatim, arithmetic is computed rather than judged,
and severity follows the evidence:

- major, when a check confirmed a listed major flaw with verbatim quotes;
- major, when a computed mismatch is in a figure the manuscript reuses (it is load-bearing);
- otherwise the read's own rating, labelled as the model's judgement;
- the reviewer decides in the end.

There are no pass votes: the same model reading a segment again mostly restates itself.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .errors import ReviewError
from .evidence import LOAD_BEARING_BLOCKS
from .evidence import REFERENCE_HEADING as _REFERENCE_HEADING
from .evidence import check_quote as _check_quote
from .evidence import number_checks as _number_checks
from .evidence import same_check as _same_check
from .io import sha256_file
from .parsers import parse_document

# Minors shown before the rest wait in a reserve, as in the deep scan.
MAX_ACTIVE_MINORS = 9


def open_document(path: Path) -> dict[str, Any]:
    """Parse a manuscript into blocks with stable locators."""
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ReviewError(f"input is not a file: {resolved}")
    parsed = parse_document(resolved)
    return {
        "source_id": "manuscript",
        "path": str(resolved),
        "sha256": sha256_file(resolved),
        "format": parsed.format,
        "page_count": parsed.page_count,
        "warnings": parsed.warnings,
        "segments": parsed.segments,
    }


def _sources(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {document["source_id"]: document}


def check_quotes(document: dict[str, Any], quotes: list[Any]) -> dict[str, Any]:
    """Each {quote, locator?} must be verbatim in the manuscript; a missing or wrong locator is
    found from the quote. Returns the verified quotes and the problems, one per refused quote."""
    verified, problems = [], []
    for index, item in enumerate(quotes, start=1):
        if isinstance(item, str):
            item = {"quote": item}
        evidence, problem = _check_quote(f"quote {index}", item, _sources(document))
        if evidence:
            verified.append(evidence)
        else:
            problems.append(problem)
    return {"verified": verified, "problems": problems}


def number_checks(document: dict[str, Any], checks: list[Any]) -> dict[str, Any]:
    """Compute each {expression, stated, quote}: the figure the manuscript states, against what the
    arithmetic gives. A mismatch carries `recurs`: the stated figure appears in several places."""
    results, problems = _number_checks(checks, _sources(document))
    for result in results:
        stated = float(result["stated"])
        if not result["matches"] and _on_percent_scale(
            result["computed"], stated, result["stated"]
        ):
            # "101 / 412" against a stated 24.5 is the same figure as a percentage, not a mismatch.
            result["matches"] = True
            result["scale"] = "percent"
        result["identity"] = list(_same_check(result))
        result["recurs"] = (not result["matches"]) and recurring_figure(document, result["stated"])
    return {"checks": results, "problems": problems}


def _on_percent_scale(computed: float, stated: float, stated_text: str) -> bool:
    """Whether the stated figure is the computed fraction written as a percentage, to the precision
    the manuscript gives. Only that direction: a computed figure a hundred times the stated one is a
    real mismatch."""
    decimals = len(stated_text.split(".")[1]) if "." in stated_text else 0
    tolerance = 0.5 * 10**-decimals + 1e-9
    return abs(computed * 100 - stated) <= tolerance


def recurring_figure(document: dict[str, Any], stated: str) -> bool:
    """Whether a stated figure appears in at least LOAD_BEARING_BLOCKS blocks outside the
    references: totals and denominators built on it inherit a mismatch."""
    stated = stated.replace(",", "").strip().rstrip("%")
    whole = f"{float(stated):,.0f}" if float(stated).is_integer() else stated
    forms = {stated, whole, whole.replace(",", "")}
    pattern = re.compile(r"(?<![\w.,])(?:" + "|".join(map(re.escape, forms)) + r")(?![\w]|[.,]\d)")
    blocks = [
        b
        for b in document["segments"]
        if not _REFERENCE_HEADING.match(b["locator"]) and pattern.search(b["text"])
    ]
    return len(blocks) >= LOAD_BEARING_BLOCKS


SOURCE_MISREAD_FLAWS = frozenset({"general/misread-source", "legal-analysis/misread-provision"})


def confirmed_check(item: dict[str, Any]) -> bool:
    """Whether a check has the evidence needed for a confirmed-flaw rating.

    A source-misreading check also needs the source's words as quoted in the manuscript. This
    does not independently establish that the quotation accurately represents the source.
    """
    source = item.get("source_quote")
    source_quoted = isinstance(source, dict) and bool(source.get("quote") and source.get("locator"))
    return bool(
        item.get("shown")
        and item.get("quotes_verified")
        and (item.get("flaw") not in SOURCE_MISREAD_FLAWS or source_quoted)
    )


def severity(finding: dict[str, Any]) -> dict[str, Any]:
    """The severity creview sets from a finding's evidence, with its basis.

    A finding is {model_severity, flaw_checks: [{flaw, model, shown, quotes_verified}],
    number_check?: {matches, recurs, stated}}."""
    check = finding.get("number_check")
    if check:
        if not check.get("matches") and check.get("recurs"):
            return {
                "severity": "major",
                "basis": "evidence",
                "reasons": [f"mismatched figure {check['stated']} recurs across the manuscript"],
            }
        return {"severity": "minor", "basis": "evidence", "reasons": ["computed mismatch"]}
    confirmed: dict[str, set[str]] = {}
    for item in finding.get("flaw_checks") or []:
        if confirmed_check(item):
            confirmed.setdefault(str(item["flaw"]), set()).add(str(item.get("model") or ""))
    if confirmed:
        return {
            "severity": "major",
            "basis": "evidence",
            "reasons": [
                f"listed major flaw {flaw}, confirmed by {', '.join(sorted(models))}"
                for flaw, models in sorted(confirmed.items())
            ],
        }
    if finding.get("model_severity") == "major":
        return {"severity": "major", "basis": "judgement", "reasons": ["rated major by the read"]}
    return {"severity": "minor", "basis": "judgement", "reasons": []}


def merge_number_checks(findings: list[dict[str, Any]]) -> list[list[str]]:
    """Groups of finding ids holding the same number-check mismatch (the stated figure and what
    it computes to), however each expression was written. Each group is shown as one finding."""
    groups: dict[tuple[float, float], list[str]] = {}
    for finding in findings:
        check = finding.get("number_check")
        if check:
            groups.setdefault(_same_check(check), []).append(str(finding["id"]))
    return [ids for ids in groups.values() if len(ids) > 1]


def _verifiable(finding: dict[str, Any]) -> bool:
    """Shown by the manuscript itself: a computed mismatch, or an inconsistency quoting two
    places."""
    if finding.get("number_check"):
        return True
    return (
        finding.get("type") == "inconsistency"
        and len({q.get("locator") for q in finding.get("evidence") or []}) >= 2
    )


def order(findings: list[dict[str, Any]], segment_order: list[str]) -> dict[str, Any]:
    """The order findings are shown in: majors on evidence, then majors on judgement, each in plan
    order; then minors, verifiable ones first. Minors past MAX_ACTIVE_MINORS wait in a reserve
    (verifiable ones never do)."""
    position = {segment: n for n, segment in enumerate(segment_order)}

    def where(finding: dict[str, Any]) -> int:
        return position.get(str(finding.get("segment_id")), len(position))

    rated = [(finding, severity(finding)) for finding in findings]
    majors = sorted(
        (pair for pair in rated if pair[1]["severity"] == "major"),
        key=lambda pair: (pair[1]["basis"] != "evidence", where(pair[0])),
    )
    minors = sorted(
        (pair for pair in rated if pair[1]["severity"] == "minor"),
        key=lambda pair: (not _verifiable(pair[0]), where(pair[0])),
    )
    shown_minors = [p for p in minors if _verifiable(p[0])]
    rest = [p for p in minors if not _verifiable(p[0])]
    room = max(0, MAX_ACTIVE_MINORS - len(shown_minors))
    shown_minors += rest[:room]
    reserve = rest[room:]
    entry = lambda pair: {"id": pair[0]["id"], **pair[1]}  # noqa: E731
    return {
        "order": [entry(p) for p in majors + shown_minors],
        "reserve": [entry(p) for p in reserve],
    }
