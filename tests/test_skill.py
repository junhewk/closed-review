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


def test_repository_skills_folder_holds_only_the_hermes_skill() -> None:
    # Hermes discovers every skill under skills/ when a profile points skills.external_dirs at a
    # checkout (docs/install.md), so nothing else may live there.
    assert sorted(p.name for p in Path("skills").iterdir()) == ["journal-article-review"]


def test_support_modules_replace_the_default_scan() -> None:
    skill = " ".join(Path("skills/journal-article-review/SKILL.md").read_text().split())
    review = " ".join(
        Path("skills/journal-article-review/references/review.md").read_text().split()
    )

    assert "## Workflow" in skill
    assert "a complete verdict" in skill
    assert "The reviewer owns every scientific judgment" in skill
    for command in ("modules", "start", "next", "submit", "report", "record", "export"):
        assert f"creview support {command}" in skill, command
    assert "Never automatically run all modules" in skill
    assert "disclose totals" in skill
    assert "one finding per turn" in skill
    assert "user's configured response language" in skill
    assert "## Legacy compatibility" in skill
    assert "not a full review" in review
    assert "counterevidence" in review


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


def test_legacy_profiles_are_not_the_new_module_rules() -> None:
    skill = Path("skills/journal-article-review/SKILL.md").read_text()
    index = (DESIGNS / "index.md").read_text()
    assert "earlier design profiles" in skill
    assert "legacy major-flaw profiles" in skill
    assert "Load at most three" in index
    assert "`model_lead`" in index
