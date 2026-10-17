import pytest
from conftest import reviewer_says

from closed_review.cases import create_case
from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, case_root
from closed_review.lookups import create_lookup, run_lookup, show_lookup
from closed_review.session import start_session


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


def test_direct_review_lookups_belong_to_the_checked_session(isolated_env, monkeypatch) -> None:
    from test_workflow import setup_profile

    setup_profile(isolated_env)
    monkeypatch.setenv("HERMES_SESSION_ID", "unchecked")
    with pytest.raises(ReviewError, match="creview session start"):
        create_lookup(None, "crossref", "Strech Sofaer 2012 systematic reviews of reasons")
    monkeypatch.setenv("HERMES_SESSION_ID", "checked")
    start_session("reviewer", live=False)
    request = create_lookup(None, "crossref", "Strech Sofaer 2012 systematic reviews of reasons")
    assert request["status"] == "pending_approval" and "case_id" not in request
    with pytest.raises(ReviewError, match="explicit approval"):
        run_lookup(None, request["request_id"])
    monkeypatch.setattr("closed_review.lookups.httpx.get", lambda *args, **kwargs: FakeResponse())
    # The approval must be the reviewer's own words, sent after the request was prepared.
    with pytest.raises(ReviewError, match="cannot read this Hermes session's messages"):
        run_lookup(None, request["request_id"], approval_statement="Yes, run that query.")
    reviewer_says(isolated_env / "hermes", "checked", "What does Crossref have on it?")
    with pytest.raises(ReviewError, match="not in any of those messages"):
        run_lookup(None, request["request_id"], approval_statement="Yes, run that query.")
    reviewer_says(isolated_env / "hermes", "checked", "Yes, run that query.")
    result = run_lookup(None, request["request_id"], approval_statement="Yes, run that query.")
    assert result["approval"]["verified"] is True
    assert result["status"] == "executed"
    assert show_lookup(None, request["request_id"])["result"][0]["doi"] == "10.1/example"

    monkeypatch.setenv("HERMES_SESSION_ID", "another")
    start_session("reviewer", live=False)
    with pytest.raises(ReviewError, match="does not exist"):
        show_lookup(None, request["request_id"])
