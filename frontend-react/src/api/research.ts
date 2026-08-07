import { apiFetch } from './client'

export interface ResearchSession {
  thread_id: string
  title: string
  topic: string
  stage: string
  created_at: string
  updated_at: string
}

export interface ResearchReference {
  paper_id: string
  title: string
  source: string
  reasoning: string
  added_by_stage?: string
}

export interface ResearchCitation {
  paper_id: string
  reasoning: string
}

// research_workflow.WorkflowState의 필드 그대로 — 스테이지별로 채워지는 필드만 다르고
// 나머지는 기본값(빈 문자열/빈 리스트)으로 남는다.
export interface ResearchState {
  topic: string
  stage: 'hypothesis' | 'design' | 'operation' | 'report' | 'writing'
  hypothesis: string
  rationale: string
  testable_prediction: string
  independent_variable: string
  dependent_variable: string
  controlled_variables: string
  equipment_needed: string
  procedure: string
  experiment_results: string
  analysis: string
  outcome: string
  experiment_report: string
  title: string
  abstract: string
  introduction: string
  methods: string
  results: string
  discussion: string
  citations: ResearchCitation[]
  references: ResearchReference[]
  comment: string
  // 이 체크포인트를 만든 요청이 어느 옵션이었는지(예: "설계 재생성") — research_workflow.py의
  // WorkflowState.action_label과 1:1 대응, 08-07 신설. 옵션 선택이 아닌 요청(최초 가설
  // 생성 등)은 빈 문자열 — BranchTimeline이 그 경우 단계명으로 폴백해서 보여준다.
  action_label: string
}

export interface HistoryEntry {
  checkpoint_id: string
  stage: string
  created_at: string
  values: ResearchState
  // 이 턴이 복원(from_checkpoint_id)으로 만들어졌다면 그 원본 체크포인트 id, 아니면
  // null — LangGraph 체크포인터의 parent_config는 항상 선형이라 못 쓰고(RoadMap
  // "타임라인·체크 결합(브랜치형)" 설계 노트 참고) 백엔드가 research_branches
  // 사이드테이블에서 붙여준다.
  branched_from_checkpoint_id: string | null
  // 이 체크포인트에 남긴 자유 텍스트 메모, 없으면 빈 문자열(08-04 후속 — RoadMap
  // "타임라인·체크 결합(브랜치형)" 설계 노트 §단계별 메모, 방식 B). WorkflowState가
  // 아니라 별도 사이드테이블(research_notes.py)이라 tip뿐 아니라 과거 체크포인트에도
  // 붙는다.
  note: string
}

export function listResearchSessions() {
  return apiFetch<{ sessions: ResearchSession[] }>('/research/sessions')
}

export function renameResearchSession(threadId: string, title: string) {
  return apiFetch(`/research/sessions/${threadId}/title`, {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
}

export function closeResearchSession(threadId: string) {
  return apiFetch(`/research/sessions/${threadId}`, { method: 'DELETE' })
}

export function getResearchHistory(threadId: string) {
  return apiFetch<{ history: HistoryEntry[] }>(`/research/${threadId}/history`)
}

export interface AdvanceBody {
  stage: string
  topic?: string
  experiment_results?: string
  user_guidance?: string
  from_checkpoint_id?: string
  keep_reference_paper_ids?: string[]
  action_label?: string
}

export function advanceResearch(threadId: string, body: AdvanceBody) {
  return apiFetch<ResearchState>(`/research/${threadId}/advance`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export interface DraftUpdateBody {
  title?: string
  abstract?: string
  introduction?: string
  methods?: string
  results?: string
  discussion?: string
}

export function updateResearchDraft(threadId: string, body: DraftUpdateBody) {
  return apiFetch<ResearchState>(`/research/${threadId}/draft`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

// 참고문헌만 독립 재시도(08-04 후속, Part B) — 그 단계 산출물은 안 건드리고 참고문헌
// 검색(검색어 추출+스크리닝)만 다시 돈다. 백엔드가 tip에서만 지원(main.py 참고).
export function retryResearchReferences(threadId: string) {
  return apiFetch<ResearchState>(`/research/${threadId}/references/retry`, { method: 'POST' })
}

// 단계별 메모 저장(08-04 후속) — 어느 checkpoint_id든 가능(tip 제한 없음, DraftEditor와
// 다른 지점). 빈 문자열을 보내면 메모를 지운다(research_notes.py 계약).
export function saveResearchNote(threadId: string, checkpointId: string, note: string) {
  return apiFetch<{ checkpoint_id: string; note: string }>(`/research/${threadId}/notes/${checkpointId}`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  })
}
