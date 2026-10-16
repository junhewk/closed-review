import json
from pathlib import Path

import pytest
import yaml

from closed_review import hermes
from closed_review.cases import attest_case, create_case
from closed_review.errors import ReviewError
from closed_review.io import case_root
from closed_review.review import (
    dismiss_finding,
    export_review,
    next_finding,
    next_item,
    prepare_draft,
    prepare_finding_response,
    propose_case_plan,
    respond_finding,
    review_status,
    set_case_plan,
    start_batch,
    start_review,
    submit_draft,
    submit_findings,
)


def setup_profile(tmp_path: Path) -> None:
    profile = tmp_path / "hermes" / "profiles" / "reviewer"
    profile.mkdir(parents=True)
    (profile / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "model": {"default": "qwen3.8-flash-next", "provider": "local"},
                "providers": {"local": {"base_url": "http://127.0.0.1:8091/v1"}},
                "tools": {"enabled_toolsets": ["terminal", "file", "skills"]},
            }
        )
    )
    hermes.install_skill("reviewer", apply=True)


def new_case(tmp_path: Path, *, plan: bool = True) -> str:
    manuscript = tmp_path / "paper.md"
    manuscript.write_text(
        "# Introduction\n\nThis study claims a broad contribution without defining its "
        "target population.\n\n"
        "# Methods\n\nWe reviewed 10 records and used a predefined coding framework.\n"
    )
    case_id = create_case(manuscript, journal="Fixture Journal")["case_id"]
    if plan:
        # One segment over the whole fixture keeps the batch and session tests about batching.
        draft_path = Path(propose_case_plan(case_id)["plan_draft_path"])
        draft = json.loads(draft_path.read_text())
        blocks = [block for segment in draft["segments"] for block in segment["block_ids"]]
        draft["segments"] = [
            {
                "id": "ls-01",
                "title": "Whole fixture",
                "source_id": "manuscript",
                "block_ids": blocks,
                "theme": "",
                "profile_areas": [],
                "tier": "medium",
            }
        ]
        draft_path.write_text(json.dumps(draft))
        set_case_plan(case_id, draft_path)
    return case_id


def accept_pending_findings(case_id: str) -> None:
    while review_status(case_id)["next_action"] == "finding_next":
        issued = next_finding(case_id)
        for item in issued["items"]:
            proposal_path = Path(item["proposal_path"])
            proposal = json.loads(proposal_path.read_text())
            proposal.update(
                {
                    "disposition": "accepted",
                    "reviewer_reasoning": "The reviewer accepts this issue and its scope.",
                    "agent_synthesis": "The candidate was retained without broadening it.",
                }
            )
            proposal_path.write_text(json.dumps(proposal))
            respond_finding(case_id, proposal["finding_id"], proposal_path)


def test_review_requires_attestation(isolated_env) -> None:
    setup_profile(isolated_env)
    case_id = new_case(isolated_env)
    with pytest.raises(ReviewError, match="attestation"):
        start_review(case_id, "reviewer", live_doctor=False)


