import { BACKEND_URL, apiFetch, ApiError } from './client'

export interface PaperCatalogRow {
  paper_id: string
  doi: string | null
  arxiv_id: string | null
  title: string
  authors: string
  year: string
  status: 'recommended' | 'owned' | 'dismissed'
  journal_ref: string | null
  citation_count: number | null
  created_at: string
  updated_at: string
}

export interface TitleCheck {
  status: string
  given_title: string
  pdf_title: string
}

export interface RegisterPaperResult {
  paper_id: string
  text_extractable: boolean
  chunk_count: number
  page_count: number
  title_check?: TitleCheck
}

export function listPapers(status?: string) {
  const query = status ? `?status=${encodeURIComponent(status)}` : ''
  return apiFetch<{ papers: PaperCatalogRow[] }>(`/papers${query}`)
}

// multipart/form-data라 apiFetch(JSON 전용)를 못 쓴다 — Content-Type을 직접 안 정해야
// 브라우저가 boundary를 붙여서 알아서 채운다.
export async function registerPaper(file: File, doi?: string, arxivId?: string): Promise<RegisterPaperResult> {
  const form = new FormData()
  form.append('file', file)
  if (doi) form.append('doi', doi)
  if (arxivId) form.append('arxiv_id', arxivId)

  const res = await fetch(`${BACKEND_URL}/papers`, { method: 'POST', body: form })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new ApiError(res.status, body?.detail ?? res.statusText)
  }
  return res.json()
}

export interface Evidence {
  kind: string
  detail: string
}

export interface PaperExtraction {
  core_claims: string[]
  evidence: Evidence[]
  author_stated_limitations: string[]
  unresolved_questions: string[]
  code_data_availability: string
}

export interface PaperSummary {
  paper_id: string
  extraction: PaperExtraction
  from_cache: boolean
  generated_by: string | null
  tokens_used: Record<string, number> | null
}

export function getPaperSummary(paperId: string) {
  return apiFetch<PaperSummary>(`/papers/${encodeURIComponent(paperId)}/summary`)
}
