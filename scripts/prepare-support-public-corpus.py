"""Prepare attributed public-article text fixtures from already downloaded Europe PMC JATS.

No inference, invented issues or approval decisions. The fixed selection is evaluator-only;
only manuscripts and the key-free manifest belong on the model host. This deliberately
does not download graphics, supplements, raw data, cited papers or peer-review subarticles.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from closed_review.errors import ReviewError
from closed_review.io import (
    atomic_write_json,
    atomic_write_text,
    ensure_private_dir,
    read_json,
    sha256_file,
)
from closed_review.support import PROTOCOL
from closed_review.support.evaluation import SAFE_ID, load_manifest
from closed_review.support.methods import MODULES


def plain(node) -> str:
    return " ".join("".join(node.itertext()).split()) if node is not None else ""


def table_text(node) -> str:
    """Preserve all header rows and cells, explicitly describing merged-cell geometry.

    Covered positions are empty, not new data or repeated values. No clinical interpretation
    or derived number is inserted. Row/column coordinates below are conversion metadata.
    """
    table = node.find("table")
    if table is None or table.findall(".//table"):
        raise ReviewError("missing/nested JATS table; choose another fixture or conversion")
    rows = table.findall(".//tr")
    if not rows or len(rows) > 1000:
        raise ReviewError("empty/oversized JATS table")
    grid, occupied, spans = [], set(), []
    for ri, row in enumerate(rows):
        cells, ci = {}, 0
        for cell in row:
            if cell.tag not in {"td", "th"}:
                continue
            while (ri, ci) in occupied:
                ci += 1
            rs, cs = int(cell.get("rowspan", "1")), int(cell.get("colspan", "1"))
            if not 1 <= rs <= len(rows) - ri or not 1 <= cs <= 100:
                raise ReviewError("invalid JATS table span")
            positions = {(r, c) for r in range(ri, ri + rs) for c in range(ci, ci + cs)}
            if positions & occupied:
                raise ReviewError("overlapping JATS table spans")
            text = plain(cell)
            if "|" in text:
                raise ReviewError("literal pipe in JATS cell needs another conversion")
            cells[ci] = text
            occupied.update(positions)
            if rs > 1 or cs > 1:
                spans.append(f"source row {ri + 1}, column {ci + 1}: {rs} row(s), {cs} column(s)")
            ci += cs
        grid.append(cells)
    width = max(c for _, c in occupied) + 1 if occupied else 0
    if not width:
        raise ReviewError("JATS table has no cells")
    caption = " ".join(filter(None, [plain(node.find("label")), plain(node.find("caption"))]))
    lines = [f"### {caption}", "", "Conversion layout: all source header rows are retained below."]
    if spans:
        lines += ["Merged source cells (coordinates are metadata; covered positions are blank):"]
        lines += ["- " + span for span in spans]
    lines += ["", "| " + " | ".join(f"Column {i + 1}" for i in range(width)) + " |"]
    lines += ["| " + " | ".join("---" for _ in range(width)) + " |"]
    lines += ["| " + " | ".join(row.get(i, "") for i in range(width)) + " |" for row in grid]
    foot = node.find("table-wrap-foot")
    if foot is not None:
        lines += ["", plain(foot)]
    return "\n".join(lines)


def render(node, depth=1) -> str:
    if node.tag == "table-wrap":
        return table_text(node)
    if node.tag in {"supplementary-material", "media"}:
        return plain(node) + "\n\n[Linked file not fetched or included in this text fixture.]"
    if node.tag in {"graphic", "inline-graphic"}:
        return "[Linked non-text material not included in this text fixture.]"
    if node.tag == "fig":
        return "\n\n".join(
            filter(
                None,
                [
                    plain(node.find("label")),
                    plain(node.find("caption")),
                    "[Figure graphic not included; caption only. Do not infer its plotted values.]",
                ],
            )
        )
    if node.tag == "title":
        return "#" * min(depth, 6) + " " + plain(node)
    if node.tag in {"p", "ref", "disp-quote", "fn", "statement"}:
        return plain(node)
    if node.tag == "list":
        return "\n".join("- " + plain(item) for item in node.findall("list-item"))
    if node.tag in {"disp-formula", "inline-formula"}:
        raise ReviewError("math requires another fixture/conversion, not flattened formulae")
    parts = [node.text.strip()] if node.text and node.text.strip() else []
    for child in node:
        parts.append(render(child, depth + (node.tag == "sec")))
        if child.tail and child.tail.strip():
            parts.append(child.tail.strip())
    return "\n\n".join(filter(None, parts))


def convert(xml: Path, article: dict) -> tuple[str, dict]:
    if xml.is_symlink() or not xml.is_file() or xml.stat().st_size > 25_000_000:
        raise ReviewError("use a regular, bounded original JATS file")
    root = ElementTree.parse(xml).getroot()
    front, body = root.find("front/article-meta"), root.find("body")
    if root.tag != "article" or front is None or body is None:
        raise ReviewError("expected one main JATS article")
    identifiers = {n.get("pub-id-type"): plain(n) for n in front.findall("article-id")}
    if identifiers.get("doi") != article["doi"] or article["pmcid"] not in {
        identifiers.get("pmcid"),
        "PMC" + identifiers.get("pmc", ""),
    }:
        raise ReviewError("article identifiers differ from the fixed selection")
    title = plain(front.find("title-group/article-title"))
    if title != article["title"]:
        raise ReviewError("article title differs from the fixed selection")
    licenses = front.findall("permissions/license")
    license_text = "\n\n".join(plain(n) for n in licenses)
    license_markup = " ".join(ElementTree.tostring(n, encoding="unicode") for n in licenses)
    if not re.search(r"creativecommons\.org/licenses/by/(?:4\.0|3\.0|2\.0)/", license_markup):
        raise ReviewError("fixture needs explicit CC BY licensing; free to read is not enough")
    if root.findall(".//{http://www.w3.org/1998/Math/MathML}math"):
        raise ReviewError("MathML is outside this converter's scope")
    authors = [
        " ".join(filter(None, [plain(n.find("given-names")), plain(n.find("surname"))]))
        for n in front.findall("contrib-group/contrib/name")
    ]
    sections = [
        f"# {title}",
        "Authors: " + "; ".join(authors),
        f"Original publication: {article['url']}\nDOI: {article['doi']}\nPMCID: {article['pmcid']}",
        "## Text-fixture provenance and limits",
        "Real published article, not synthetic and not a known-error or clean control. "
        "Converted from Europe PMC JATS: whitespace normalized; inline styling flattened; "
        "all source table header rows/cells retained with merged-cell coordinates. "
        "Graphics are omitted (captions retained); linked supplements, raw data and "
        "cited full texts have not been fetched. Peer-review subarticles bundled in "
        "the original XML are excluded from this fixture. "
        "This is a derived text fixture, not native-PDF/layout qualification.",
        "## Original license",
        license_text,
        "## Abstract",
    ]
    sections += [render(n) for n in front.findall("abstract")]
    sections += [render(body)]
    back = root.find("back")
    if back is not None:
        sections.append(render(back))
    text = "\n\n".join(filter(None, sections)) + "\n"
    normalized = " ".join(text.split())
    # These are literal text-retention checks, not semantic or layout certification.
    nodes = body.findall(".//p") + body.findall(".//td") + body.findall(".//th")
    if back is not None:
        nodes += back.findall(".//ref")
    missing = [plain(n) for n in nodes if plain(n) and plain(n) not in normalized]
    if missing:
        raise ReviewError(
            f"conversion omitted/changed {len(missing)} paragraph/cell/reference texts"
        )
    return text, {
        **article,
        "xml_sha256": sha256_file(xml),
        "license_text": license_text,
        "literal_text_nodes_checked": len(nodes),
        "source_tables": len(body.findall(".//table-wrap")),
        "omitted_figure_graphics": len(body.findall(".//fig")),
        "conversion": "jats-text-and-all-header-rows-v1",
        "semantic_fidelity": "not_assessed",
        "independently_reviewed": False,
    }


def prepare(selection: Path, xml_dir: Path, output: Path) -> dict:
    if output.exists():
        raise ReviewError("choose a NEW corpus directory; existing inputs are never overwritten")
    chosen = read_json(selection)
    if not isinstance(chosen, list) or not chosen:
        raise ReviewError("selection must be a nonempty list")
    seen = set()
    for row in chosen:
        if (
            not isinstance(row, dict)
            or set(row) != {"case_id", "module", "pmcid", "doi", "url", "title"}
            or any(not isinstance(v, str) or not v for v in row.values())
            or not SAFE_ID.fullmatch(row["case_id"])
            or row["case_id"] in seen
            or row["module"] not in MODULES
            or not re.fullmatch(r"PMC[0-9]+", row["pmcid"])
            or not row["url"].startswith("https://")
        ):
            raise ReviewError("selection needs distinct safe IDs, known modules and attribution")
        seen.add(row["case_id"])
    converted = [(row, *convert(xml_dir / (row["module"] + ".xml"), row)) for row in chosen]
    ensure_private_dir(output)
    cases, provenance = [], []
    for row, text, meta in converted:
        paper = output / f"{row['case_id']}.md"
        atomic_write_text(paper, text)
        cases.append(
            {
                "case_id": row["case_id"],
                "module": row["module"],
                "file": paper.name,
                "sha256": sha256_file(paper),
            }
        )
        provenance.append({**meta, "manuscript_sha256": sha256_file(paper)})
    manifest = {
        "protocol": PROTOCOL,
        "corpus_id": "public-medical-articles-20261029",
        "synthetic_only": False,
        "independently_reviewed": False,
        "cases": cases,
    }
    atomic_write_json(output / "manifest.json", manifest)
    load_manifest(output / "manifest.json", output)
    atomic_write_json(
        output / "article-provenance.json",
        {
            "selection_sha256": sha256_file(selection),
            "manifest_sha256": sha256_file(output / "manifest.json"),
            "qualification": "not_qualified",
            "seeded_recall": "not_applicable_no_known_issue_keys",
            "articles": provenance,
        },
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--xml-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        value = prepare(args.selection, args.xml_dir, args.output)
    except (
        ReviewError,
        OSError,
        ValueError,
        KeyError,
        ElementTree.ParseError,
        DefusedXmlException,
    ) as exc:
        parser.exit(2, f"{exc}\n")
    print(f"Prepared {len(value['cases'])} real-article engineering inputs: {args.output}")


if __name__ == "__main__":
    main()
