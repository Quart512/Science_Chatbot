import { apiFetch } from './client'

export interface LibraryFile {
  path: string
  tracked: boolean
}

export function listLibraryFiles() {
  return apiFetch<{ files: LibraryFile[] }>('/library/files')
}

export function trackLibraryFile(path: string) {
  return apiFetch<{ paper_id: string; text_extractable: boolean; chunk_count: number; page_count: number }>(
    '/library/track',
    { method: 'POST', body: JSON.stringify({ path }) },
  )
}