def test_complete_review_and_export(isolated_env) -> None:
    setup_profile(isolated_env)
    case_id = new_case(isolated_env)
    attest_case(case_id, "I confirm that this journal permits the intended local AI assistance.")
    start_review(case_id, "reviewer", live_doctor=False)
    added = False
    while True:
        status = review_status(case_id)
        if status["next_action"] == "draft_prepare":
            break
        if status["next_action"] == "finding_next":
            accept_pending_findings(case_id)
            continue
        if status["next_action"] == "review_batch_start":
            start_batch(case_id)
        issued = next_item(case_id)
        proposal_path = Path(issued["proposal_path"])
        proposal = json.loads(proposal_path.read_text())
        proposal["task_status"] = "reviewed"
        if issued["task"]["kind"] in {"source", "segment"} and not added:
            segment = issued["task"]["content"][1]
            proposal["findings"] = [
                {
                    "category": "contribution_scope",
                    "severity": "major",
                    "audience": "authors",
                    "source_evidence": [
                        {
                            "source_id": issued["task"]["source_id"],
                            "locator": segment["locator"],
                            "quote": "broad contribution",
                        }
                    ],
                    "critique": "The target population is not defined.",
                    "why_it_matters": "The scope of the contribution cannot be evaluated.",
                    "requested_action": "Define the target population and bound the claim.",
                    "confidence": "high",
                    "verification_state": "verified",
                    "external_lookup_ids": [],
                }
            ]
            added = True
        proposal_path.write_text(json.dumps(proposal))
        submit_findings(case_id, proposal_path)

    prepared = prepare_draft(case_id)
    draft_path = Path(prepared["proposal_path"])
    draft = json.loads(draft_path.read_text())
    draft.update(
        {
            "author_summary": "The manuscript presents a coding study.",
            "author_overall_assessment": (
                "The question is relevant but its population needs definition."
            ),
            "editor_confidential_comments": (
                "The central scope issue should be resolved before publication."
            ),
            "recommendation": "major_revision",
            "recommendation_rationale": (
                "The scope affects interpretation of the central contribution."
            ),
            "recommendation_user_reasoning": (
                "The reviewer selected major revision because the central scope remains reparable."
            ),
        }
    )
    draft_path.write_text(json.dumps(draft))
    submit_draft(case_id, draft_path)
    result = export_review(case_id, isolated_env / "export")
    assert "comments-to-authors.md" in result["files"]
    receipt = json.loads((isolated_env / "export" / "receipt.json").read_text())
    assert result["receipt_id"] == receipt["receipt_id"]
    assert [subject["role"] for subject in receipt["subjects"]] == [
        "authors",
        "editor",
        "development",
    ]
    assert receipt["environment"]["doctor"] == "pass"
    assert receipt["environment"]["endpoint_class"] == "loopback"
    assert receipt["preflight"]["status"] == "passed"
    assert receipt["preflight"]["session_source"] == "audited_case"
    assert "target population" in (isolated_env / "export" / "comments-to-authors.md").read_text()
    editor = (isolated_env / "export" / "comments-to-editor.md").read_text()
    assert "Major Revision" in editor
    assert (
        "provisional"
        not in (isolated_env / "export" / "comments-to-authors.md").read_text().lower()
    )
    finding_id = json.loads(isolated_env.joinpath("export", "review.json").read_text())["findings"][
        0
    ]["finding_id"]
    dismiss_finding(case_id, finding_id, "User determined that the scope was defined elsewhere.")
    with pytest.raises(ReviewError, match="complete draft"):
        export_review(case_id, isolated_env / "export-2")


def test_finding_quote_must_be_verbatim(isolated_env) -> None:
    setup_profile(isolated_env)
    case_id = new_case(isolated_env)
    attest_case(case_id, "The journal permits this local analysis and I confirm permission.")
    start_review(case_id, "reviewer", live_doctor=False)
    start_batch(case_id)
    issued = next_item(case_id)
    proposal_path = Path(issued["proposal_path"])
    proposal = json.loads(proposal_path.read_text())
    proposal["task_status"] = "reviewed"
    segment = issued["task"]["content"][1]
    proposal["findings"] = [
        {
            "category": "organization_clarity",
            "severity": "minor",
            "audience": "authors",
            "source_evidence": [
                {"source_id": "manuscript", "locator": segment["locator"], "quote": "not present"}
            ],
            "critique": "A problem.",
            "why_it_matters": "It matters.",
            "requested_action": "Fix it.",
            "confidence": "high",
            "verification_state": "verified",
            "external_lookup_ids": [],
        }
    ]
    proposal_path.write_text(json.dumps(proposal))
    with pytest.raises(ReviewError, match="not verbatim"):
        submit_findings(case_id, proposal_path)


