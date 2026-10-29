"""Offline fixtures for public-paper conversion; no network or medical judgments."""

import importlib.util
from pathlib import Path

import pytest

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, read_json
from closed_review.support.evaluation import load_manifest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prepare-support-public-corpus.py"
SPEC = importlib.util.spec_from_file_location("public_corpus", SCRIPT)
public = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(public)


def fixture(tmp_path):
    row = {
        "case_id": "public-test",
        "module": "statistics",
        "pmcid": "PMC123",
        "doi": "10.0000/test",
        "title": "Simulated XML conversion fixture, not a real article",
        "url": "https://example.org/article",
    }
    xml = tmp_path / "statistics.xml"
    xml.write_text(
        '<article><front><article-meta><article-id pub-id-type="pmcid">PMC123</article-id>'
        '<article-id pub-id-type="doi">10.0000/test</article-id><title-group><article-title>'
        + row["title"]
        + "</article-title></title-group><contrib-group><contrib><name>"
        "<surname>Example</surname><given-names>Anne</given-names></name></contrib></contrib-group>"
        "<permissions><license><license-p>CC BY: https://creativecommons.org/licenses/by/4.0/"
        "</license-p></license></permissions><abstract><p>Original abstract.</p></abstract>"
        "</article-meta></front><body><sec><title>Methods</title><p>We report 7 of 20 (35%).</p>"
        "<table-wrap><label>Table 1</label><caption><p>Groups</p></caption><table><thead>"
        '<tr><th rowspan="2">Outcome</th><th colspan="2">Trial A</th></tr>'
        "<tr><th>Intervention</th><th>Control</th></tr></thead><tbody>"
        "<tr><td>Events</td><td>7 (35%)</td><td>4 (20%)</td></tr></tbody></table>"
        "<table-wrap-foot><p>Each group n=20.</p></table-wrap-foot></table-wrap>"
        "<fig><label>Figure 1</label><caption><p>Caption retained.</p></caption>"
        '<graphic href="not-fetched.png"/></fig><supplementary-material><p>Appendix S1.</p>'
        "</supplementary-material></sec></body><back><ref-list><title>References</title>"
        '<ref id="r1"><label>1</label><mixed-citation>Original reference 2024.</mixed-citation>'
        "</ref></ref-list></back><sub-article><body><p>EXCLUDED PUBLIC REVIEW REPORT</p>"
        "</body></sub-article></article>",
        encoding="utf-8",
    )
    selection = tmp_path / "selection.json"
    atomic_write_json(selection, [row])
    return row, xml, selection


def test_converter_keeps_all_headers_numbers_references_and_attribution(tmp_path):
    row, xml, _ = fixture(tmp_path)
    text, metadata = public.convert(xml, row)
    assert "Anne Example" in text and row["doi"] in text and row["url"] in text
    assert "Original abstract." in text and "Original reference 2024." in text
    assert "|  | Intervention | Control |" in text
    assert "| Events | 7 (35%) | 4 (20%) |" in text
    assert "source row 1, column 1: 2 row(s), 1 column(s)" in text
    assert "Each group n=20." in text
    assert "Caption retained." in text and "Appendix S1." in text
    assert "EXCLUDED PUBLIC REVIEW REPORT" not in text
    assert metadata["source_tables"] == 1 and metadata["omitted_figure_graphics"] == 1
    assert metadata["semantic_fidelity"] == "not_assessed"
    assert metadata["independently_reviewed"] is False


@pytest.mark.parametrize("problem", ["doi", "pmcid", "title", "license", "math", "pipe", "span"])
def test_wrong_identity_or_unsupported_conversion_is_refused(tmp_path, problem):
    row, xml, _ = fixture(tmp_path)
    text = xml.read_text()
    if problem in {"doi", "pmcid", "title"}:
        row[problem] = "wrong"
    elif problem == "license":
        text = text.replace("licenses/by/", "licenses/by-nc-nd/")
    elif problem == "math":
        text = text.replace(
            "<body>", '<body><m:math xmlns:m="http://www.w3.org/1998/Math/MathML"/>', 1
        )
    elif problem == "pipe":
        text = text.replace("7 (35%)", "7 | 35%")
    else:
        text = text.replace('rowspan="2"', 'rowspan="100"')
    xml.write_text(text)
    with pytest.raises(ReviewError):
        public.convert(xml, row)


def test_public_manifest_needs_no_input_approval_and_never_invents_a_gold_role(tmp_path):
    _, _, selection = fixture(tmp_path)
    output = tmp_path / "corpus"
    result = public.prepare(selection, tmp_path, output)
    manifest, cases = load_manifest(output / "manifest.json", output)
    assert result == manifest and manifest["synthetic_only"] is False
    assert manifest["independently_reviewed"] is False and len(cases) == 1
    assert set(cases[0]) == {"case_id", "module", "file", "sha256", "path"}
    provenance = read_json(output / "article-provenance.json")
    assert provenance["qualification"] == "not_qualified"
    assert provenance["seeded_recall"] == "not_applicable_no_known_issue_keys"
    with pytest.raises(ReviewError, match="NEW corpus"):
        public.prepare(selection, tmp_path, output)


@pytest.mark.parametrize("problem", ["escape", "duplicate", "unknown-module", "symlink"])
def test_bad_selection_is_rejected_before_creating_a_corpus(tmp_path, problem):
    row, xml, selection = fixture(tmp_path)
    chosen = [row]
    if problem == "escape":
        row["case_id"] = "../escape"
    elif problem == "duplicate":
        chosen.append(row)
    elif problem == "unknown-module":
        row["module"] = "../statistics"
    else:
        original = tmp_path / "original.xml"
        xml.rename(original)
        xml.symlink_to(original)
    atomic_write_json(selection, chosen)
    output = tmp_path / "corpus"
    with pytest.raises(ReviewError):
        public.prepare(selection, tmp_path, output)
    assert not output.exists()
