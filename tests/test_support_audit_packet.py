import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from conftest import assert_mode
from test_support import begin, finish
from test_support import support_env as support_env

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, atomic_write_text, read_json, sha256_file
from closed_review.receipts import installed_identity
from closed_review.support import PROTOCOL
from closed_review.support.render import export
from closed_review.support.workflow import _load, _root

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prepare-support-audit.py"
SPEC = importlib.util.spec_from_file_location("support_audit_packet", SCRIPT)
packet = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(packet)


def copied_fixture(support_env, tmp_path, *, concern=True, malicious_title=False):
    run_id = begin(support_env)
    finish(run_id, concern=concern)
    run = _load(_root(run_id))
    if malicious_title:
        run["modules"]["statistics"]["observations"][0]["title"] = "<script>injected()</script>"
        atomic_write_json(_root(run_id) / "run.json", run)
    result = export(run_id)
    root = tmp_path / "copied-batch"
    profile = root / "case-01/hermes/profiles/pilot"
    destination = profile / "review-data/support" / run_id / "exports/dossier"
    shutil.copytree(result["directory"], destination)
    (profile / "work").mkdir()
    shutil.copyfile(support_env[0], profile / "work/manuscript.md")
    batch = root / "batch.json"
    atomic_write_json(
        batch,
        {
            "protocol": PROTOCOL,
            "synthetic_only": True,
            "identity": {"sums_sha256": run["identity"]["runner"]},
            "runs": [
                {
                    "case_id": "case-01",
                    "module": "statistics",
                    "manuscript_sha256": run["source"]["sha256"],
                    "engineering_passed": True,
                }
            ],
        },
    )
    return batch, root


def test_packet_keeps_original_manuscript_and_all_judgments_blank(support_env, tmp_path):
    batch, root = copied_fixture(support_env, tmp_path)
    output = tmp_path / "new-packet"
    result = packet.prepare(batch, root, output)
    assert result["cases"] == result["observations"] == 1
    assert result["judgments"] == "blank_requires_human_review"
    assert result["keys_imported"] is False and result["qualification"] == "not_qualified"
    audit = read_json(output / "audit-template.json")
    assert audit["reviewer"] is None and not any(audit["workflow"].values())
    row = audit["runs"][0]
    assert row["control"] is None and row["expected_issue_ids"] is None
    assert row["coverage_reviewed"] is None and row["checking_seconds"] is None
    assert row["judgments"][0]["valid"] is None
    assert row["judgments"][0]["contains_computed_error_claim"] is None
    assert row["numerical_claims_reviewed"] is None and row["baseline_reviewed"] is None
    assert audit["corpus"]["source_only_validated"] is None
    assert audit["evaluation"]["batch_sha256"] == sha256_file(output / "evaluation-batch.json")
    assert row["judgments"][0]["audit_label"] == "O001"
    observations = (output / "OBSERVATIONS.md").read_text()
    assert "O001" in observations and "case-01/manuscript.md" in observations
    assert "undecided until the reviewer supplies it" in observations
    assert sha256_file(output / "case-01/manuscript.md") == sha256_file(support_env[0])
    assert "Original manuscript" in (output / "case-01/index.html").read_text()
    assert "default-src 'none'" in (output / "index.html").read_text()
    assert_mode(output, 0o700)
    for path in output.rglob("*"):
        assert_mode(path, 0o700 if path.is_dir() else 0o600)


def test_packet_rejects_changed_original_before_creating_output(support_env, tmp_path):
    batch, root = copied_fixture(support_env, tmp_path)
    (root / "case-01/hermes/profiles/pilot/work/manuscript.md").write_text("different version")
    output = tmp_path / "packet"
    with pytest.raises(ReviewError, match="manuscript identity"):
        packet.prepare(batch, root, output)
    assert not output.exists()


def test_packet_rejects_export_tampering(support_env, tmp_path):
    batch, root = copied_fixture(support_env, tmp_path)
    next(
        root.glob("case-*/hermes/profiles/pilot/review-data/support/*/exports/*/dossier.md")
    ).write_text("tampered")
    with pytest.raises(ReviewError, match="receipt integrity"):
        packet.prepare(batch, root, tmp_path / "packet")


