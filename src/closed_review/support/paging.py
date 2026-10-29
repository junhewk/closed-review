"""Lossless record pages, including records larger than a local tool-output budget."""

from __future__ import annotations

import json
from typing import Any

from ..errors import ReviewError
from .budgets import READ_CHARS

NOTE = (
    "Provided context is not a certificate of semantic review. "
    "For fragments, join text in character-offset order and parse the resulting JSON record. "
    "Follow both next_offset and next_fragment_offset; null next_offset means finished."
)


def record_text(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"))


def payload_chars(payload: Any) -> int:
    """Match the CLI's pretty-printed JSON, not just the unescaped manuscript text."""
    return len(json.dumps(payload, ensure_ascii=False, indent=2))


def page_records(
    records: list[dict[str, Any]], offset: int = 0, fragment_offset: int = 0
) -> dict[str, Any]:
    if (
        type(offset) is not int
        or type(fragment_offset) is not int
        or not 0 <= offset <= len(records)
        or fragment_offset < 0
        or fragment_offset and offset == len(records)
    ):
        raise ReviewError("invalid record or fragment offset")
    result = {
        "items": [],
        "fragments": [],
        "total": len(records),
        "next_offset": offset if offset < len(records) else None,
        "next_fragment_offset": 0,
        "note": NOTE,
    }
    for index in range(offset, min(len(records), offset + 12)):
        item = records[index]
        result["items"].append(item)
        result["next_offset"] = index + 1 if index + 1 < len(records) else None
        if not fragment_offset and payload_chars(result) <= READ_CHARS:
            continue
        result["items"].pop()
        result["next_offset"] = index
        if result["items"]:
            break
        serialized = record_text(item)
        if fragment_offset >= len(serialized):
            raise ReviewError("fragment offset is outside the selected record")
        fragment = {
            "id": item["id"],
            "encoding": "json-text",
            "offset": fragment_offset,
            "total_characters": len(serialized),
            "text": "",
        }
        result["fragments"] = [fragment]
        low, high = fragment_offset + 1, len(serialized)
        best = fragment_offset
        while low <= high:
            end = (low + high) // 2
            fragment["text"] = serialized[fragment_offset:end]
            if payload_chars(result) <= READ_CHARS:
                best, low = end, end + 1
            else:
                high = end - 1
        if best == fragment_offset:
            raise ReviewError("record metadata exceeds the read budget")
        fragment["text"] = serialized[fragment_offset:best]
        if best < len(serialized):
            result["next_fragment_offset"] = best
        else:
            result["next_offset"] = index + 1 if index + 1 < len(records) else None
        # The next cursor can add a handful of digits after sizing the fragment.
        while payload_chars(result) > READ_CHARS:
            best -= 1
            fragment["text"] = serialized[fragment_offset:best]
            result["next_offset"] = index
            result["next_fragment_offset"] = best
        break
    return result


def unread_records(records: list[dict[str, Any]], reads: list[dict[str, Any]]) -> list[str]:
    """Account for full records or a contiguous union of supplied fragments, never meaning."""
    full = {identifier for entry in reads for identifier in entry["ids"]}
    missing = []
    for record in records:
        identifier = record["id"]
        if identifier in full:
            continue
        intervals = sorted(
            (fragment["offset"], fragment["end"])
            for entry in reads
            for fragment in entry.get("fragments", [])
            if fragment["id"] == identifier
        )
        end = 0
        for first, last in intervals:
            if first > end:
                break
            end = max(end, last)
        if end < len(record_text(record)):
            missing.append(identifier)
    return missing
