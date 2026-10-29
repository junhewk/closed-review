import runpy
from pathlib import Path

import pytest
from conftest import assert_mode

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, read_json, sha256_file


def test_offline_audit_saves_only_explicit_human_decisions(tmp_path, monkeypatch, capsys):
    script = runpy.run_path("scripts/audit-qualification.py")
    output, keys, manifest = tmp_path / "output", tmp_path / "keys", tmp_path / "manifest.json"
    atomic_write_json(manifest, {"cases": [{"id": "ms1"}]})
    atomic_write_json(
        output / "results.json",
        {
            "identity": {"manifest": sha256_file(manifest)},
            "runs": {"ms1-r1": {"case": "ms1", "passed": True}},
        },
    )
    atomic_write_json(keys / "ms1.json", {"planted": [{"id": "P1", "description": "fixture"}]})
    finding = {
        "id": "F1",
        "flaw_checks": [
            {"shown": True, "quotes_verified": True, "flaw": "general/self-contradiction"}
        ],
    }
    atomic_write_json(output / "ms1-r1/scan.json", {"review": {"findings": [finding]}})
    audit_path = output / "ms1-r1/audit.json"
    atomic_write_json(
        audit_path,
        {
            "reviewer": "",
            "findings": [
                {
                    "id": "F1",
                    "valid": None,
                    "matches": [],
                    "confirmed_supported": None,
                    "rationale": "",
                }
            ],
        },
    )
    answers = iter(["y", "P1", "y", "The specific claim and its evidence match the issue."])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    result = script["audit_run"](output, keys, manifest, "ms1-r1", "Human evaluator")
    assert result["decisions_saved"] == 1
    saved = read_json(audit_path)
    assert saved["reviewer"] == "Human evaluator"
    assert saved["findings"][0]["matches"] == ["P1"]
    assert saved["findings"][0]["confirmed_supported"] is True
    assert "shared quotes are not credit" in capsys.readouterr().out
    with pytest.raises(ReviewError, match="already belongs"):
        script["audit_run"](output, keys, manifest, "ms1-r1", "Another evaluator")


def test_image_only_pdf_fixture_exposes_extraction_limit(tmp_path):
    from closed_review.parsers import parse_document

    script = runpy.run_path("scripts/probe-hermes-recovery.py")
    paper = Path(tmp_path) / "image-only.pdf"
    script["write_image_only_pdf"](paper)
    warnings = parse_document(paper).warnings
    assert any("no extractable text" in warning for warning in warnings)
    assert any("embedded image" in warning for warning in warnings)


def test_empty_result_requires_explicit_reviewer_signoff(tmp_path, monkeypatch):
    script = runpy.run_path("scripts/audit-qualification.py")
    output, keys, manifest = tmp_path / "output", tmp_path / "keys", tmp_path / "manifest.json"
    atomic_write_json(manifest, {"cases": [{"id": "control", "control": True}]})
    atomic_write_json(
        output / "results.json",
        {
            "identity": {"manifest": sha256_file(manifest)},
            "runs": {"control-r1": {"case": "control", "passed": True}},
        },
    )
    atomic_write_json(output / "control-r1/scan.json", {"review": {"findings": []}})
    audit_path = output / "control-r1/audit.json"
    atomic_write_json(audit_path, {"reviewer": "", "findings": []})
    monkeypatch.setattr("builtins.input", lambda _: "n")
    script["audit_run"](output, keys, manifest, "control-r1", "Human evaluator")
    assert read_json(audit_path)["reviewer"] == ""
    monkeypatch.setattr("builtins.input", lambda _: "y")
    script["audit_run"](output, keys, manifest, "control-r1", "Human evaluator")
    assert read_json(audit_path)["reviewer"] == "Human evaluator"


