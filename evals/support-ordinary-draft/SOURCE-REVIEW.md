# Source-only approval before a formal medical evaluation

This is a reviewer worksheet, not an assessment or answer key. All six drafts are invented,
unreviewed development inputs. Their successful parsing, length and table counts do not establish
medical plausibility, correctness or suitability as controls. Do not fill this worksheet by
copying the model's findings or treating the author's intentions as independent approval.

## What to read and decide

Read the original manuscript, including its tables and discussion, **before** looking at its
support or baseline output. Choose `revise`, `exclude` or `suitable for the specified purpose`.
Record your name, review date, relevant expertise and reasons in an evaluator-only copy.
Approval of a draft is not approval of the plugin's findings.

| Original source | Requested branch | Source-only questions | Human decision / reasons |
| --- | --- | --- | --- |
| [r17.md](manuscripts/r17.md) | Statistics | Are populations, denominators, endpoints, timing, table labels and reported analyses coherent? Are proposed recalculations justified by printed sufficient inputs rather than imagined records? | Not reviewed |
| [q28.md](manuscripts/q28.md) | Qualitative study | Are recruitment, participant construction, stated analytic tradition, excerpts, coding and themes coherent? Are contrasting accounts represented without imposing a different qualitative tradition? | Not reviewed |
| [s43.md](manuscripts/s43.md) | Systematic review | Are records, reports and studies distinguished; related reports linked; outcomes comparable; and appraisal/synthesis choices supportable from the manuscript? | Not reviewed |
| [h36.md](manuscripts/h36.md) | Scoping review | Are the question, inclusion process and source-level mapping coherent? Are overlapping categories distinguished from exclusive flow counts, without implying effectiveness or population prevalence? | Not reviewed |
| [n54.md](manuscripts/n54.md) | Narrative review | Does the declared purposive approach support the stated conceptual purpose? Are descriptive, associative, intervention and normative claims separated without pretending this is an exhaustive systematic review? | Not reviewed |
| [l62.md](manuscripts/l62.md) | Logic | Are fictional rules, empirical stipulations, normative premises, bridge claims and objection–reply links distinguishable? Can a reviewer inspect the argument without treating moral disagreement as a factual defect? | Not reviewed |

The review manuscripts contain fictional source accounts, not real published studies to retrieve
or independently verify. The qualitative draft does not supply raw interviews; the statistical
draft does not supply patient records. Judge whether those limitations fit a **manuscript-only
support** test. If genuine literature validation, participant-level analysis or a real legal rule
is needed, exclude or redesign the case; do not invent the missing material.

Also record whether the six drafts adequately represent the intended deployment domain and
workload. One authored example per branch does not demonstrate broad medical representativeness.
Native-format copies of one short article are not additional independent medical cases.

## Keep source approval and issue adjudication separate

1. Preserve this development corpus, manifest and engineering outputs unchanged. Its manifest
   remains `independently_reviewed: false`; later approval cannot qualify an already-started batch.
2. In a **new evaluator-held corpus**, revise or replace unsuitable sources. A qualified human
   must establish the comparison cases and genuinely seeded cases for every branch. Do not call
   any present draft a clean control merely because no defect was intended.
3. Keep case assignments, expected issues, exact supporting locations, acceptable alternatives,
   exclusions and reviewer reasons in a separate private packet. Never put these in manuscript
   filenames, the model-host manifest, prompts or a repository commit. Do not use legacy keys.
4. Independently approve the final sources and their intended test roles, then freeze exact file
   hashes and a **new** key-free manifest before starting the formal evaluation. Only a completed
   human review can justify `independently_reviewed: true`. Keep approval identity/date/reasons
   separately; the strict manifest accepts no extra key or review fields.
5. Run the original three-repetition support/baseline batch on that frozen corpus and build its
   offline audit packet. Record actual human finding judgments, missed seeded issues, unsupported
   numerical claims, baseline quality and checking times there. Leave unknown values blank.

The key-free manifest contains only protocol, corpus ID, synthetic/reviewed flags and
case ID/module/file/hash entries. Source-only approval, medical usefulness, workflow completion,
reviewer time saving and release authorization are different decisions; none substitutes for
another. See [the pilot protocol](../../docs/support-pilot.md) and
[deployment readiness](../../docs/deployment-readiness.md).

## 한국어 안내

이 문서는 원고 승인용 빈 검토 안내입니다. 정답지나 플러그인 성능 판정이 아닙니다.
먼저 위의 원고 파일 자체와 표를 읽고, 모델의 의견을 보기 전에 `수정 필요`, `제외`,
`명시한 시험 목적에 적합` 중 하나와 근거를 별도의 평가자 전용 사본에 기록해 주세요.
검토자 이름·날짜·전문 분야도 실제 검토 후 기록합니다. 아직 어느 원고도 승인되지 않았습니다.

통계는 원고에 인쇄된 수치만으로 재계산이 가능한지, 질적 연구는 명시한 분석 전통과
자료–코드–주제 연결이 일관적인지 살핍니다. SR은 기록·보고서·연구의 구분과 합성 근거,
ScR은 중복 분류와 배타적 흐름 수치의 구분, 서술적 문헌고찰은 주장 종류와 선정 목적,
논증은 사실 전제·규범 전제·연결 전제와 반론 응답을 확인합니다. 다른 방법론을 일률적으로
강요하거나 윤리적 견해 차이를 오류로 판정하는 시험이 되어서는 안 됩니다.

이 원고들은 가상의 사례입니다. 실제 논문의 진위, 원자료 또는 실제 법률의 정확성을
검증했다고 간주할 수 없습니다. 정답·삽입 오류·대조군 표시는 모델 서버에 보내지 않습니다.
기존 개발 시험은 소급 승인하지 않으며, 사람이 확정한 새 원고 집합으로 새 평가를 해야 합니다.
