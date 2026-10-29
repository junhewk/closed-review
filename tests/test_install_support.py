import json
import os
import re
import shlex
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from closed_review import __version__

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "relative",
    ["README.md", "docs/install.md", "scripts/install.sh", "scripts/install-windows.ps1"],
)
def test_install_instructions_and_installers_name_the_current_wheel(relative):
    content = (ROOT / relative).read_text(encoding="utf-8")
    wheel_versions = set(re.findall(r"closed_review-([0-9][\w.]+)-py3-none-any\.whl", content))
    assert wheel_versions == {__version__}, "do not leave users with a stale wheel path"
    if relative.startswith("scripts/"):
        assert (
            f"/download/v{__version__}/closed_review-{__version__}-py3-none-any.whl" in content
        ), "the release tag and wheel version must match"


def test_package_lock_and_release_gate_track_the_current_version():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    locked = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    package = next(p for p in locked["package"] if p["name"] == "closed-review")
    gate = json.loads((ROOT / "evals/deployment/release-gate.json").read_text(encoding="utf-8"))
    assert project["project"]["version"] == package["version"] == gate["version"] == __version__


@pytest.mark.parametrize("relative", ["README.md", "docs/install.md"])
def test_unpublished_development_install_uses_an_explicit_local_wheel(relative):
    guide = (ROOT / relative).read_text(encoding="utf-8")
    assert f"--source ./dist/closed_review-{__version__}-py3-none-any.whl" in guide


def test_legacy_guide_does_not_launch_the_current_skill_as_an_old_scan():
    guide = (ROOT / "docs/review.md").read_text()
    introduction = " ".join(guide.split("## What happens", 1)[0].split())
    assert guide.startswith("# Historical scan workflow (legacy)")
    assert "[Medical methodological support](support.md)" in introduction
    assert "does not enter the historical one-finding-at-a-time queue" in introduction
    assert "not as the support deployment path" in introduction
    assert "```text\n/journal-article-review\n```" not in guide
    assert "It is good at checkable problems" not in guide


def test_existing_profile_instructions_require_the_managed_support_path_before_attaching():
    guide = (ROOT / "docs/install.md").read_text()
    section = " ".join(guide.split("## Installing into an existing profile", 1)[1].split(
        "## The model server", 1,
    )[0].split())
    assert "do not make an existing unmanaged profile eligible for medical support" in section
    assert "strict `--support` doctor before attaching a manuscript" in section
    assert "Start a review by attaching" not in section
    assert "Do not edit a frozen support configuration to work around a failed check" in section


@pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"), reason="Bash installer")
@pytest.mark.parametrize("context", [None, "32768", "not-a-number", "999999999999999999999"])
def test_review_install_rejects_missing_or_bad_context_before_mutating_installation(context):
    command = [
        "bash",
        str(ROOT / "scripts/install.sh"),
        "--review-profile",
        "isolated",
        "--gateway-url",
        "http://127.0.0.1:8091/v1",
        "--model",
        "local",
    ]
    if context:
        command += ["--context-length", context]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    assert result.returncode == 2
    assert "--context-length" in result.stderr
    assert "Installing creview" not in result.stdout


@pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"), reason="Bash installer")
def test_review_installer_passes_context_and_strict_doctor_without_legacy_smoke(tmp_path):
    tools = tmp_path / "tools"
    binaries = tmp_path / "bin"
    binaries.mkdir()
    tools.mkdir()
    uv = binaries / "uv"
    uv.write_text(
        '#!/bin/sh\ncase "$*" in\n'
        f"'tool dir') printf '%s\\n' {shlex.quote(str(tools))} ;;\n"
        f"'tool dir --bin') printf '%s\\n' {shlex.quote(str(binaries))} ;;\n"
        "esac\n"
    )
    uv.chmod(0o700)
    creview = binaries / "creview"
    creview.write_text("#!/bin/sh\nprintf 'MOCK-CREVIEW'; printf ' <%s>' \"$@\"; printf '\\n'\n")
    creview.chmod(0o700)
    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/install.sh"),
            "--source",
            "fake-candidate.whl",
            "--review-profile",
            "isolated",
            "--gateway-url",
            "http://127.0.0.1:8091/v1",
            "--model",
            "local",
            "--context-length",
            "131072",
        ],
        env={**os.environ, "PATH": str(binaries) + ":/usr/bin:/bin"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "<--context-length> <131072>" in result.stdout
    assert "<doctor> <--profile> <isolated> <--support>" in result.stdout
    assert "creview hermes smoke" not in result.stdout


@pytest.mark.skipif(not shutil.which("pwsh"), reason="PowerShell unavailable")
def test_windows_installer_parses_without_executing_it():
    script = str(ROOT / "scripts/install-windows.ps1").replace("'", "''")
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$tokens=$null; $errors=$null; "
            f"[System.Management.Automation.Language.Parser]::ParseFile('{script}', "
            "[ref]$tokens, [ref]$errors) | Out-Null; if ($errors.Count) { $errors; exit 1 }",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
