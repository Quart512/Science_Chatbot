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
