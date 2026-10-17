import shutil
from pathlib import Path, PureWindowsPath

import pytest
import yaml

from closed_review import hermes
from closed_review.errors import ReviewError


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self):
        return {"data": [{"id": "qwen3.8-flash-next"}]}


def make_profile(tmp_path: Path) -> Path:
    profile = tmp_path / "hermes" / "profiles" / "reviewer"
    profile.mkdir(parents=True)
    config = {
        "model": {"default": "qwen3.8-flash-next", "provider": "local"},
        "providers": {"local": {"base_url": "http://127.0.0.1:8091/v1"}},
        "tools": {"enabled_toolsets": ["terminal", "file", "skills"]},
    }
    (profile / "config.yaml").write_text(yaml.safe_dump(config))
    return profile


def write_exact_skill(destination: Path) -> None:
    for relative, content in hermes._skill_files().items():
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def test_skill_changes_use_posix_names_on_windows(tmp_path, monkeypatch) -> None:
    destination = tmp_path / "skill"
    write_exact_skill(destination)
    (destination / "references" / "lessons.md").write_text("learned")
    (destination / "references" / "development.md").write_text("edited content")
    original_relative_to = Path.relative_to

    def windows_relative_to(self, *args, **kwargs):
        return PureWindowsPath(original_relative_to(self, *args, **kwargs))

    monkeypatch.setattr(Path, "relative_to", windows_relative_to)

    assert hermes.skill_changes(destination) == [
        {"file": "references/development.md", "change": "modified"},
        {"file": "references/lessons.md", "change": "added"},
    ]


def test_install_is_dry_run_and_doctor_checks_current_profile(isolated_env, monkeypatch) -> None:
    profile = make_profile(isolated_env)
    original_config = (profile / "config.yaml").read_bytes()
    plan = hermes.install_skill("reviewer")
    assert not plan["applied"]
    assert not (profile / "skills").exists()
    hermes.install_skill("reviewer", apply=True)
    monkeypatch.setattr(hermes.httpx, "get", lambda *args, **kwargs: FakeResponse())
    report = hermes.inspect_profile("reviewer")
    assert report["ready"]
    assert report["profile"] == "reviewer"
    assert report["gateway"]["checked"]
    assert report["skill_privacy_block"] == "match"
    assert report["skill_changes"] == []
    assert report["privacy_boundary"] == "instructional_shell_guardrail"
    assert (profile / "config.yaml").read_bytes() == original_config


def hermes_edit(skill: Path, marker: str = "Lesson: quote the table number.") -> None:
    """Mimic Hermes's self-improvement appending a lesson outside the privacy block."""
    path = skill / "SKILL.md"
    path.write_text(path.read_text() + f"\n{marker}\n")


def test_doctor_accepts_hermes_edits_outside_the_privacy_block(isolated_env) -> None:
    profile = make_profile(isolated_env)
    hermes.install_skill("reviewer", apply=True)
    skill = profile / "skills" / "journal-article-review"
    hermes_edit(skill)
    (skill / "references" / "lessons.md").write_text("Learned from a previous review.\n")

    report = hermes.inspect_profile("reviewer", live=False)

    assert report["ready"], report["problems"]
    assert report["skill_privacy_block"] == "match"
    assert report["skill_changes"] == [
        {"file": "SKILL.md", "change": "modified"},
        {"file": "references/lessons.md", "change": "added"},
    ]


def test_doctor_stops_on_privacy_block_edit_and_restore_keeps_other_edits(isolated_env) -> None:
    profile = make_profile(isolated_env)
    hermes.install_skill("reviewer", apply=True)
    skill = profile / "skills" / "journal-article-review"
    hermes_edit(skill)
    path = skill / "SKILL.md"
    path.write_text(
        path.read_text().replace("If it fails, stop", "If it fails, continue with caution")
    )

    report = hermes.inspect_profile("reviewer", live=False)
    assert not report["ready"]
    assert report["skill_privacy_block"] == "changed"
    assert any("skill-diff" in problem for problem in report["problems"])
    diff = hermes.skill_diff("reviewer")
    assert "+If it fails, continue with caution" in diff["privacy_block_diff"]

    plan = hermes.restore_privacy_block("reviewer")
    assert plan == {
        "applied": False,
        "skill_path": str(path),
        "privacy_block": "changed",
        "changed": True,
        "other_edits_preserved": True,
    }
    assert "continue with caution" in path.read_text()

    hermes.restore_privacy_block("reviewer", apply=True)

    text = path.read_text()
    assert "continue with caution" not in text
    assert "Lesson: quote the table number." in text
    assert hermes.inspect_profile("reviewer", live=False)["ready"]


