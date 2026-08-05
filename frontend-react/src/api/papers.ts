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
  // 업로드 원본 파일명(08-04 사용자 요청) — title이 비어있는 논문(서지정보를 못 찾은
  // 경우)을 화면에서 해시 대신 사람이 읽을 수 있는 이름으로 보여줄 차선책.
  // 추천(검색) 경로로 생긴 행은 업로드 파일이 없어 빈 문자열.
  filename: string
  // library/ 루트 기준 상대경로(③, 08-05) — ②-B "트래킹에 추가"로 등록된 논문만 값이
  // 있다. 기존 업로드 다이얼로그 경로(tempfile만 쓰고 버림)로 등록된 논문은 원본이
  // 아예 없어 null — PaperRow가 이 값으로 PDF 뷰어 섹션을 보여줄지 결정한다.
  file_path: string | null
  // 분석(파싱·청킹·임베딩) 진행 상태(④, 08-05 — RoadMap 설계 노트 항목 G). library/
  // 경유로 등록된 논문만 pending/analyzing을 실제로 거친다 — 기존 업로드 다이얼로그로
  // 등록된 논문(①에서 스키마만 먼저 추가됐을 때 만들어진 행)은 이 컬럼이 여전히
  // "untracked"로 남아있을 수 있지만 실제로는 이미 분석이 끝난 상태다(등록 자체가
  // 동기·전체 완료였으므로) — PaperRow가 pending/analyzing일 때만 별도 배지를 보여주고
  // 그 외(untracked 포함)는 기존과 똑같이 요약을 시도하는 이유.
  analysis_status: string
  created_at: string
  updated_at: string
}

// analysis_status가 이 안에 있으면 아직 분석 중 — 요약 조회를 시도하면 안 됨.
export const ANALYSIS_IN_PROGRESS = ['pending', 'analyzing']

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

  const res = await fetch(`${BACKEND_URL}/api/papers`, { method: 'POST', body: form })
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

// JSON이 아니라 PDF 바이트를 그대로 스트리밍하는 엔드포인트라 apiFetch를 안 쓴다 —
// registerPaper()와 같은 이유. <iframe src>에 직접 박아 브라우저 내장 뷰어로 렌더.
export function getPaperFileUrl(paperId: string) {
  return `${BACKEND_URL}/api/papers/${encodeURIComponent(paperId)}/file`
}
