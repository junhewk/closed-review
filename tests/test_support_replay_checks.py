"""Mechanical replay checks must not become human verdicts or mutate audit artifacts."""

import copy
import importlib.util
import math
import shutil
from pathlib import Path

import pytest
from test_support import begin, bound_percentage, finish
from test_support import support_env as support_env
from test_support_audit_packet import packet as packet_builder
from test_support_comparison_view import replay

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, atomic_write_text, read_json, sha256_file
from closed_review.receipts import installed_identity, receipt_id, text_sha256
from closed_review.support.calculators import METHODS
from closed_review.support.render import export
from closed_review.support.workflow import _load, _root

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check-support-replays.py"
SPEC = importlib.util.spec_from_file_location("support_replay_checks", SCRIPT)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def pdf_snapshot():
    return {
        "path": "/original/manuscript.pdf",
        "format": "pdf",
        "tables": [{"bbox": [1.0, 2.0, 3.0, 4.0]}],
        "blocks": [{"text": "PRIVATE 25.00"}],
    }


@pytest.mark.parametrize(
    "change",
    [
        "one-ulp",
        "large-coordinate",
        "text",
        "bool-coordinate",
        "string-coordinate",
        "format",
        "missing-coordinate",
    ],
)
def test_source_difference_diagnostics_never_accept_a_tolerance_or_echo_text(change):
    saved = pdf_snapshot()
    fresh = copy.deepcopy(saved)
    if change == "one-ulp":
        fresh["tables"][0]["bbox"][1] = math.nextafter(2.0, math.inf)
    elif change == "large-coordinate":
        fresh["tables"][0]["bbox"][1] = 200.0
    elif change == "text":
        fresh["blocks"][0]["text"] = "PRIVATE 26.00"
    elif change == "bool-coordinate":
        fresh["tables"][0]["bbox"][1] = False
    elif change == "string-coordinate":
        fresh["tables"][0]["bbox"][1] = "2.0"
    elif change == "format":
        fresh["format"] = "markdown"
    else:
        fresh["tables"][0]["bbox"].pop()
    result = checker.compare_sources(saved, fresh)
    assert not result["matches"]
    assert result["only_table_bbox_coordinates_differ"] is (
        change in {"one-ulp", "large-coordinate"}
    )
    assert result["differing_fields_total"] >= 1
    assert "PRIVATE" not in str(result)
    if result["only_table_bbox_coordinates_differ"]:
        assert "Strict mismatch retained" in result["runtime_note"]
        assert "does not establish" in result["runtime_note"]


def test_source_relocation_is_the_only_ignored_field():
    saved = pdf_snapshot()
    fresh = copy.deepcopy(saved)
    fresh["path"] = "/copied/manuscript.pdf"
    result = checker.compare_sources(saved, fresh)
    assert result["matches"] and not result["differing_fields"]
    assert not result["only_table_bbox_coordinates_differ"]


def test_late_text_difference_cannot_hide_behind_a_truncated_geometry_diagnostic():
    saved = pdf_snapshot()
    saved["tables"] *= 7
    saved["zz_note"] = "PRIVATE original"
    fresh = copy.deepcopy(saved)
    for table in fresh["tables"]:
        table["bbox"] = [value + 1 for value in table["bbox"]]
    fresh["zz_note"] = "PRIVATE changed"
    result = checker.compare_sources(saved, fresh)
    assert result["differing_fields_truncated"] and len(result["differing_fields"]) == 24
    assert result["differing_fields_total"] == 29
    assert not result["only_table_bbox_coordinates_differ"] and not result["matches"]
    assert "PRIVATE" not in str(result)


@pytest.fixture
def replay_packet(support_env, tmp_path, request):
    method = getattr(request, "param", None)
    if method:
        calculation, source = replay(method)
        paper = support_env[0]
        paper.write_text(paper.read_text() + "\n\n" + source["blocks"][0]["text"])
    run_id = begin(support_env)
    if method:
        source = _load(_root(run_id))["source"]
        block = next(b for b in source["blocks"] if "Declared method." in b["text"])
        raw = {
            key: calculation[key]
            for key in (
                "method",
                "inputs",
                "parameters",
                "method_evidence",
                "assumptions",
            )
        }
        comparison = calculation["comparison"]
        raw["reported"] = {**comparison["reported"], "output": comparison["output"]}

        # Construct a new unit-test submission, not a saved-record migration. The model
        # contract takes block_id/quote only; Python adds locator/ambiguity on acceptance.
        def evidence(items):
            return [{"block_id": block["id"], "quote": item["quote"]} for item in items]

        raw["method_evidence"] = evidence(raw["method_evidence"])
        for binding in [*raw["inputs"].values(), raw["reported"]]:
            binding["evidence"] = evidence(binding["evidence"])
    else:
        raw = bound_percentage(run_id)
    run = finish(run_id, calculations=[raw], withdraw_calculations=True)
    exported = Path(export(run_id)["directory"])
    root = tmp_path / "copied"
    profile = root / "case-01/hermes/profiles/pilot"
    shutil.copytree(exported, profile / "review-data/support" / run_id / "exports/dossier")
    (profile / "work").mkdir()
    shutil.copyfile(support_env[0], profile / "work/manuscript.md")
    batch = root / "batch.json"
    atomic_write_json(
        batch,
        {
            "protocol": run["protocol"],
            "synthetic_only": True,
            "identity": {"sums_sha256": run["identity"]["runner"]},
            "runs": [
                {
                    "case_id": "case-01",
                    "module": "statistics",
                    "artifact_sha256": sha256_file(exported / "support.json"),
                    "manuscript_sha256": run["source"]["sha256"],
                    "engineering_passed": True,
                }
            ],
        },
    )
    output = tmp_path / "packet"
    packet_builder.prepare(batch, root, output)
    sums = tmp_path / "trusted.sums"
    atomic_write_text(sums, installed_identity()["sums"])
    return output, sums


