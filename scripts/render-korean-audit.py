"""Render one synthetic qualification run and its supplied Korean translation offline.

The resulting single HTML file has no external assets or answer key. The original manuscript
and model quotations remain available for comparison; translations are not audit decisions.
"""

from __future__ import annotations

import argparse
import html
import os
import re
from pathlib import Path
from typing import Any

from closed_review.errors import ReviewError
from closed_review.findings import confirmed_check, severity
from closed_review.io import read_json, sha256_file

CSS = """<style>
:root { color-scheme: light; } * { box-sizing: border-box; }
body { margin: 0; background: #f4f6fa; color: #172233;
       font: 17px/1.7 system-ui, -apple-system, sans-serif; }
main { max-width: 1000px; padding: 1rem; margin: 0 auto; }
h1,h2,h3,h4 { line-height: 1.35; } h2 { margin-top: 2rem; }
.intro, article, .paper { background: #fff; border: 1px solid #d6deea;
                         border-radius: .65rem; margin: 1rem 0; padding: 1rem 1.3rem; }
.intro { background: #edf5ff; } .warning { color: #8b3d00; }
nav { display: flex; flex-wrap: wrap; gap: .5rem; }
nav a { padding: .25rem .7rem; background: #e8f0fd; border-radius: 1rem; }
a { color: #0752a0; } summary { cursor: pointer; font-weight: 600; }
details { margin: .8rem 0; } .evidence { background: #f7f9fc; padding: .5rem .8rem;
                                         border-radius: .4rem; }
blockquote { border-left: 4px solid #9aadc2; margin: .5rem 0; padding: 0 1rem; }
small { color: #526276; } .line:target { background: #fff2bd; }
.table-scroll { overflow-x: auto; } table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #d6deea; padding: .35rem .5rem; text-align: left; }
th { background: #eaf0f7; } pre { white-space: pre-wrap; overflow-wrap: anywhere; }
</style>"""


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _evidence(item: Any, source: str, translated: dict[str, str]) -> str:
    if not isinstance(item, dict):
        return f"<p>구조화되지 않은 근거: {esc(item)}</p>"
    quote = str(item.get("quote") or "")
    source_id = str(item.get("source_id") or "unknown")
    location = str(item.get("locator") or "위치 정보 없음")
    offset = source.find(quote) if quote and source_id == "manuscript" else -1
    if offset >= 0:
        line = source.count("\n", 0, offset) + 1
        count = source.count(quote)
        position = "첫 번째 일치 위치" if count > 1 else "원문 위치"
        link = f'<a href="#ko-{line}">{position}: {line}행의 번역 문단으로 이동</a>'
        paragraph = translated.get(str(line), "참고 문헌은 원어로 유지합니다.")
        label = "아래는 인용문을 포함한 전체 문단의 번역입니다. 인용문 자체와 구별해 읽어 주세요."
    else:
        link = esc(location)
        paragraph = (
            "이 원고에서 인용문과 정확히 일치하는 위치를 찾지 못했습니다. 직접 확인해 주세요."
        )
        label = "원문 위치를 자동으로 확인하지 못했습니다."
    return (
        f'<div class="evidence"><p>{link}<br><small>{esc(label)}</small></p>'
        f"<p>{esc(paragraph)}</p><details><summary>모델이 인용한 영어 원문 보기</summary>"
        f"<blockquote>{esc(quote or '인용문 없음')}</blockquote></details>"
        f"<small>출처: {esc(source_id)} · 모델이 기록한 위치: {esc(location)}. "
        "텍스트 일치만으로 지적의 타당성이 입증되지는 않습니다.</small></div>"
    )


def _table_row(text: str, line: int, header: bool = False) -> str:
    tag = "th" if header else "td"
    cells = [cell.strip() for cell in text.strip().strip("|").split("|")]
    return (
        f'<tr id="ko-{line}" class="line">'
        + "".join(f"<{tag}>{esc(cell)}</{tag}>" for cell in cells)
        + "</tr>"
    )


