import hashlib
import json
from pathlib import Path

import pytest
from conftest import assert_mode, setup_profile

from closed_review.cli import main
from closed_review.direct import finalize_direct_export, prepare_direct_export
from closed_review.errors import ReviewError
from closed_review.receipts import (
    endpoint_class,
    installed_sums,
    normalize_text,
    receipt_id,
    text_sha256,
)


def test_text_hash_survives_web_form_reformatting_but_not_rewording() -> None:
    exported = "# Comments\n\n1. **The sample** is small.\r\n\n\n2. Define\tthe population.\n"
    pasted = "# Comments 1. **The sample** is small.\n2. Define the  population."
    reworded = "# Comments 1. **The sample** is large. 2. Define the population."

    assert normalize_text(exported) == normalize_text(pasted)
    assert text_sha256(exported) == text_sha256(pasted)
    assert text_sha256(exported) != text_sha256(reworded)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (None, "unknown"),
        ("http://localhost:8091/v1", "loopback"),
        ("http://127.0.0.1:8091/v1", "loopback"),
        ("http://192.168.0.5:8091/v1", "private-network"),
        ("http://100.101.102.103:8091/v1", "private-network"),
        ("http://gpu.tail1234.ts.net:8091/v1", "private-network"),
        ("http://gateway.example.org/v1", "hostname"),
        ("http://8.8.8.8/v1", "public"),
    ],
)
def test_endpoint_is_recorded_as_a_category(url: str | None, expected: str) -> None:
    assert endpoint_class(url) == expected


def test_installed_sums_cover_package_and_skill_but_not_caches() -> None:
    sums = installed_sums()
    paths = [line.split("  ", 1)[1] for line in sums.splitlines()]

    assert "receipts.py" in paths
    assert "resources/skills/journal-article-review/SKILL.md" in paths
    assert not any("__pycache__" in path or path.endswith(".pyc") for path in paths)
    assert paths == sorted(paths)


def test_direct_finalize_writes_receipt_and_log(isolated_env: Path) -> None:
    setup_profile(isolated_env)
    prepared = prepare_direct_export()
    assert prepared["finalize_command"] == f"creview direct finalize {prepared['export_id']}"
    Path(prepared["output_paths"]["authors"]).write_text("Define the population.\n", newline="\n")
    Path(prepared["output_paths"]["editor"]).write_text("Major revision.\n", newline="\n")

    result = finalize_direct_export(prepared["export_id"], "reviewer")

    receipt_path = Path(prepared["receipt_path"])
    receipt = json.loads(receipt_path.read_text())
    assert result["receipt_id"] == receipt["receipt_id"] == receipt_id(receipt)
    assert result["subjects"] == ["authors", "editor"]
    assert_mode(receipt_path, 0o600)
    assert receipt["tool"]["sums_sha256"] == hashlib.sha256(installed_sums().encode()).hexdigest()
    assert receipt["environment"] == {
        "host": "hermes",
        "model": "qwen3.8-flash-next",
        "endpoint_class": "loopback",
        "doctor": "pass",
        "doctor_checked_at": receipt["environment"]["doctor_checked_at"],
        "skill_privacy_block": "match",
    }
    assert receipt["preflight"] == {"status": "none", "session_source": None, "checked_at": None}
    assert receipt["attestations"] == [{"type": "self"}]
    authors = receipt["subjects"][0]
    assert authors["sha256"] == hashlib.sha256(b"Define the population.\n").hexdigest()
    assert authors["text_sha256"] == text_sha256("Define the population.")
    serialized = json.dumps(receipt)
    assert "Define the population" not in serialized
    assert "127.0.0.1" not in serialized

    log = isolated_env / "data" / "receipts.jsonl"
    assert_mode(log, 0o600)
    assert [json.loads(line)["receipt_id"] for line in log.read_text().splitlines()] == [
        receipt["receipt_id"]
    ]


def test_direct_finalize_records_failed_profile_check(isolated_env: Path) -> None:
    prepared = prepare_direct_export()
    Path(prepared["output_paths"]["authors"]).write_text("Text.\n")

    assert finalize_direct_export(prepared["export_id"])["doctor"] == "fail"


def test_direct_refinalize_after_edit_appends_new_receipt(isolated_env: Path) -> None:
    setup_profile(isolated_env)
    prepared = prepare_direct_export()
    authors = Path(prepared["output_paths"]["authors"])
    authors.write_text("First wording.\n")
    first = finalize_direct_export(prepared["export_id"], "reviewer")
    authors.write_text("Second wording.\n")
    second = finalize_direct_export(prepared["export_id"], "reviewer")

    assert first["receipt_id"] != second["receipt_id"]
    current = json.loads(Path(prepared["receipt_path"]).read_text())
    assert current["receipt_id"] == second["receipt_id"]
    assert len((isolated_env / "data" / "receipts.jsonl").read_text().splitlines()) == 2


def test_direct_finalize_rejects_bad_or_empty_exports(isolated_env: Path) -> None:
    with pytest.raises(ReviewError, match="invalid direct export id"):
        finalize_direct_export("../cases/x")
    with pytest.raises(ReviewError, match="does not exist"):
        finalize_direct_export("direct-20260101T000000Z-0123abcd")
    prepared = prepare_direct_export()
    with pytest.raises(ReviewError, match="before finalizing"):
        finalize_direct_export(prepared["export_id"])


def test_cli_direct_finalize(isolated_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    setup_profile(isolated_env)
    prepared = prepare_direct_export()
    Path(prepared["output_paths"]["development"]).write_text("Private record.\n")

    assert main(["direct", "finalize", prepared["export_id"], "--profile", "reviewer"]) == 0
    assert json.loads(capsys.readouterr().out)["subjects"] == ["development"]
