"""Prepare an offline source-only approval packet; no findings, keys or inferred decisions.

This evaluator utility creates private files only. It never starts a server, contacts a model,
reads author proposals, changes a source manifest or certifies a medical test case.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import os
import shutil
from pathlib import Path

from closed_review.errors import ReviewError
from closed_review.io import atomic_write_json, atomic_write_text, ensure_private_dir, sha256_file
from closed_review.support.evaluation import load_manifest

RENDERER = Path(__file__).with_name("render-korean-audit.py")
MODULE_LABELS = {
    "statistics": "통계",
    "qualitative-study": "질적 연구",
    "systematic-review": "체계적 문헌고찰 (SR)",
    "scoping-review": "주제범위 문헌고찰 (ScR)",
    "narrative-review": "서술적 문헌고찰",
    "logic": "논증·윤리·법",
}
INSTRUCTIONS = """# 원고 자체의 시험 적합성 검토 / Source-only approval

아직 승인되지 않은 가상 원고입니다. 임상·법률 지침이나 플러그인 성능 판정이 아닙니다.
한국어는 검토 안내에만 사용하며 원고와 표는 영어 원문 그대로 제공합니다.
모델의 지적, 베이스라인 출력, 작성자의 오류 제안과 정답키는 이 자료에 포함하지 않습니다.

1. 먼저 각 원고의 본문·표·논의를 읽고 `명시한 시험 목적에 적합`, `수정 필요`, `제외`
   또는 `보류`와 구체적인 근거를 기록해 주세요. 아직 어느 항목도 자동 승인되지 않았습니다.
2. 통계는 인쇄된 수치와 분석 모집단·분모·검정의 대응, 질적 연구는 명시한 분석 전통과
   자료–코드–주제 연결, SR/ScR/서술적 고찰은 해당 목적에 맞는 선정·합성·주장 범위,
   논증은 사실·규범·연결 전제와 반론 응답을 살펴주세요. 다른 전통을 일률적으로 강요하거나
   윤리적 견해 차이를 오류로 간주해서는 안 됩니다. 원자료·실제 외부 문헌은 제공하지 않습니다.
3. 검토자 이름·날짜·관련 전문성·판단 근거와 실제 배포 영역에 대한 대표성도 별도로 기록합니다.
   관련된 퇴원·전화 사례 12편이라는 사실만으로 모든 의학 분야를 대표하지는 않습니다.

원고 적합성 승인과 대조군·삽입 오류 역할 확정은 별개입니다. 후자의 정확한 근거·위치와
정답키는 사람이 독립적으로 확정하여 평가자 전용 위치에만 보관하고 모델 서버에 보내지 않습니다.
부적합한 원고를 수정·교체한다면 새 파일·해시·검토가 필요합니다. 모델의 무지적 결과나 작성자의
의도만으로 정상 대조군을 만들지 마세요. 새 승인 원고와 키 없는 manifest를 확정한 후에만
새 공식 3회 반복 지원/베이스라인 시험을 시작합니다. 기존 개발 시험은 소급 승인할 수 없습니다.

이 HTML은 읽기 전용입니다. 입력 버튼은 없으며, 사본의 source-review-template.json에
기록하거나 채팅으로 `원고 ID: 판단 — 근거`를 전달할 수 있습니다. 원고 적합성 판단은
플러그인 지적의 승인이나 성능 검증을 뜻하지 않습니다. 알 수 없는 항목은 미검토로 유지합니다.