def _table_separator(text: str) -> bool:
    stripped = text.strip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        return False
    return all(
        re.fullmatch(r":?-+:?", cell.strip())
        for cell in stripped[1:-1].split("|")
    )


def _manuscript(source: str, translated: dict[str, str]) -> str:
    originals = source.splitlines()
    parts = []
    index = 0
    while index < len(originals):
        original = originals[index]
        line = index + 1
        if not original.strip():
            index += 1
            continue
        ko = translated.get(str(line), original)
        if original.startswith("|"):
            rows = [_table_row(ko, line, header=True)]
            index += 1
            if index < len(originals) and _table_separator(originals[index]):
                index += 1
            while index < len(originals) and originals[index].startswith("|"):
                line = index + 1
                rows.append(_table_row(translated.get(str(line), originals[index]), line))
                index += 1
            parts.append('<div class="table-scroll"><table>' + "".join(rows) + "</table></div>")
            continue
        clean = ko.lstrip("# ") if original.startswith("#") else ko
        if original.startswith("### "):
            parts.append(f'<h4 id="ko-{line}" class="line">{esc(clean)}</h4>')
        elif original.startswith("## "):
            parts.append(f'<h3 id="ko-{line}" class="line">{esc(clean)}</h3>')
        elif original.startswith("# "):
            parts.append(f'<h2 id="ko-{line}" class="line">{esc(clean)}</h2>')
        elif original.startswith("> "):
            parts.append(
                f'<blockquote id="ko-{line}" class="line">{esc(ko.removeprefix("> "))}</blockquote>'
            )
        else:
            parts.append(f'<p id="ko-{line}" class="line">{esc(ko)}</p>')
        index += 1
    return "".join(parts)


