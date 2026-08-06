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
  // library/ 루트 기준 상대경로(③, 08-05) — ⑤ 업로드 재정의 이후로는 업로드·트래킹
  // 둘 다 library/에 파일을 남기므로 거의 항상 값이 있다. null인 건 ⑤ 이전(tempfile만
  // 쓰고 버리던 시절)에 등록된 옛 레코드뿐 — PaperRow가 이 값으로 PDF 뷰어 섹션을
  // 보여줄지 결정한다.
  file_path: string | null
  // 분석(파싱·청킹·임베딩) 진행 상태(④, 08-05 — RoadMap 설계 노트 항목 G). ⑤ 이전에
  // 등록된 옛 레코드(①에서 스키마만 먼저 추가됐을 때 만들어진 행)는 이 컬럼이 여전히
  // "untracked"로 남아있을 수 있지만 실제로는 이미 분석이 끝난 상태다(등록 자체가
  // 동기·전체 완료였으므로) — PaperRow가 pending/analyzing일 때만 별도 배지를 보여주고
  // 그 외(untracked 포함)는 기존과 똑같이 요약을 시도하는 이유.
  analysis_status: string
  created_at: string
  updated_at: string
}

// analysis_status가 이 안에 있으면 아직 분석 중 — 요약 조회를 시도하면 안 됨.
export const ANALYSIS_IN_PROGRESS = ['pending', 'analyzing']

// ⑤(08-05) 업로드 재정의 이후 공용 — 등록(track_in_background 경유)은 항상 즉시
// 반환되고 분석은 백그라운드에서 돈다. library.ts의 trackLibraryFile()도 같은 모양.
export interface TrackResult {
  paper_id: string
  analysis_status: string
}

// sort(08-06) — 생략하면 백엔드가 수동 정렬(sort_order)로 돌려준다. 정렬이나 검색어가
// 켜지면 화면이 위/아래 순서 버튼을 꺼서(Papers.tsx) "정렬 기준이 sort_order가 아닌데
// 버튼을 눌러도 눈에 보이는 변화가 없는" 혼란을 막는다.
export type PaperSort = 'created_desc' | 'created_asc' | 'updated_desc' | 'updated_asc'

export function listPapers(status?: string, sort?: PaperSort, q?: string) {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (sort) params.set('sort', sort)
  if (q) params.set('q', q)
  const query = params.toString()
  return apiFetch<{ papers: PaperCatalogRow[] }>(`/papers${query ? `?${query}` : ''}`)
}

export function movePaper(paperId: string, direction: 'up' | 'down') {
  return apiFetch<{ paper_id: string; moved: boolean }>(
    `/papers/${encodeURIComponent(paperId)}/move?direction=${direction}`,
    { method: 'POST' },
  )
}

// multipart/form-data라 apiFetch(JSON 전용)를 못 쓴다 — Content-Type을 직접 안 정해야
// 브라우저가 boundary를 붙여서 알아서 채운다.
// title(08-05) — arxiv_id가 없는 논문은 자동 조회가 안 걸려 제목을 넣을 방법이 없었다.
// arxiv_id를 같이 줘도 이 값이 우선한다(백엔드 "명시값 우선" 규칙, main.py 주석 참고).
export async function registerPaper(file: File, doi?: string, arxivId?: string, title?: string): Promise<TrackResult> {
  const form = new FormData()
  form.append('file', file)
  if (doi) form.append('doi', doi)
  if (arxivId) form.append('arxiv_id', arxivId)
  if (title) form.append('title', title)

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