def test_candidate_requires_reviewer_development_before_compilation(isolated_env) -> None:
    setup_profile(isolated_env)
    case_id = new_case(isolated_env)
    attest_case(case_id, "The journal permits this local analysis and I confirm permission.")
    start_review(case_id, "reviewer", live_doctor=False)
    start_batch(case_id)
    issued = next_item(case_id)
    proposal_path = Path(issued["proposal_path"])
    proposal = json.loads(proposal_path.read_text())
    proposal["task_status"] = "reviewed"
    segment = issued["task"]["content"][1]
    proposal["findings"] = [
        {
            "category": "contribution_scope",
            "severity": "major",
            "audience": "authors",
            "source_evidence": [
                {
                    "source_id": "manuscript",
                    "locator": segment["locator"],
                    "quote": "broad contribution",
                }
            ],
            "critique": "The contribution may be too broad.",
            "why_it_matters": "The claimed scope cannot yet be evaluated.",
            "requested_action": "Define and bound the contribution.",
            "solution_candidates": ["Narrow the claim.", "Add evidence for the broader scope."],
            "literature_evidence": [
                {
                    "tier": "model_lead",
                    "citation": "Relevant scope literature",
                    "relevance": "A lead for testing the novelty claim.",
                    "verification_state": "unverified",
                }
            ],
            "confidence": "medium",
            "verification_state": "inference",
            "external_lookup_ids": [],
        }
    ]
    proposal_path.write_text(json.dumps(proposal))
    submitted = submit_findings(case_id, proposal_path)
    finding = submitted["candidate_findings"][0]

    assert review_status(case_id)["next_action"] == "finding_next"
    with pytest.raises(ReviewError, match="coverage is incomplete|development is incomplete"):
        prepare_draft(case_id)

    response_path = Path(prepare_finding_response(case_id, finding["finding_id"])["proposal_path"])
    response = json.loads(response_path.read_text())
    response.update(
        {
            "disposition": "accepted",
            "reviewer_reasoning": (
                "The scope concern is valid, but the comment should allow either narrowing or "
                "additional evidence rather than prescribe one solution."
            ),
            "agent_synthesis": (
                "Retained the issue and both proportionate solution paths without strengthening it."
            ),
        }
    )
    response_path.write_text(json.dumps(response))
    developed = respond_finding(case_id, finding["finding_id"], response_path)

    assert developed["status"] == "accepted"
    assert developed["discussion_history"][0]["reviewer_reasoning"].startswith("The scope concern")
    assert developed["progress"]["accepted"] == 1


def test_profile_drift_blocks_manuscript_read(isolated_env) -> None:
    setup_profile(isolated_env)
    case_id = new_case(isolated_env)
    attest_case(case_id, "The journal permits this local analysis and I confirm permission.")
    start_review(case_id, "reviewer", live_doctor=False)
    config_path = isolated_env / "hermes" / "profiles" / "reviewer" / "config.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["providers"]["local"]["base_url"] = "https://cloud.example/v1"
    config_path.write_text(yaml.safe_dump(config))
    with pytest.raises(ReviewError, match="privacy gate"):
        next_item(case_id)


def test_review_requires_and_completes_bounded_phase_batch(isolated_env) -> None:
    setup_profile(isolated_env)
    case_id = new_case(isolated_env)
    attest_case(case_id, "The journal permits this local analysis and I confirm permission.")
    started = start_review(case_id, "reviewer", live_doctor=False)
    assert started["phase"] == "evidence_coverage"
    assert started["next_action"] == "review_batch_start"
    assert next_item(case_id)["state"] == "batch_required"

    batch = start_batch(case_id, limit=5)
    assert batch["batch"]["phase"] == "evidence_coverage"
    assert len(batch["batch"]["task_ids"]) == 1
    issued = next_item(case_id)
    proposal_path = Path(issued["proposal_path"])
    proposal = json.loads(proposal_path.read_text())
    proposal["task_status"] = "reviewed"
    proposal_path.write_text(json.dumps(proposal))
    submitted = submit_findings(case_id, proposal_path)

    assert submitted["review"]["active_batch"] is None
    assert submitted["review"]["last_batch"]["completed"] == 1
    assert submitted["review"]["phase"] == "cross_cutting_appraisal"
    assert submitted["review"]["next_action"] == "review_batch_start"
    rubric_batch = start_batch(case_id)
    assert rubric_batch["batch"]["phase"] == "cross_cutting_appraisal"
    assert len(rubric_batch["batch"]["task_ids"]) == 3