def render(source: str, scan: dict, translation: dict, source_hash: str, run_id: str) -> str:
    if translation.get("source_sha256") != source_hash:
        raise ReviewError("translation was made for a different manuscript")
    paragraphs = translation.get("paragraphs", {})
    translated_findings = translation.get("findings", {})
    originals = source.splitlines()
    try:
        references_line = originals.index("## References") + 1
    except ValueError as exc:
        raise ReviewError("cannot locate the manuscript reference section") from exc
    missing = [
        str(number)
        for number, value in enumerate(originals, start=1)
        if value.strip()
        and number <= references_line
        and (
            not isinstance(paragraphs.get(str(number)), str) or not paragraphs[str(number)].strip()
        )
    ]
    if missing:
        raise ReviewError("missing manuscript translations for lines: " + ", ".join(missing))
    findings = [
        f for f in scan["review"]["findings"] if f.get("status") not in {"screened", "dismissed"}
    ]
    if {str(f["id"]) for f in findings} != set(translated_findings):
        raise ReviewError("translated finding IDs differ from the saved scan")
    cards = []
    navigation = []
    for finding in findings:
        finding_id = str(finding["id"])
        ko = translated_findings[finding_id]
        checks = finding.get("flaw_checks") or []
        if not ko.get("issue") or not ko.get("why") or len(ko.get("checks", [])) != len(checks):
            raise ReviewError(f"incomplete finding or check translation: {finding_id}")
        navigation.append(f'<a href="#finding-{esc(finding_id)}">{esc(finding_id)}</a>')
        evidence = finding.get("evidence") or []
        evidence_html = "".join(_evidence(item, source, paragraphs) for item in evidence)
        check_html = []
        for check, check_translation in zip(checks, ko["checks"], strict=True):
            status = (
                "도구가 확인됨으로 표시"
                if confirmed_check(check)
                else "도구가 확인됨으로 표시하지 않음"
            )
            check_evidence = "".join(
                _evidence(item, source, paragraphs) for item in check.get("quotes") or []
            )
            check_html.append(
                f"<li><strong>{esc(check.get('flaw') or '검토 항목')}</strong> — {status}"
                f"<p>{esc(check_translation)}</p>"
                "<details><summary>이 검토 항목이 인용한 근거 보기</summary>"
                f"{check_evidence}</details></li>"
            )
        raw_rating = {"major": "중대", "minor": "경미"}.get(
            finding.get("model_severity"), "명시되지 않음"
        )
        scored_rating = {"major": "중대", "minor": "경미"}.get(
            severity(finding)["severity"], "미상"
        )
        cards.append(
            f'<article id="finding-{esc(finding_id)}"><h3>{esc(finding_id)}</h3>'
            f"<p><strong>모델이 제기한 지적</strong><br>{esc(ko['issue'])}</p>"
            f"<p><strong>모델이 설명한 중요성</strong><br>{esc(ko['why'])}</p>"
            f"<p><small>모델의 분류: {raw_rating} · 평가 도구의 분류: {scored_rating}. "
            "둘 다 사람의 판단이 아닙니다.</small></p>"
            f"<details><summary>인용 근거 {len(evidence)}개 보기</summary>{evidence_html}</details>"
            f"<details><summary>모델의 세부 검토 {len(checks)}개 보기</summary>"
            f"<ul>{''.join(check_html)}</ul></details>"
            '<p><a href="#findings">지적 목록으로</a> · '
            '<a href="#manuscript">원고 전체 읽기</a></p>'
            "</article>"
        )
    body = (
        "<h1>연구 검토 지원: 합성 원고 한국어 평가 자료</h1>"
        f'<div class="intro"><p>평가 실행: <strong>{esc(run_id)}</strong>. '
        "이 자료는 테스트용으로 만든 합성 원고이며 실제 학술지 투고 논문이 아닙니다.</p>"
        "<p>한국어는 원문을 돕기 위한 미검증 번역입니다. "
        "문장·숫자·모순을 원문대로 보존하려 했으며, "
        "판단할 때는 영어 원문도 확인하세요. 참고 문헌은 원어 표기를 유지합니다.</p>"
        '<p class="warning">모델의 지적과 분류는 확정된 사실이 아닙니다. '
        "인용문이 일치해도 해석의 타당성이 입증되는 것은 아닙니다. "
        "판단이 어렵다면 미평가로 두세요. "
        "비공개 정답 키와 평가자의 결정은 이 페이지에 포함하지 않았습니다.</p></div>"
        f'<h2 id="findings">모델이 제기한 지적 {len(findings)}건</h2>'
        f"<nav>{''.join(navigation)}</nav>{''.join(cards)}"
        '<section id="manuscript" class="paper"><h2>합성 원고 전체: 한국어 번역</h2>'
        f"<p><small>영어 원고 SHA-256: {esc(source_hash)}</small></p>"
        f"{_manuscript(source, paragraphs)}"
        "<details><summary>영어 원고 전체 보기</summary>"
        f"<pre>{esc(source)}</pre></details></section>"
    )
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>합성 원고 한국어 평가 자료</title>{CSS}</head>"
        f"<body><main>{body}</main></body></html>\n"
    )


def prepare(run: Path, translation_path: Path, output: Path) -> dict:
    report = read_json(run.parent / "results.json")
    run_id = run.name
    record = report.get("runs", {}).get(run_id)
    if not record or not record.get("passed"):
        raise ReviewError("the selected run is not a completed successful run")
    manuscript = run / "manuscript.md"
    source_hash = sha256_file(manuscript)
    if report.get("identity", {}).get("manuscripts", {}).get(record.get("case")) != source_hash:
        raise ReviewError("manuscript does not match the executed batch")
    source = manuscript.read_text(encoding="utf-8")
    content = render(
        source, read_json(run / "scan.json"), read_json(translation_path), source_hash, run_id
    )
    try:
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if (
            output.is_symlink()
            or not output.is_file()
            or output.read_text(encoding="utf-8") != content
        ):
            raise ReviewError(
                "output exists with different content; refusing to overwrite it"
            ) from None
    else:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(content)
    return {"run": run_id, "output": str(output), "manuscript_sha256": source_hash}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--translation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.run, args.translation, args.output)
    except (OSError, ReviewError, ValueError, KeyError) as exc:
        parser.exit(2, f"cannot render audit: {exc}\n")
    for key, value in result.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
