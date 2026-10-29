"""Logical segments: the manuscript's sections, drafted from its headings for the deep scan.

The parsers split a document into blocks (paragraphs, table rows, PDF text blocks; stored as
`segments` with `seg-NNNNN` ids). A logical segment is the run of blocks under one heading; the
scan's orientation then groups the segments into reading units and parts.
"""

from __future__ import annotations

import re
from typing import Any

# Any short slug: ids name task and proposal files, so no path separators or dots.
MIN_DRAFT_CHARS = 1_500
LARGE_SEGMENT_CHARS = 24_000

SECTION_NAMES = (
    "abstract",
    "introduction",
    "background",
    "literature review",
    "related work",
    "theoretical framework",
    "conceptual framework",
    "methods",
    "method",
    "methodology",
    "materials and methods",
    "study design",
    "participants",
    "data collection",
    "data analysis",
    "analysis",
    "results",
    "findings",
    "discussion",
    "argument",
    "objections",
    "limitations",
    "strengths and limitations",
    "implications",
    "recommendations",
    "conclusion",
    "conclusions",
    "main text",
    "ethics",
    "ethical approval",
    "ethics statement",
    "funding",
    "acknowledgements",
    "acknowledgments",
    "declarations",
    "conflict of interest",
    "conflicts of interest",
    "competing interests",
    "data availability",
    "author contributions",
    "references",
    "bibliography",
    "appendix",
    "supplementary material",
)
NUMBERED_HEADING = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[IVX]{1,6}\.)\s+\S.{0,100}$")


def _bare(text: str) -> str:
    return re.sub(r"^(?:\d+(?:\.\d+)*\.?|[IVX]{1,6}\.)\s+", "", text).rstrip(":").strip()


def _named_section(text: str) -> str | None:
    """A standard section name, alone or fused onto the start of a paragraph ("Background How")."""
    if _bare(text).lower() in SECTION_NAMES:
        return text
    if not text[:1].isupper():
        return None
    for name in sorted(SECTION_NAMES, key=len, reverse=True):
        match = re.match(rf"^{re.escape(name)}\s+(\S)", text, re.IGNORECASE)
        # The next word starts a sentence or a numbered entry ("References 1. Smith").
        if match and (match.group(1)[:1].isupper() or match.group(1)[:1] in "0123456789["):
            return text[: len(name)]
    return None


def _running_text(blocks: list[dict[str, Any]]) -> set[str]:
    """Text repeated on three or more pages: running heads and page numbers, never headings."""
    pages: dict[str, set[str]] = {}
    for block in blocks:
        page = block["locator"].split("/")[0]
        key = re.sub(r"\d+", "#", " ".join(block["text"].split()).lower())
        pages.setdefault(key, set()).add(page)
    return {key for key, found in pages.items() if len(found) >= 3}


def _is_short_title(text: str) -> bool:
    """A short capitalized line without final punctuation: not a caption, footnote, or citation."""
    if len(text) > 100 or not text[:1].isupper():
        return False
    if text.endswith((".", ",", ";", ":", "?", "!")):
        return False
    if re.match(r"^(?:fig\.?|figure|table|box)\s*\d", text, re.IGNORECASE):
        return False
    if re.match(r"^[^:]{1,25}:\s+\S", text):
        return False  # a labelled line such as "Keywords: ..." or "Correspondence: ..."
    if NUMBERED_HEADING.match(text):
        return len(_bare(text).split()) <= 8
    if re.match(r"^\d+\s", text):
        return False  # a footnote
    return len(text.split()) <= 12 and not re.search(r"\b(?:19|20)\d\d\b", text)


def _headings(blocks: list[dict[str, Any]]) -> dict[str, str]:
    """Map block id to the heading it starts.

    Styled headings (DOCX heading styles, Markdown #) are used as they are. Without them, as in
    PDFs, a heading is a standard section name (alone or fused onto a paragraph), or, once the body
    has started and outside the reference list, a short title line that is not a running head.
    """
    found: dict[str, str] = {}
    if any(block.get("kind") == "heading" for block in blocks):
        for block in blocks:
            text = " ".join(block["text"].split())
            named = len(text) <= 120 and _bare(text).lower() in SECTION_NAMES
            if block.get("kind") == "heading" or named:
                found[block["segment_id"]] = text[:160]
        return found
    running = _running_text(blocks)
    started = in_references = False
    for block in blocks:
        text = " ".join(block["text"].split())
        key = re.sub(r"\d+", "#", text.lower())
        if key in running or re.match(r"^page # of #$", key):
            continue
        named = _named_section(text)
        if named:
            started = True
            in_references = _bare(named).lower() in {"references", "bibliography"}
            found[block["segment_id"]] = named[:160]
        elif started and not in_references and _is_short_title(text):
            found[block["segment_id"]] = text[:160]
    return found


def _length(blocks: list[dict[str, Any]]) -> int:
    return sum(len(block["text"]) for block in blocks)


def draft_plan(sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Draft logical segments for parsed sources ({source_id, segments}) from their headings."""
    segments: list[dict[str, Any]] = []
    for source in sources:
        parts: list[tuple[str, list[dict[str, Any]]]] = []
        title = "Opening" if source["source_id"] == "manuscript" else source["source_id"]
        current: list[dict[str, Any]] = []
        headings = _headings(source["segments"])
        for block in source["segments"]:
            heading = headings.get(block["segment_id"])
            if heading and current:
                parts.append((title, current))
                current = []
            if heading:
                title = heading
            current.append(block)
        if current:
            parts.append((title, current))
        merged: list[tuple[str, list[dict[str, Any]]]] = []
        for title, blocks in parts:
            # Fold short numbered subsections ("2.1 Analysis") into the part before them. Other
            # sections stay separate however short: merging unrelated themes is worse, and the
            # scan's orientation joins short parts where they belong.
            subsection = bool(re.match(r"^\d+\.\d+", title))
            if (
                merged
                and subsection
                and _length(blocks) < MIN_DRAFT_CHARS
                and _length(merged[-1][1]) < LARGE_SEGMENT_CHARS
            ):
                merged[-1] = (merged[-1][0], merged[-1][1] + blocks)
            else:
                merged.append((title, blocks))
        for title, blocks in merged:
            segments.append(
                {
                    "id": f"ls-{len(segments) + 1:02d}",
                    "title": title,
                    "source_id": source["source_id"],
                    "block_ids": [block["segment_id"] for block in blocks],
                }
            )
    return {"schema_version": "1", "segments": segments}
