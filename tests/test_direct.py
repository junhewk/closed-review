from pathlib import Path

import pytest
from conftest import assert_mode

from closed_review.direct import _severity_labels, finalize_direct_export, prepare_direct_export
from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, data_home, read_json
from closed_review.session import session_key


def test_prepare_direct_export_creates_private_parent(isolated_env: Path) -> None:
    prepared = prepare_direct_export()
    directory = Path(prepared["directory"])

    assert directory.parent == isolated_env / "data" / "exports"
    assert_mode(directory, 0o700)
    assert_mode((isolated_env / "data"), 0o700)
    assert prepared["output_paths"] == {
        "development": str(directory / "review-development.md"),
        "authors": str(directory / "comments-to-authors.md"),
        "editor": str(directory / "comments-to-editor.md"),
    }


def _linked_scan(monkeypatch, *, words="I accept this concern."):
    monkeypatch.setenv("HERMES_SESSION_ID", "test-export-session")
    key, _ = session_key()
    scan_id = "scan-20261028T120000Z-0123abcd"
    path = data_home() / "scans" / scan_id / "scan.json"
    atomic_write_json(
        path,
        {
            "schema_version": "2",
            "scan_id": scan_id,
            "session_id": key,
            "phase": "ready",
            "surfaced": {
                "F1": {"disposition": "accepted", "response": {"words": words, "verified": True}},
            },
            "review": {
                "findings": [
                    {"id": "F1", "model_severity": "minor"},
                    {"id": "F2", "model_severity": "major", "issue": "unsurfaced private issue"},
                ]
            },
        },
    )
    return scan_id, path


def _write_drafts(prepared, editor):
    Path(prepared["output_paths"]["authors"]).write_text("Please resolve the concern.")
    Path(prepared["output_paths"]["editor"]).write_text(editor)
    Path(prepared["output_paths"]["development"]).write_text("The reviewer accepted the concern.")


def test_scan_linked_export_rejects_the_observed_severity_mismatch(isolated_env, monkeypatch):
    scan_id, path = _linked_scan(monkeypatch)
    prepared = prepare_direct_export(scan_id=scan_id)
    assert [entry["id"] for entry in prepared["accepted_scan_records"]] == ["F1"]
    assert read_json(Path(prepared["directory"]) / "export.json")["scan_id"] == scan_id
    _write_drafts(prepared, "One major inconsistency was found and accepted.")
    with pytest.raises(ReviewError, match="major.*minor"):
        finalize_direct_export(prepared["export_id"])
    assert not Path(prepared["receipt_path"]).exists()
    _write_drafts(prepared, "One minor inconsistency was found and accepted.")
    assert finalize_direct_export(prepared["export_id"])["severity_check"]["status"] == (
        "no_explicit_conflict_found"
    )
    # Finalization rereads the scan instead of trusting an out-of-date preparation snapshot.
    scan = read_json(path)
    scan["review"]["findings"][0]["model_severity"] = "major"
    atomic_write_json(path, scan)
    with pytest.raises(ReviewError, match="minor.*major"):
        finalize_direct_export(prepared["export_id"])


def test_reviewer_severity_words_are_not_overridden_by_model_rating(isolated_env, monkeypatch):
    scan_id, _ = _linked_scan(monkeypatch, words="I accept this and consider it a major concern.")
    prepared = prepare_direct_export(scan_id=scan_id)
    _write_drafts(prepared, "The reviewer considered this a major concern.")
    result = finalize_direct_export(prepared["export_id"])
    assert result["severity_check"]["status"] == "manual_review_required"


def test_scan_export_rejects_observed_mentions_of_unsurfaced_candidates(isolated_env, monkeypatch):
    scan_id, _ = _linked_scan(monkeypatch)
    prepared = prepare_direct_export(scan_id=scan_id)
    _write_drafts(prepared, "One minor concern was accepted.")
    development = Path(prepared["output_paths"]["development"])
    for disclosure in (
        "The scan state reported further candidates as available.",
        "Minor-severity candidates were not surfaced.",
        "Unsurfaced findings are in the private record.",
    ):
        development.write_text(disclosure)
        with pytest.raises(ReviewError, match="findings not shown"):
            finalize_direct_export(prepared["export_id"])
        assert not Path(prepared["receipt_path"]).exists()
    development.write_text("The reviewer accepted this concern; no other issues are raised.")
    result = finalize_direct_export(prepared["export_id"])
    assert result["scope_check"]["status"] == "no_explicit_conflict_found"


def test_linked_export_rejects_another_session(isolated_env, monkeypatch):
    scan_id, _ = _linked_scan(monkeypatch)
    monkeypatch.setenv("HERMES_SESSION_ID", "different-session")
    with pytest.raises(ReviewError, match="same review session"):
        prepare_direct_export(scan_id=scan_id)
    assert not (data_home() / "exports").exists()


def test_severity_checks_ignore_negated_language():
    assert _severity_labels("This is not a major concern.\n## Minor issues") == {"minor"}
