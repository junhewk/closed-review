"Private, static dossiers. All manuscript/model strings are treated as inert text."

from __future__ import annotations

import html
import json
import re
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import quote

from filelock import FileLock

from ..errors import ReviewError
from ..io import atomic_write_json, atomic_write_text, ensure_private_dir, now_iso, sha256_file
from ..receipts import RECEIPT_VERSION, installed_identity, receipt_id, text_sha256
from . import PROTOCOL
from .localization import COMPARISON_LABELS, labels_for, normalize_language
from .methods import MODULES
from .workflow import LABELS, _load, _phase, _root


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _md(value: Any) -> str:
    return re.sub(r"([\\`*_{}\[\]()#+.!|>-])", r"\\\1", html.escape(str(value)))


def render(run: dict[str, Any]) -> tuple[str, str, str]:
    language = normalize_language(run["resolved_language"] or run["language"])
    defaults = labels_for(language) if language in {"en", "ko"} else {}
    first = next((m for m in run["modules"].values() if m.get("labels")), {})
    saved_labels = first.get("labels") or {}
    labels = saved_labels
    if not labels:
        labels = (
            defaults if language in {"en", "ko"} else {key: key.replace("_", " ") for key in LABELS}
        )

    def label(key: str) -> str:
        return labels.get(key, defaults.get(key, key.replace("_", " ")))

    # Historical custom-language snapshots may lack the new labels. Keep their old
    # detailed view rather than invent translations or migrate saved model/reviewer data.
    overview_available = all(key in saved_labels or key in defaults for key in COMPARISON_LABELS)

    def calculation_link(identifier: str) -> str:
        return "#calculation-" + quote(identifier, safe="")

    parts = []
    markdown = [
        f"# {_md(label('scope'))}",
        f"{PROTOCOL} | {_md(_phase(run))} | not_qualified",
        _md(f"{run['source']['sha256']} | revision {run['revision']}"),
    ]
    notes = [f"# {_md(label('reviewer_record'))}"]
    parts.append(
        f"<h1>{_e(label('scope'))}</h1><p>{_e(PROTOCOL)} · "
        f"{_e(label(_phase(run)))} · not_qualified</p>"
    )
    parts.append(
        f"<p class='meta'>SHA256 {_e(run['source']['sha256'])} · revision {run['revision']}</p>"
    )
    parts.append(
        "<nav>"
        + " · ".join(
            f"<a href='#module-{_e(name)}'>{_e(state.get('title', name))}</a>"
            for name, state in run["modules"].items()
        )
        + f" · <a href='#source'>{_e(label('source'))}</a></nav>"
    )

    def evidence(items: list[dict[str, Any]]) -> str:
        return "".join(
            f"<blockquote><a href='#source-{_e(e['block_id'])}'>{_e(e['locator'])}</a> "
            f"{_e(e['quote'])}</blockquote>"
            for e in items
        )

    def md_evidence(items: list[dict[str, Any]]) -> list[str]:
        return [
            f"- [{_md(e['locator'])}](#source-{e['block_id']}) {_md(e['quote'])}" for e in items
        ]

    def comparison_overview(calculations: list[dict[str, Any]]) -> None:
        if not calculations or not overview_available:
            return
        headings = [
            "calculation_method",
            "compared_output",
            "reported",
            "outputs",
            "numerical_agreement",
            "comparison_status",
        ]
        parts.append(
            f"<h3>{_e(label('comparison_overview'))}</h3>"
            f"<p>{_e(label('comparison_overview_note'))}</p>"
            f"<table class='calculation-overview' tabindex='0' "
            f"aria-label='{_e(label('comparison_overview'))}'><thead><tr>"
            + "".join(f"<th scope='col'>{_e(label(key))}</th>" for key in headings)
            + "</tr></thead><tbody>"
        )
        markdown.extend(
            [
                f"### {_md(label('comparison_overview'))}",
                _md(label("comparison_overview_note")),
            ]
        )
        table_lines = [
            "| " + " | ".join(_md(label(key)).replace("\n", " ") for key in headings) + " |",
            "| " + " | ".join("---" for _ in headings) + " |",
        ]
        for calculation in calculations:
            comparison = calculation.get("comparison", {})
            output = comparison.get("output")
            outputs = calculation["outputs"]
            reported = comparison.get("reported")
            reported_text = (
                f"{comparison.get('relation', '=')} {reported['value']}"
                if reported
                else label("not_compared")
            )
            output_text = str(output) if output else ", ".join(outputs)
            computed = (
                str(outputs[output])
                if output in outputs
                else label("agreement_unrecorded")
                if output
                else "; ".join(f"{key}: {value}" for key, value in outputs.items())
            )
            agreement = comparison.get("numerical_match")
            agreement_key = (
                "numerically_matches"
                if agreement is True
                else "numerically_differs"
                if agreement is False
                else "not_compared"
                if comparison.get("status") == "not_compared"
                else "agreement_unrecorded"
            )
            status = label(comparison.get("status", "not_compared"))
            identifier = calculation["id"]
            values = [output_text, reported_text, computed, label(agreement_key), status]
            parts.append(
                f"<tr data-numerical-agreement='{agreement_key}'><td>"
                f"<a href='{_e(calculation_link(identifier))}'>{_e(identifier)}</a><br>"
                f"{_e(calculation['method'])}</td>"
                + "".join(f"<td>{_e(value)}</td>" for value in values)
                + "</tr>"
            )
            table_lines.append(
                "| "
                + f"[{_md(identifier)}]({calculation_link(identifier)}) · "
                + _md(calculation["method"])
                + " | "
                + " | ".join(_md(value).replace("\n", " ") for value in values)
                + " |"
            )
        parts.append("</tbody></table>")
        markdown.append("\n".join(table_lines))

    for name, state in run["modules"].items():
        title = state.get("title", name)
        parts.append(
            f"<section id='module-{_e(name)}'><h2>{_e(title)}</h2>"
            f"<p>{_e(label(state['status']))}</p><p>{_e(state.get('summary', ''))}</p>"
        )
        provided = len(state["provided_blocks"])
        total = len(run["source"]["blocks"])
        parts.append(
            f"<p>{_e(label('coverage'))}: {provided}/{total} · "
            f"{_e(label('observations'))}: {len(state['observations'])}</p>"
        )
        markdown += [
            f"\n## {_md(title)}",
            _md(label(state["status"])),
            _md(state.get("summary", "")),
            f"{_md(label('coverage'))}: {provided}/{total}",
        ]
        limits = run["source"]["warnings"] + state.get("extraction_limits", [])
        limits += [f["error"] for f in state["failures"]]
        limits = list(dict.fromkeys(limits))
        if limits:
            parts.append(
                f"<aside><h3>{_e(label('limitations'))}</h3>"
                + "".join(f"<p>{_e(x)}</p>" for x in limits)
                + "</aside>"
            )
            markdown += [f"### {_md(label('limitations'))}"] + [f"- {_md(x)}" for x in limits]
        if state.get("coverage_gaps"):
            parts.append(f"<aside><h3>{_e(label('coverage_gaps'))}</h3>")
            markdown.append(f"### {_md(label('coverage_gaps'))}")
            for gap in state["coverage_gaps"]:
                references = " · ".join(
                    f"<a href='#source-{_e(identifier)}'>{_e(identifier)}</a>"
                    for identifier in gap["block_ids"]
                )
                parts.append(
                    f"<p>{_e(gap['detail'])}<br><small>{_e(gap['kind'])} · "
                    f"{_e(gap['role'])} · {references}</small></p>"
                )
                markdown += [
                    f"- {_md(gap['detail'])} ({_md(gap['kind'])}; {_md(gap['role'])})",
                    "  "
                    + " · ".join(
                        f"[{_md(identifier)}](#source-{identifier})"
                        for identifier in gap["block_ids"]
                    ),
                ]
            parts.append("</aside>")
        if state.get("scope_limits"):
            parts.append(
                f"<details><summary>{_e(label('scope_limits'))}</summary>"
                + "".join(f"<p>{_e(x)}</p>" for x in state["scope_limits"])
                + "</details>"
            )
            markdown += [f"### {_md(label('scope_limits'))}"] + [
                f"- {_md(x)}" for x in state["scope_limits"]
            ]
        comparison_overview(state["calculations"])
        parts.append(f"<h3>{_e(label('reconstruction'))}</h3>")
        markdown.append(f"### {_md(label('reconstruction'))}")
        if state["facts"]:
            parts.append("<table><tbody>")
        for fact in state["facts"]:
            parts.append(
                f"<tr id='{_e(fact['id'])}'><td>{_e(fact['label'])} "
                f"<small>{_e(fact['role'])}</small></td><td>{_e(fact['value'])}</td>"
                f"<td><details><summary>{_e(label('source'))}</summary>"
                f"{evidence(fact['evidence'])}</details></td></tr>"
            )
            markdown += [
                f"#### {_md(fact['label'])} ({_md(fact['id'])})",
                _md(fact["value"]),
                *md_evidence(fact["evidence"]),
            ]
        if state["facts"]:
            parts.append("</tbody></table>")
        if state["connections"]:
            parts.append(f"<h3>{_e(label('connections'))}</h3><table><tbody>")
            markdown.append(f"### {_md(label('connections'))}")
            for connection in state["connections"]:
                origin, target = ", ".join(connection["from"]), ", ".join(connection["to"])
                parts.append(
                    f"<tr><td>{_e(origin)}</td><td>{_e(connection['relation'])}<br>"
                    f"{_e(connection['basis'])}</td><td>{_e(target)}</td><td>"
                    f"{_e(connection['explanation'])}{evidence(connection['evidence'])}</td></tr>"
                )
                markdown += [
                    _md(f"{origin} — {connection['relation']} ({connection['basis']}) → {target}"),
                    _md(connection["explanation"]),
                    *md_evidence(connection["evidence"]),
                ]
            parts.append("</tbody></table>")
        parts.append(f"<h3>{_e(label('observations'))} ({len(state['observations'])})</h3>")
        markdown.append(f"### {_md(label('observations'))} ({len(state['observations'])})")
        for observation in state["observations"]:
            parts.append(
                f"<article id='{_e(observation['id'])}'><h4>{_e(observation['title'])}</h4>"
                f"<p class='meta'>{_e(observation['id'])} · {_e(label(observation['kind']))}"
                f" · {_e(label('model_proposal'))}</p><p>{_e(observation['explanation'])}</p>"
                f"{evidence(observation['evidence'])}"
                + (
                    f"<h5>{_e(label('counterevidence'))}</h5>"
                    + evidence(observation["counterevidence"])
                    if observation["counterevidence"]
                    else ""
                )
                + "".join(f"<p class='meta'>{_e(x)}</p>" for x in observation["limits"])
                + "</article>"
            )
            if observation.get("calculation_ids"):
                parts.append(
                    f"<p>{_e(label('linked_calculations'))}: "
                    + ", ".join(
                        f"<a href='{_e(calculation_link(c))}'>{_e(c)}</a>"
                        for c in observation["calculation_ids"]
                    )
                    + "</p>"
                )
            markdown += [
                f"#### {_md(observation['id'])}: {_md(observation['title'])}",
                _md(label(observation["kind"])),
                _md(observation["explanation"]),
                *md_evidence(observation["evidence"]),
                *md_evidence(observation["counterevidence"]),
            ]
            markdown += [
                f"[{_md(c)}]({calculation_link(c)})" for c in observation.get("calculation_ids", [])
            ]
        parts.append(f"<details><summary>{_e(label('criteria'))}</summary>")
        markdown.append(f"### {_md(label('criteria'))}")
        for criterion in state["criteria"]:
            parts.append(
                f"<h4>{_e(criterion['id'])} · {_e(label(criterion['status']))}</h4>"
                f"<p>{_e(criterion['criterion'])}</p><p>{_e(criterion['analysis'])}</p>"
                f"<p>{_e(criterion['why_matters'])}</p><p>{_e(criterion['limits'])}</p>"
                f"{evidence(criterion['evidence'])}{evidence(criterion['counterevidence'])}"
            )
            markdown += [
                f"#### {_md(criterion['id'])}: {_md(label(criterion['status']))}",
                _md(criterion["analysis"]),
                _md(criterion["why_matters"]),
                _md(criterion["limits"]),
                *md_evidence(criterion["evidence"]),
                *md_evidence(criterion["counterevidence"]),
            ]
        parts.append("</details>")
        if state["withdrawn"]:
            parts.append(f"<details><summary>{_e(label('withdrawn'))}</summary>")
            markdown.append(f"### {_md(label('withdrawn'))}")
            for item in state["withdrawn"]:
                parts.append(
                    f"<p>{_e(item['criterion'])}: {_e(item['reason'])}</p>"
                    f"{evidence(item['evidence'])}"
                )
                markdown += [
                    _md(f"{item['criterion']}: {item['reason']}"),
                    *md_evidence(item["evidence"]),
                ]
            parts.append("</details>")
        if state["calculations"]:
            parts.append(
                (
                    f"<section class='calculation-records'><h3>{_e(label('calculations'))}</h3>"
                    if overview_available
                    else f"<details open><summary>{_e(label('calculations'))}</summary>"
                )
                + f"<p>{_e(label('calculation_note'))}</p>"
            )
            markdown.append(f"### {_md(label('calculations'))}")
            for calculation in state["calculations"]:
                data = json.dumps(calculation, ensure_ascii=False, indent=2)
                comparison = calculation["comparison"]
                parts.append(
                    f"<article id='calculation-{_e(calculation['id'])}'><h4>"
                    f"{_e(calculation['id'])} · {_e(calculation['method'])} · "
                    f"{_e(label(comparison['status']))}</h4>"
                    + (
                        f"<details class='calculation-details'><summary>"
                        f"{_e(label('calculation_details'))}</summary>"
                        if overview_available
                        else ""
                    )
                    + f"<p>{_e(label('formula'))}: {_e(calculation['formula'])}</p>"
                    f"<h5>{_e(label('inputs'))}</h5><table><tbody>"
                )
                markdown += [
                    f'<a id="calculation-{_e(calculation["id"])}"></a>',
                    f"#### {_md(calculation['method'])}",
                    _md(label(comparison["status"])),
                    _md(calculation["formula"]),
                ]
                for key, binding in calculation["inputs"].items():
                    parts.append(
                        f"<tr><td>{_e(key)}</td><td>{_e(binding['value'])}</td>"
                        f"<td>{evidence(binding['evidence'])}</td></tr>"
                    )
                    markdown += [
                        f"- {_md(key)}: {_md(binding['value'])}",
                        *md_evidence(binding["evidence"]),
                    ]
                parts.append(f"</tbody></table><h5>{_e(label('outputs'))}</h5><dl>")
                for key, value in calculation["outputs"].items():
                    display = str(value)
                    parts.append(f"<dt>{_e(key)}</dt><dd>{_e(display)}</dd>")
                    markdown.append(f"- {_md(key)}: {_md(display)}")
                parts.append("</dl>")
                if comparison.get("reported"):
                    reported = comparison["reported"]
                    parts.append(
                        f"<p>{_e(label('reported'))}: {_e(comparison['relation'])} "
                        f"{_e(reported['value'])}</p>{evidence(reported['evidence'])}"
                    )
                    markdown += [
                        f"{_md(label('reported'))}: {_md(comparison['relation'])} "
                        f"{_md(reported['value'])}",
                        *md_evidence(reported["evidence"]),
                    ]
                parts.append(
                    f"<h5>{_e(label('assumptions'))}</h5>"
                    + "".join(f"<p>{_e(a)}</p>" for a in calculation["assumptions"])
                )
                parts.append(
                    f"<details><summary>JSON</summary><pre>{_e(data)}</pre></details>"
                    + ("</details>" if overview_available else "")
                    + "</article>"
                )
                markdown += [_md(label("assumptions"))] + [
                    f"- {_md(a)}" for a in calculation["assumptions"]
                ]
            parts.append("</section>" if overview_available else "</details>")
        parts.append(
            f"<details><summary>{_e(label('guidance'))}</summary>"
            + "".join(f"<p>{_e(g)}</p>" for g in MODULES[name]["guidance"])
            + "</details></section>"
        )
    parts.append(f"<section><h2>{_e(label('reviewer_record'))}</h2>")
    for note in run["notes"]:
        statement = (
            f"{note['observation_id']} · {note['disposition']} · "
            f"transcript_verified={note['verified']}"
        )
        parts.append(f"<p>{_e(statement)}</p><blockquote>{_e(note['words'])}</blockquote>")
        markdown += [f"### {_md(statement)}", _md(note["words"])]
        notes += [f"## {_md(statement)}", _md(note["words"])]
    parts.append("</section>")
    parts.append(f"<section id='source'><h2>{_e(label('source'))}</h2>")
    markdown.append(f"\n## {_md(label('source'))}")
    for table in run["source"]["tables"]:
        parts.append(
            f"<h3>{_e(table['id'])}</h3><p>{_e(table.get('caption_context', ''))}</p>"
            f"<p class='meta'>{_e(table['notes'])} · ambiguous={table['ambiguous']}</p>"
            "<table><tbody>"
        )
        for row in range(1, table["rows"] + 1):
            parts.append("<tr>")
            for cell in table["cells"]:
                if cell["row"] == row and not cell.get("merged_into"):
                    parts.append(
                        f"<td rowspan='{cell['row_span']}' colspan='{cell['column_span']}'>"
                        f"<a href='#source-{_e(cell['id'])}'>{_e(cell['text']) or ' '}</a></td>"
                    )
            parts.append("</tr>")
        parts.append("</tbody></table>")
    for block in run["source"]["blocks"]:
        parts.append(
            f"<div class='source-block' id='source-{_e(block['id'])}'>"
            f"<small>{_e(block['id'])} · {_e(block['locator'])}</small>"
            f"<pre>{_e(block['text'])}</pre>"
        )
        markdown += [
            f'<a id="source-{block["id"]}"></a>',
            f"### {_md(block['locator'])}",
            "\n".join("    " + line for line in block["text"].splitlines()),
        ]
        if "extracted_text" in block:
            layout_label = {
                "en": "Original extracted PDF layout — quote text changes whitespace only",
                "ko": "추출된 PDF의 원래 줄 배치 — 인용문은 공백만 정리함",
            }.get(language, label("source") + " · PDF")
            parts.append(
                f"<details><summary>{_e(layout_label)}</summary>"
                f"<pre>{_e(block['extracted_text'])}</pre></details>"
            )
            markdown += [
                _md(layout_label),
                "\n".join("    " + line for line in block["extracted_text"].splitlines()),
            ]
        parts.append("</div>")
    parts.append("</section>")
    language = language if language != "inherit" else "und"
    style = (
        "body{font:17px/1.6 system-ui,sans-serif;max-width:1100px;mar"
        "gin:2rem auto;padding:0 "
        "1rem;color:#202932}nav{position:sticky;top:0;background:whit"
        "e;padding:.7rem;border-bottom:1px solid "
        "#ddd}section{margin:2rem 0}article,details,aside{border:1px "
        "solid #d5dce1;border-radius:6px;padding:1rem;margin:.7rem "
        "0}aside{background:#fff6df}summary{cursor:pointer;font-weigh"
        "t:600}blockquote{margin:.5rem 0;padding:.6rem "
        "1rem;border-left:3px solid "
        "#7190a6;background:#f3f6f8;white-space:pre-wrap}table{border"
        "-collapse:collapse;display:block;overflow:auto;width:100%}td"
        ",th{border:1px solid "
        "#bcc6ce;padding:.5rem;min-width:65px;white-space:pre-wrap}pr"
        "e{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}s"
        "mall,.meta{color:#526471;font-size:.85rem;overflow-wrap:anywhere}.source-block{padd"
        "ing:.6rem;border-bottom:1px solid "
        "#ddd;scroll-margin-top:5rem}:target{background:#fff4b8}a{col"
        "or:#135a83}h2,h3,article[id]{scroll-margin-top:5rem}@media "
        "print{nav{position:static}details{display:block}}"
    )
    document = (
        f"<!doctype html><html lang='{_e(language)}'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; "
        "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
        f"<title>{_e(label('scope'))}</title><style>{style}</style></head><body>"
        + "".join(parts)
        + "</body></html>"
    )
    return document, "\n\n".join(markdown) + "\n", "\n\n".join(notes) + "\n"