def test_restore_reinserts_a_deleted_privacy_block(isolated_env) -> None:
    profile = make_profile(isolated_env)
    hermes.install_skill("reviewer", apply=True)
    path = profile / "skills" / "journal-article-review" / "SKILL.md"
    text = path.read_text()
    start = text.index("## Privacy gate")
    end = text.index("## Development loop")
    path.write_text(text[:start] + text[end:])
    assert hermes.inspect_profile("reviewer", live=False)["skill_privacy_block"] == "missing"

    hermes.restore_privacy_block("reviewer", apply=True)

    assert path.read_text() == text


def test_install_update_keeps_hermes_lessons(isolated_env) -> None:
    profile = make_profile(isolated_env)
    hermes.install_skill("reviewer", apply=True)
    skill = profile / "skills" / "journal-article-review"
    hermes_edit(skill)
    (skill / "references" / "lessons.md").write_text("Learned.\n")

    plan = hermes.install_skill("reviewer", apply=True)

    assert plan["updated"] == plan["merged"] == plan["kept_local"] == []
    assert not plan["privacy_block_restored"]
    assert "Lesson: quote the table number." in (skill / "SKILL.md").read_text()
    assert (skill / "references" / "lessons.md").read_text() == "Learned.\n"


def pretend_previous_release(profile: Path, relative: str, old: bytes) -> None:
    """Rewrite the baseline and manifest as if `old` had shipped in the installed release."""
    skill = profile / "skills" / "journal-article-review"
    (profile / hermes.BASELINE_DIR / "journal-article-review" / relative).write_bytes(old)
    manifest_path = skill / hermes.MANIFEST_NAME
    manifest = hermes.json.loads(manifest_path.read_text())
    manifest["files"][relative] = hermes.sha256_bytes(old)
    manifest_path.write_text(hermes.json.dumps(manifest))


def test_install_update_merges_upstream_changes_with_hermes_edits(isolated_env) -> None:
    profile = make_profile(isolated_env)
    hermes.install_skill("reviewer", apply=True)
    relative = "references/development.md"
    new = hermes._skill_files()[relative]
    first, rest = new.split(b"\n", 1)
    old = b"# An older heading\n" + rest
    pretend_previous_release(profile, relative, old)
    path = profile / "skills" / "journal-article-review" / relative
    path.write_bytes(old + b"\nLesson: keep the reviewer's wording.\n")

    plan = hermes.install_skill("reviewer", apply=True)

    assert plan["merged"] == [relative]
    merged = path.read_bytes()
    assert merged.startswith(first + b"\n")
    assert merged.endswith(b"Lesson: keep the reviewer's wording.\n")
    baseline = profile / hermes.BASELINE_DIR / "journal-article-review" / relative
    assert baseline.read_bytes() == new


def test_install_update_keeps_conflicting_edit_and_saves_upstream(isolated_env) -> None:
    profile = make_profile(isolated_env)
    hermes.install_skill("reviewer", apply=True)
    relative = "references/development.md"
    new = hermes._skill_files()[relative]
    _first, rest = new.split(b"\n", 1)
    pretend_previous_release(profile, relative, b"# An older heading\n" + rest)
    path = profile / "skills" / "journal-article-review" / relative
    path.write_bytes(b"# Hermes's own heading\n" + rest)

    plan = hermes.install_skill("reviewer", apply=True)

    assert plan["kept_local"] == [relative]
    assert path.read_bytes() == b"# Hermes's own heading\n" + rest
    upstream = Path(plan["upstream_copies"])
    assert upstream.parent == profile / hermes.UPDATES_DIR
    assert (upstream / relative).read_bytes() == new