def reseal(packet, mutate):
    """A deliberately self-resealed synthetic fixture, not authenticated production evidence."""
    folder = packet / "case-01"
    run = read_json(folder / "support.json")
    mutate(run)
    atomic_write_json(folder / "support.json", run)
    receipt = read_json(folder / "receipt.json")
    subject = next(s for s in receipt["subjects"] if s["file"] == "support.json")
    subject.update(
        sha256=sha256_file(folder / "support.json"),
        text_sha256=text_sha256((folder / "support.json").read_text()),
    )
    receipt["receipt_id"] = receipt_id(receipt)
    atomic_write_json(folder / "receipt.json", receipt)
    batch = read_json(packet / "evaluation-batch.json")
    batch["runs"][0]["artifact_sha256"] = subject["sha256"]
    atomic_write_json(packet / "evaluation-batch.json", batch)


def test_relocated_snapshot_and_real_calculation_reproduce_without_any_input_changes(replay_packet):
    packet, sums = replay_packet
    before = {p: p.read_bytes() for p in packet.rglob("*") if p.is_file()}
    result = checker.check(packet, sums)
    assert result["all_checks_passed"] and result["calculations_checked"] == 1
    assert result["cases"][0]["source_snapshot"]["matches"]
    assert result["cases"][0]["calculations"][0]["accepted"]
    assert result["cases"][0]["calculations"][0]["differing_fields"] == []
    assert result["qualification"] == "not_qualified"
    assert not result["human_judgments_created"] and not result["model_or_network_calls"]
    assert before == {p: p.read_bytes() for p in packet.rglob("*") if p.is_file()}


@pytest.mark.parametrize("replay_packet", list(METHODS), indirect=True)
def test_all_thirteen_workflow_saved_calculators_reproduce(replay_packet):
    packet, sums = replay_packet
    result = checker.check(packet, sums)
    assert result["all_checks_passed"] and result["calculations_checked"] == 1
    assert result["cases"][0]["calculations"][0]["differing_fields"] == []


def test_failed_module_is_not_promoted_when_its_existing_records_reproduce(replay_packet):
    packet, sums = replay_packet
    reseal(
        packet, lambda run: run["modules"]["statistics"].update(status="failed", calculations=[])
    )
    result = checker.check(packet, sums)
    assert result["all_checks_passed"] and result["calculations_checked"] == 0
    assert result["cases"][0]["saved_module_status"] == "failed"
    assert result["qualification"] == "not_qualified"


@pytest.mark.parametrize(
    "change,field", [("output", "outputs"), ("flag", "comparison"), ("status", "comparison")]
)
def test_resealed_wrong_outputs_flags_and_statuses_do_not_pass(replay_packet, change, field):
    packet, sums = replay_packet

    def mutate(run):
        calculation = run["modules"]["statistics"]["calculations"][0]
        if change == "output":
            calculation["outputs"]["value"] = 21.0
        elif change == "flag":
            # bool False and int 0 compare equal in Python, but are not the same saved record.
            calculation["comparison"]["numerical_match"] = 0
        else:
            calculation["comparison"]["status"] = "match"

    reseal(packet, mutate)
    result = checker.check(packet, sums)
    row = result["cases"][0]
    assert not result["all_checks_passed"]
    assert row["receipt_verified"] and row["source_snapshot"]["matches"]
    assert row["calculations"][0]["accepted"]
    assert row["calculations"][0]["differing_fields"] == [field]


