import type { ResearchReference, ResearchState } from '../../api/research'

// frontend/views/research.py의 STAGES/STAGE_DONE_FIELD와 완전히 같은 계약 —
// research_workflow.py의 _STAGE_ORDER/_STAGE_FIELDS와도 짝이 맞아야 한다.
export const STAGES: Array<[string, string]> = [
  ['hypothesis', '가설'],
  ['design', '설계'],
  ['operation', '실험 운영'],
  ['report', '보고서'],
  ['writing', '논문 초안'],
]

export const STAGE_LABELS: Record<string, string> = Object.fromEntries(STAGES)

// 각 단계가 "완료됐다"를 판정하는 대표 필드
export const STAGE_DONE_FIELD: Record<string, keyof ResearchState> = {
  hypothesis: 'hypothesis',
  design: 'procedure',
  operation: 'outcome',
  report: 'experiment_report',
  writing: 'abstract',
}

export function stageIndex(stage: string): number {
  return STAGES.findIndex(([s]) => s === stage)
}

// research_workflow.REFERENCE_NODE_BY_STAGE와 같은 계약 — report/writing은 참고문헌
// 노드가 없어(새 텍스트를 안 만들어 검색할 새 주장이 없음) "참고문헌만 다시 찾기"
// 버튼을 이 단계들에는 안 보여준다.
export const STAGES_WITH_REFERENCES = new Set(['hypothesis', 'design', 'operation'])

export type CellStatus = 'fresh' | 'inherited' | 'pending'

// 브랜치형 타임라인의 셀 3분류(RoadMap 설계 노트 참고) — 체크포인트 값을 diff할 필요
// 없이 entryStage 하나만으로 결정론적으로 나온다: research_workflow._reset_downstream_fields가
// 각 stage 진입 노드는 정확히 자기 필드만 채우고 뒤 단계는 항상 리셋하도록 보장하기
// 때문에, cellStage가 entryStage보다 앞이면 그 체크포인트가 만들어질 때 안 건드려서
// 부모에서 그대로 넘어온 값("계승"), 같으면 그 턴에 막 채운 값("fresh"), 뒤면
// 리셋되어 비어있는 값("미진행")이다.
export function cellStatus(entryStage: string, cellStage: string): CellStatus {
  const entryIdx = stageIndex(entryStage)
  const cellIdx = stageIndex(cellStage)
  if (cellIdx < entryIdx) return 'inherited'
  if (cellIdx === entryIdx) return 'fresh'
  return 'pending'
}

// target_stage(포함) 이후 단계 중 이미 값이 채워진 게 있으면, 재생성해도 자동으로
// 안 지워지고 낡은 채 남는다(WorkflowState에 버전 관리가 없음 — RoadMap 설계 노트 참고).
export function hasStaleDownstream(values: ResearchState, targetStage: string): boolean {
  const idx = stageIndex(targetStage)
  return STAGES.slice(idx).some(([s]) => Boolean(values[STAGE_DONE_FIELD[s]]))
}

// design_experiment()가 만드는 procedure는 "1. ... 2. ... 3. ..."처럼 번호는 붙지만
// 실제 줄바꿈이 없어 화면에 한 덩어리로 붙어 나온다(08-04 사용자 지적) — 백엔드
// 프롬프트를 바꾸는 대신 화면에서 정규식으로 후처리(더 견고 — 어느 모델이 만들든
// 항상 적용됨). 맨 앞 번호(문단 시작)는 그대로 두고, 그 뒤 "숫자. " 앞에만 줄바꿈 삽입.
export function formatNumberedList(text: string): string {
  if (!text) return text
  return text.replace(/ (\d+\.\s)/g, '\n$1')
}

export function resolveCitations(text: string, references: ResearchReference[]): string {
  const mapping = new Map(references.map((r) => [r.paper_id, r.title]))
  return (text || '').replace(/\[CITE:([^\]]+)\]/g, (match, paperId) => {
    const title = mapping.get(paperId)
    return title ? `(${title})` : match
  })
}