def test_review_batch_limit_is_capped(isolated_env) -> None:
    setup_profile(isolated_env)
    case_id = new_case(isolated_env)
    attest_case(case_id, "The journal permits this local analysis and I confirm permission.")
    start_review(case_id, "reviewer", live_doctor=False)
    with pytest.raises(ReviewError, match="between 1 and 5"):
        start_batch(case_id, limit=6)


def test_existing_unbatched_review_resumes_at_current_item(isolated_env) -> None:
    setup_profile(isolated_env)
    case_id = new_case(isolated_env)
    attest_case(case_id, "The journal permits this local analysis and I confirm permission.")
    start_review(case_id, "reviewer", live_doctor=False)
    state_path = case_root(case_id) / "review-state.json"
    state = json.loads(state_path.read_text())
    current_id = state["coverage"][0]["id"]
    state["schema_version"] = "1"
    state["current_item"] = current_id
    state.pop("active_batch")
    state.pop("last_batch")
    state_path.write_text(json.dumps(state))
    state_path.chmod(0o600)

    status = review_status(case_id)
    assert status["next_action"] == "review_batch_start"
    start_batch(case_id)
    issued = next_item(case_id)
    assert issued["task"]["id"] == current_id


def test_hermes_session_boundary_blocks_intake_and_consecutive_batches(
    isolated_env, monkeypatch
) -> None:
    setup_profile(isolated_env)
    case_id = new_case(isolated_env)
    attest_case(case_id, "The journal permits this local analysis and I confirm permission.")
    monkeypatch.setenv("HERMES_SESSION_ID", "intake-session")
    start_review(case_id, "reviewer", live_doctor=False)
    assert start_batch(case_id)["state"] == "session_checkpoint_required"

    monkeypatch.setenv("HERMES_SESSION_ID", "evidence-session")
    start_batch(case_id)
    issued = next_item(case_id)
    proposal_path = Path(issued["proposal_path"])
    proposal = json.loads(proposal_path.read_text())
    proposal["task_status"] = "reviewed"
    proposal_path.write_text(json.dumps(proposal))
    submit_findings(case_id, proposal_path)

    blocked = start_batch(case_id)
    assert blocked["state"] == "session_checkpoint_required"
    monkeypatch.setenv("HERMES_SESSION_ID", "appraisal-session")
    assert start_batch(case_id)["state"] == "batch_started"


def test_finalization_requires_new_hermes_session(isolated_env, monkeypatch) -> None:
    setup_profile(isolated_env)
    case_id = new_case(isolated_env)
    attest_case(case_id, "The journal permits this local analysis and I confirm permission.")
    start_review(case_id, "reviewer", live_doctor=False)
    state_path = case_root(case_id) / "review-state.json"
    state = json.loads(state_path.read_text())
    for item in [*state["coverage"], *state["rubric"]]:
        item["status"] = "reviewed"
    state["last_batch"] = {"batch_id": "batch-test", "session_id": "last-appraisal"}
    state_path.write_text(json.dumps(state))
    state_path.chmod(0o600)

    monkeypatch.setenv("HERMES_SESSION_ID", "last-appraisal")
    with pytest.raises(ReviewError, match="new Hermes session"):
        prepare_draft(case_id)
    monkeypatch.setenv("HERMES_SESSION_ID", "finalization-session")
    assert prepare_draft(case_id)["case_id"] == case_id


