import json
from pathlib import Path

import pytest
from conftest import assert_mode

from closed_review.errors import ReviewError
from closed_review.references import (
    check_references,
    request_reference_metadata,
    run_reference_metadata,
    show_reference_check,
)


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self):
        return {
            "message": {
                "DOI": "10.1000/example",
                "title": ["Example source"],
                "published": {"date-parts": [[2020]]},
            }
        }


def test_author_year_reference_check_is_local_and_persisted(isolated_env: Path) -> None:
    manuscript = isolated_env / "paper.md"
    manuscript.write_text(
        "# Introduction\n\nA claim is attributed to Smith (2020) and (Missing, 2021).\n\n"
        "# References\n\nSmith, A. (2020). Example source. https://doi.org/10.1000/example\n\n"
        "Unused, B. (2018). Unused source. https://doi.org/10.1000/unused\n"
    )

    report = check_references(manuscript)

    assert report["citation_style"] == "author_year"
    assert report["parse_confidence"] == "high"
    kinds = {item["kind"] for item in report["issues"]}
    assert "citation_without_reference" in kinds
    assert "uncited_reference" in kinds
    assert show_reference_check(report["check_id"])["source_sha256"] == report["source_sha256"]
    report_path = isolated_env / "data" / "reference-checks" / f"{report['check_id']}.json"
    assert_mode(report_path, 0o600)
    assert_mode(report_path.parent, 0o700)


def test_numbered_reference_ranges_and_duplicate_doi(isolated_env: Path) -> None:
    manuscript = isolated_env / "numbered.md"
    manuscript.write_text(
        "# Text\n\nPrior work [1-2] and an absent source [4].\n\n"
        "# References\n\n[1] First. doi:10.1000/same\n\n"
        "[2] Second. doi:10.1000/same\n\n[3] Unused.\n"
    )

    report = check_references(manuscript)
    kinds = {item["kind"] for item in report["issues"]}

    assert report["citation_style"] == "numbered"
    assert {"citation_without_reference", "uncited_reference", "duplicate_doi"} <= kinds


def test_dense_line_numbers_do_not_force_numbered_reference_style(isolated_env: Path) -> None:
    manuscript = isolated_env / "line-numbered.md"
    line_numbers = " ".join(str(number) for number in range(1, 31))
    manuscript.write_text(
        f"{line_numbers} Claim (Smith, 2020; Jones, 2021).\n\n"
        f"{line_numbers} References {line_numbers} "
        "Smith, A. (2020). First source. "
        "Jones, B. (2021). Second source."
    )

    report = check_references(manuscript)

    assert report["citation_style"] == "author_year"
    assert report["reference_count"] == 2
    assert report["parse_confidence"] == "medium"
    assert not report["warnings"]
    assert any(
        item["kind"] == "dense_line_numbers_removed" for item in report["normalizations"]
    )


def test_extraction_breaks_are_normalized_not_reported_as_issues(isolated_env: Path) -> None:
    manuscript = isolated_env / "extracted.md"
    line_numbers = " ".join(str(number) for number in range(1, 31))
    manuscript.write_text(
        f"{line_numbers} Prior work (Ha lvorsen, 1999; Northern Health Council, 2019; "
        "Northern Health Council, 2025; Okonkwo, 1998; Núñez-Ålund, 2020).\n\n"
        f"References {line_numbers} "
        "Halvorsen, C. (1999). Fictional study of ward routines. "
        "Northern Health Council. (2019). Fictional position statement. "
        "Northern Health Council. (2025). Updated fictional position statement. "
        "Okonkwo, M. (1998). Fictional household survey. https://doi.org/10.5555/ XMPL199809205 "
        "Núñez-Ålund, C. (2020). Fictional consent interviews. "
        "https://doi.org/10.5555/ x1291- 020 -00495- 1"
    )

    report = check_references(manuscript)

    assert report["citation_style"] == "author_year"
    assert report["citation_count"] == 5
    assert report["reference_count"] == 5
    assert report["issues"] == []
    kinds = {item["kind"] for item in report["normalizations"]}
    assert {
        "dense_line_numbers_removed",
        "split_author_tokens_repaired",
        "doi_spacing_repaired",
    } <= kinds
    dois = {doi for entry in report["entries"] for doi in entry["dois"]}
    assert "10.5555/xmpl199809205" in dois
    assert "10.5555/x1291-020-00495-1" in dois


def test_metadata_manifest_requires_approval_and_is_immutable(
    isolated_env: Path, monkeypatch
) -> None:
    manuscript = isolated_env / "paper.md"
    manuscript.write_text(
        "Claim (Smith, 2020).\n\nReferences\n\n"
        "Smith, A. (2020). Example source. doi:10.1000/example\n"
    )
    report = check_references(manuscript)
    request = request_reference_metadata(report["check_id"], "crossref")

    assert request["status"] == "pending_approval"
    assert request["queries"][0]["url"].startswith("https://api.crossref.org/")
    with pytest.raises(ReviewError, match="explicit approval"):
        run_reference_metadata(report["check_id"], request["request_id"])

    request_path = (
        isolated_env
        / "data"
        / "reference-checks"
        / f"{request['request_id']}.json"
    )
    tampered = json.loads(request_path.read_text())
    tampered["queries"][0]["query"] = "changed"
    request_path.write_text(json.dumps(tampered))
    with pytest.raises(ReviewError, match="changed"):
        run_reference_metadata(
            report["check_id"],
            request["request_id"],
            approval_statement="I approve the displayed immutable manifest.",
        )

    request = request_reference_metadata(report["check_id"], "crossref")
    monkeypatch.setattr(
        "closed_review.references.httpx.get", lambda *args, **kwargs: FakeResponse()
    )
    result = run_reference_metadata(
        report["check_id"],
        request["request_id"],
        approval_statement="I approve the displayed immutable manifest.",
    )
    assert result["status"] == "executed"
    assert result["results"][0]["identity_status"] == "doi_match"