def test_install_update_restores_block_in_edited_pre_marker_skill(isolated_env) -> None:
    profile = make_profile(isolated_env)
    hermes.install_skill("reviewer", apply=True)
    skill = profile / "skills" / "journal-article-review"
    legacy = (
        "---\nname: journal-article-review\n---\n\n# Journal article review development\n\n"
        "## Privacy gate\n\nRun `creview hermes doctor` once before reading.\n\n"
        "## Development loop\n\nLesson: one issue at a time.\n"
    )
    (skill / "SKILL.md").write_text(legacy)
    shutil.rmtree(profile / hermes.BASELINE_DIR)
    manifest_path = skill / hermes.MANIFEST_NAME
    manifest = hermes.json.loads(manifest_path.read_text())
    manifest["files"]["SKILL.md"] = hermes.sha256_bytes(b"an unedited older release")
    manifest_path.write_text(hermes.json.dumps(manifest))

    plan = hermes.install_skill("reviewer", apply=True)

    assert plan["kept_local"] == ["SKILL.md"]
    assert plan["privacy_block_restored"]
    text = (skill / "SKILL.md").read_text()
    assert "once before reading" not in text
    assert "Lesson: one issue at a time." in text
    assert hermes.privacy_block_status(text) == "match"


def test_install_update_removes_dropped_managed_files(isolated_env) -> None:
    profile = make_profile(isolated_env)
    hermes.install_skill("reviewer", apply=True)
    skill = profile / "skills" / "journal-article-review"
    old = skill / "references" / "retired.md"
    old.write_text("from an older release")
    manifest_path = skill / hermes.MANIFEST_NAME
    manifest = hermes.json.loads(manifest_path.read_text())
    manifest["files"]["references/retired.md"] = hermes.sha256_file(old)
    manifest_path.write_text(hermes.json.dumps(manifest))

    plan = hermes.install_skill("reviewer", apply=True)

    assert plan["removed"] == ["references/retired.md"]
    assert not old.exists()
    assert "references/retired.md" not in hermes.json.loads(manifest_path.read_text())["files"]


def test_install_update_keeps_dropped_file_that_hermes_edited(isolated_env) -> None:
    profile = make_profile(isolated_env)
    hermes.install_skill("reviewer", apply=True)
    skill = profile / "skills" / "journal-article-review"
    old = skill / "references" / "retired.md"
    manifest_path = skill / hermes.MANIFEST_NAME
    manifest = hermes.json.loads(manifest_path.read_text())
    manifest["files"]["references/retired.md"] = hermes.sha256_bytes(b"as shipped")
    manifest_path.write_text(hermes.json.dumps(manifest))
    old.write_text("as shipped, plus a lesson")

    plan = hermes.install_skill("reviewer", apply=True)

    assert plan["removed"] == []
    assert plan["kept_local"] == ["references/retired.md"]
    assert old.read_text() == "as shipped, plus a lesson"


def test_install_replaces_unmanaged_copy_only_on_request(isolated_env) -> None:
    profile = make_profile(isolated_env)
    skill = profile / "skills" / "journal-article-review"
    write_exact_skill(skill)
    (skill / "SKILL.md").write_text("manually copied older version")
    with pytest.raises(ReviewError, match="--replace-unmanaged"):
        hermes.install_skill("reviewer", apply=True)

    plan = hermes.install_skill("reviewer", apply=True, replace_unmanaged=True)

    backup = Path(plan["backup"])
    assert backup.parent == profile / "creview-skill-backups"
    assert (backup / "SKILL.md").read_text() == "manually copied older version"
    assert (skill / hermes.MANIFEST_NAME).is_file()
    assert hermes.inspect_profile("reviewer", live=False)["skill_privacy_block"] == "match"


