"""Prepare a private, static evaluator packet from copied medical-support artifacts.

No inference, network, private-key import, or automatic validity judgments. Run only on the
evaluator machine; copy the artifacts there first. Never send a completed audit to the model.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
from pathlib import Path

from closed_review.errors import ReviewError
from closed_review.io import (
    atomic_write_json,
    atomic_write_text,
    ensure_private_dir,
    read_json,
    secure_file,
    sha256_file,
)
from closed_review.receipts import verify_receipt
from closed_review.support import PROTOCOL
from closed_review.support.evaluation import load_manifest
from closed_review.support.methods import MODULES
from closed_review.support.qualification import WORKFLOW_CHECKS

SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
STYLE = (
    "body{font:17px/1.6 system-ui,sans-serif;max-width:1050px;margin:2rem auto;"
    "padding:0 1rem;color:#202932}table{border-collapse:collapse;display:block;overflow:auto}"
    "td,th{border:1px solid #bcc6ce;padding:.6rem}article,aside{border:1px solid #d5dce1;"
    "padding:1rem;margin:1rem 0;border-radius:.4rem}a{color:#135a83}"
    "blockquote{white-space:pre-wrap}small{color:#526471}"
)


def page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; "
        "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
        f"<title>{html.escape(title)}</title><style>{STYLE}</style></head><body>"
        f"{body}</body></html>\n"
    )


def inside(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root) or path.is_symlink():
        raise ReviewError("artifact paths must stay inside the copied batch; no symlink inputs")
    return resolved


def copy_private(source: Path, destination: Path) -> None:
    if not source.is_file() or source.is_symlink():
        raise ReviewError("missing or symlink artifact; recopy the original verified export")
    shutil.copyfile(source, destination)
    secure_file(destination)


def matched_baseline(
    batch: dict,
    row: dict,
    root: Path,
    identity: str,
    model: str,
) -> dict | None:
    """Rebase only known copied paths. Never follow a remote artifact path from model output."""
    candidates = [
        baseline
        for baseline in batch.get("baselines", [])
        if (baseline.get("case_id"), baseline.get("module"), baseline.get("repetition", 1))
        == (row["case_id"], row["module"], row.get("repetition", 1))
    ]
    if not candidates:
        return None
    if len(candidates) != 1:
        raise ReviewError("each repeated case can have only one matched baseline")
    baseline = candidates[0]
    label = row.get("artifact_id", row["case_id"])
    if (
        baseline.get("artifact_id", baseline.get("case_id")) != label
        or baseline.get("identity") != identity
    ):
        raise ReviewError("baseline case/build does not match its support run")
    if baseline.get("kind") != "ordinary_hermes_baseline" or (
        baseline.get("engineering_passed") is True and baseline.get("model") != model
    ):
        raise ReviewError("baseline must be the ordinary-Hermes comparison on the same model")
    case_root = inside(root, root / "baselines" / label)
    record = inside(root, case_root / "result.json")
    if read_json(record) != baseline:
        raise ReviewError("baseline result differs from the batch snapshot")
    paper_root = case_root / "hermes/profiles/pilot/work"
    artifact = paper_root / "baseline.md"
    if artifact.exists():
        artifact = inside(root, artifact)
        papers = list(paper_root.glob("manuscript.*"))
        if (
            len(papers) != 1
            or sha256_file(inside(root, papers[0])) != row["manuscript_sha256"]
            or baseline.get("manuscript_sha256") != row["manuscript_sha256"]
            or sha256_file(artifact) != baseline.get("artifact_sha256")
        ):
            raise ReviewError("baseline source/output integrity does not match its paired case")
    else:
        artifact = None
        if baseline.get("engineering_passed") is True:
            raise ReviewError("a passed baseline must include its actual output")
    return {"record": record, "artifact": artifact, "result": baseline}


def prepare(batch: Path, root: Path, output: Path, *, runner_sums: Path | None = None) -> dict:
    if os.environ.get("HERMES_SESSION_ID"):
        raise ReviewError("prepare human audits outside Hermes on the evaluator machine")
    batch, root, output = batch.resolve(), root.resolve(), output.expanduser().resolve()
    if output.exists():
        raise ReviewError("choose a new packet directory; never overwrite reviewer work")
    value = read_json(batch)
    if value.get("protocol") != PROTOCOL or type(value.get("synthetic_only")) is not bool:
        raise ReviewError("expected a medical-methods-v1 batch with explicit source kind")
    if value["synthetic_only"] is False and not value.get("manifest_sha256"):
        raise ReviewError("published-article batches require their frozen corpus manifest")
    identity = value.get("identity", {}).get("sums_sha256")
    if not isinstance(identity, str) or len(identity) != 64:
        raise ReviewError("batch must identify the exact runner")
    if runner_sums is not None and (
        not runner_sums.is_file()
        or runner_sums.is_symlink()
        or sha256_file(runner_sums) != identity
    ):
        raise ReviewError("reference sums must independently match the batch runner identity")
    runs = value.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ReviewError("batch has no completed case records")
    manifest = None
    if value.get("manifest_sha256"):
        manifest = inside(root, root / "corpus-manifest.json")
        if not manifest.is_file() or sha256_file(manifest) != value["manifest_sha256"]:
            raise ReviewError("include the unchanged frozen corpus manifest from this batch")
        corpus, _ = load_manifest(manifest)
        if (
            corpus["synthetic_only"] is not value["synthetic_only"]
            or (corpus["corpus_id"] != value.get("corpus_id"))
            or corpus["independently_reviewed"] is not value.get("corpus_independently_reviewed")
        ):
            raise ReviewError("corpus provenance cannot be relabeled after the batch")
    checked = []
    seen, folders, run_ids = set(), set(), set()
    # Verify every input before creating the packet. Batch remote paths are never followed.
    for row in runs:
        logical_case, module = row.get("case_id"), row.get("module")
        case = row.get("artifact_id", logical_case)
        repetition = row.get("repetition", 1)
        key = (logical_case, module, repetition)
        if (
            not isinstance(logical_case, str)
            or not SAFE_ID.fullmatch(logical_case)
            or not isinstance(case, str)
            or not SAFE_ID.fullmatch(case)
            or type(repetition) is not int
            or repetition not in {1, 2, 3}
            or key in seen
            or case in folders
            or module not in MODULES
        ):
            raise ReviewError("each case needs a distinct safe ID and known module")
        seen.add(key)
        folders.add(case)
        base = root / "support" if "artifact_id" in row else root
        case_root = inside(root, base / case)
        profile = case_root / "hermes/profiles/pilot"
        exports = list((profile / "review-data/support").glob("*/exports/*/support.json"))
        if len(exports) != 1:
            raise ReviewError(
                f"{case}: expected one export; preserve ambiguous/failed-run evidence"
            )
        artifact = inside(root, exports[0])
        receipt = inside(root, artifact.parent / "receipt.json")
        run = read_json(artifact)
        run_key = (module, run.get("id"))
        if not isinstance(run.get("id"), str) or not run["id"] or run_key in run_ids:
            raise ReviewError("repetitions must contain distinct actual support runs")
        run_ids.add(run_key)
        if (
            run.get("protocol") != PROTOCOL
            or run.get("identity", {}).get("runner") != identity
            or set(run.get("modules", {})) != {module}
        ):
            raise ReviewError(f"{case}: exported runner/protocol/module does not match the batch")
        receipt_body = read_json(receipt)
        names = [s.get("file") for s in receipt_body.get("subjects", [])]
        expected_names = {"dossier.html", "dossier.md", "support.json", "reviewer-notes.md"}
        if len(names) != len(expected_names) or set(names) != expected_names:
            raise ReviewError(f"{case}: receipt must name exactly the dossier's four local files")
        for name in names:
            inside(root, artifact.parent / name)
        if receipt_body.get("tool", {}).get("sums_sha256") != identity:
            raise ReviewError(f"{case}: receipt and batch runner identities differ")
        if not verify_receipt(receipt, runner_sums)["verified"]:
            raise ReviewError(f"{case}: receipt integrity check failed")
        papers = list((profile / "work").glob("manuscript.*"))
        if len(papers) != 1:
            raise ReviewError(f"{case}: include the original manuscript copy")
        paper = inside(root, papers[0])
        digest = sha256_file(paper)
        if digest != run.get("source", {}).get("sha256") or digest != row.get("manuscript_sha256"):
            raise ReviewError(f"{case}: manuscript identity differs from the run")
        for name in ("dossier.html", "dossier.md", "support.json", "reviewer-notes.md"):
            inside(root, artifact.parent / name)
        baseline = matched_baseline(value, row, root, identity, run["route"]["model"])
        checked.append((row, run, artifact, receipt, paper, baseline))
    ensure_private_dir(output)
    if manifest:
        copy_private(manifest, output / "corpus-manifest.json")
    copy_private(batch, output / "evaluation-batch.json")
    audit = {
        "protocol": PROTOCOL,
        "identity": {"runner": identity},
        "reviewer": None,
        "purpose": (
            "diagnostic_pilot_not_qualification_evidence_until_cases_are_validated"
            if value["synthetic_only"]
            else "published_article_engineering_not_seeded_quality_evidence"
        ),
        "synthetic_only": value["synthetic_only"],
        "corpus_independently_reviewed": value.get("corpus_independently_reviewed"),
        "corpus": {
            "manifest": "corpus-manifest.json" if manifest else None,
            "manifest_sha256": sha256_file(manifest) if manifest else None,
            "source_only_validated": None,
            "representative_medical_cases": None,
            "validation_reviewer": None,
        },
        "evaluation": {
            "batch": "evaluation-batch.json",
            "batch_sha256": sha256_file(output / "evaluation-batch.json"),
        },
        "hardware": dict.fromkeys(
            ["hardware", "weights", "quantization", "runtime", "context_length", "peak_memory"]
        ),
        "workflow": dict.fromkeys(sorted(WORKFLOW_CHECKS)),
        "runs": [],
    }
    cards = []
    lines = [
        "# Offline medical-support audit",
        "",
        "All judgments are blank. Integrity checks do not establish concern validity.",
        "Read each original manuscript and dossier. Keep private keys and completed judgments "
        "off the inference host. Do not automatically count comparison-case alerts as false.",
        "",
        "| Case | Module | Status | Observations | Files |",
        "| --- | --- | --- | ---: | --- |",
    ]
    sequence = 0
    observation_lines = [
        "# Observation index for offline review",
        "",
        "These are model proposals, not established errors. Read the linked original manuscript "
        "and full source-bound dossier before deciding. A failed module's zero observations "
        "do not mean its manuscript is clear of problems.",
        "",
        "Optional chat response: `O001 valid / invalid / undecided — reason`. "
        "No browser inputs are needed. These labels are local to this packet. "
        "Also check the manuscripts for missed issues; an observation-only audit is incomplete.",
    ]
    for row, run, artifact, _receipt, paper, baseline in checked:
        logical_case, module = row["case_id"], row["module"]
        case = row.get("artifact_id", logical_case)
        destination = ensure_private_dir(output / case)
        for name in (
            "dossier.html",
            "dossier.md",
            "support.json",
            "reviewer-notes.md",
            "receipt.json",
        ):
            copy_private(artifact.parent / name, destination / name)
        copy_private(paper, destination / paper.name)
        baseline_link = "<p>Matched ordinary-Hermes baseline: not available.</p>"
        if baseline:
            copy_private(baseline["record"], destination / "baseline-result.json")
            if baseline["artifact"]:
                copy_private(baseline["artifact"], destination / "baseline.md")
                baseline_link = (
                    "<p><a href='baseline.md'>Matched ordinary-Hermes baseline</a> · "
                    "<a href='baseline-result.json'>Baseline trace checks</a>. "
                    "Engineering: "
                    + ("passed" if baseline["result"]["engineering_passed"] else "failed")
                    + "; medical validity and reviewer checking time remain unjudged.</p>"
                )
        state = run["modules"][module]
        judgments = []
        details = []
        for observation in state["observations"]:
            sequence += 1
            label = f"O{sequence:03d}"
            observation_lines += [
                "",
                f"## {label} — {case} / {module}",
                "",
                f"Workflow: {state['status']}. Type: {observation['kind']}.",
                "",
                # Raw source/model lines are blockquoted to keep them distinct from packet
                # instructions. Original dossier/manuscript content is copied unchanged.
                *["> " + html.escape(line) for line in observation["title"].splitlines()],
                "",
                *["> " + html.escape(line) for line in observation["explanation"].splitlines()],
                "",
                f"[Original manuscript]({case}/{paper.name}) · "
                f"[Full Markdown dossier]({case}/dossier.md) · "
                f"[Source-linked HTML]({case}/dossier.html#{observation['id']})",
                "",
                "Decision: undecided until the reviewer supplies it.",
            ]
            judgments.append(
                {
                    "id": observation["id"],
                    "audit_label": label,
                    "valid": None,
                    "matches": [],
                    "rationale": "",
                    "computed_supported": None,
                    "contains_computed_error_claim": None,
                }
            )
            details.append(
                f"<article id='{label}'><h3>{label}: "
                f"{html.escape(observation['title'])}</h3><small>"
                f"{html.escape(observation['id'])} · {html.escape(observation['kind'])}"
                " · model proposal, not a human judgment</small><p>"
                f"{html.escape(observation['explanation'])}</p>"
                "<p>Decision: valid / invalid / undecided; explain why. Check the "
                "linked source and counterevidence before deciding.</p>"
                f"<a href='dossier.html#{html.escape(observation['id'], quote=True)}'>"
                "Source-linked observation</a></article>"
            )
        audit["runs"].append(
            {
                "case_id": logical_case,
                "module": module,
                "control": None,
                "repetition": row.get("repetition", 1),
                "artifact": f"{case}/support.json",
                "artifact_sha256": sha256_file(destination / "support.json"),
                "expected_issue_ids": None,
                "coverage_reviewed": None,
                "numerical_claims_reviewed": None,
                "other_numerical_error_claims_supported": None,
                "judgments": judgments,
                "checking_seconds": None,
                "baseline_checking_seconds": None,
                "baseline_model": baseline["result"].get("model") if baseline else None,
                "baseline_reviewed": None,
                "baseline_review_notes": "",
                "baseline_artifact": f"{case}/baseline.md"
                if baseline and baseline["artifact"]
                else None,
                "baseline_artifact_sha256": sha256_file(destination / "baseline.md")
                if baseline and baseline["artifact"]
                else None,
                "baseline_record": f"{case}/baseline-result.json" if baseline else None,
                "baseline_record_sha256": sha256_file(destination / "baseline-result.json")
                if baseline
                else None,
                "baseline_engineering_passed": baseline["result"]["engineering_passed"]
                if baseline
                else None,
            }
        )
        body = (
            f"<h1>{html.escape(case)} — {html.escape(module)}</h1>"
            f"<p>Workflow: {html.escape(state['status'])}; "
            f"{len(state['observations'])} retained observations. Not qualified.</p>"
            f"<p><a href='{html.escape(paper.name, quote=True)}'>Original manuscript</a> · "
            "<a href='dossier.html'>Full dossier and extracted source</a> · "
            "<a href='dossier.md'>Markdown</a> · <a href='../index.html'>All cases</a></p>"
            + baseline_link
            + (
                "".join(details)
                if details
                else "<p>No observations were retained. A stopped "
                "or incomplete module is not a clean review; inspect its status and limits.</p>"
            )
        )
        atomic_write_text(destination / "index.html", page(f"Audit {case}", body))
        cards.append(
            f"<tr><td><a href='{case}/index.html'>{case}</a></td><td>{module}</td>"
            f"<td>{html.escape(state['status'])}</td><td>{len(state['observations'])}</td></tr>"
        )
        lines.append(
            f"| {case} | {module} | {state['status']} | {len(state['observations'])} | "
            f"[manuscript]({case}/{paper.name}) · [dossier]({case}/dossier.md)"
            + (f" · [baseline]({case}/baseline.md)" if baseline and baseline["artifact"] else "")
            + " |"
        )
    atomic_write_json(output / "audit-template.json", audit)
    atomic_write_text(output / "OBSERVATIONS.md", "\n".join(observation_lines) + "\n")
    introduction = (
        "<h1>Offline medical-support audit</h1><aside>"
        "<p>These are model proposals on synthetic manuscripts, not established errors. "
        "All human judgment fields remain blank. Inspect every observation, missed issue, "
        "counterargument, duplicate and calculation-input interpretation.</p>"
        "<p>The original manuscripts and exported files were hash-checked. That proves "
        "integrity, not medical validity. Comparison cases are not certified error-free. "
        "Keep private keys and completed judgments off the model host.</p>"
        "<p>These pages contain no JavaScript, forms or input widgets: record decisions in the "
        "local audit template or provide them in chat using the O-labels. Ambiguous "
        "decisions must remain undecided.</p></aside>"
    )
    atomic_write_text(
        output / "index.html",
        page(
            "Offline medical-support audit",
            introduction
            + "<table><tr><th>Case</th><th>Module</th><th>Status</th><th>Observations</th></tr>"
            + "".join(cards)
            + "</table>",
        ),
    )
    lines += [
        "",
        "## Completing the audit",
        "",
        "Record valid / invalid / undecided for every O-label with a rationale. Also inspect "
        "the manuscript for missed issues. Do not fill unknown fields with zero or false.",
        "Check contains_computed_error_claim on every observation, regardless of its label/kind. "
        "Any numerical-error claim needs computed_supported; also inspect summaries/appraisals "
        "before completing numerical_claims_reviewed and other_numerical_error_claims_supported.",
        "",
        "Independently review corpus sources/representativeness and the actual matched baseline; "
        "record the validation reviewer, baseline notes and measured checking times only after "
        "doing that work. Frozen manifest/batch hashes are provenance, not expert approval. "
        "An unreviewed-at-start diagnostic corpus cannot be retroactively qualified.",
        "",
        "[OBSERVATIONS.md](OBSERVATIONS.md) lists every O-label for headless reading. "
        "You can reply in chat using those labels; no input button or text box is required.",
        "",
        "The audit template intentionally omits expected issues and control assignments. "
        "Use evaluator-held keys only after independently reviewing the cases; never upload "
        "them to Hermes. This short pilot is not independently validated qualification evidence.",
        "",
        "Only after completing repeated cases, the baseline, corpus/workflow/hardware "
        "reviews and all human fields should you invoke creview support score offline.",
    ]
    atomic_write_text(output / "README.md", "\n".join(lines) + "\n")
    return {
        "directory": str(output),
        "cases": len(checked),
        "observations": sequence,
        "judgments": "blank_requires_human_review",
        "keys_imported": False,
        "qualification": "not_qualified",
        "server_started": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--runner-sums",
        type=Path,
        help=(
            "independently obtained sums from the exact candidate, "
            "never extracted from the audited batch"
        ),
    )
    args = parser.parse_args(argv)
    try:
        result = prepare(args.batch, args.artifacts, args.output, runner_sums=args.runner_sums)
    except (ReviewError, OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"{exc}\n")
    import json

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