def test_packet_escapes_model_titles_and_never_overwrites_reviewer_edits(support_env, tmp_path):
    batch, root = copied_fixture(support_env, tmp_path, malicious_title=True)
    output = tmp_path / "packet"
    packet.prepare(batch, root, output)
    document = (output / "case-01/index.html").read_text()
    assert "<script>" not in document and "&lt;script&gt;" in document
    assert "<script>" not in (output / "OBSERVATIONS.md").read_text()
    audit_path = output / "audit-template.json"
    audit_path.write_text("my in-progress human judgments")
    with pytest.raises(ReviewError, match="never overwrite"):
        packet.prepare(batch, root, output)
    assert audit_path.read_text() == "my in-progress human judgments"


def test_empty_observations_do_not_turn_into_a_quality_pass(support_env, tmp_path):
    batch, root = copied_fixture(support_env, tmp_path, concern=False)
    output = tmp_path / "packet"
    result = packet.prepare(batch, root, output)
    assert result["observations"] == 0 and result["qualification"] == "not_qualified"
    assert "not a clean review" in (output / "case-01/index.html").read_text()


def test_case_path_and_agent_context_are_refused(support_env, tmp_path, monkeypatch):
    batch, root = copied_fixture(support_env, tmp_path)
    value = read_json(batch)
    value["runs"][0]["case_id"] = "../keys"
    batch.write_text(json.dumps(value))
    with pytest.raises(ReviewError, match="safe ID"):
        packet.prepare(batch, root, tmp_path / "packet")
    monkeypatch.setenv("HERMES_SESSION_ID", "model-session")
    with pytest.raises(ReviewError, match="outside Hermes"):
        packet.prepare(batch, root, tmp_path / "packet")


def test_explicit_independent_build_reference_is_verified(support_env, tmp_path):
    batch, root = copied_fixture(support_env, tmp_path)
    sums = tmp_path / "reference.sums"
    atomic_write_text(sums, installed_identity()["sums"])
    assert packet.prepare(batch, root, tmp_path / "packet", runner_sums=sums)["cases"] == 1
    atomic_write_text(sums, "wrong candidate\n")
    with pytest.raises(ReviewError, match="independently match"):
        packet.prepare(batch, root, tmp_path / "packet-2", runner_sums=sums)


def test_receipt_cannot_redirect_subject_read_outside_export(support_env, tmp_path):
    batch, root = copied_fixture(support_env, tmp_path)
    receipt = next(
        root.glob("case-*/hermes/profiles/pilot/review-data/support/*/exports/*/receipt.json")
    )
    body = read_json(receipt)
    body["subjects"][0]["file"] = "../../../../../../.env"
    atomic_write_json(receipt, body)
    with pytest.raises(ReviewError, match="four local files"):
        packet.prepare(batch, root, tmp_path / "packet")


def repeated_fixture(support_env, tmp_path, *, same_run=False):
    first, original = copied_fixture(support_env, tmp_path / "first")
    second, second_root = (
        (first, original) if same_run else copied_fixture(support_env, tmp_path / "second")
    )
    body = read_json(first)
    root = tmp_path / "repeated"
    rows = []
    for rep, source in enumerate((original, second_root), 1):
        label = f"case-01-r{rep}"
        shutil.copytree(source / "case-01", root / "support" / label)
        record = dict(
            read_json(first if rep == 1 else second)["runs"][0], artifact_id=label, repetition=rep
        )
        rows.append(record)
    body["runs"] = rows
    batch = root / "batch.json"
    atomic_write_json(batch, body)
    return batch, root


def test_repeated_audit_has_distinct_folders_but_preserves_logical_case_id(support_env, tmp_path):
    batch, root = repeated_fixture(support_env, tmp_path)
    output = tmp_path / "repeated-audit"
    assert packet.prepare(batch, root, output)["cases"] == 2
    audit = read_json(output / "audit-template.json")
    assert [r["case_id"] for r in audit["runs"]] == ["case-01", "case-01"]
    assert [r["repetition"] for r in audit["runs"]] == [1, 2]
    assert [r["artifact"] for r in audit["runs"]] == [
        "case-01-r1/support.json",
        "case-01-r2/support.json",
    ]
    assert all(r["baseline_checking_seconds"] is None for r in audit["runs"])


