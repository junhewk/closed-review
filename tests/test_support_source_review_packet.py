"""Source-only packets never import model findings/keys or manufacture source approval."""

import importlib.util
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, read_json, sha256_file
from closed_review.support import PROTOCOL
from closed_review.support.sources import snapshot

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "source_review_packet", ROOT / "scripts/prepare-support-source-review.py",
)
packet = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(packet)


class TableReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.table, self.row, self.cell = [], None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table = []
        elif tag == "tr":
            self.row = []
        elif tag in {"td", "th"}:
            self.cell = ""

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag in {"td", "th"}:
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr":
            self.table.append(self.row)
        elif tag == "table":
            self.tables.append(self.table)
            self.table = None


def small_corpus(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    paper = corpus / "a01.md"
    paper.write_text(
        "# Invented source\n\n<script>alert('not executable')</script>\n\n"
        "| Count | P |\n|---|---|\n| 20 / 100 | p<0.05 |\n",
    )
    manifest = tmp_path / "manifest.json"
    atomic_write_json(manifest, {
        "protocol": PROTOCOL, "corpus_id": "source-only-unit-fixture",
        "synthetic_only": True, "independently_reviewed": False,
        "cases": [{
            "case_id": "a01", "module": "statistics", "file": "a01.md",
            "sha256": sha256_file(paper),
        }],
    })
    return manifest, corpus


def test_all_twelve_real_candidates_are_readable_original_and_explicitly_unreviewed(tmp_path):
    base = ROOT / "evals/support-ordinary-candidates"
    manifest = base / "manifest.json"
    before = sha256_file(manifest)
    output = tmp_path / "source-review"
    report = packet.prepare(manifest, base / "manuscripts", output)
    assert report["sources"] == 12 and report["human_decisions"] == "all_blank"
    assert report["keys_imported"] is False and report["author_proposals_read"] is False
    assert report["model_findings_included"] is False and report["server_started"] is False
    assert report["qualification"] == "not_qualified"
    assert sha256_file(manifest) == before == sha256_file(output / "input-manifest.json")
    template = read_json(output / "source-review-template.json")
    assert template["independently_reviewed"] is False
    assert all(template[k] is None for k in (
        "reviewer", "reviewed_at", "relevant_expertise", "representative_for_intended_deployment",
    ))
    for row in template["sources"]:
        assert row["decision"] is None and row["reasons"] == ""
        assert sha256_file(output / "manuscripts" / f"{row['case_id']}.md") == row["source_sha256"]
        assert not ({"control", "expected_issue_ids", "valid"} & row.keys())
    text = (output / "source-review-ko.html").read_text()
    anchors = re.findall(r'\bid="([^"]+)"', text)
    assert len(anchors) == len(set(anchors))
    assert text.count("<table>") == 36 and "원고는 영어 원문" in text
    reader = TableReader()
    reader.feed(text)
    expected_grids = []
    for row in read_json(manifest)["cases"]:
        for table in snapshot(base / "manuscripts" / row["file"])["tables"]:
            expected_grids.append([
                [cell["text"] for cell in table["cells"] if cell["row"] == number]
                for number in range(1, table["rows"] + 1)
            ])
    assert reader.tables == expected_grids
    assert "default-src 'none'" in text
    assert not any(tag in text for tag in ("<script", "<form", "<iframe", "<img", "<input"))
    assert output.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in output.rglob("*") if p.is_file())


def test_renderer_escapes_source_and_never_reads_unlisted_private_keys(tmp_path, monkeypatch):
    manifest, corpus = small_corpus(tmp_path)
    secret = tmp_path / "private-author-proposals.json"
    secret.write_text("PRIVATE_UNAPPROVED_KEY_NOT_TO_READ")
    original_read = Path.read_bytes

    def guarded_read(path):
        assert path != secret, "private proposals must not be read by packet generation"
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    output = tmp_path / "packet"
    packet.prepare(manifest, corpus, output)
    text = (output / "source-review-ko.html").read_text()
    assert "<script>" not in text and "&lt;script&gt;" in text
    assert "20 / 100" in text and "p&lt;0.05" in text
    assert "PRIVATE_UNAPPROVED_KEY_NOT_TO_READ" not in text


@pytest.mark.parametrize("separator", ["|---|---|", "| --- | --- |", "| :--- | ---: |"])
def test_reused_renderer_treats_only_the_header_separator_as_structure(
    tmp_path, separator,
):
    manifest, corpus = small_corpus(tmp_path)
    paper = corpus / "a01.md"
    paper.write_text(f"# Source\n\n| Count | P |\n{separator}\n| 20 / 100 | p<0.05 |\n")
    value = read_json(manifest)
    value["cases"][0]["sha256"] = sha256_file(paper)
    atomic_write_json(manifest, value)
    output = tmp_path / "packet"
    packet.prepare(manifest, corpus, output)
    reader = TableReader()
    reader.feed((output / "source-review-ko.html").read_text())
    assert reader.tables == [[["Count", "P"], ["20 / 100", "p<0.05"]]]


def test_existing_reviewer_work_is_not_overwritten(tmp_path):
    manifest, corpus = small_corpus(tmp_path)
    output = tmp_path / "packet"
    packet.prepare(manifest, corpus, output)
    template = output / "source-review-template.json"
    template.write_text("human review in progress")
    with pytest.raises(ReviewError, match="never overwrite"):
        packet.prepare(manifest, corpus, output)
    assert template.read_text() == "human review in progress"


@pytest.mark.parametrize("change", ["approved", "changed-source", "keys-in-manifest", "hermes"])
def test_packet_refuses_inappropriate_inputs_before_creating_output(tmp_path, monkeypatch, change):
    manifest, corpus = small_corpus(tmp_path)
    value = read_json(manifest)
    if change == "approved":
        value["independently_reviewed"] = True
        atomic_write_json(manifest, value)
    elif change == "changed-source":
        (corpus / "a01.md").write_text("a different manuscript")
    elif change == "keys-in-manifest":
        value["expected_issue_ids"] = ["private"]
        atomic_write_json(manifest, value)
    else:
        monkeypatch.setenv("HERMES_SESSION_ID", "inference-host-session")
    output = tmp_path / "packet"
    with pytest.raises(ReviewError):
        packet.prepare(manifest, corpus, output)
    assert not output.exists()
