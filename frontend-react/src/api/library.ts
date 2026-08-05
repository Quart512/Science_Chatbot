import { apiFetch } from './client'

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
  return apiFetch<{ paper_id: string; analysis_status: string }>('/library/track', {
    method: 'POST',
    body: JSON.stringify({ path }),
  })
}