def test_compilation_can_omit_recommendation(isolated_env, monkeypatch) -> None:
    setup_profile(isolated_env)
    case_id = new_case(isolated_env)
    attest_case(case_id, "The journal permits this local analysis and I confirm permission.")
    start_review(case_id, "reviewer", live_doctor=False)
    state_path = case_root(case_id) / "review-state.json"
    state = json.loads(state_path.read_text())
    for item in [*state["coverage"], *state["rubric"]]:
        item["status"] = "reviewed"
    state["last_batch"] = {"batch_id": "batch-test", "session_id": "prior-session"}
    state_path.write_text(json.dumps(state))
    state_path.chmod(0o600)
    monkeypatch.setenv("HERMES_SESSION_ID", "compile-session")

    prepared = prepare_draft(case_id)
    draft_path = Path(prepared["proposal_path"])
    proposal = json.loads(draft_path.read_text())
    proposal.update(
        {
            "author_summary": "The manuscript addresses a relevant question.",
            "author_overall_assessment": "This compilation intentionally contains no verdict.",
        }
    )
    draft_path.write_text(json.dumps(proposal))
    submitted = submit_draft(case_id, draft_path)
    export_review(case_id, isolated_env / "no-recommendation")

    assert submitted["recommendation"] is None
    editor = (isolated_env / "no-recommendation" / "comments-to-editor.md").read_text()
    assert "recommendation" not in editor.lower()
    assert (isolated_env / "no-recommendation" / "review-development.md").is_file()


def test_legacy_active_finding_migrates_without_inventing_reasoning(isolated_env) -> None:
    setup_profile(isolated_env)
    case_id = new_case(isolated_env)
    attest_case(case_id, "The journal permits this local analysis and I confirm permission.")
    start_review(case_id, "reviewer", live_doctor=False)
    root = case_root(case_id)
    state_path = root / "review-state.json"
    state = json.loads(state_path.read_text())
    state["schema_version"] = "2"
    state["finding_ids"] = ["finding-legacy"]
    state_path.write_text(json.dumps(state))
    state_path.chmod(0o600)
    finding_path = root / "findings" / "finding-legacy.json"
    finding_path.write_text(
        json.dumps(
            {
                "finding_id": "finding-legacy",
                "status": "active",
                "requested_action": "Clarify the claim.",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        )
    )
    finding_path.chmod(0o600)

    status = review_status(case_id)
    migrated = json.loads(finding_path.read_text())

    assert status["finding_status_counts"]["accepted"] == 1
    assert migrated["status"] == "accepted"
    assert migrated["discussion_history"][0]["reviewer_reasoning"] is None
    assert review_status(case_id)["finding_status_counts"]["accepted"] == 1


def test_review_requires_a_complete_segment_plan(isolated_env) -> None:
    setup_profile(isolated_env)
    case_id = new_case(isolated_env, plan=False)
    attest_case(case_id, "I confirm that this journal permits the intended local AI assistance.")
    with pytest.raises(ReviewError, match="set a segment plan first"):
        start_review(case_id, "reviewer", live_doctor=False)

    draft_path = Path(propose_case_plan(case_id)["plan_draft_path"])
    draft = json.loads(draft_path.read_text())
    draft["segments"][0]["block_ids"] = draft["segments"][0]["block_ids"][:1]
    partial = isolated_env / "partial.json"
    partial.write_text(json.dumps(draft))
    with pytest.raises(ReviewError, match="uncovered"):
        set_case_plan(case_id, partial)

    draft = json.loads(draft_path.read_text())
    blocks = [block for segment in draft["segments"] for block in segment["block_ids"]]
    draft["segments"] = [
        {
            "id": "ls-01",
            "title": "Claims",
            "source_id": "manuscript",
            "block_ids": blocks[:2],
            "theme": "scope of the claims",
            "profile_areas": [],
            "tier": "medium",
        },
        {
            "id": "ls-02",
            "title": "Methods",
            "source_id": "manuscript",
            "block_ids": blocks[1:],
            "theme": "sampling",
            "profile_areas": ["sampling"],
            "tier": "high",
        },
    ]
    refined = isolated_env / "refined.json"
    refined.write_text(json.dumps(draft))
    set_case_plan(case_id, refined)
    started = start_review(case_id, "reviewer", live_doctor=False)

    assert started["coverage_total"] == 2
    start_batch(case_id)
    task = next_item(case_id)["task"]
    assert task["kind"] == "segment"
    assert task["title"] == "Claims"
    assert [entry["id"] for entry in task["outline"]] == ["ls-01", "ls-02"]
    with pytest.raises(ReviewError, match="already started"):
        set_case_plan(case_id, refined)
