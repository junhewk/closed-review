"""Make a readable offline audit packet from a completed synthetic qualification run.

The manuscript is checked against the batch's recorded hash. No model or network is used.
An optional private answer-key view is generated only on the evaluator's own machine.
"""

from __future__ import annotations

import argparse
import html
import os
from pathlib import Path
from typing import Any

from closed_review.errors import ReviewError
from closed_review.findings import confirmed_check, severity
from closed_review.io import read_json, sha256_file

STYLE = """<style>
body { font: 17px/1.55 system-ui, sans-serif; color: #19212c; background: #f5f7fa;
       max-width: 1000px; margin: 2rem auto; padding: 0 1rem; }
h1,h2,h3 { line-height: 1.25; } h2 { margin-top: 2rem; }
article, .paper, .note { background: white; padding: 1rem 1.3rem; margin: 1rem 0;
                       border: 1px solid #d9e0e8; border-radius: .4rem; }
blockquote { margin: .6rem 0; padding: .2rem 1rem; border-left: 4px solid #9aadc2; }
summary { cursor: pointer; font-weight: 600; } details { margin: .7rem 0; }
a { color: #0752a0; } .warning { color: #933b00; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; font: 15px/1.55 monospace; }
.line { display: block; } .line:target { background: #fff2bd; }
.lineno { color: #65768b; text-decoration: none; user-select: none; }
dt { font-weight: 600; } dd { margin: 0 0 .6rem 1rem; overflow-wrap: anywhere; }
</style>"""


def escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def page(title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)}</title>{STYLE}</head><body>{body}</body></html>\n"
    )