def export(run_id: str, output: Path | None = None) -> dict[str, Any]:
    root = _root(run_id)
    with FileLock(str(root / ".lock")):
        run = _load(root)
        if output is None:
            output = root / "exports" / f"dossier-{secrets.token_hex(4)}"
        else:
            output = output.expanduser().resolve()
            if output.exists():
                raise ReviewError(
                    "choose a new export directory; existing material will not be overwritten"
                )
        ensure_private_dir(output)
        html_text, markdown, notes = render(run)
        for name, content in (
            ("dossier.html", html_text),
            ("dossier.md", markdown),
            ("reviewer-notes.md", notes),
        ):
            atomic_write_text(output / name, content)
        atomic_write_json(output / "support.json", run)
        subjects = [
            {
                "role": "support-dossier",
                "file": name,
                "sha256": sha256_file(output / name),
                "text_sha256": text_sha256((output / name).read_text(encoding="utf-8")),
            }
            for name in ("dossier.html", "dossier.md", "reviewer-notes.md", "support.json")
        ]
        identity = installed_identity()
        receipt = {
            "receipt_version": RECEIPT_VERSION,
            "tool": {
                "name": "closed-review",
                "version": identity["version"],
                "sums_sha256": identity["sums_sha256"],
            },
            "protocol": PROTOCOL,
            "run_id": run_id,
            "revision": run["revision"],
            "execution_identity": run["identity"],
            "source_sha256": run["source"]["sha256"],
            "language": run["resolved_language"] or run["language"],
            "modules": {
                k: {
                    "status": v["status"],
                    "guide_version": MODULES[k]["version"],
                    "provided_blocks": len(v["provided_blocks"]),
                }
                for k, v in run["modules"].items()
            },
            "model": run["route"]["model"],
            "qualification": "not_qualified",
            "preflight": {
                "status": "passed_at_start",
                "network_isolation": "not_enforced_by_plugin",
            },
            "exported_at": now_iso(),
            "subjects": subjects,
            "attestations": [{"type": "self"}],
        }
        receipt = {"receipt_id": receipt_id(receipt), **receipt}
        atomic_write_json(output / "receipt.json", receipt)
    return {
        "directory": str(output),
        "html": str(output / "dossier.html"),
        "markdown": str(output / "dossier.md"),
        "receipt": str(output / "receipt.json"),
        "phase": _phase(run),
        "note": (
            "No server started. This dossier is model support, not a full review or certification."
        ),
    }
