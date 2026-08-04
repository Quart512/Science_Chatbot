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
