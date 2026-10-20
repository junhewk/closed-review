from importlib import resources
from pathlib import Path


def test_repository_skill_matches_packaged_skill() -> None:
    packaged = resources.files("closed_review").joinpath(
        "resources", "skills", "journal-article-review"
    )
    repository = Path("skills/journal-article-review")
    package_files = {
        str(path.relative_to(packaged)): path.read_bytes()
        for path in packaged.rglob("*")
        if path.is_file()
    }
    repository_files = {
        str(path.relative_to(repository)): path.read_bytes()
        for path in repository.rglob("*")
        if path.is_file()
    }
    assert repository_files == package_files


def test_skill_defaults_to_development_and_keeps_audit_explicit() -> None:
    skill = Path("skills/journal-article-review/SKILL.md").read_text()
    workflow = Path("skills/journal-article-review/references/workflow.md").read_text()

    development = Path("skills/journal-article-review/references/development.md").read_text()

    assert "## Development loop" in skill
    assert "## Default: direct conversation" in skill
    assert "## Optional audited review" in skill
    assert "Do not begin with a complete verdict" in skill
    assert "recommendation is optional and belongs to the user" in skill
    assert "Compile only when the user explicitly asks" in development
    assert "run `creview direct prepare-export`" in skill
    assert "Use `creview` for every confidential manuscript" not in skill
    assert "creview case create" not in skill
    assert "creview case create" in workflow
    assert "Direct review must not create a case" in workflow
    assert "finding respond" in workflow
    assert "request-metadata" in skill
    assert "Do not announce, enumerate, summarize, or count possible future issues" in skill
    assert "status counts for surfaced records only" in development


DESIGNS = Path("skills/journal-article-review/references/designs")
PROFILE_SECTIONS = [
    "## Recognize",
    "## Where it usually breaks",
    "## Major flaws",
    "## Common false alarms",
    "## Monitoring areas",
]


def _front_matter(text: str) -> dict:
    import yaml

    assert text.startswith("---\n")
    return yaml.safe_load(text.split("---\n", 2)[1])


def test_design_profiles_share_structure_and_are_indexed() -> None:
    index = (DESIGNS / "index.md").read_text()
    profiles = sorted(path for path in DESIGNS.glob("*.md") if path.name != "index.md")
    assert profiles
    for path in profiles:
        text = path.read_text()
        meta = _front_matter(text)
        assert meta["id"] == path.stem
        for key in ("applies_to", "not_for", "reporting_guidance", "version"):
            assert meta.get(key), f"{path.name} lacks {key}"
        for section in PROFILE_SECTIONS:
            assert section in text, f"{path.name} lacks {section}"
        assert len(text.splitlines()) <= 150, f"{path.name} exceeds the line budget"
        assert f"]({path.name})" in index, f"{path.name} is not listed in the index"


def test_design_profiles_are_wired_into_skill() -> None:
    skill = Path("skills/journal-article-review/SKILL.md").read_text()
    index = (DESIGNS / "index.md").read_text()
    assert "references/designs/index.md" in skill
    assert "wait for the reviewer to confirm" in skill
    assert "Load at most three" in index
    assert "`model_lead`" in index


def test_logical_segments_and_deep_review_are_in_the_skill() -> None:
    skill = Path("skills/journal-article-review/SKILL.md").read_text()
    workflow = Path("skills/journal-article-review/references/workflow.md").read_text()
    deep = Path("skills/journal-article-review/references/deep.md").read_text()
    assert "plan the review by logical segments, in every mode" in skill
    assert "creview segments propose MANUSCRIPT" in skill
    assert "## Deep review" in skill
    assert "references/deep.md" in skill
    assert "creview segments set --case CASE PLAN_PATH" in workflow
    for command in (
        "scan start",
        "scan next",
        "scan submit",
        "scan candidate",
        "scan record",
        "scan purge",
    ):
        assert f"creview {command}" in deep, command
    assert "never show them, list them, or count them to the reviewer" in " ".join(deep.split())
    assert "Do not tell the reviewer how many remain" in " ".join(deep.split())