def test_copied_run_is_not_accepted_as_an_independent_repetition(support_env, tmp_path):
    batch, root = repeated_fixture(support_env, tmp_path, same_run=True)
    with pytest.raises(ReviewError, match="distinct actual support runs"):
        packet.prepare(batch, root, tmp_path / "packet")


def test_paired_baseline_is_preserved_but_no_human_checking_time_is_invented(support_env, tmp_path):
    batch, root = repeated_fixture(support_env, tmp_path)
    body = read_json(batch)
    label = "case-01-r1"
    destination = root / "baselines" / label
    work = destination / "hermes/profiles/pilot/work"
    work.mkdir(parents=True)
    shutil.copyfile(support_env[0], work / "manuscript.md")
    artifact = work / "baseline.md"
    atomic_write_text(artifact, "# Ordinary baseline adapter\n\nNo medical quality assessment.")
    record = {
        "case_id": "case-01",
        "module": "statistics",
        "repetition": 1,
        "artifact_id": label,
        "identity": body["identity"]["sums_sha256"],
        "model": "local-test",
        "kind": "ordinary_hermes_baseline",
        "engineering_passed": True,
        "manuscript_sha256": sha256_file(support_env[0]),
        "artifact_sha256": sha256_file(artifact),
    }
    atomic_write_json(destination / "result.json", record)
    body["baselines"] = [record]
    atomic_write_json(batch, body)
    output = tmp_path / "paired-audit"
    packet.prepare(batch, root, output)
    row = read_json(output / "audit-template.json")["runs"][0]
    assert row["baseline_artifact"] == f"{label}/baseline.md"
    assert row["baseline_engineering_passed"] is True
    assert row["baseline_checking_seconds"] is None and row["baseline_model"] == "local-test"
    assert row["baseline_reviewed"] is None and row["baseline_review_notes"] == ""
    assert "baseline.md" in (output / label / "index.html").read_text()
    assert sha256_file(output / label / "baseline.md") == sha256_file(artifact)
    artifact.write_text("changed baseline")
    with pytest.raises(ReviewError, match="integrity"):
        packet.prepare(batch, root, tmp_path / "changed-packet")


@pytest.mark.parametrize("synthetic", [False, True])
def test_packet_preserves_frozen_manifest_without_claiming_human_validation(
    support_env, tmp_path, synthetic
):
    batch, root = copied_fixture(support_env, tmp_path)
    body = read_json(batch)
    manifest = root / "corpus-manifest.json"
    atomic_write_json(
        manifest,
        {
            "protocol": PROTOCOL,
            "corpus_id": "not-reviewed-pilot",
            "synthetic_only": synthetic,
            "independently_reviewed": False,
            "cases": [
                {
                    "case_id": "case-01",
                    "module": "statistics",
                    "file": "case-01.md",
                    "sha256": body["runs"][0]["manuscript_sha256"],
                }
            ],
        },
    )
    body.update(
        synthetic_only=synthetic,
        manifest_sha256=sha256_file(manifest),
        corpus_id="not-reviewed-pilot",
        corpus_independently_reviewed=False,
    )
    atomic_write_json(batch, body)
    output = tmp_path / "manifest-packet"
    packet.prepare(batch, root, output)
    audit = read_json(output / "audit-template.json")
    assert audit["corpus_independently_reviewed"] is False
    assert audit["synthetic_only"] is synthetic
    assert audit["corpus"]["manifest_sha256"] == sha256_file(output / "corpus-manifest.json")
    assert audit["corpus"]["validation_reviewer"] is None
    assert audit["corpus"]["representative_medical_cases"] is None
    body["corpus_independently_reviewed"] = True
    atomic_write_json(batch, body)
    with pytest.raises(ReviewError, match="cannot be relabeled"):
        packet.prepare(batch, root, tmp_path / "relabeled-packet")
