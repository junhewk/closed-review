"""Development distribution never grants production or medical qualification."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def release():
    return yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8"))


def step(release, name):
    return next(s for s in release["jobs"]["build"]["steps"] if s.get("name") == name)


def python_block(step):
    return step["run"].split("\n", 1)[1].rsplit("\nPY", 1)[0]


@pytest.mark.parametrize(
    "version,prerelease,development",
    [
        ("0.9.0.dev7", "true", "true"),
        ("0.9.0a1", "true", "false"),
        ("0.9.0b15", "true", "false"),
        ("0.9.0rc1", "true", "false"),
        ("0.9.0", "false", "false"),
        ("0.9.0.post1", "false", "false"),
    ],
)
def test_workflow_classifies_only_dev_versions_for_the_test_distribution_exception(
    release, tmp_path, version, prerelease, development
):
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nversion = "{version}"\n', encoding="utf-8"
    )
    code = python_block(step(release, "Check the tag matches the package version"))
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env={**os.environ, "GITHUB_REF_NAME": f"v{version}"},
        capture_output=True,
        text=True,
        check=True,
    )
    assert dict(line.split("=", 1) for line in result.stdout.splitlines()) == {
        "version": version, "prerelease": prerelease, "development": development,
    }


def test_workflow_rejects_a_mismatched_tag(release, tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nversion = "0.9.0.dev7"\n', encoding="utf-8"
    )
    code = python_block(step(release, "Check the tag matches the package version"))
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env={**os.environ, "GITHUB_REF_NAME": "v0.9.0"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0 and "does not match" in result.stderr


def test_qualification_gate_stays_mandatory_for_non_dev_versions(release):
    jobs = release["jobs"]
    gate = step(release, "Require model and workflow qualification for this exact wheel")
    assert gate["if"] == "steps.version.outputs.development != 'true'"
    assert "check_release_gate" in gate["run"]
    assert jobs["build"]["needs"] == "test"
    assert jobs["build"]["outputs"]["development"] == "${{ steps.version.outputs.development }}"
    assert jobs["testpypi"]["if"] == "needs.build.outputs.prerelease == 'true'"
    assert jobs["pypi"]["if"] == (
        "needs.build.outputs.prerelease == 'false' && needs.build.outputs.development == 'false'"
    )
    publish = next(s for s in jobs["testpypi"]["steps"] if "pypi-publish" in s.get("uses", ""))
    assert publish["with"]["repository-url"] == "https://test.pypi.org/legacy/"
    assert jobs["testpypi"]["permissions"] == {"id-token": "write"}


def test_development_notice_explicitly_denies_qualification(release, tmp_path):
    notice_step = step(release, "Mark the unqualified development-only distribution")
    assert notice_step["if"] == "steps.version.outputs.development == 'true'"
    (tmp_path / "dist").mkdir()
    identity = {"version": "0.9.0.dev7", "sums_sha256": "a" * 64}
    (tmp_path / "sums.json").write_text(json.dumps(identity), encoding="utf-8")
    subprocess.run(
        [sys.executable, "-c", python_block(notice_step)], cwd=tmp_path, check=True,
        capture_output=True,
    )
    notice_path = tmp_path / "dist/creview-development-only.json"
    notice = json.loads(notice_path.read_text(encoding="utf-8"))
    assert notice["version"] == identity["version"]
    assert notice["runner_sums_sha256"] == identity["sums_sha256"]
    assert notice["channel"] == "TestPyPI" and notice["development_only"] is True
    assert notice["qualified"] is False and notice["production_release"] is False
