"""Logical segments: theme-level parts of a manuscript that every review mode works through.

The parsers split a document into blocks (paragraphs, table rows, PDF text blocks; stored as
`segments` with `seg-NNNNN` ids for compatibility). A logical segment groups blocks that share a
theme, such as the sampling description or the main argument. Segments may overlap and need not be
contiguous, but together they must cover every block of each planned source, so nothing in the
manuscript falls outside the review.

`creview` drafts a plan from headings; the agent refines it (merge, split, overlap, tag with the
confirmed design profiles' areas, set an effort tier); `creview` validates coverage before storing.
"""

from __future__ import annotations

import re
from typing import Any

from .errors import ReviewError

TIERS = ("light", "medium", "high")
TIER_PASSES = {"light": 1, "medium": 2, "high": 3}
# Any short slug: ids name task and proposal files, so no path separators or dots.
SEGMENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")
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
LIGHT_WORDS = (
    "abstract",
    "introduction",
    "background",
    "acknowledg",
    "funding",
    "declaration",
    "conflict",
    "competing",
    "contribution",
    "availability",
    "reference",
    "bibliograph",
    "conclusion",
)
HIGH_WORDS = (
    "method",
    "design",
    "participant",
    "sampl",
    "data collection",
    "analys",
    "result",
    "finding",
    "argument",
    "synthesis",
    "search",
    "eligibility",
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


def suggested_tier(title: str) -> str:
    lowered = title.lower()
    if any(word in lowered for word in HIGH_WORDS):
        return "high"
    if any(word in lowered for word in LIGHT_WORDS):
        return "light"
    return "medium"


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
            # sections stay separate however short: merging unrelated themes is worse than
            # leaving the agent to merge.
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
                    "theme": "",
                    "profile_areas": [],
                    "tier": suggested_tier(title),
                }
            )
    return {
        "schema_version": "1",
        "segments": segments,
        "instructions": (
            "Refine this draft: merge or split segments so each holds one theme, add overlapping "
            "segments where a theme spans parts (block_ids may repeat and need not be contiguous), "
            "write a short theme, tag profile_areas with the confirmed design profiles' monitoring "
            "areas, and set tier to light, medium, or high by how much scrutiny the part needs. "
            "Every block must stay in at least one segment."
        ),
    }


def validate_plan(plan: Any, sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Check a plan against parsed sources; every block of each planned source must be covered."""
    if not isinstance(plan, dict) or not isinstance(plan.get("segments"), list):
        raise ReviewError("segment plan must be an object with a segments list")
    by_source = {source["source_id"]: source for source in sources}
    known = {
        source_id: {block["segment_id"]: block for block in source["segments"]}
        for source_id, source in by_source.items()
    }
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(plan["segments"], start=1):
        if not isinstance(raw, dict):
            raise ReviewError(f"segment {index} must be an object")
        segment_id = str(raw.get("id") or "").strip()
        if not SEGMENT_ID_RE.fullmatch(segment_id) or segment_id in seen_ids:
            raise ReviewError(
                f"segment {index} needs a unique id of letters, digits, '-' or '_', like ls-01"
            )
        seen_ids.add(segment_id)
        title = str(raw.get("title") or "").strip()
        if not title:
            raise ReviewError(f"{segment_id} needs a title")
        source_id = str(raw.get("source_id") or "")
        if source_id not in known:
            raise ReviewError(f"{segment_id} names unknown source {source_id!r}")
        block_ids = raw.get("block_ids")
        if not isinstance(block_ids, list) or not block_ids:
            raise ReviewError(f"{segment_id} needs a non-empty block_ids list")
        unknown = [str(block) for block in block_ids if str(block) not in known[source_id]]
        if unknown:
            raise ReviewError(f"{segment_id} names unknown blocks: {', '.join(unknown[:5])}")
        tier = str(raw.get("tier") or "").strip().lower()
        if tier not in TIERS:
            raise ReviewError(f"{segment_id} tier must be one of {', '.join(TIERS)}")
        areas = raw.get("profile_areas") or []
        if not isinstance(areas, list):
            raise ReviewError(f"{segment_id} profile_areas must be a list")
        ordered = [b for b in known[source_id] if b in {str(item) for item in block_ids}]
        normalized.append(
            {
                "id": segment_id,
                "title": title[:200],
                "source_id": source_id,
                "block_ids": ordered,
                "locators": [known[source_id][block]["locator"] for block in ordered],
                "theme": str(raw.get("theme") or "").strip()[:500],
                "profile_areas": [str(area).strip() for area in areas if str(area).strip()],
                "tier": tier,
                "character_count": sum(len(known[source_id][block]["text"]) for block in ordered),
            }
        )
    if not normalized:
        raise ReviewError("segment plan has no segments")
    planned_sources = {segment["source_id"] for segment in normalized}
    if "manuscript" in by_source and "manuscript" not in planned_sources:
        raise ReviewError("segment plan must cover the manuscript")
    for source_id in sorted(planned_sources):
        covered = {
            block for s in normalized if s["source_id"] == source_id for block in s["block_ids"]
        }
        missing = [block for block in known[source_id] if block not in covered]
        if missing:
            raise ReviewError(
                f"segment plan leaves {len(missing)} block(s) of {source_id} uncovered, starting "
                f"at {known[source_id][missing[0]]['locator']}"
            )
    warnings = [
        f"{segment['id']} is long ({segment['character_count']} characters); consider splitting it"
        for segment in normalized
        if segment["character_count"] > LARGE_SEGMENT_CHARS
    ]
    return {"schema_version": "1", "segments": normalized, "warnings": warnings}


def outline(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """The plan without block lists: enough context for one segment's reviewer."""
    return [
        {key: segment[key] for key in ("id", "title", "source_id", "theme", "tier")}
        | {"first_locator": segment["locators"][0], "last_locator": segment["locators"][-1]}
        for segment in plan["segments"]
    ]


def segment_blocks(segment: dict[str, Any], source: dict[str, Any]) -> list[dict[str, Any]]:
    selected = set(segment["block_ids"])
    return [
        {key: block[key] for key in ("segment_id", "locator", "kind", "text")}
        for block in source["segments"]
        if block["segment_id"] in selected
    ]
