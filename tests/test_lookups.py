import pytest

from closed_review.cases import create_case
from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, case_root
from closed_review.lookups import create_lookup, run_lookup


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self):
        return {"message": {"items": [{"DOI": "10.1/example", "title": ["Example"]}]}}


def test_lookup_requires_explicit_approval(isolated_env, monkeypatch) -> None:
    manuscript = isolated_env / "paper.md"
    manuscript.write_text("# Paper\n\nText.")
    case_id = create_case(manuscript, journal="Journal")["case_id"]
    request = create_lookup(case_id, "crossref", "exact approved query")
    with pytest.raises(ReviewError, match="explicit approval"):
        run_lookup(case_id, request["request_id"])
    monkeypatch.setattr("closed_review.lookups.httpx.get", lambda *args, **kwargs: FakeResponse())
    result = run_lookup(
        case_id,
        request["request_id"],
        approval_statement="I approve this exact Crossref query.",
    )
    assert result["status"] == "executed"
    assert result["query"] == "exact approved query"
    assert result["result"][0]["doi"] == "10.1/example"


def test_lookup_rejects_tampered_url(isolated_env) -> None:
    manuscript = isolated_env / "paper.md"
    manuscript.write_text("# Paper\n\nText.")
    case_id = create_case(manuscript, journal="Journal")["case_id"]
    request = create_lookup(case_id, "openalex", "approved words")
    request["url"] = "https://example.invalid/private"
    atomic_write_json(case_root(case_id) / "lookups" / f"{request['request_id']}.json", request)
    with pytest.raises(ReviewError, match="does not match"):
        run_lookup(
            case_id,
            request["request_id"],
            approval_statement="I approve this exact request.",
        )
