import { BACKEND_URL, apiFetch, ApiError } from './client'
import type { TrackResult } from './papers'

export interface LibraryFile {
  path: string
  tracked: boolean
}

export function listLibraryFiles() {
  return apiFetch<{ files: LibraryFile[] }>('/library/files')
}

// ④(08-05) 파싱 분리 후 응답이 바뀌었다 — 등록만 동기로 끝내고(analysis_status가
// 항상 "pending"), 무거운 파싱·청킹·임베딩은 서버가 백그라운드로 돌린다. 완료 여부는
// papers 목록을 다시 불러와 analysis_status로 확인한다(Papers.tsx의 폴링).
export function trackLibraryFile(path: string) {
  return apiFetch<TrackResult>('/library/track', {
    method: 'POST',
    body: JSON.stringify({ path }),
  })
}

// ⑥-A(08-05) — ZIP 바이너리를 그대로 받는다(JSON이 아니라서 apiFetch를 못 씀,
// registerPaper()와 같은 이유). 호출부(Settings.tsx)가 Blob URL을 만들어 다운로드 트리거.
export async function exportLibrary(includeIndex: boolean, includeLibrary: boolean): Promise<Blob> {
  const res = await fetch(`${BACKEND_URL}/api/library/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ include_index: includeIndex, include_library: includeLibrary }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new ApiError(res.status, body?.detail ?? res.statusText)
  }
  return res.blob()
}

export interface ImportResult {
  papers: number
  interests: number
  equipment: number
  notes: number
  // chroma_db를 포함해 가져왔으면 true — retrieval.py의 Chroma 클라이언트가 프로세스
  // 시작 시점에 한 번만 만들어져 여러 모듈이 그 객체를 그대로 들고 있으므로(파이썬
  // import 의미론), 파일을 갈아치워도 재시작 전까지는 검색·요약이 깨진다(main.py
  // import_library() 주석에 실제 재현 확인 근거 있음).
  restart_required: boolean
}

// ⑥-B(08-05) — multipart/form-data라 apiFetch(JSON 전용)를 못 쓴다(registerPaper()와
// 같은 이유). 서버가 기존 데이터가 하나라도 있으면 400으로 거부(병합 없음, 새로 설치한
// 상태에서만 허용 — 사용자 결정).
export async function importLibrary(file: File): Promise<ImportResult> {
  const form = new FormData()
  form.append('file', file)

  const res = await fetch(`${BACKEND_URL}/api/library/import`, { method: 'POST', body: form })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new ApiError(res.status, body?.detail ?? res.statusText)
  }
  return res.json()
}
