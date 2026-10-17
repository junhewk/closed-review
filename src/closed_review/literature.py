"""Citations in a candidate's text, labelled by creview rather than by the model.

A cited work the manuscript itself cites (in its reference list, a footnote, or the text) is
`manuscript_reported`; any other is `model_lead`, an unverified recollection. A work is found by
author and year, or, for works in the manuscript's reference list, by the author's surname alone,
since model-written text often drops the year. The label is about the work only: a sentence that
says what a work argues, requires, or recommends is a content claim, and it stays `model_lead`
whatever the work's label, because creview cannot check it. creview also builds the exact lookup
query for each work from bibliographic data, so offering a lookup does not depend on the model
remembering to, and the query never carries the candidate's or the manuscript's prose.
"""

from __future__ import annotations

import re
from typing import Any

from .references import DOI, SURNAME, YEAR, _partition_segments, _reference_entries

CITATION = re.compile(
    rf"\b({SURNAME})(?:\s+et\s+al\.?|\s+(?:and|&)\s+{SURNAME})?,?\s*\(?((?:19|20)\d{{2}})[a-z]?\b"
)
# Capitalised words that precede a year without being an author.
_NOT_AUTHOR_TEXT = """
act acts article articles appendix box chapter chapters figure fig in item line note
paragraph para part parts phase regulation regulations rule rules schedule section sections
see since stage step table until version vol volume wave from by before after during between
january february march april may june july august september october november december
spring summer autumn fall winter the this our its their of and or to for
"""
NOT_AUTHORS = frozenset(_NOT_AUTHOR_TEXT.split())
MAX_LOOKUPS = 3
ATTRIBUTION = re.compile(
    r"\b(?:argu|recommend|requir|expect|warn|hold|holds|state|show|find|found|propos|say|says|"
    r"claim|note|suggest|insist|caution|treat|regard|consider|define|endorse|reject|call)\w*\b",
    re.I,
)


def cited_works(text: str) -> list[tuple[str, str]]:
    """(surname, year) pairs that look like citations in free text, in order of appearance."""
    found: dict[tuple[str, str], None] = {}
    for match in CITATION.finditer(text):
        surname, year = match.group(1), match.group(2)
        if surname.casefold() not in NOT_AUTHORS and not re.fullmatch(r"[IVXLC]+", surname):
            found[(surname, year)] = None
    return list(found)


def _in_manuscript(surname: str, year: str, blocks: list[dict[str, Any]]) -> bool:
    lowered = surname.casefold()
    return any(lowered in b["text"].casefold() and year in b["text"] for b in blocks)


def _content_claim(surname: str, text: str) -> str | None:
    """The first sentence that names the work and says what it argues or requires."""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if re.search(rf"\b{re.escape(surname)}\b", sentence) and ATTRIBUTION.search(sentence):
            return " ".join(sentence.split())[:300]
    return None


def _entries(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reference entries with a first author and year. When the full parser does not recognise
    the style ("Strech D, Sofaer N. 2012. Title"), each reference block is read as one entry."""
    _, reference_blocks, _ = _partition_segments(blocks)
    if not reference_blocks:
        return []
    entries = [e for e in _reference_entries(reference_blocks)[0] if e.get("author")]
    if entries:
        return entries
    simple = []
    for block in reference_blocks:
        text = " ".join(block["text"].split())
        author, year = re.match(SURNAME, text), YEAR.search(text)
        if author and year:
            simple.append({"author": author.group(0), "year": year.group(0), "text": text})
    return simple


def label_citations(texts: list[str], blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Label every citation in `texts` against the manuscript's blocks and reference list."""
    entries = _entries(blocks)
    joined = " ".join(texts)
    works = cited_works(joined)
    # Reference-list authors named without a year ("the Strech and Sofaer model"), when the
    # manuscript itself cites them with a year, so a surname that is also a word ("Bill",
    # "Green") is not read as a citation.
    cited_in_body = {surname for surname, _ in cited_works(" ".join(b["text"] for b in blocks))}
    for entry in entries:
        author, year = entry.get("author"), entry.get("year")
        if not author or not year or " " in author or author not in cited_in_body:
            continue
        surname = author
        if len(surname) < 3 or any(s == surname and y[:4] == year[:4] for s, y in works):
            continue
        if re.search(rf"(?<![\w-]){re.escape(surname)}(?![\w-])", joined):
            works.append((surname, year[:4]))
    labelled = []
    for surname, year in works:
        entry = next(
            (
                e
                for e in entries
                if year in e["text"] and surname.casefold() in e["text"].casefold()
            ),
            None,
        )
        reported = entry is not None or _in_manuscript(surname, year, blocks)
        doi = DOI.search(entry["text"]) if entry else None
        labelled.append(
            {
                "citation": f"{surname} {year}",
                "label": "manuscript_reported" if reported else "model_lead",
                "reference": " ".join(entry["text"].split())[:300] if entry else None,
                "doi": doi.group(0).rstrip(".").lower() if doi else None,
                "content_claim": _content_claim(surname, joined),
            }
        )
    return labelled


def lookup_query(item: dict[str, Any]) -> str:
    """Bibliographic terms only: the DOI, else the reference entry, else surname and year."""
    return item["doi"] or item["reference"] or item["citation"]


def lookup_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unverified recollections first: they are what a lookup most often settles."""
    ordered = sorted(items, key=lambda item: item["label"] != "model_lead")
    return ordered[:MAX_LOOKUPS]