def test_doctor_reports_stale_managed_skill(isolated_env) -> None:
    profile = make_profile(isolated_env)
    hermes.install_skill("reviewer", apply=True)
    skill = profile / "skills" / "journal-article-review"
    (skill / "SKILL.md").write_text("older release")
    manifest_path = skill / hermes.MANIFEST_NAME
    manifest = hermes.json.loads(manifest_path.read_text())
    manifest["files"]["SKILL.md"] = hermes.sha256_file(skill / "SKILL.md")
    manifest_path.write_text(hermes.json.dumps(manifest))

    report = hermes.inspect_profile("reviewer", live=False)

    assert not report["ready"]
    assert any("hermes install --apply" in problem for problem in report["problems"])


def test_hermes_home_defaults_to_local_app_data_on_windows(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(hermes, "_windows", lambda: True)
    assert hermes.hermes_home() == tmp_path / "hermes"
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "custom"))
    assert hermes.hermes_home() == tmp_path / "custom"


def test_doctor_rejects_cloud_endpoint_and_fallback(isolated_env) -> None:
    profile = make_profile(isolated_env)
    config = yaml.safe_load((profile / "config.yaml").read_text())
    config["providers"]["local"]["base_url"] = "https://api.example.com/v1"
    config["fallback_model"] = "cloud-model"
    (profile / "config.yaml").write_text(yaml.safe_dump(config))
    hermes.install_skill("reviewer", apply=True)
    report = hermes.inspect_profile("reviewer", live=False)
    assert not report["ready"]
    assert any("endpoint" in problem for problem in report["problems"])
    assert any("fallback" in problem for problem in report["problems"])


def test_doctor_ignores_nonrouting_fallback_settings(isolated_env) -> None:
    profile = make_profile(isolated_env)
    config = yaml.safe_load((profile / "config.yaml").read_text())
    config["paste_collapse_threshold_fallback"] = 5
    (profile / "config.yaml").write_text(yaml.safe_dump(config))
    hermes.install_skill("reviewer", apply=True)

    report = hermes.inspect_profile("reviewer", live=False)

    assert report["ready"]


def test_doctor_accepts_current_hermes_toolset_schema(isolated_env) -> None:
    profile = make_profile(isolated_env)
    config = yaml.safe_load((profile / "config.yaml").read_text())
    config.pop("tools")
    config["toolsets"] = ["hermes-cli"]
    config["platform_toolsets"] = {"cli": ["file", "terminal", "skills"]}
    (profile / "config.yaml").write_text(yaml.safe_dump(config))
    hermes.install_skill("reviewer", apply=True)

    report = hermes.inspect_profile("reviewer", live=False)

    assert report["ready"]


def test_default_profile_accepts_external_skill_and_endpoint_without_v1(isolated_env) -> None:
    root = isolated_env / "hermes"
    root.mkdir(parents=True)
    external = isolated_env / "checkout" / "skills" / "journal-article-review"
    write_exact_skill(external)
    config = {
        "model": {"default": "qwen3.8-flash-next", "provider": "local"},
        "providers": {"local": {"base_url": "http://127.0.0.1:8091"}},
        "tools": {"enabled_toolsets": ["terminal", "file"]},
        "skills": {"external_dirs": [str(external.parent)]},
    }
    (root / "config.yaml").write_text(yaml.safe_dump(config))

    report = hermes.inspect_profile(None, live=False)

    assert report["ready"]
    assert report["profile"] == "default"
    assert report["profile_root"] == str(root)
    assert report["skill_source"] == "external_dir"
    assert report["skill_path"] == str(external)


def test_local_unmanaged_exact_skill_is_accepted(isolated_env) -> None:
    profile = make_profile(isolated_env)
    write_exact_skill(profile / "skills" / "journal-article-review")
    report = hermes.inspect_profile("reviewer", live=False)
    assert report["ready"]
    assert report["skill_source"] == "profile_local"


def test_named_session_uses_effective_hermes_home(isolated_env, monkeypatch) -> None:
    active_home = isolated_env / "active-profile"
    monkeypatch.setenv("HERMES_HOME", str(active_home))
    monkeypatch.setenv("HERMES_SESSION_PROFILE", "reviewer")
    active_home.mkdir()
    config = {
        "model": {"default": "qwen3.8-flash-next", "provider": "local"},
        "providers": {"local": {"base_url": "http://127.0.0.1:8091/v1"}},
        "tools": {"enabled_toolsets": ["terminal", "file"]},
    }
    (active_home / "config.yaml").write_text(yaml.safe_dump(config))
    write_exact_skill(active_home / "skills" / "journal-article-review")

    report = hermes.inspect_profile(None, live=False)

    assert report["ready"]
    assert report["profile"] == "reviewer"
    assert report["profile_root"] == str(active_home)


