import importlib.util
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_text, read_json
from closed_review.session import start_session
from closed_review.smoke import environment

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/test-support-baseline.py"
SPEC = importlib.util.spec_from_file_location("support_baseline", SCRIPT)
baseline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(baseline)
CORPUS = SCRIPT.parents[1] / "evals/support-pilot/manuscripts"


def transcript(root, *, command="creview session start --support", auto=False):
    root.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(root / "state.db") as db:
        db.execute(
            "CREATE TABLE messages (session_id TEXT, role TEXT, content TEXT, tool_calls TEXT, "
            "timestamp REAL, tool_name TEXT)"
        )
        content = (
            '[IMPORTANT: The "journal-article-review" skill is auto-loaded'
            if auto
            else "Synthetic baseline"
        )
        db.execute("INSERT INTO messages VALUES ('test', 'user', ?, NULL, 0, NULL)", (content,))
        calls = [{"function": {"name": "terminal", "arguments": json.dumps({"command": command})}}]
        db.execute(
            "INSERT INTO messages VALUES ('test', 'assistant', NULL, ?, 0, NULL)",
            (json.dumps(calls),),
        )


@pytest.mark.parametrize(
    "command",
    [
        "creview session start --support",
        "/private/test/review-bin/creview session start --support",
        "creview hermes doctor --support",
        "python -c 'print(20 / 100)'",
    ],
)
def test_ordinary_trace_allows_privacy_preflight_and_normal_local_computation(tmp_path, command):
    transcript(tmp_path, command=command)
    assert all(baseline.baseline_trace(tmp_path, "test").values())


@pytest.mark.parametrize(
    "command",
    [
        "creview support start manuscript.md --module statistics",
        "creview scan start manuscript.md",
        "creview direct prepare-export",
        "creview session start --support; creview support modules",
        "python -c 'from closed_review.support import workflow'",
        "cat /profile/skills/journal-article-review/SKILL.md",
    ],
)
def test_support_or_legacy_use_cannot_be_counted_as_plain_baseline(tmp_path, command):
    transcript(tmp_path, command=command)
    report = baseline.baseline_trace(tmp_path, "test")
    assert report["tool_trace_available"] and not report["ordinary_tools_only"]


def test_auto_loaded_skill_and_missing_trace_are_refused(tmp_path):
    assert not baseline.baseline_trace(tmp_path, "missing")["tool_trace_available"]
    transcript(tmp_path, auto=True)
    report = baseline.baseline_trace(tmp_path, "test")
    assert not report["ordinary_tools_only"] and not report["no_auto_loaded_support_skill"]


@pytest.mark.parametrize("contaminated", [False, True])
def test_real_profile_preflight_and_saved_output_are_audited_without_quality_judgments(
    isolated_env,
    monkeypatch,
    contaminated,
):
    args = SimpleNamespace(
        output=isolated_env / "baseline", corpus=CORPUS, hermes="fake", language="en", timeout=30
    )
    commands = []

    def fake_hermes(command, env, work, log, deadline):
        commands.append(command)
        root = Path(env["HERMES_HOME"])
        transcript(
            root,
            command="creview support modules"
            if contaminated
            else "creview session start --support",
        )
        with sqlite3.connect(root / "state.db") as db:
            db.execute(
                "CREATE TABLE sessions (id TEXT, model TEXT, billing_provider TEXT, "
                "billing_base_url TEXT)"
            )
            db.execute(
                "INSERT INTO sessions VALUES ('test', 'qwen3.8-flash-next', 'custom', 'http://127.0.0.1:8091/v1')"
            )
        with environment(dict(env, HERMES_SESSION_ID="test")):
            start_session(None, live=False, support=True)
        atomic_write_text(
            work / "baseline.md",
            "# Synthetic ordinary baseline\n\nNo scientific judgment in this adapter.",
        )

    monkeypatch.setattr(baseline, "_run_turn", fake_hermes)
    result = baseline.run_case(
        args,
        "case-02",
        "statistics",
        {
            "gateway_url": "http://127.0.0.1:8091/v1",
            "model": "qwen3.8-flash-next",
            "context_length": 65536,
        },
    )
    assert result["engineering_passed"] is not contaminated, result
    assert (
        result["checks"]["strict_local_runtime"] and result["checks"]["strict_preflight_recorded"]
    )
    assert result["artifact_sha256"] and len(commands) == 1
    assert "--skills" not in commands[0]
    assert result["baseline_checking_seconds"] is None
    assert result["qualification"] == "not_qualified"
    assert "semantic_quality" in result
    assert read_json(args.output / "case-02/result.json") == result


def test_reading_copied_packaged_criteria_is_not_an_unassisted_baseline(tmp_path):
    transcript(tmp_path)
    with sqlite3.connect(tmp_path / "state.db") as db:
        db.execute(
            "UPDATE messages SET tool_calls=? WHERE role='assistant'",
            (
                json.dumps(
                    [
                        {
                            "function": {
                                "name": "read_file",
                                "arguments": {
                                    "path": (
                                        "/profile/creview-skill-baseline/references/"
                                        "designs/quantitative.md"
                                    )
                                },
                            }
                        }
                    ]
                ),
            ),
        )
    assert not baseline.baseline_trace(tmp_path, "test")["ordinary_tools_only"]