def test_resealed_source_edits_are_detected_without_rewriting_or_normalizing(replay_packet):
    packet, sums = replay_packet
    reseal(packet, lambda run: run["source"]["blocks"][0].update(text="Changed source block."))
    source = (packet / "case-01/support.json").read_bytes()
    result = checker.check(packet, sums)
    assert not result["all_checks_passed"]
    assert result["cases"][0]["receipt_verified"]
    assert not result["cases"][0]["source_snapshot"]["matches"]
    assert (packet / "case-01/support.json").read_bytes() == source


@pytest.mark.parametrize("change", ["parameter", "private-quote"])
def test_invalid_replays_fail_without_echoing_confidential_values(replay_packet, change):
    packet, sums = replay_packet

    def mutate(run):
        calculation = run["modules"]["statistics"]["calculations"][0]
        if change == "parameter":
            calculation["parameters"] = {"PRIVATE-PARAMETER": 99}
        else:
            calculation["method_evidence"][0]["quote"] = "PRIVATE-UNBOUND-QUOTE"

    reseal(packet, mutate)
    result = checker.check(packet, sums)
    row = result["cases"][0]["calculations"][0]
    assert not row["accepted"] and not row["matches_saved"]
    assert row["error_type"] == "ReviewError"
    assert "PRIVATE" not in str(result)


def test_external_source_path_and_private_audit_fields_are_never_followed(
    replay_packet, monkeypatch
):
    packet, sums = replay_packet
    reseal(packet, lambda run: run["source"].update(path="/private/answer-key.json"))
    original = checker.read_json
    read_paths = []

    def guarded(path):
        assert Path(path).name not in {"audit-template.json", "answer-key.json"}
        read_paths.append(Path(path))
        return original(path)

    monkeypatch.setattr(checker, "read_json", guarded)
    result = checker.check(packet, sums)
    assert result["all_checks_passed"]
    assert not result["audit_template_or_private_keys_read"]
    assert read_paths and all(p.is_relative_to(packet) for p in read_paths)


def test_changed_replay_code_is_refused_instead_of_reinterpreting_old_records(
    replay_packet, monkeypatch
):
    packet, sums = replay_packet
    identity = installed_identity()
    identity["sums"] = identity["sums"].replace(
        next(
            line
            for line in identity["sums"].splitlines()
            if line.endswith("support/calculators.py")
        ),
        "0" * 64 + "  support/calculators.py",
    )
    monkeypatch.setattr(checker, "installed_identity", lambda: identity)
    with pytest.raises(ReviewError, match="code differs"):
        checker.check(packet, sums)


@pytest.mark.parametrize("problem", ["path", "symlink", "receipt", "manuscript"])
def test_changed_or_unsafe_packet_inputs_are_refused(replay_packet, tmp_path, problem):
    packet, sums = replay_packet
    if problem == "path":
        batch = read_json(packet / "evaluation-batch.json")
        batch["runs"][0]["artifact_id"] = "../answer-key"
        atomic_write_json(packet / "evaluation-batch.json", batch)
    elif problem == "symlink":
        target = packet / "case-01/support.json"
        copied = tmp_path / "external.json"
        shutil.move(target, copied)
        target.symlink_to(copied)
    elif problem == "receipt":
        (packet / "case-01/dossier.md").write_text("tampered")
    else:
        (packet / "case-01/manuscript.md").write_text("different source")
    with pytest.raises(ReviewError):
        checker.check(packet, sums)


def test_checker_is_offline_and_cli_preserves_output_and_packet(
    replay_packet, tmp_path, monkeypatch
):
    packet, sums = replay_packet
    monkeypatch.setenv("HERMES_SESSION_ID", "not-an-offline-auditor")
    with pytest.raises(ReviewError, match="offline"):
        checker.check(packet, sums)
    monkeypatch.delenv("HERMES_SESSION_ID")
    output = tmp_path / "fresh-report.json"
    args = ["--packet", str(packet), "--runner-sums", str(sums), "--output", str(output)]
    assert checker.main(args) == 0
    original = output.read_bytes()
    with pytest.raises(SystemExit) as refused:
        checker.main(args)
    assert refused.value.code == 2 and output.read_bytes() == original
    args[-1] = str(packet / "do-not-add.json")
    with pytest.raises(SystemExit):
        checker.main(args)
    assert not (packet / "do-not-add.json").exists()


def test_cli_keeps_failed_reproduction_report_without_fixing_the_original(replay_packet, tmp_path):
    packet, sums = replay_packet
    reseal(
        packet,
        lambda run: run["modules"]["statistics"]["calculations"][0]["outputs"].update(value=21),
    )
    original = (packet / "case-01/support.json").read_bytes()
    report = tmp_path / "failed-reproduction.json"
    assert (
        checker.main(["--packet", str(packet), "--runner-sums", str(sums), "--output", str(report)])
        == 1
    )
    assert not read_json(report)["all_checks_passed"]
    assert (packet / "case-01/support.json").read_bytes() == original