def test_profile_flag_session_is_named_after_its_profile_home(isolated_env, monkeypatch) -> None:
    # `hermes -p reviewer` sets HERMES_HOME to the profile directory and no profile variable.
    profile = make_profile(isolated_env)
    hermes.install_skill("reviewer", apply=True)
    monkeypatch.setenv("HERMES_HOME", str(profile))

    report = hermes.inspect_profile(None, live=False)

    assert report["ready"]
    assert report["profile"] == "reviewer"
    assert report["profile_root"] == str(profile)


def test_packaged_skill_includes_nested_reference_files() -> None:
    files = hermes._skill_files()
    assert "references/designs/index.md" in files
    assert "references/designs/qualitative.md" in files
    assert not any("__pycache__" in name for name in files)


TRUSTED = "http://127.0.0.1:8091/v1"


def doctor_with(isolated_env, **changes) -> dict:
    profile = isolated_env / "hermes" / "profiles" / "reviewer"
    if not profile.exists():
        make_profile(isolated_env)
    config = yaml.safe_load((profile / "config.yaml").read_text())
    config.update(changes)
    (profile / "config.yaml").write_text(yaml.safe_dump(config))
    hermes.install_skill("reviewer", apply=True)
    return hermes.inspect_profile("reviewer", live=False)


def problems_mention(report: dict, text: str) -> bool:
    return any(text in problem for problem in report["problems"])


def test_doctor_rejects_auxiliary_task_routed_to_cloud(isolated_env) -> None:
    report = doctor_with(
        isolated_env,
        auxiliary={"compression": {"provider": "openrouter", "model": "google/gemini-3-flash"}},
    )
    assert not report["ready"]
    assert problems_mention(report, "auxiliary.compression routes to provider 'openrouter'")


def test_doctor_accepts_auxiliary_tasks_on_main_or_trusted_gateway(isolated_env) -> None:
    report = doctor_with(
        isolated_env,
        auxiliary={
            "compression": {"provider": "auto", "model": ""},
            "title_generation": {"provider": "main"},
            "vision": {"provider": "custom", "base_url": TRUSTED},
            "background_review": {"provider": "local"},
            "free_only": False,
        },
    )
    assert report["ready"], report["problems"]
    targets = {route["path"]: route["target"] for route in report["routes"]}
    assert targets["auxiliary.compression"] == "main"
    assert targets["auxiliary.vision"] == "trusted"
    assert targets["auxiliary.background_review"] == "trusted"


def test_doctor_requires_trusted_models_for_other_gateway_models(isolated_env, monkeypatch) -> None:
    changes = {"auxiliary": {"compression": {"provider": "auto", "model": "gemma-4-31b"}}}
    report = doctor_with(isolated_env, **changes)
    assert problems_mention(report, "selects model 'gemma-4-31b'")

    monkeypatch.setenv("CREVIEW_TRUSTED_MODELS", "gemma-4-31b")
    report = hermes.inspect_profile("reviewer", live=False)
    assert report["ready"], report["problems"]
    assert report["trusted_models"] == ["qwen3.8-flash-next", "gemma-4-31b"]


def test_doctor_rejects_untrusted_base_url_and_bare_custom_fallback(isolated_env) -> None:
    report = doctor_with(
        isolated_env,
        auxiliary={
            "compression": {"base_url": "https://api.example.com/v1"},
            "vision": {"provider": "custom"},
        },
        fallback_providers=[{"provider": "ollama", "model": "qwen3.8-flash-next"}],
    )
    assert problems_mention(report, "auxiliary.compression sends requests to")
    assert not problems_mention(report, "auxiliary.vision")
    assert problems_mention(report, "fallback_providers[0] uses provider 'ollama' without base_url")


