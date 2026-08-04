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
}

export interface HistoryEntry {
  checkpoint_id: string
  stage: string
  created_at: string
  values: ResearchState
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
  from_checkpoint_id?: string
  keep_reference_paper_ids?: string[]
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
