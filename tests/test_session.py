import json
from pathlib import Path

import pytest
from conftest import assert_mode, reviewer_answers_clarify, reviewer_says, setup_profile

from closed_review.cli import main
from closed_review.direct import finalize_direct_export, prepare_direct_export
from closed_review.errors import ReviewError
from closed_review.receipts import installed_identity, verify_receipt
from closed_review.session import start_session
from closed_review.transcript import reviewer_words


def export_with(session: str | None = None) -> dict:
    prepared = prepare_direct_export(session)
    Path(prepared["output_paths"]["authors"]).write_text("Define the population.\n")
    return prepared


def test_session_start_returns_package_rules_and_links_hermes_session(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_profile(isolated_env)
    monkeypatch.setenv("HERMES_SESSION_ID", "20261015_101500_abcdef")

    started = start_session("reviewer", live=False)

    assert started["session_source"] == "hermes_session"
    assert started["export_command"] == "creview direct prepare-export"
    assert started["rules"].startswith("# Privacy rules for journal-article-review")
    assert "Do not put manuscript text in shell arguments." in started["rules"]
    assert any("display.inline_diffs: false" in warning for warning in started["warnings"])
    record = isolated_env / "data" / "preflights" / f"{started['session_id']}.json"
    assert_mode(record, 0o600)
    assert "20261015_101500_abcdef" not in record.read_text()

    prepared = export_with()
    finalized = finalize_direct_export(prepared["export_id"], "reviewer")

    assert finalized["preflight"] == "passed"
    receipt = json.loads(Path(prepared["receipt_path"]).read_text())
    assert receipt["preflight"] == {
        "status": "passed",
        "session_source": "hermes_session",
        "checked_at": started["checked_at"],
    }


def test_skill_text_hermes_loaded_into_a_user_message_is_not_the_reviewer(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In the TUI and Desktop, `/journal-article-review deep ...` is stored as one user message:
    the whole skill, then what the reviewer typed (live TUI run, 2026-10-27)."""
    setup_profile(isolated_env)
    monkeypatch.setenv("HERMES_SESSION_ID", "20261027_154408_0f133b")
    start_session("reviewer", live=False)
    invoked = (
        '[IMPORTANT: The user has invoked the "journal-article-review" skill, indicating they '
        "want you to follow its instructions. The full skill content is loaded below.]\n\n"
        "Yes, qualitative only. Do not begin with a complete verdict.\n\n"
        "The user has provided the following instruction alongside the skill invocation: deep\n\n"
        "Please run a deep review; I use the qualitative profile."
    )
    reviewer_says(isolated_env / "hermes", "20261027_154408_0f133b", invoked)
    check = {"hermes_session": True, "what": "the response to F1"}
    with pytest.raises(ReviewError, match="not in any of those messages"):
        reviewer_words("Yes, qualitative only.", **check)
    assert reviewer_words("I use the qualitative profile", **check)["verified"]


def test_an_answered_clarify_is_the_reviewer_and_an_unanswered_one_is_not(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hermes's own way to ask: a clarify answer counts, whether the reviewer picked an option or
    typed one; a question no one answered (one-shot mode) gives nothing."""
    setup_profile(isolated_env)
    monkeypatch.setenv("HERMES_SESSION_ID", "20261027_ms5i3")
    hermes = isolated_env / "hermes"
    reviewer_answers_clarify(hermes, "20261027_ms5i3", None, status="unanswered")
    check = {"hermes_session": True, "what": "the response to F1"}
    with pytest.raises(ReviewError, match="not in any of those messages"):
        reviewer_words("Accept", **check)
    reviewer_answers_clarify(hermes, "20261027_ms5i3", "Accept")
    assert reviewer_words("Accept", **check)["verified"]


def test_session_without_hermes_id_uses_explicit_session(isolated_env: Path) -> None:
    setup_profile(isolated_env)
    started = start_session("reviewer", live=False)
    assert started["session_source"] == "explicit"
    assert started["export_command"].endswith(f"--session {started['session_id']}")
    linked = export_with(started["session_id"])
    unlinked = export_with()

    assert finalize_direct_export(linked["export_id"], "reviewer")["preflight"] == "passed"
    assert finalize_direct_export(unlinked["export_id"], "reviewer")["preflight"] == "none"


def test_failed_preflight_is_recorded_in_the_receipt(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERMES_SESSION_ID", "unconfigured-session")
    with pytest.raises(ReviewError, match="privacy preflight failed"):
        start_session("reviewer", live=False)

    prepared = export_with()
    assert finalize_direct_export(prepared["export_id"])["preflight"] == "failed"


def test_another_hermes_session_does_not_inherit_a_preflight(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_profile(isolated_env)
    monkeypatch.setenv("HERMES_SESSION_ID", "first")
    start_session("reviewer", live=False)
    monkeypatch.setenv("HERMES_SESSION_ID", "second")

    prepared = export_with()

    assert finalize_direct_export(prepared["export_id"], "reviewer")["preflight"] == "none"


def test_invalid_session_id_is_rejected(isolated_env: Path) -> None:
    with pytest.raises(ReviewError, match="invalid session id"):
        prepare_direct_export("../preflights/x")


def finalized_receipt(isolated_env: Path) -> Path:
    setup_profile(isolated_env)
    prepared = export_with()
    finalize_direct_export(prepared["export_id"], "reviewer")
    return Path(prepared["receipt_path"])


def test_verify_receipt_checks_text_and_tool(isolated_env: Path, tmp_path: Path) -> None:
    receipt_path = finalized_receipt(isolated_env)

    report = verify_receipt(receipt_path)
    assert report["verified"]
    assert report["tool"] == {
        "receipt_version": installed_identity()["version"],
        "status": "match",
        "reference": "this_creview",
    }
    assert report["subjects"] == [{"file": "comments-to-authors.md", "status": "match"}]

    authors = receipt_path.parent / "comments-to-authors.md"
    authors.write_text("Define  the\npopulation.")
    assert verify_receipt(receipt_path)["subjects"][0]["status"] == "text_match"
    authors.write_text("Describe the population.\n")
    report = verify_receipt(receipt_path)
    assert not report["verified"]
    assert report["subjects"][0]["status"] == "changed"


def test_verify_receipt_detects_tampering_and_other_builds(
    isolated_env: Path, tmp_path: Path
) -> None:
    receipt_path = finalized_receipt(isolated_env)
    sums = tmp_path / "SHA256SUMS"
    sums.write_text(installed_identity()["sums"], newline="\n")
    assert verify_receipt(receipt_path, sums)["tool"]["status"] == "match"
    sums.write_text(installed_identity()["sums"].replace("0", "1", 1), newline="\n")
    assert verify_receipt(receipt_path, sums)["tool"]["status"] == "mismatch"

    receipt = json.loads(receipt_path.read_text())
    receipt["tool"]["version"] = "0.0.1"
    receipt_path.write_text(json.dumps(receipt))
    report = verify_receipt(receipt_path)
    assert not report["receipt_id_valid"]
    assert report["tool"]["status"] == "not_checked"
    assert not report["verified"]


def test_cli_session_and_receipt_commands(
    isolated_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    setup_profile(isolated_env)
    assert main(["session", "start", "--profile", "reviewer", "--skip-live"]) == 0
    session_id = json.loads(capsys.readouterr().out)["session_id"]
    assert main(["direct", "prepare-export", "--session", session_id]) == 0
    prepared = json.loads(capsys.readouterr().out)
    Path(prepared["output_paths"]["editor"]).write_text("Minor revision.\n")
    assert main(["direct", "finalize", prepared["export_id"], "--profile", "reviewer"]) == 0
    assert json.loads(capsys.readouterr().out)["preflight"] == "passed"
    assert main(["receipts", "verify", prepared["receipt_path"]]) == 0
    assert json.loads(capsys.readouterr().out)["verified"]
    assert main(["receipts", "sums"]) == 0
    assert "receipts.py" in json.loads(capsys.readouterr().out)["sums"]