def test_doctor_accepts_typical_ollama_profile(isolated_env, monkeypatch) -> None:
    monkeypatch.setenv("CREVIEW_TRUSTED_MODEL_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("CREVIEW_MODEL", "qwen3:32b")
    report = doctor_with(
        isolated_env,
        model={
            "default": "qwen3:32b",
            "provider": "custom",
            "base_url": "http://localhost:11434/v1",
        },
        providers={},
        auxiliary={
            "compression": {"provider": "ollama", "base_url": "http://localhost:11434/v1"},
            "title_generation": {"provider": "ollama"},
        },
    )
    assert report["ready"], report["problems"]


def test_doctor_uses_lmstudio_default_url(isolated_env, monkeypatch) -> None:
    monkeypatch.setenv("CREVIEW_TRUSTED_MODEL_URL", "http://localhost:1234/v1")
    report = doctor_with(
        isolated_env,
        model={"default": "qwen3.8-flash-next", "provider": "lmstudio"},
        providers={},
        auxiliary={"vision": {"provider": "lmstudio"}},
    )
    assert report["ready"], report["problems"]
    assert report["base_url"] == "http://127.0.0.1:1234/v1"


def test_doctor_reports_missing_main_base_url(isolated_env) -> None:
    report = doctor_with(
        isolated_env, model={"default": "qwen3.8-flash-next", "provider": "ollama"}, providers={}
    )
    assert problems_mention(report, "model.base_url is not set")


def test_loopback_spellings_are_one_endpoint() -> None:
    from closed_review.routes import normalized_endpoint

    same = {
        normalized_endpoint(url)
        for url in (
            "http://localhost:11434/v1",
            "http://127.0.0.1:11434",
            "http://[::1]:11434/v1/",
            "http://0.0.0.0:11434/v1",
        )
    }
    assert len(same) == 1
    assert normalized_endpoint("http://localhost:11434") != normalized_endpoint(
        "http://localhost:8080"
    )
    assert normalized_endpoint("http://10.0.0.5:8000/v1") == "http://10.0.0.5:8000"


def test_doctor_checks_auxiliary_fallback_chain(isolated_env) -> None:
    report = doctor_with(
        isolated_env,
        auxiliary={"compression": {"fallback_chain": [{"provider": "nous", "model": "x"}]}},
    )
    assert problems_mention(report, "auxiliary.compression.fallback_chain[0] routes to provider")


def test_doctor_rejects_auto_main_provider(isolated_env) -> None:
    report = doctor_with(
        isolated_env,
        model={"default": "qwen3.8-flash-next", "provider": "auto", "base_url": TRUSTED},
    )
    assert problems_mention(report, "model.provider is 'auto'")


def test_doctor_checks_delegation_and_fallbacks(isolated_env) -> None:
    report = doctor_with(
        isolated_env,
        delegation={"max_iterations": 50, "provider": "openrouter", "model": "deepseek/chat"},
        fallback_providers=[{"provider": "local", "model": "qwen3.8-flash-next"}],
    )
    assert problems_mention(report, "delegation routes to provider 'openrouter'")
    assert not problems_mention(report, "fallback_providers")


def test_doctor_accepts_delegation_to_trusted_gateway(isolated_env, monkeypatch) -> None:
    monkeypatch.setenv("CREVIEW_TRUSTED_MODELS", "gemma-4-31b")
    report = doctor_with(
        isolated_env,
        delegation={"base_url": TRUSTED, "model": "gemma-4-31b", "fallback_providers": []},
    )
    assert report["ready"], report["problems"]


def test_doctor_rejects_switchable_cloud_routes(isolated_env) -> None:
    report = doctor_with(
        isolated_env,
        model_aliases={"opus": {"model": "claude-opus-4-6", "provider": "anthropic"}},
        custom_providers=[{"name": "cloud", "base_url": "https://ollama.com/v1"}],
        moa={"presets": {"default": {"aggregator": {"provider": "openrouter", "model": "x"}}}},
        curator={"auxiliary": {"provider": "openrouter", "model": "y"}},
        memory={"provider": "honcho"},
    )
    for text in (
        "model_aliases.opus routes to provider 'anthropic'",
        "custom_providers[cloud] sends requests to",
        "moa.presets.default.aggregator routes to provider 'openrouter'",
        "curator.auxiliary routes to provider 'openrouter'",
        "memory.provider is 'honcho'",
    ):
        assert problems_mention(report, text), text


def test_doctor_reads_auxiliary_environment_overrides(isolated_env, monkeypatch) -> None:
    monkeypatch.setenv("AUXILIARY_VISION_PROVIDER", "openrouter")
    report = doctor_with(isolated_env)
    assert problems_mention(report, "AUXILIARY_VISION_* environment routes to provider")


def test_doctor_warns_about_unpinned_vision_when_vision_lane_credentials_exist(
    isolated_env,
) -> None:
    profile = make_profile(isolated_env)
    (profile / ".env").write_text("export OPENROUTER_API_KEY='sk-or-test'\n")
    report = doctor_with(isolated_env)
    assert report["ready"], report["problems"]
    assert any("auxiliary.vision is not pinned" in w for w in report["warnings"])
    assert all("sk-or-test" not in text for text in [*report["problems"], *report["warnings"]])
    assert report["cloud_credentials"] == [
        {"source": ".env", "name": "OPENROUTER_API_KEY", "provider": "openrouter"}
    ]

    pinned = doctor_with(isolated_env, auxiliary={"vision": {"provider": "local"}})
    assert pinned["ready"], pinned["problems"]
    assert not any("auxiliary.vision" in warning for warning in pinned["warnings"])
    assert any("OPENROUTER_API_KEY" in warning for warning in pinned["warnings"])


def test_doctor_warns_about_other_cloud_credentials(isolated_env) -> None:
    profile = make_profile(isolated_env)
    (profile / "auth.json").write_text(
        '{"providers": {}, "active_provider": null, "credential_pool": {"copilot": [{"k": 1}]}}'
    )
    report = doctor_with(isolated_env)
    assert report["ready"], report["problems"]
    assert any("copilot" in warning for warning in report["warnings"])


def test_doctor_ignores_openai_key_for_the_trusted_gateway(isolated_env) -> None:
    profile = make_profile(isolated_env)
    (profile / ".env").write_text(f"OPENAI_BASE_URL={TRUSTED}\nOPENAI_API_KEY=local\n")
    report = doctor_with(isolated_env)
    assert report["cloud_credentials"] == []


def test_doctor_warns_about_outbound_toolsets_and_mcp_servers(isolated_env) -> None:
    report = doctor_with(
        isolated_env,
        tools={"enabled_toolsets": ["terminal", "file", "web", "browser"]},
        mcp_servers={"literature": {"url": "https://mcp.example.com"}},
    )
    assert report["ready"], report["problems"]
    assert any("toolsets browser, web" in warning for warning in report["warnings"])
    assert any("MCP servers literature" in warning for warning in report["warnings"])

    quiet = doctor_with(
        isolated_env,
        tools={"enabled_toolsets": ["terminal", "file", "web"]},
        agent={"disabled_toolsets": ["web"]},
        mcp_servers={},
    )
    assert not any("toolsets" in warning for warning in quiet["warnings"])


def test_install_refuses_when_an_external_checkout_provides_the_skill(isolated_env) -> None:
    profile = make_profile(isolated_env)
    external = isolated_env / "checkout" / "skills"
    write_exact_skill(external / "journal-article-review")
    config = yaml.safe_load((profile / "config.yaml").read_text())
    config["skills"] = {"external_dirs": [str(external)]}
    (profile / "config.yaml").write_text(yaml.safe_dump(config))

    with pytest.raises(ReviewError, match="external directory"):
        hermes.install_skill("reviewer")
    assert not (profile / "skills" / "journal-article-review").exists()


def test_doctor_requires_readable_session_messages(isolated_env) -> None:
    profile = make_profile(isolated_env)
    hermes.install_skill("reviewer", apply=True)
    (profile / "state.db").write_bytes(b"not a database")
    report = hermes.inspect_profile("reviewer", live=False)
    assert not report["ready"]
    assert problems_mention(report, "cannot read session messages")
