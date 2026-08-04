import { apiFetch } from './client'

export interface Interest {
  id: number
  title: string
  looking_for: string
  already_known: string
  excluded_topics: string
  created_at: string
  updated_at: string
}

export interface InterestDraft {
  title: string
  looking_for: string
  already_known: string
  excluded_topics: string
}

export interface RecommendResult {
  paper_id: string
  title: string
  reasoning: string
  is_relevant: boolean
  peer_reviewed: boolean
  citation_count: number | null
  year: string | null
}

export interface InterestPaper {
  paper_id: string
  title: string
  status: string
  reasoning: string
}

export function listInterests() {
  return apiFetch<{ interests: Interest[] }>('/interests')
}

export function getInterestDraft(threadId: string) {
  return apiFetch<InterestDraft>(`/interests/draft?thread_id=${encodeURIComponent(threadId)}`)
}

export interface SaveInterestBody extends InterestDraft {
  update_existing_id?: number
}

export function saveInterest(body: SaveInterestBody) {
  return apiFetch<{ interest_id: number; action: string }>('/interests', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function deleteInterest(id: number) {
  return apiFetch<{ interest_id: number; action: string }>(`/interests/${id}`, { method: 'DELETE' })
}

export function searchInterest(id: number, start: number) {
  return apiFetch<{ recommended: RecommendResult[] }>(`/interests/${id}/search?start=${start}`, {
    method: 'POST',
  })
}

export function refreshInterest(id: number, existingCandidates: RecommendResult[]) {
  return apiFetch<{ recommended: RecommendResult[] }>(`/interests/${id}/refresh`, {
    method: 'POST',
    body: JSON.stringify({ existing_candidates: existingCandidates }),
  })
}

export function listInterestPapers(id: number) {
  return apiFetch<{ papers: InterestPaper[] }>(`/interests/${id}/papers?only_relevant=true`)
}
