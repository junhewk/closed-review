from conftest import write_xlsx

from closed_review.cases import create_case
from closed_review.io import case_root, data_home


def test_case_snapshot_and_store_are_private(isolated_env) -> None:
    manuscript = isolated_env / "paper.md"
    manuscript.write_text("# Paper\n\nPrivate content.")
    case_id = create_case(manuscript, journal="Journal")["case_id"]
    root = case_root(case_id)
    assert data_home().stat().st_mode & 0o777 == 0o700
    assert root.stat().st_mode & 0o777 == 0o700
    original = next((root / "originals").iterdir())
    assert original.stat().st_mode & 0o777 == 0o600


def test_case_accepts_xlsx_supplement(isolated_env) -> None:
    manuscript = isolated_env / "paper.md"
    manuscript.write_text("# Paper\n\nPrivate content.")
    supplement = isolated_env / "data.xlsx"
    write_xlsx(supplement)
    manifest = create_case(manuscript, journal="Journal", supplements=[supplement])
    source = manifest["sources"][1]
    assert source["format"] == "xlsx"
    assert source["segment_count"] == 2


def test_store_privacy_uses_the_user_profile_on_windows(tmp_path, monkeypatch) -> None:
    from closed_review import io

    inside = tmp_path / "profile" / ".local" / "share" / "closed-review"
    inside.mkdir(parents=True)
    inside.chmod(0o777)
    outside = tmp_path / "shared" / "closed-review"
    outside.mkdir(parents=True)
    monkeypatch.setattr(io, "_windows", lambda: True)
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "profile"))

    assert io.permission_problem(inside) is None
    assert "outside your Windows user profile" in io.permission_problem(outside)

    monkeypatch.setattr(io, "_windows", lambda: False)
    assert "not private: 0o777" in io.permission_problem(inside)
    inside.chmod(0o700)
    assert io.permission_problem(inside) is None
