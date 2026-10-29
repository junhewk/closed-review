"""Deterministic navigation for supported locales; model prose follows user preference."""

from __future__ import annotations

from ..errors import ReviewError

EN = {
    "scope": "Review support scope",
    "reconstruction": "Manuscript reconstruction",
    "observations": "Observations for reviewer consideration",
    "criteria": "Criterion assessments",
    "calculations": "Source-bound calculations",
    "source": "Original extracted manuscript",
    "notes": "Notes",
    "limitations": "Limitations",
    "coverage": "Source blocks provided",
    "model_proposal": "Model proposal — not reviewer-adopted",
    "reviewer_record": "Reviewer record",
    "withdrawn": "Not surfaced / withdrawn",
    "calculated_discrepancy": "Calculated discrepancy",
    "reporting_gap": "Reporting question",
    "methodological_concern": "Provisional methodological concern",
    "not_assessable": "Not assessable from this manuscript",
    "calculation_note": (
        "Arithmetic is checked on the selected manuscript inputs. "
        "Their interpretation, mapping and scientific importance remain unverified."
    ),
    "supported": "Supported by the displayed manuscript",
    "concern": "Provisional concern",
    "not_located": "Not located in this manuscript",
    "not_applicable": "Not applicable",
    "connections": "Support, conclusion and rebuttal connections",
    "status": "Workflow status",
    "guidance": "Packaged guidance and applicability",
    "complete": "Workflow completed — not certified",
    "partial": "Incomplete coverage",
    "running": "In progress",
    "pending": "Pending",
    "failed": "Stopped with failure",
    "inputs": "Selected inputs",
    "outputs": "Computed outputs",
    "reported": "Reported value",
    "formula": "Formula",
    "assumptions": "Input-selection assumptions",
    "match": "Matches reported rounding",
    "mismatch": "Does not match reported rounding",
    "conditional": "Conditional statistical comparison",
    "not_compared": "Not compared",
    "counterevidence": "Counterevidence and author qualifications",
    "scope_limits": "Manuscript-only scope limitations",
    "coverage_gaps": "Processing / coverage gaps",
    "linked_calculations": "Calculation evidence for this observation",
    "comparison_overview": "Numerical comparison overview",
    "calculation_method": "Calculation",
    "compared_output": "Compared output",
    "numerical_agreement": "Agreement on selected inputs",
    "numerically_matches": "Agrees on selected inputs",
    "numerically_differs": "Differs on selected inputs",
    "agreement_unrecorded": "Agreement not recorded",
    "comparison_status": "Comparison status",
    "calculation_details": "Inspect inputs, outputs, sources and assumptions",
    "comparison_overview_note": (
        "Conditional comparisons can agree or differ numerically. Neither result certifies "
        "input roles, scientific validity or an error. Inspect the linked sources and "
        "assumptions. Computed values are shown as saved; reported numeric tokens are unchanged. "
        "On narrow screens, scroll the table horizontally."
    ),
}
KO = {
    "scope": "검토 지원 범위",
    "reconstruction": "원고 구조 재구성",
    "observations": "검토자가 판단할 관찰 사항",
    "criteria": "항목별 검토 내용",
    "calculations": "원문 근거에 연결된 계산",
    "source": "추출된 원고 원문",
    "notes": "메모",
    "limitations": "한계",
    "coverage": "제공된 원문 블록",
    "model_proposal": "모델 제안 — 검토자가 채택한 의견 아님",
    "reviewer_record": "검토자 기록",
    "withdrawn": "제시하지 않거나 철회한 사항",
    "calculated_discrepancy": "계산상 불일치",
    "reporting_gap": "보고 내용에 대한 확인 질문",
    "methodological_concern": "잠정적인 방법론적 우려",
    "not_assessable": "이 원고만으로 평가할 수 없음",
    "calculation_note": (
        "선택한 원고 수치에 대한 산술 계산을 확인했습니다. "
        "수치의 의미와 대응 관계, 과학적 중요성까지 검증한 것은 아닙니다."
    ),
    "supported": "제시된 원고에서 뒷받침됨",
    "concern": "잠정적 우려",
    "not_located": "이 원고에서 찾지 못함",
    "not_applicable": "해당 없음",
    "connections": "근거·결론·반론의 연결",
    "status": "작업 상태",
    "guidance": "적용 범위가 명시된 검토 지침",
    "complete": "작업 완료 — 검증 인증 아님",
    "partial": "일부 범위 미완료",
    "running": "진행 중",
    "pending": "대기 중",
    "failed": "오류로 중단됨",
    "inputs": "선택한 입력값",
    "outputs": "계산 결과",
    "reported": "원고에 보고된 값",
    "formula": "계산식",
    "assumptions": "입력값 선택의 전제",
    "match": "보고된 반올림 범위에서 일치",
    "mismatch": "보고된 반올림 범위에서 불일치",
    "conditional": "조건부 통계 비교",
    "not_compared": "비교하지 않음",
    "counterevidence": "반대 근거와 저자의 단서",
    "scope_limits": "원고만 검토하는 데 따른 한계",
    "coverage_gaps": "처리 또는 검토 범위의 누락",
    "linked_calculations": "이 관찰 사항에 연결된 계산 근거",
    "comparison_overview": "수치 비교 요약",
    "calculation_method": "계산",
    "compared_output": "비교한 출력값",
    "numerical_agreement": "선택한 입력값 기준 수치 일치 여부",
    "numerically_matches": "선택한 입력값 기준 일치",
    "numerically_differs": "선택한 입력값 기준 불일치",
    "agreement_unrecorded": "일치 여부가 기록되지 않음",
    "comparison_status": "비교 상태",
    "calculation_details": "입력값·출력값·원문 근거·전제 확인",
    "comparison_overview_note": (
        "조건부 비교도 수치가 일치하거나 다를 수 있습니다. 어느 쪽도 입력값의 의미, "
        "과학적 타당성 또는 오류 여부를 인증하지 않습니다. 연결된 원문과 전제를 "
        "확인하세요. 계산 결과는 저장된 값으로, 보고값은 원문의 수치 표기를 그대로 표시합니다. "
        "좁은 화면에서는 표를 좌우로 스크롤하세요."
    ),
}
LABELS = tuple(EN)
COMPARISON_LABELS = (
    "comparison_overview",
    "calculation_method",
    "compared_output",
    "numerical_agreement",
    "numerically_matches",
    "numerically_differs",
    "agreement_unrecorded",
    "comparison_status",
    "calculation_details",
    "comparison_overview_note",
)


def normalize_language(language: str) -> str:
    value = language.strip()
    if value.casefold() in {"english", "en", "en-us", "en-gb"}:
        return "en"
    if value.casefold() in {"korean", "ko", "ko-kr", "한국어"}:
        return "ko"
    return value


def labels_for(language: str, custom: dict | None = None) -> dict[str, str]:
    language = normalize_language(language)
    if language in {"en", "ko"}:
        return dict(EN if language == "en" else KO)
    if not isinstance(custom, dict) or set(custom) != set(LABELS):
        raise ReviewError(
            "provide all navigation labels for this response language: " + ", ".join(LABELS)
        )
    if any(not isinstance(v, str) or not v.strip() or len(v) > 400 for v in custom.values()):
        raise ReviewError("each navigation label must be a nonempty string, at most 400 characters")
    if custom["calculation_note"] == "calculation_note":
        raise ReviewError(
            "calculation_note must explain arithmetic versus input-interpretation limits"
        )
    return dict(custom)