def _create_or_verify(path: Path, content: bytes) -> None:
    """Never overwrite an existing packet or auditor-edited file."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
            raise ReviewError(
                f"existing file differs; preserve it and choose another path: {path}"
            ) from None
        return
    with os.fdopen(fd, "wb") as file:
        file.write(content)


def _evidence(evidence: Any, manuscript: str) -> str:
    if not isinstance(evidence, dict):
        return f"<p class='warning'>Unstructured evidence: {escape(evidence)}</p>"
    quote = str(evidence.get("quote") or "")
    source = str(evidence.get("source_id") or "unknown")
    locator = str(evidence.get("locator") or "no locator")
    offset = manuscript.find(quote) if quote and source == "manuscript" else -1
    if offset >= 0:
        line = manuscript.count("\n", 0, offset) + 1
        prefix = (
            "First matching occurrence" if manuscript.count(quote) > 1 else "Open the manuscript"
        )
        location = f'<a href="#manuscript-line-{line}">{prefix} at line {line}</a>'
        status = "Exact quotation found; this alone does not establish the concern."
    else:
        location = escape(locator)
        status = "Exact quotation not found in this manuscript copy; verify it manually."
    return (
        f"<p><strong>{escape(source)}</strong> · {location}<br><small>{escape(status)}</small></p>"
        f"<blockquote>{escape(quote) if quote else '<em>No quote supplied.</em>'}</blockquote>"
    )


def review_page(run_id: str, findings: list[dict], manuscript: str, digest: str) -> str:
    menu = " ".join(
        f'<a href="#finding-{escape(f.get("id", ""))}">{escape(f.get("id", "?"))}</a>'
        for f in findings
    )
    cards = []
    for finding in findings:
        finding_id = finding.get("id", "?")
        evidence = finding.get("evidence") or []
        evidence_html = "".join(_evidence(item, manuscript) for item in evidence)
        checks = finding.get("flaw_checks") or []
        checks_html = []
        for check in checks:
            if not isinstance(check, dict):
                checks_html.append(f"<li>{escape(check)}</li>")
                continue
            status = (
                "marked confirmed by the tool" if confirmed_check(check) else "not marked confirmed"
            )
            quotes = "".join(_evidence(item, manuscript) for item in check.get("quotes") or [])
            checks_html.append(
                f"<li><strong>{escape(check.get('flaw') or 'Check')}</strong> — {status}<br>"
                f"{escape(check.get('reason') or 'No explanation supplied.')}{quotes}</li>"
            )
        issue = escape(finding.get("issue") or finding.get("title") or "Not stated.")
        importance = escape(finding.get("why") or "Not stated.")
        model_rating = escape(finding.get("model_severity") or "not stated")
        cards.append(
            f'<article id="finding-{escape(finding_id)}"><h2>{escape(finding_id)}</h2>'
            f"<p><strong>Model's concern:</strong> {issue}</p>"
            f"<p><strong>Model's claimed importance:</strong> {importance}</p>"
            f"<p><strong>Model's severity:</strong> {model_rating} "
            f"; <strong>qualification rating:</strong> {escape(severity(finding)['severity'])} "
            "(neither is the evaluator's judgment)</p>"
            f"<details><summary>Show cited passages ({len(evidence)})</summary>"
            f"{evidence_html or '<p>No evidence was supplied.</p>'}</details>"
            f"<details><summary>Show model's checks ({len(checks)})</summary>"
            f"<ul>{''.join(checks_html)}</ul></details>"
            '<p><a href="#findings">Back to findings</a> · '
            '<a href="#manuscript">Read full manuscript</a></p></article>'
        )
    lines = "\n".join(
        f'<span class="line" id="manuscript-line-{index}">'
        f'<a class="lineno" href="#manuscript-line-{index}">{index:>4}</a>  {escape(line)}</span>'
        for index, line in enumerate(manuscript.splitlines(), start=1)
    )
    body = (
        f"<h1>Audit packet: {escape(run_id)}</h1>"
        '<div class="note"><p>This is a <strong>synthetic test paper</strong>, not a journal '
        "submission. The manuscript copy below was checked against the recorded batch hash.</p>"
        "<p>The concerns, importance, severity and checks are <strong>model claims</strong>, "
        "not established facts. Inspect the cited passages and the full manuscript; claims "
        "that something is absent require broader checking. If unsure, leave the judgment "
        "undecided. Matching quotations alone does not establish validity.</p>"
        '<p>Optional: <a href="answer-key.html">open your private answer-key view</a> '
        "after generating it locally. Do not upload or share the key with a model.</p></div>"
        f'<h2 id="findings">Findings ({len(findings)})</h2><nav>{menu or "None retained."}</nav>'
        f"{''.join(cards)}"
        f'<section class="paper" id="manuscript"><h2>Full synthetic manuscript</h2>'
        f'<p><a href="manuscript.md">Download/open the exact source file</a><br>'
        f"<small>SHA-256: {escape(digest)}</small></p><pre>{lines}</pre></section>"
    )
    return page(f"Synthetic audit {run_id}", body)


def _render_private(value: Any) -> str:
    if isinstance(value, dict):
        return (
            "<dl>"
            + "".join(
                f"<dt>{escape(name)}</dt><dd>{_render_private(child)}</dd>"
                for name, child in value.items()
            )
            + "</dl>"
        )
    if isinstance(value, list):
        return "<ol>" + "".join(f"<li>{_render_private(child)}</li>" for child in value) + "</ol>"
    return escape(value)


def key_page(key: dict, run_id: str) -> str:
    sections = []
    for name, value in key.items():
        if isinstance(value, list):
            entries = []
            for number, item in enumerate(value, start=1):
                label = (
                    item.get("id", f"Item {number}") if isinstance(item, dict) else f"Item {number}"
                )
                entries.append(
                    f"<details><summary>{escape(label)}</summary>{_render_private(item)}</details>"
                )
            content = "".join(entries) or "<p>None.</p>"
        else:
            content = _render_private(value)
        sections.append(f"<article><h2>{escape(name)}</h2>{content}</article>")
    return page(
        f"Private answer key {run_id}",
        f"<h1>Private answer key: {escape(run_id)}</h1>"
        '<p class="warning">Keep this page on the evaluator\'s machine; do not share with a model. '
        "Use it to identify planted issues, not as a substitute for independent judgment.</p>"
        '<p><a href="review.html">Back to the finding and manuscript view</a></p>'
        + "".join(sections),
    )


def prepare_packet(
    output: Path, corpus: Path, manifest: Path, run_id: str, keys: Path | None = None
) -> dict:
    report = read_json(output / "results.json")
    if report.get("identity", {}).get("manifest") != sha256_file(manifest):
        raise ReviewError("manifest differs from the executed batch")
    run = report.get("runs", {}).get(run_id)
    if not run or not run.get("passed") or "/" in run_id or "\\" in run_id:
        raise ReviewError("select a completed, successful run")
    definition = read_json(manifest)
    case = next((c for c in definition["cases"] if c["id"] == run.get("case")), None)
    if not case:
        raise ReviewError("run is missing from the manifest")
    base = manifest.parent if case.get("control") else corpus
    source = base / case["file"]
    expected_hash = report.get("identity", {}).get("manuscripts", {}).get(case["id"])
    if not source.is_file() or not expected_hash or sha256_file(source) != expected_hash:
        raise ReviewError("manuscript is missing or differs from the executed batch")
    content = source.read_bytes()
    try:
        manuscript = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReviewError("synthetic manuscript is not UTF-8 text") from exc
    run_path = output / run_id
    scan = read_json(run_path / "scan.json")
    findings = [
        f for f in scan["review"]["findings"] if f.get("status") not in {"screened", "dismissed"}
    ]
    _create_or_verify(run_path / "manuscript.md", content)
    view = review_page(run_id, findings, manuscript, expected_hash)
    _create_or_verify(run_path / "review.html", view.encode("utf-8"))
    key_path = None
    if keys is not None and not case.get("timing_only"):
        key = (
            {"planted": [], "decoys": []}
            if case.get("control")
            else read_json(keys / f"{case['id']}.json")
        )
        key_path = run_path / "answer-key.html"
        _create_or_verify(key_path, key_page(key, run_id).encode("utf-8"))
    return {
        "run": run_id,
        "review": str(run_path / "review.html"),
        "manuscript": str(run_path / "manuscript.md"),
        "private_key_view": str(key_path) if key_path else None,
        "findings": len(findings),
        "manuscript_sha256": expected_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument(
        "--keys", type=Path, help="optional private keys, on the evaluator's machine"
    )
    args = parser.parse_args()
    try:
        result = prepare_packet(args.output, args.corpus, args.manifest, args.run, args.keys)
    except (ReviewError, OSError) as exc:
        parser.exit(2, f"cannot prepare packet: {exc}\n")
    for name, value in result.items():
        if value is not None:
            print(f"{name}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
