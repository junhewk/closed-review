from pathlib import Path

from closed_review.direct import prepare_direct_export


def test_prepare_direct_export_creates_private_parent(isolated_env: Path) -> None:
    prepared = prepare_direct_export()
    directory = Path(prepared["directory"])
    output = Path(prepared["output_path"])

    assert directory.parent == isolated_env / "data" / "exports"
    assert directory.stat().st_mode & 0o777 == 0o700
    assert (isolated_env / "data").stat().st_mode & 0o777 == 0o700
    assert output == directory / "journal-review.md"
    assert not output.exists()
    assert prepared["output_paths"] == {
        "development": str(directory / "review-development.md"),
        "authors": str(directory / "comments-to-authors.md"),
        "editor": str(directory / "comments-to-editor.md"),
    }