def test_audit_all_walks_only_available_quality_runs_and_quit_stops(tmp_path, monkeypatch):
    script = runpy.run_path("scripts/audit-qualification.py")
    output, keys, manifest = tmp_path / "output", tmp_path / "keys", tmp_path / "manifest.json"
    atomic_write_json(
        manifest,
        {
            "cases": [{"id": "control", "control": True}, {"id": "long", "timing_only": True}],
            "repetitions": 3,
        },
    )
    atomic_write_json(
        output / "results.json",
        {
            "identity": {"manifest": sha256_file(manifest)},
            "runs": {
                **{f"control-r{i}": {"case": "control", "passed": True} for i in (1, 2, 3)},
                "long-r1": {"case": "long", "passed": True},
            },
        },
    )
    for i in (1, 2, 3):
        findings = [{"id": "F1"}] if i == 2 else []
        atomic_write_json(output / f"control-r{i}/scan.json", {"review": {"findings": findings}})
        atomic_write_json(
            output / f"control-r{i}/audit.json", {"reviewer": "", "findings": findings}
        )
    answers = iter(["y", "quit"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    result = script["audit_available_runs"](output, keys, manifest, "Human evaluator")
    assert result["quality_runs_available"] == 3
    assert result["runs_visited"] == 2
    assert result["stopped"] is True
    assert read_json(output / "control-r1/audit.json")["reviewer"] == "Human evaluator"
    assert read_json(output / "control-r2/audit.json")["reviewer"] == ""
    assert read_json(output / "control-r3/audit.json")["reviewer"] == ""


@pytest.mark.parametrize("answers", [["unsure"], ["y", "unsure"], ["y", "P1", "unsure"]])
def test_unsure_never_records_a_judgment(tmp_path, monkeypatch, answers):
    script = runpy.run_path("scripts/audit-qualification.py")
    output, keys, manifest = tmp_path / "output", tmp_path / "keys", tmp_path / "manifest.json"
    atomic_write_json(manifest, {"cases": [{"id": "ms1"}]})
    atomic_write_json(
        output / "results.json",
        {
            "identity": {"manifest": sha256_file(manifest)},
            "runs": {"ms1-r1": {"case": "ms1", "passed": True}},
        },
    )
    atomic_write_json(keys / "ms1.json", {"planted": [{"id": "P1"}]})
    finding = {"id": "F1", "flaw_checks": [{"shown": True, "quotes_verified": True}]}
    atomic_write_json(output / "ms1-r1/scan.json", {"review": {"findings": [finding]}})
    audit_path = output / "ms1-r1/audit.json"
    audit = {"reviewer": "", "findings": [{"id": "F1", "valid": None}]}
    atomic_write_json(audit_path, audit)
    replies = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _: next(replies))
    result = script["audit_run"](output, keys, manifest, "ms1-r1", "Human evaluator")
    assert result["decisions_saved"] == 0
    assert read_json(audit_path) == audit


def test_readable_packet_checks_and_includes_exact_manuscript_without_overwrite(tmp_path):
    script = runpy.run_path("scripts/prepare-audit-packet.py")
    output, corpus, keys = tmp_path / "output", tmp_path / "corpus", tmp_path / "keys"
    manifest = tmp_path / "manifest.json"
    manuscript = corpus / "ms1/manuscript.md"
    manuscript.parent.mkdir(parents=True)
    manuscript.write_text("# Synthetic\n\nA quoted sentence.\n", encoding="utf-8")
    atomic_write_json(manifest, {"cases": [{"id": "ms1", "file": "ms1/manuscript.md"}]})
    atomic_write_json(
        output / "results.json",
        {
            "identity": {
                "manifest": sha256_file(manifest),
                "manuscripts": {"ms1": sha256_file(manuscript)},
            },
            "runs": {"ms1-r1": {"case": "ms1", "passed": True}},
        },
    )
    finding = {
        "id": "F1",
        "issue": "<script>alert('unsafe')</script>",
        "evidence": [{"source_id": "manuscript", "quote": "A quoted sentence."}],
    }
    run_path = output / "ms1-r1"
    atomic_write_json(run_path / "scan.json", {"review": {"findings": [finding]}})
    result = script["prepare_packet"](output, corpus, manifest, "ms1-r1")
    assert result["private_key_view"] is None
    assert (run_path / "manuscript.md").read_bytes() == manuscript.read_bytes()
    view = (run_path / "review.html").read_text(encoding="utf-8")
    assert "&lt;script&gt;" in view and "<script>" not in view
    assert 'href="#manuscript-line-3"' in view
    assert "this alone does not establish the concern" in view
    atomic_write_json(keys / "ms1.json", {"planted": [{"id": "P1", "description": "dummy"}]})
    script["prepare_packet"](output, corpus, manifest, "ms1-r1", keys)
    assert "dummy" in (run_path / "answer-key.html").read_text(encoding="utf-8")
    assert "dummy" not in view
    assert_mode(run_path / "answer-key.html", 0o600)
    (run_path / "review.html").write_text("user-edited", encoding="utf-8")
    with pytest.raises(ReviewError, match="existing file differs"):
        script["prepare_packet"](output, corpus, manifest, "ms1-r1")
    assert (run_path / "review.html").read_text(encoding="utf-8") == "user-edited"
    manuscript.write_text("changed", encoding="utf-8")
    with pytest.raises(ReviewError, match="differs from the executed batch"):
        script["prepare_packet"](output, corpus, manifest, "ms1-r1")


def test_interactive_audit_with_corpus_prepares_views_before_prompt(tmp_path, monkeypatch):
    script = runpy.run_path("scripts/audit-qualification.py")
    output, corpus, keys = tmp_path / "output", tmp_path / "corpus", tmp_path / "keys"
    manifest = tmp_path / "manifest.json"
    manuscript = corpus / "ms1/manuscript.md"
    manuscript.parent.mkdir(parents=True)
    manuscript.write_text("Synthetic manuscript.\n", encoding="utf-8")
    atomic_write_json(manifest, {"cases": [{"id": "ms1", "file": "ms1/manuscript.md"}]})
    atomic_write_json(
        output / "results.json",
        {
            "identity": {
                "manifest": sha256_file(manifest),
                "manuscripts": {"ms1": sha256_file(manuscript)},
            },
            "runs": {"ms1-r1": {"case": "ms1", "passed": True}},
        },
    )
    atomic_write_json(keys / "ms1.json", {"planted": [{"id": "P1", "description": "dummy"}]})
    run_path = output / "ms1-r1"
    atomic_write_json(run_path / "scan.json", {"review": {"findings": [{"id": "F1"}]}})
    atomic_write_json(run_path / "audit.json", {"reviewer": "", "findings": [{"id": "F1"}]})
    monkeypatch.setattr("builtins.input", lambda _: "unsure")
    result = script["audit_run"](output, keys, manifest, "ms1-r1", "Human", corpus=corpus)
    assert result["decisions_saved"] == 0
    assert (run_path / "review.html").is_file()
    assert (run_path / "answer-key.html").is_file()
    assert (run_path / "manuscript.md").read_bytes() == manuscript.read_bytes()