Read originals before model findings or author proposals. Record genuine reviewer identity,
date, expertise, source suitability and representativeness. Blank fields are not decisions.
Keep private case assignments/keys offline; freeze a NEW approved corpus before formal runs.
No model, server or network request is made by this packet builder.
"""


def prepare(manifest: Path, corpus: Path, output: Path) -> dict:
    if os.environ.get("HERMES_SESSION_ID"):
        raise ReviewError("prepare source approval outside Hermes on the evaluator machine")
    manifest, corpus, output = manifest.resolve(), corpus.resolve(), output.resolve()
    if output.exists():
        raise ReviewError("choose a NEW packet directory; never overwrite reviewer work")
    manifest_hash = sha256_file(manifest)
    value, rows = load_manifest(manifest, corpus)
    if value["independently_reviewed"] is not False:
        raise ReviewError(
            "this packet is for unreviewed candidate sources, not approval relabeling"
        )
    spec = importlib.util.spec_from_file_location("source_only_renderer", RENDERER)
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    checked = []
    for row in rows:
        if row["path"].suffix.lower() != ".md":
            raise ReviewError("source-only packet accepts original synthetic Markdown sources")
        raw = row["path"].read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ReviewError("candidate source changed while preparing the packet")
        text = raw.decode("utf-8")
        identifier = row["case_id"]
        # Reuse the existing escaped, offline paragraph/table renderer, not the legacy
        # finding renderer. Prefix line anchors so the twelve papers have unique IDs.
        rendered = renderer._manuscript(text, {}).replace('id="ko-', f'id="{identifier}-line-')
        checked.append((row, text, rendered))
    if sha256_file(manifest) != manifest_hash:
        raise ReviewError("candidate manifest changed while preparing the packet")
    ensure_private_dir(output)
    sources = ensure_private_dir(output / "manuscripts")
    shutil.copyfile(manifest, output / "input-manifest.json")
    (output / "input-manifest.json").chmod(0o600)
    if sha256_file(output / "input-manifest.json") != manifest_hash:
        raise ReviewError("candidate manifest changed while copying it")
    nav, papers, decisions = [], [], []
    for row, text, rendered in checked:
        identifier, module = row["case_id"], row["module"]
        copy = sources / f"{identifier}.md"
        shutil.copyfile(row["path"], copy)
        copy.chmod(0o600)
        if sha256_file(copy) != row["sha256"]:
            raise ReviewError("candidate source changed while copying it")
        label = html.escape(MODULE_LABELS[module])
        nav.append(f'<a href="#{identifier}">{identifier} · {label}</a>')
        papers.append(
            f'<article id="{identifier}"><h2>{identifier} · {label}</h2>'
            '<p>판단: 미검토 · 원고는 영어 원문이며 번역·의학적 승인을 뜻하지 않습니다.</p>'
            f'<small>SHA256 {row["sha256"]} · 원문 {len(text.split())}단어</small>'
            f'<div lang="en" class="paper">{rendered}</div>'
            '<details><summary>변경 없는 Markdown 원문 보기</summary>'
            f'<pre lang="en">{html.escape(text)}</pre></details>'
            '<p><a href="#top">원고 목록으로</a></p></article>'
        )
        decisions.append({
            "case_id": identifier, "module": module, "source_sha256": row["sha256"],
            "decision": None, "reasons": "",
        })
    template = {
        "protocol": value["protocol"], "purpose": "source_only_candidate_review",
        "input_manifest_sha256": manifest_hash, "independently_reviewed": False,
        "reviewer": None, "reviewed_at": None, "relevant_expertise": None,
        "representative_for_intended_deployment": None, "representativeness_reasons": "",
        "sources": decisions,
        "note": (
            "No case roles/keys or human decisions inferred. "
            "Do not send completed reviews to models."
        ),
    }
    intro = (
        '<section id="top" class="intro"><h1>가상 원고 후보: 원고 자체의 적합성 검토</h1>'
        '<p>미승인 · 성능 판정 아님 · 모델 결과·작성자 제안·정답키 없음</p>'
        f'<pre>{html.escape(INSTRUCTIONS)}</pre><nav>{"".join(nav)}</nav></section>'
    )
    document = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        'style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
        '<title>원고 후보 독립 검토 — 미승인</title>' + renderer.CSS
        + '</head><body><main>' + intro + "".join(papers) + '</main></body></html>\n'
    )
    atomic_write_text(output / "source-review-ko.html", document)
    atomic_write_text(output / "README.md", INSTRUCTIONS)
    atomic_write_json(output / "source-review-template.json", template)
    report = {
        "directory": str(output), "sources": len(rows), "source_language": "original English",
        "instructions_language": "Korean and English", "human_decisions": "all_blank",
        "manifest_sha256": manifest_hash, "renderer_sha256": sha256_file(RENDERER),
        "builder_sha256": sha256_file(Path(__file__)),
        "html_sha256": sha256_file(output / "source-review-ko.html"),
        "original_source_copies_verified": True, "model_findings_included": False,
        "author_proposals_read": False, "keys_imported": False,
        "server_started": False, "qualification": "not_qualified",
    }
    atomic_write_json(output / "packet-provenance.json", report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(prepare(args.manifest, args.corpus, args.output), ensure_ascii=False))
    except (ReviewError, OSError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