def replace_tool_call(root, name, arguments):
    transcript(root)
    with sqlite3.connect(root / "state.db") as db:
        db.execute(
            "UPDATE messages SET tool_calls=? WHERE role='assistant'",
            (json.dumps([{"function": {"name": name, "arguments": arguments}}]),),
        )


@pytest.mark.parametrize(
    "arguments",
    [
        {"pattern": "manuscript.pdf", "target": "files"},
        {"pattern": "Table", "path": ".", "target": "content"},
        {"pattern": "Table", "path": None},
        {"pattern": "*.md", "path": "", "target": "find"},
        {"pattern": "participants", "path": "manuscript.md", "target": "grep"},
        {"pattern": "methods", "file_glob": "*.md"},
    ],
)
def test_ordinary_local_file_search_is_not_review_skill_contamination(tmp_path, arguments):
    replace_tool_call(tmp_path, "search_files", arguments)
    assert all(baseline.baseline_trace(tmp_path, "test").values())


def test_actual_native_pdf_discovery_shape_is_allowed(tmp_path):
    replace_tool_call(
        tmp_path,
        "search_files",
        json.dumps(
            {"pattern": "manuscript.pdf", "target": "files", "path": str(tmp_path / "work")}
        ),
    )
    assert all(baseline.baseline_trace(tmp_path, "test").values())


@pytest.mark.parametrize(
    "arguments",
    [
        {"pattern": "*.md", "path": ".."},
        {"pattern": "*.md", "path": "/"},
        {"pattern": "journal-article-review"},
        {"pattern": "*.md", "path": "creview-skill-baseline"},
        {"pattern": "closed_review"},
        {"pattern": "methods", "file_glob": "*journal-article-review*"},
        {"pattern": "methods", "target": "web"},
        {"pattern": "methods", "path": []},
        {"pattern": "methods", "file_glob": []},
        {"pattern": None},
        {},
    ],
)
def test_file_search_does_not_allow_review_criteria_or_outside_work_discovery(tmp_path, arguments):
    replace_tool_call(tmp_path, "search_files", arguments)
    report = baseline.baseline_trace(tmp_path, "test")
    assert report["tool_trace_available"] and not report["ordinary_tools_only"]


def test_file_search_symlink_cannot_escape_baseline_work(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "outside").symlink_to(tmp_path, target_is_directory=True)
    replace_tool_call(tmp_path, "search_files", {"pattern": "*.md", "path": "outside"})
    assert not baseline.baseline_trace(tmp_path, "test")["ordinary_tools_only"]


def test_unknown_or_external_tools_still_refuse_baseline(tmp_path):
    replace_tool_call(tmp_path, "web_search", {"query": "synthetic only"})
    assert not baseline.baseline_trace(tmp_path, "test")["ordinary_tools_only"]


def test_main_requires_explicit_cases_and_new_output(tmp_path, monkeypatch):
    monkeypatch.delenv("HERMES_SESSION_ID", raising=False)
    monkeypatch.setattr(baseline.shutil, "which", lambda value: "/bin/true")
    with pytest.raises(SystemExit) as error:
        baseline.main(
            [
                "--case",
                "case-02",
                "--output",
                str(tmp_path),
                "--gateway-url",
                "http://127.0.0.1:8091/v1",
                "--model",
                "local",
                "--context-length",
                "65536",
            ]
        )
    assert error.value.code == 2


@pytest.mark.parametrize(
    "suffix,payload",
    [
        (".md", b"# Synthetic\r\n\r\nPreserve the exact bytes.\r\n"),
        (".txt", b"Synthetic\r\nKeep this line ending.\r\n"),
        (".pdf", b"%PDF-1.4\nSynthetic opaque copying fixture, not a parsed PDF."),
        (".docx", b"PK\x03\x04Synthetic opaque copying fixture, not a parsed DOCX."),
    ],
)
def test_baseline_copies_source_bytes_and_extension_without_normalization(
    isolated_env, monkeypatch, suffix, payload
):
    paper = isolated_env / ("source" + suffix)
    paper.write_bytes(payload)
    args = SimpleNamespace(
        output=isolated_env / "copy-test",
        corpus=CORPUS,
        hermes="fake",
        language="en",
        timeout=30,
        paper_override=paper,
    )

    def stopped(*args):
        raise ReviewError("stop before inference; copy adapter only")

    monkeypatch.setattr(baseline, "_run_turn", stopped)
    result = baseline.run_case(
        args,
        "copy-fixture",
        "statistics",
        {
            "gateway_url": "http://127.0.0.1:8091/v1",
            "model": "qwen3.8-flash-next",
            "context_length": 65536,
        },
    )
    copied = Path(result["profile_root"]) / "work" / ("manuscript" + suffix)
    assert copied.read_bytes() == payload
    assert not result["engineering_passed"] and "copy adapter only" in result["error"]