// research_workflow._STAGE_FIELDS와 짝이 맞는 필드 라벨 — 재시도 폼에서 "직접 수정"
// 입력창을 만드는 데만 쓴다. operation은 일부러 뺌: analysis/outcome은 LLM이
// experiment_results로부터 다시 판정하는 값이라 직접 고칠 대상이 아니고, 그 단계의
// 진짜 "사용자 입력"은 이미 experiment_results 텍스트박스(needsResults)가 담당한다.
// writing도 뺌 — user_guidance를 읽는 노드가 generate_hypothesis/design_experiment/
// analyze_results 셋뿐(research_workflow.WorkflowState.user_guidance 필드 참고).
export const STAGE_FIELD_LABELS: Partial<Record<string, Array<[keyof ResearchState, string]>>> = {
  hypothesis: [
    ['hypothesis', '가설'],
    ['rationale', '근거'],
    ['testable_prediction', '검증 가능한 예측'],
  ],
  design: [
    ['independent_variable', '독립변수'],
    ['dependent_variable', '종속변수'],
    ['controlled_variables', '통제변수'],
    ['equipment_needed', '필요 장비'],
    ['procedure', '절차'],
  ],
}

// 재시도 폼이 보낼 user_guidance 문자열을 조립한다 — 직접 수정한 필드(원래 값과
// 달라진 것만)와 방향 지시 텍스트박스 내용을 하나로 합친다. 백엔드는 이 텍스트
// 안에 뭐가 들었는지 신경 안 쓴다(research_workflow._with_user_guidance 참고) —
// 구조화된 별도 채널 대신 하나의 텍스트로 합치는 게 노드마다 다른 필드 집합을
// 따로 받는 것보다 단순하다(사용자 결정).
export function buildRetryGuidance(
  target: string,
  draftFields: Record<string, string>,
  original: ResearchState,
  guidanceText: string,
): string | undefined {
  const parts: string[] = []
  const fieldLabels = STAGE_FIELD_LABELS[target]
  if (fieldLabels) {
    const edited = fieldLabels.filter(([field]) => draftFields[field] !== (original[field] as string))
    if (edited.length > 0) {
      parts.push(
        '사용자가 다음과 같이 수정했습니다:\n' +
          edited.map(([field, label]) => `${label}: ${draftFields[field]}`).join('\n'),
      )
    }
  }
  if (guidanceText.trim()) parts.push(`추가 지시: ${guidanceText.trim()}`)
  return parts.length > 0 ? parts.join('\n\n') : undefined
}

export interface NextOption {
  label: string
  target: string
  recommended: boolean
  needsResults: boolean
}

// frontend/views/research.py의 _next_options()와 완전히 같은 계약(추천 옵션이 위로 오게 정렬).
export function nextOptions(values: ResearchState): NextOption[] {
  const stage = values.stage
  if (!values[STAGE_DONE_FIELD[stage]]) return []

  let options: NextOption[] = []
  if (stage === 'hypothesis') {
    options = [{ label: '설계 진행', target: 'design', recommended: true, needsResults: false }]
  } else if (stage === 'design') {
    options = [
      // "실험 시작"은 클릭 즉시 결과 입력을 요구해서 "아직 시작도 안 했는데?" 혼란을
      // 줬다(08-04 사용자 지적) — operation stage 자체가 analyze_results(결과 분석)라
      // "실험 진행 중"이라는 중간 상태가 그래프에 없어서 생기는 문구 공백이었다.
      { label: '실험 결과 입력하고 분석', target: 'operation', recommended: true, needsResults: true },
      { label: '설계 재생성', target: 'design', recommended: false, needsResults: false },
    ]
  } else if (stage === 'operation') {
    const outcome = values.outcome ?? ''
    options = [
      { label: '보고서 작성', target: 'report', recommended: outcome === 'supported', needsResults: false },
      { label: '가설부터 재수립', target: 'hypothesis', recommended: outcome === 'hypothesis_wrong', needsResults: false },
      { label: '재설계', target: 'design', recommended: outcome === 'design_flawed', needsResults: false },
      { label: '같은 설계로 재실험', target: 'operation', recommended: outcome === 'execution_error', needsResults: true },
      { label: '결과 다시 입력해 재분석', target: 'operation', recommended: outcome === 'analysis_error', needsResults: true },
    ]
  } else if (stage === 'report') {
    options = [{ label: '논문 작성', target: 'writing', recommended: true, needsResults: false }]
    for (const [target, label] of STAGES.slice(0, 3)) {
      options.push({ label: `${label}로 돌아가 고치기`, target, recommended: false, needsResults: target === 'operation' })
    }
  } else if (stage === 'writing') {
    options = [{ label: '초안 재생성', target: 'writing', recommended: false, needsResults: false }]
  }

  return [...options].sort((a, b) => Number(b.recommended) - Number(a.recommended))
}
